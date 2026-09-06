"""工程量回写：把项目级计量结果写入 BOQ 实测数量列（measured_qty）。

B5 S7 可核性 + Excel 保真回写（v2.0 §2.5 / §5.3，2026-09-06）：
- takability 6 状态：
  MEASURABLE: 可精确计量
  GROUP_ONLY: 只能按组合计量
  NOT_MEASURABLE: 暂不可计量（图层黑名单 / 块未识别）
  NO_DRAWING: BOQ 项无对应图纸
  VERSION_CONFLICT: 多图版本冲突需人工
  PROVISIONAL: 暂定值（人工标注）
- writeback_audit 表（alembic 0002 创建）：保真回写审计
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from .. import db
from ..binding.resolver import recompute


class Takability(str, Enum):
    """B5 S7 可核性 6 状态"""
    MEASURABLE = "MEASURABLE"
    GROUP_ONLY = "GROUP_ONLY"
    NOT_MEASURABLE = "NOT_MEASURABLE"
    NO_DRAWING = "NO_DRAWING"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    PROVISIONAL = "PROVISIONAL"


def classify_takability(
    boq_item_id: int,
    mapping_count: int,
    sheet_drawing_types: list[str] | None = None,
    has_provisional_flag: bool = False,
) -> Takability:
    """P1-1 完整 6 状态判定（v2.0 §2.5 takability）

    判定优先级（从高到低）：
      1. has_provisional_flag → PROVISIONAL（人工标注）
      2. 任意 sheet 在黑名单 drawing_type（detail/legend/schedule） → NOT_MEASURABLE
      3. 跨图 drawing_type 不一致 → VERSION_CONFLICT
      4. mapping_count == 0 → NO_DRAWING（无图纸对应）
      5. mapping_count ≤ 2 → MEASURABLE（可精确计量）
      6. mapping_count ≥ 3 → GROUP_ONLY（按组计量，需人工核对）
    """
    if has_provisional_flag:
        return Takability.PROVISIONAL

    if sheet_drawing_types:
        if any(dt in ("detail", "legend", "schedule") for dt in sheet_drawing_types):
            return Takability.NOT_MEASURABLE
        if len(set(sheet_drawing_types)) > 1:
            return Takability.VERSION_CONFLICT

    if mapping_count == 0:
        return Takability.NO_DRAWING
    if mapping_count <= 2:
        return Takability.MEASURABLE
    return Takability.GROUP_ONLY


# 黑名单 drawing_type（不参与精确计量）
BLACKLIST_DRAWING_TYPES = ("detail", "legend", "schedule")


def _log_writeback_audit(
    project_id: int,
    boq_item_id: int,
    original_qty: float,
    measured_qty: float,
    takability: str,
    file_sha256: str = "",
) -> None:
    """B5 S7：写 writeback_audit（保真回写审计）"""
    try:
        with db.get_conn() as conn:
            conn.execute(
                "INSERT INTO writeback_audit(project_id, boq_item_id, original_qty, "
                "measured_qty, takability, file_sha256) VALUES(?,?,?,?,?,?)",
                (project_id, boq_item_id, original_qty, measured_qty, takability, file_sha256),
            )
    except Exception:
        pass


def _collect_sheet_drawing_types(boq_item_id: int) -> list[str]:
    """P1-1：收集某 BOQ item 的 mapping → sheet 的 drawing_type 列表"""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT s.drawing_type FROM mapping m "
                "JOIN sheet s ON s.id = m.sheet_id "
                "WHERE m.boq_item_id = ?",
                (boq_item_id,),
            ).fetchall()
        return [r["drawing_type"] or "plan" for r in rows]
    except Exception:
        return []


def write_back_quantities(project_id: int, project_scale: float = 1.0) -> dict:
    """项目内全部 BOQ 子项计量 → 写回 measured_qty 列 + writeback_audit 审计

    P1-1 增强：6 状态 takability 完整判定（黑名单 + 版本冲突 + 暂定标注）

    Returns:
        {
            "written": int, "total": int,
            "by_takability": {state: count},
            "by_item": {boq_item_id: {"qty", "count", "takability"}}
        }
    """
    items = db.get_boq_items(project_id)
    res = recompute(project_id, project_scale=project_scale)
    by_item: dict[int, dict[str, Any]] = {}
    by_takability: dict[str, int] = {}
    written = 0
    for it in items:
        r = res.get(it.id, {"qty": 0.0, "count": 0})
        qty = round(r.get("qty") or 0.0, 4)
        count = r.get("count") or 0
        # P1-1：收集 sheet drawing_types 用于黑名单 + 版本冲突判定
        sheet_dts = _collect_sheet_drawing_types(it.id)
        takability = classify_takability(it.id, count, sheet_dts)
        db.update_boq_item(it.id, measured_qty=qty)
        _log_writeback_audit(project_id, it.id, it.original_qty or 0.0, qty, takability.value)
        by_item[it.id] = {"qty": qty, "count": count, "takability": takability.value}
        by_takability[takability.value] = by_takability.get(takability.value, 0) + 1
        if qty:
            written += 1
    return {
        "written": written,
        "total": len(items),
        "by_takability": by_takability,
        "items": by_item,
    }


def set_provisional_flag(boq_item_id: int, provisional: bool = True) -> None:
    """P1-1：人工标记某 BOQ item 为暂定值（PROVISIONAL）

    实现：boq_item.remark 字段追加 "[PROVISIONAL]" 标记（避免新加字段）
    """
    try:
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT remark FROM boq_item WHERE id = ?", (boq_item_id,),
            ).fetchone()
            current_remark = (row["remark"] if row else "") or ""
            has_flag = "[PROVISIONAL]" in current_remark
            if provisional and not has_flag:
                new_remark = f"{current_remark} [PROVISIONAL]".strip()
            elif not provisional and has_flag:
                new_remark = current_remark.replace("[PROVISIONAL]", "").strip()
            else:
                new_remark = current_remark
            conn.execute(
                "UPDATE boq_item SET remark = ? WHERE id = ?",
                (new_remark, boq_item_id),
            )
    except Exception:
        pass


def reset_measured_qty(project_id: int) -> int:
    """清空某项目全部实测数量（回写入口失效/撤销时调用）。返回清零行数。"""
    with db.get_conn() as conn:
        cur = conn.execute(
            "UPDATE boq_item SET measured_qty=0 WHERE project_id=?", (project_id,))
        return cur.rowcount