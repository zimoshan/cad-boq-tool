"""匹配编排：为未绑定工程对象生成 BindingCandidate（分层覆盖模式）。

分层顺序（优先生成规则，大模型补充，非二选一）：
  第1层 历史确认复用 —— 同 block/layer 的历史 ACCEPTED 候选（score=1.0，0 成本）
  第2层 规则匹配     —— 关键词+学科冲突检测（score=0.7-0.95，0 成本）
  第3层 语义召回     —— Embedding 余弦相似度（score≈0.5-0.8，Ollama 可用时）
  第4层 LLM 重排序   —— Qwen 在候选子集内精排（use_llm=True 时；失败保底）

早停/降载：
  - 第1层命中（历史确认）→ 最高置信，跳过后续。
  - 第2层强命中（score ≥ RULE_STRONG）→ 规则已覆盖，不再跑 LLM（省成本）。
  - 其余 → 语义召回补充，use_llm=True 时再 LLM 精排。
  - 语义/规则双无时以关键词交集兜底喂给 LLM，保证待定对象尽量有候选。

AI/规则只写 PENDING 候选；确认/拒绝走人工队列。
REJECTED 组合（同 EO + 同 BOQ）不再重复推荐（用例 E）。
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from .. import db, config
from ..llm.runner import llm_available
from . import candidate as cand
from .rule_matcher import match_rule, historical_confirmed, already_bound
from .embedding_matcher import semantic_candidates, enriched_eo_text
from .llm_matcher import llm_rerank
from .text_norm import boq_searchable

# 候选元组: (boq_item_id, score, reason, method, llm_run_id|None)
RULE_STRONG_MIN = 0.6   # 规则强命中阈值：≥此分认为规则已覆盖，跳过 LLM（省成本）
HIST_SCORE = 1.0         # 历史确认复用分数（最高优先级）


def _boq_top_n_for_llm(project_id: int, eo, top_n: int = 5) -> list:
    """兜底：拿全部 BOQ 中文本与 EO 关键词有"最弱交集"的 top_n。

    用于 embedding 无命中且 use_llm=True 时给 LLM 一个候选子集去筛选。
    """
    items = db.get_boq_items(project_id)
    if not items or not eo:
        return []
    eo_text = enriched_eo_text(project_id, eo).upper()
    if not eo_text:
        return []
    # 拆词（短词优先）
    eo_words = [w for w in re.split(r"[\s_\-/\\.,()\[\]]+", eo_text) if len(w) >= 2]
    if not eo_words:
        return []
    scored = []
    for it in items:
        btext = boq_searchable(it)
        if not btext:
            continue
        # 关键词交集数
        hit = sum(1 for w in eo_words if w in btext)
        if hit >= 1:
            scored.append((it.id, hit / max(1, len(eo_words)), f"关键词交集{hit}: {[w for w in eo_words if w in btext][:3]}"))
    scored.sort(key=lambda x: -x[1])
    # 限制不让 prompt 过大：取前 30 做 LLM 重排
    head = scored[:max(top_n, 15)]
    return [(bid, score, reason, cand.METHOD_EMBEDDING, None) for bid, score, reason in head]


def _rejected_pairs(project_id: int, eo) -> set:
    """该 EO 已被人工拒绝的 boq_item_id 集合"""
    rej = db.get_candidates(project_id, status="REJECTED", engineering_object_id=eo.id)
    return {c.boq_item_id for c in rej}


def _write_final(project_id: int, eo, final: list, rejected: set,
                 stats: dict, created: list) -> int:
    """过滤被拒组合后写候选，返回实际写入数。"""
    wrote = 0
    for bid, score, reason, method, run_id in final:
        if bid in rejected:
            stats["skipped_rejected"] += 1
            continue
        created.append(db.create_binding_candidate(
            project_id, eo.id, bid, method=method,
            score=float(score), confidence=float(score),
            reason=reason, llm_run_id=run_id))
        wrote += 1
    return wrote


def _count_layer(final: list, stats: dict) -> None:
    """按该 EO 最终候选的 method 归属层级（LLM > Embedding > Rule 优先）"""
    if any(c[3] == cand.METHOD_LLM for c in final):
        stats["llm"] += 1
    elif any(c[3] == cand.METHOD_EMBEDDING for c in final):
        stats["embedding"] += 1
    else:
        stats["rule"] += 1


def _run_llm_jobs(llm_jobs: list, project_id: int, top_n: int,
                  items: list, workers: int = 2) -> None:
    """并发执行 LLM 精排（in-place 覆盖 llm_jobs 的 base → final）。

    每个作业独立调 ``llm_rerank``（自带失败保底 + llm_run 审计）；
    线程安全说明：llm_rerank 只读 BOQ（immutable）+ 写 llm_run 审计（get_conn
    线程本地连接 + SQLite WAL busy_timeout 串行化），绑定候选仍在主线程写。
    """
    def _one(job):
        eo, base = job
        return llm_rerank(project_id, eo, base, top_n=top_n, items=items)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_one, llm_jobs))
    for job, final in zip(llm_jobs, results):
        job[1] = list(final)   # 保底：llm_rerank 失败时原 base 原样返回


def generate_candidates(project_id: int, sheet_id: int = None,
                        use_llm: bool = True, top_n: int = None) -> dict:
    """为项目（可选单图纸）未绑定 EO 生成候选（分层覆盖）。

    分层：历史确认 → 规则 → 语义 → LLM（规则强命中及历史确认命中不跑 LLM，
    节省成本；use_llm=False 可强制纯本地层）。LLM 前先 llm_available() 秒级探测：
    后端不可用自动降级为纯本地层并在 stats["llm_unavailable"] 计数。
    各层产出的候选均为 PENDING，统一在写库前过滤已被人工拒绝的组合。

    P2-2 并发：需要 LLM 精排的 EO 先收集，再经 ``ThreadPoolExecutor``
    （max_workers=config.LLM_BATCH_WORKERS）并行调用；仍逐 EO 写 llm_run 审计，
    候选落库保持主线程串行（WAL 写锁单一）。

    Args:
        use_llm: 是否启用第4层 LLM 精排（默认 True；后端不可用时自动降级）。
        top_n: 单对象候选上限（默认 config.BINDING_TOP_N）。
    Returns:
        {"candidates": int,
         "stats": {skipped_bound/rule/embedding/llm/no_match/skipped_rejected,
                   [llm_unavailable]},
         "created": [candidate_id, ...]}
    """
    top_n = top_n or config.BINDING_TOP_N
    eos = db.get_engineering_objects(project_id)
    if sheet_id is not None:
        eos = [e for e in eos if e.sheet_id == sheet_id]

    stats = {"skipped_bound": 0, "rule": 0, "embedding": 0, "llm": 0,
             "no_match": 0, "skipped_rejected": 0}
    created: list[int] = []

    # BOQ 全量只取一次（整层复用，避免每 EO 重复查表）
    boq_items = db.get_boq_items(project_id)

    # 需要 LLM 重排的作业：（eo, base）；主循环只算候选集，LLM 阶段统一并发
    llm_jobs: list[tuple] = []

    for eo in eos:
        # ① 已正式绑定 → 跳过（不再生成候选，防覆盖）
        if already_bound(eo):
            stats["skipped_bound"] += 1
            continue

        rejected = _rejected_pairs(project_id, eo)

        # 生成新候选前，先作废旧 PENDING（保持同一 EO 仅一批候选）
        db.supersede_candidates(eo.id)

        # ===== 第1层：历史确认复用（highest，0 成本） =====
        hist = historical_confirmed(project_id, eo)
        if hist:
            n = 0
            for boq_id, reason in hist:
                if boq_id in rejected:
                    stats["skipped_rejected"] += 1
                    continue
                created.append(db.create_binding_candidate(
                    project_id, eo.id, boq_id, method=cand.METHOD_RULE,
                    score=HIST_SCORE, confidence=HIST_SCORE, reason=reason))
                n += 1
            if n:
                stats["rule"] += 1
                continue  # 历史确认最高置信，不再消耗后续层

        # ===== 第2层：规则匹配（确定性，0 成本） =====
        base = []      # [(boq_item_id, score, reason, method, llm_run_id|None)]
        rule_cands = match_rule(project_id, eo, items=boq_items)
        best_rule = max((c[1] for c in rule_cands), default=0.0)
        for bid, score, reason in rule_cands:
            if bid not in rejected:
                base.append((bid, score, reason, cand.METHOD_RULE, None))

        if base and best_rule >= RULE_STRONG_MIN:
            # 规则强命中 → 已覆盖，不再跑语义/LLM（省成本）
            for bid, score, reason, method, run_id in base:
                created.append(db.create_binding_candidate(
                    project_id, eo.id, bid, method=method,
                    score=float(score), confidence=float(score),
                    reason=reason, llm_run_id=run_id))
            stats["rule"] += 1
            continue

        # ===== 第3层：语义召回（Embedding，Ollama 可用时；补充规则空隙） =====
        emb = semantic_candidates(project_id, eo)
        for bid, score, reason in emb:
            if bid in rejected:
                stats["skipped_rejected"] += 1
                continue
            if all(b != bid for b, *_ in base):
                base.append((bid, score, reason, cand.METHOD_EMBEDDING, None))

        if not base:
            # 规则/语义双空：关键词交集兜底（纯文本，0 成本；保证覆盖）
            base = _boq_top_n_for_llm(project_id, eo, top_n=top_n)
            if not use_llm:
                # 非 LLM 模式收窄到 top_n，避免每个 EO 一堆候选噪音
                base = base[:top_n]
            if not base:
                stats["no_match"] += 1
                continue

        if use_llm and base:
            llm_jobs.append([eo, list(base)])   # list：LLM 结果回填用之
        else:
            # 不跑 LLM：直接过滤写库
            final = base
            wrote = _write_final(project_id, eo, final, rejected, stats, created)
            if wrote:
                _count_layer(final, stats)
            else:
                stats["no_match"] += 1

    # ===== 第4层：LLM 精排（并发批量，失败保底原候选） =====
    if llm_jobs and not llm_available():
        # 后端不可用（Ollama 未启动 / API key 未配）→ 降级为纯本地层，
        # base 候选原样写库，避免逐 EO 调用挨个超时。
        for eo, final in llm_jobs:
            wrote = _write_final(project_id, eo, final,
                                 _rejected_pairs(project_id, eo), stats, created)
            if wrote:
                _count_layer(final, stats)
            else:
                stats["no_match"] += 1
        stats["llm_unavailable"] = len(llm_jobs)
        return {"candidates": len(created), "stats": stats, "created": created}

    if llm_jobs:
        workers = max(1, int(getattr(config, "LLM_BATCH_WORKERS", 2)))
        _run_llm_jobs(llm_jobs, project_id=project_id, top_n=top_n, items=boq_items,
                      workers=workers)

        for eo, final in llm_jobs:
            wrote = _write_final(project_id, eo, list(final),
                                 _rejected_pairs(project_id, eo), stats, created)
            if wrote == 0:
                stats["no_match"] += 1
            elif any(c[3] == cand.METHOD_LLM for c in final):
                stats["llm"] += 1
            elif any(c[3] == cand.METHOD_EMBEDDING for c in final):
                stats["embedding"] += 1
            else:
                stats["rule"] += 1

    return {"candidates": len(created), "stats": stats, "created": created}


def create_manual_candidate(project_id: int, engineering_object_id: int,
                            boq_item_id: int, reason: str = "人工选择") -> int:
    """人工手动绑定：先生成 MANUAL 候选，再走确认（统一审计通道）"""
    db.supersede_candidates(engineering_object_id)
    return db.create_binding_candidate(
        project_id, engineering_object_id, boq_item_id,
        method=cand.METHOD_MANUAL, score=1.0, confidence=1.0, reason=reason)
