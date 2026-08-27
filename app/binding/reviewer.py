"""人工复核：候选 → 正式 mapping 的唯一通道。

硬约束（任务七/原则 6/7）：
  - AI 只能生成 PENDING 候选；
  - 只有本模块（人工确认 或 确定性规则自动通过）能把候选写入正式 mapping；
  - 确认后同一 EO 的其他 PENDING 候选自动 SUPERSEDED。
"""
from __future__ import annotations

from .. import db, mapping as map_svc
from . import candidate as cand


class ReviewError(Exception):
    pass


def _write_symbol_knowledge(project_id: int, eo, boq_item_id: int) -> None:
    """人工确认后，把 EO 语义写回 symbol_library 知识库（source=manual）。

    供后续项目/同图复用：block+layer 命中时直接带出 spec/system/unit/quantity_rule。
    """
    if not eo.block_name and not eo.layer_name:
        return
    bi = next((b for b in db.get_boq_items(project_id) if b.id == boq_item_id), None)
    try:
        db.upsert_symbol(
            project_id,
            block_name=eo.block_name or "",
            layer_name=eo.layer_name or "",
            discipline=eo.discipline or "",
            system=eo.system or "",
            spec=eo.specification or (bi.description if bi else ""),
            unit=eo.unit or (bi.unit if bi else ""),
            quantity_rule=eo.quantity_rule or "",
            source="manual",
            confirmed_by="human",
        )
    except Exception:
        pass


def confirm_binding(project_id: int, candidate_id: int,
                    project_scale: float = 1.0) -> dict:
    """人工确认候选 → ACCEPTED → 写正式 mapping → 重算。

    Returns:
        {"candidate_id", "mapping_mode", "mapping_id", "boq_item_id", "qty", "count"}
    Raises:
        ReviewError: 候选不存在 / 非 PENDING / 工程对象缺失
    """
    c = db.get_candidate(candidate_id)
    if not c:
        raise ReviewError(f"候选不存在: {candidate_id}")
    if c.status != cand.STATUS_PENDING:
        raise ReviewError(f"候选状态为 {c.status}，仅 PENDING 可确认")

    eo = db.get_engineering_object(c.engineering_object_id)
    if not eo:
        raise ReviewError(f"工程对象缺失: {c.engineering_object_id}")

    # 写正式 mapping：equipment→block 模式；linear/area→layer 模式（任务八）
    if eo.object_type == "equipment" and eo.block_name:
        added, conflicts = map_svc.add_block_mapping(c.boq_item_id, eo.sheet_id, eo.block_name)
        mode = "block"
    elif eo.layer_name:
        added, conflicts = map_svc.add_layer_mapping(c.boq_item_id, eo.sheet_id, eo.layer_name)
        mode = "layer"
    else:
        raise ReviewError(f"工程对象 #{eo.id} 无 block/layer 锚点，无法映射")

    if added == 0 and not conflicts:
        raise ReviewError(f"映射写入失败：无实体可映射（{mode}={eo.block_name or eo.layer_name}）")

    # 人工标定闭环：确认语义写回知识库（T6）
    _write_symbol_knowledge(project_id, eo, c.boq_item_id)

    # 同步计量规则 = 工程对象语义（绑定即意图）；单位缺省/默认时用 EO 单位
    bi = next((b for b in db.get_boq_items(project_id) if b.id == c.boq_item_id), None)
    if bi:
        db.update_boq_item(bi.id, rule_type=eo.quantity_rule)
        if (not bi.unit or bi.unit == "个") and eo.unit:
            db.update_boq_item(bi.id, unit=eo.unit or bi.unit)

    # 状态流转：确认 + 同 EO 其他候选 SUPERSEDED
    db.update_candidate_status(candidate_id, cand.STATUS_ACCEPTED)
    db.supersede_candidates(eo.id, exclude_cid=candidate_id)

    # 确定性重算
    from .resolver import recompute
    res = recompute(project_id, boq_item_id=c.boq_item_id, project_scale=project_scale)
    r = res.get(c.boq_item_id, {"qty": 0.0, "count": 0})

    return {"candidate_id": candidate_id, "mapping_mode": mode, "boq_item_id": c.boq_item_id,
            "qty": r["qty"], "count": r["count"]}


def reject_binding(candidate_id: int, reason: str = "人工拒绝") -> None:
    """人工拒绝候选 → REJECTED（matcher 后续不再推荐同 EO+BOQ 组合）"""
    c = db.get_candidate(candidate_id)
    if not c:
        raise ReviewError(f"候选不存在: {candidate_id}")
    if c.status != cand.STATUS_PENDING:
        raise ReviewError(f"候选状态为 {c.status}，仅 PENDING 可拒绝")
    db.update_candidate_status(candidate_id, cand.STATUS_REJECTED)
    # 拒绝原因记到候选 reason（追加），供 reviewer 界面展示
    with db.get_conn() as conn:
        conn.execute("UPDATE binding_candidate SET reason=reason || ' | ' || ? WHERE id=?",
                     (reason, candidate_id))


def auto_confirm_rule_candidates(project_id: int) -> dict:
    """批量确认页：把 score=1.0 的历史确认复用候选一次性确认（任务确认项②）。

    普通 RULE 候选（score<1.0）仍需逐条人工确认。
    """
    done = 0
    for c in db.get_pending_candidates(project_id):
        if c.method == cand.METHOD_RULE and c.score >= 1.0:
            confirm_binding(project_id, c.id)
            done += 1
    return {"auto_confirmed": done}
