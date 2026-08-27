"""工程量回写：把项目级计量结果写入 BOQ 实测数量列（measured_qty）。

口径（方案 A 定稿）：
- 复用 resolver.recompute（跨图纸累加、纯确定性、LLM 不参与）
- 写入 boq_item.measured_qty —— **实测数量列**（原数量列保留不作对照覆盖）
- 导出主要材料表/算量清单时，可选择「用实测值覆盖原数量」出终表
"""
from __future__ import annotations

from .. import db
from ..binding.resolver import recompute


def write_back_quantities(project_id: int, project_scale: float = 1.0) -> dict:
    """项目内全部 BOQ 子项计量 → 写回 measured_qty 列。

    Returns:
        {"written": int, "total": int, "by_item": {boq_item_id: {"qty", "count"}}}
    """
    items = db.get_boq_items(project_id)
    res = recompute(project_id, project_scale=project_scale)
    by_item = {}
    written = 0
    for it in items:
        r = res.get(it.id, {"qty": 0.0, "count": 0})
        qty = round(r.get("qty") or 0.0, 4)
        db.update_boq_item(it.id, measured_qty=qty)
        by_item[it.id] = {"qty": qty, "count": r.get("count") or 0}
        if qty:
            written += 1
    return {"written": written, "total": len(items), "items": by_item}


def reset_measured_qty(project_id: int) -> int:
    """清空某项目全部实测数量（回写入口失效/撤销时调用）。返回清零行数。"""
    with db.get_conn() as conn:
        cur = conn.execute(
            "UPDATE boq_item SET measured_qty=0 WHERE project_id=?", (project_id,))
        return cur.rowcount