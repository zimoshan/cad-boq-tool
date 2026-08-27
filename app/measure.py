"""计量引擎：长度 / 面积 / 数量"""
from __future__ import annotations

import json

from . import db, mapping as map_svc
from .models import BoqItem


def _factor_of(item: BoqItem, sheet_scale: float, project_scale: float = 1.0) -> float:
    """总换算因子 = 项目 × 图纸 × 条目"""
    return project_scale * sheet_scale * item.scale_factor


def compute_entity_qty(item: BoqItem, entity) -> float:
    """单实体按规则计量（未乘因子）"""
    rule = item.rule_type
    if rule == "count":
        return 1.0
    if rule == "area":
        if entity.area and entity.area > 0:
            return entity.area
        # 兜底：从几何算
        try:
            g = json.loads(entity.geom_json)
            if g.get("type") == "circle":
                r = g.get("radius", 0)
                return 3.14159265358979 * r * r
        except Exception:
            pass
        return 0.0
    # length
    if entity.length and entity.length > 0:
        return entity.length
    return 0.0


def compute_item(item: BoqItem, sheet_id: int, sheet_scale: float = 1.0, project_scale: float = 1.0) -> dict:
    """计算某条目的计量结果。
    返回 {qty, count, detail: [ {entity_id, handle, qty}, ... ]}
    """
    factor = _factor_of(item, sheet_scale, project_scale)
    if item.rule_type == "count":
        factor_eff = 1.0
    elif item.rule_type == "area":
        factor_eff = factor * factor
    else:
        factor_eff = factor

    ids = map_svc.mapped_entity_ids(item.id, sheet_id)
    # 批量获取所有需要的实体（单次查询替代 N 次 get_entity）
    entities = db.get_entities_by_ids(sheet_id, ids)
    entities_by_id = {e.id: e for e in entities}

    total = 0.0
    detail = []
    for eid in ids:
        e = entities_by_id.get(eid)
        if not e:
            continue
        q = compute_entity_qty(item, e)
        total += q
        detail.append({"entity_id": e.id, "handle": e.handle, "qty": round(q, 4)})

    return {
        "qty": round(total * factor_eff, 4),
        "count": len(ids),
        "detail": detail,
        "factor": round(factor_eff, 6),
    }
