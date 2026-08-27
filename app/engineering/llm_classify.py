"""LLM 语义分类（三重兜底第 3 层）：规则+知识库都不确定时交给大模型。

设计原则：
- 可选/按需调用（不阻塞批量提取）：由调用方对"低置信度/未分类"对象显式触发。
- 结果写回 symbol_library，供后续复用（越用越准）。
- LLM 失败不阻断流程：返回 None，调用方保留规则/知识库结果。
"""
from __future__ import annotations

from .. import db, config
from ..llm.prompts import build_classify_prompt
from ..llm.schema import parse_classification
from ..llm.runner import run_llm_with_retry


def llm_classify(project_id: int, block_name: str = "", layer_name: str = "",
                 specification: str = "", tag: str = "",
                 model: str = None, host: str = None) -> dict | None:
    """对单个 CAD 对象做 LLM 语义分类，并写回知识库。

    Args:
        project_id: 项目 ID
        block_name / layer_name / specification / tag: CAD 对象语义
    Returns:
        {"discipline", "system", "spec", "quantity_rule", "confidence", "reason"}
        成功；LLM 不可用/失败返回 None。
    """
    system, user = build_classify_prompt(
        block_name=block_name, layer_name=layer_name,
        specification=specification, tag=tag)

    def _validate(content: str):
        return parse_classification(content)

    resp = run_llm_with_retry(
        project_id, task_type="classify", system=system, user=user,
        validator=_validate, model=model, host=host,
        prompt_version=config.CLASSIFY_PROMPT_VERSION)

    if not resp["ok"] or resp["parsed"] is None:
        return None

    r = resp["parsed"]
    result = {
        "discipline": r.discipline,
        "system": r.system,
        "spec": r.spec,
        "quantity_rule": r.quantity_rule,
        "confidence": r.confidence,
        "reason": r.reason,
    }
    # 写回知识库（source=llm），供后续复用
    try:
        db.upsert_symbol(
            project_id, block_name=block_name, layer_name=layer_name,
            discipline=r.discipline, system=r.system, spec=r.spec,
            quantity_rule=r.quantity_rule, source="llm")
    except Exception:
        pass
    return result


def llm_classify_uncertain(project_id: int, eos: list = None, min_confidence: float = 0.5,
                           limit: int = 100, object_ids: list = None) -> dict:
    """批量：对低置信度/未分类的工程对象做 LLM 分类（T4 第3层接线）。

    Args:
        eos: list[EngineeringObject]；None 时按 project_id 从库内拉取
            （优先：对象已由 extractor 按「规则未命中 → 置信 0.4」入库）。
        min_confidence: 低于此置信度才触发 LLM（默认 0.5）；
        limit: 单次最多处理数量（控制成本，超出部分返回 stats["deferred"]）。
        object_ids: 显式指定对象子集（与 eos 互斥，优先）。
    Returns:
        {"classified": int, "failed": int, "skipped": int, "deferred": int}
    """
    done = {"classified": 0, "failed": 0, "skipped": 0, "deferred": 0}

    if object_ids:
        cands = [db.get_engineering_object(oid) for oid in object_ids]
        cands = [c for c in cands if c is not None]
    elif eos is not None:
        cands = list(eos)
    else:
        cands = db.get_engineering_objects(project_id)

    # 先筛低置信，再截断限流（避免高置信对象占用 limit 额度）
    low_conf = [eo for eo in cands if (eo.confidence or 0) < min_confidence]
    if not low_conf:
        return done
    todo = low_conf[:limit]
    done["deferred"] = max(0, len(low_conf) - len(todo))

    for eo in todo:
        res = llm_classify(
            project_id, block_name=eo.block_name, layer_name=eo.layer_name,
            specification=eo.specification, tag=eo.tag or "")
        if res:
            # 更新工程对象语义（LLM 为第3层兜底，覆盖低置信规则结果；写回知识库在 llm_classify 内）
            try:
                db.update_engineering_object(
                    eo.id, discipline=res["discipline"] or eo.discipline,
                    system=res["system"] or eo.system,
                    specification=res["spec"] or eo.specification,
                    quantity_rule=res["quantity_rule"] or eo.quantity_rule,
                    confidence=round(max(res["confidence"], min_confidence), 3),
                    source=f"{eo.source}+llm")
                done["classified"] += 1
            except Exception:
                done["failed"] += 1
        else:
            done["failed"] += 1
    return done