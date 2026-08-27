"""Qwen 重排序：在规则/Embedding 召回的子集内做最终选择（任务十二）。

输入严格裁剪：CAD 对象 + Top-N 候选 BOQ，绝不给整张 DWG。
输出经 JSON Schema + Pydantic + 业务校验（selected ∈ 候选集），失败自动重试。
"""
from __future__ import annotations

from .. import db, config
from ..llm.prompts import build_binding_prompt
from ..llm.schema import parse_binding_suggestion
from ..llm.runner import run_llm_with_retry
from . import candidate as cand


def llm_rerank(project_id: int, eo, base_candidates: list,
               top_n: int = None, model: str = None, host: str = None,
               items: list = None) -> list:
    """对候选集重排序。

    Args:
        base_candidates: [(boq_item_id, score, reason, method), ...]（rule/embedding 已召回）
        items: 预加载的 BOQ 项（分层编排外层复用，避免每次调用全量查库）
    Returns:
        最终候选 [(boq_item_id, score, reason, method), ...]：
          - LLM 成功 → 选中项置顶（method=LLM），备选跟随
          - LLM 失败 → 原候选保底返回
    """
    top_n = top_n or config.BINDING_TOP_N
    if not base_candidates:
        return []

    # 候选 code 列表（业务校验用）+ 供 prompt 的行
    if items is None:
        items = db.get_boq_items(project_id)
    items = {it.id: it for it in items}
    allowed = [items[c[0]].code for c in base_candidates if c[0] in items]
    boq_lines = [(c[0], items[c[0]].code, items[c[0]].description, items[c[0]].unit)
                 for c in base_candidates if c[0] in items]
    if not boq_lines:
        return base_candidates

    system, user = build_binding_prompt(eo, boq_lines)

    def _validate(content: str):
        return parse_binding_suggestion(content, allowed_boq_ids=allowed)

    resp = run_llm_with_retry(
        project_id, task_type="binding", system=system, user=user,
        validator=_validate, model=model, host=host,
        prompt_version=config.BINDING_PROMPT_VERSION)

    if not resp["ok"] or resp["parsed"] is None:
        return base_candidates  # 保底：LLM 失败不丢弃规则候选

    sug = resp["parsed"]
    code2id = {it.code: it.id for it in items.values()}

    # P0 拒答：LLM 判定候选集无一匹配 → 返回空（不写候选，避免乱选污染 PENDING）
    # 调用方据此将本 EO 计入 no_match，交由人工处理。
    if getattr(sug, "no_match", False):
        return []

    # 模型自身不确定 → 选中项标记需人工复核（needs_review=True，reason 追加提示）
    review_flag = "（需复核）" if getattr(sug, "needs_review", False) else ""

    # 选中项（LLM）
    out: list = []
    sel_id = code2id.get(sug.selected_boq_id)
    if sel_id is not None:
        out.append((sel_id, sug.confidence, (sug.reason or "LLM 推荐") + review_flag,
                    cand.METHOD_LLM, resp["run_ids"][-1]))
    # 备选（LLM，置信度 ×0.9）
    for alt in sug.alternative_boq_ids[:2]:
        aid = code2id.get(alt)
        if aid is not None and aid not in [c[0] for c in out]:
            out.append((aid, round(sug.confidence * 0.9, 3),
                        "LLM 备选" + review_flag, cand.METHOD_LLM, resp["run_ids"][-1]))
    # 保底补足：未被选中的原候选（method 保持原样）
    seen = {c[0] for c in out}
    for c in base_candidates:
        if c[0] not in seen:
            out.append((c[0], c[1], c[2], c[3], None))
            seen.add(c[0])
    return out[:top_n]
