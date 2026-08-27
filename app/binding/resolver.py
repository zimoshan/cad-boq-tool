"""解析器：正式绑定 → 确定性计量 + BOQ 溯源。

Quantity 100% 由 Python 计算（measure.py），LLM 永不参与（任务四原则 4）。
"""
from __future__ import annotations

from .. import db, measure


def recompute(project_id: int, boq_item_id: int = None,
              project_scale: float = 1.0) -> dict:
    """确定性重算：项目内全部图纸对指定（或全部）条目累加计量。

    Returns:
        {boq_item_id: {"qty": float, "count": int, "detail": [...]}}
    """
    sheets = db.get_sheets(project_id)
    items = db.get_boq_items(project_id)
    if boq_item_id is not None:
        items = [i for i in items if i.id == boq_item_id]

    out = {}
    for it in items:
        total, count, detail = 0.0, 0, []
        for s in sheets:
            r = measure.compute_item(it, s.id, s.scale, project_scale)
            total += r["qty"]
            count += r["count"]
            detail.extend(r["detail"])
        out[it.id] = {"qty": round(total, 4), "count": count, "detail": detail}
    return out


def trace_quantity(project_id: int, boq_item_id: int) -> dict:
    """BOQ 溯源：条目 → 正式 mapping → 工程对象 → 实体 handle → 图纸。

    Returns:
        {"boq_item": BoqItem, "branches": [
            {"mapping": Mapping, "mode": str, "target": str,
             "eo": EngineeringObject|None, "sheet": Sheet|None,
             "entities": [Entity...], "qty": float}
        ]}
    """
    item = next((b for b in db.get_boq_items(project_id) if b.id == boq_item_id), None)
    if not item:
        return {"boq_item": None, "branches": []}

    mappings = db.get_mappings(boq_item_id=boq_item_id)
    eos = db.get_engineering_objects(project_id)
    sheets = {s.id: s for s in db.get_sheets(project_id)}

    branches = []
    for m in mappings:
        # entity 明细映射（点选/块展开的副产品）：单独成分支，锚定单个实体
        if m.mode == "entity" and m.entity_id:
            e = db.get_entity(m.sheet_id, m.entity_id)
            sheet = sheets.get(m.sheet_id)
            qty = 0.0
            if e:
                r = measure.compute_item(item, m.sheet_id, sheet.scale if sheet else 1.0)
                qty = r["qty"]
            branches.append({
                "mapping": m, "mode": "entity", "target": f"实体#{m.entity_id}",
                "eo": None, "sheet": sheet,
                "entities": [e] if e else [], "qty": round(qty, 4),
            })
            continue

        # 找到与 mapping 关联的工程对象（block 模式按块名 / layer 模式按图层名）
        eo = None
        if m.mode == "block" and m.block_name:
            eo = next((e for e in eos if e.block_name == m.block_name), None)
        elif m.mode == "layer" and m.layer_name:
            eo = next((e for e in eos if e.layer_name == m.layer_name), None)

        sheet = sheets.get(m.sheet_id)
        ents = []
        if eo:
            for eid in eo.entity_ids:
                e = db.get_entity(eo.sheet_id, eid)
                if e:
                    ents.append(e)

        # 分支计量（该 mapping 在对应图纸的实体量）
        qty = 0.0
        if eo and eo.sheet_id:
            r = measure.compute_item(item, eo.sheet_id, sheet.scale if sheet else 1.0)
            qty = r["qty"]

        branches.append({
            "mapping": m, "mode": m.mode,
            "target": m.block_name or m.layer_name or f"实体#{m.entity_id}",
            "eo": eo, "sheet": sheet, "entities": ents, "qty": round(qty, 4),
        })
    return {"boq_item": item, "branches": branches}
