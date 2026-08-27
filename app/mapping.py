"""映射服务：实体/图层/块 ↔ BOQ 条目"""
from __future__ import annotations

from . import db
from .models import Mapping


def add_entity_mapping(boq_item_id: int, sheet_id: int, entity_ids: list) -> tuple:
    """点选/框选映射。返回 (成功数, 冲突实体id列表)"""
    added = 0
    conflicts = []
    for eid in entity_ids:
        if db.entity_mapped(sheet_id, eid):
            conflicts.append(eid)
            continue
        db.add_mapping(boq_item_id, sheet_id, "entity", entity_id=eid)
        added += 1
    return added, conflicts


def add_layer_mapping(boq_item_id: int, sheet_id: int, layer_name: str) -> tuple:
    """按图层映射：该图层全部实体"""
    entities = db.get_entities(sheet_id, layer=layer_name)
    ids = [e.id for e in entities]
    added, conflicts = add_entity_mapping(boq_item_id, sheet_id, ids)
    if added:
        db.add_mapping(boq_item_id, sheet_id, "layer", layer_name=layer_name)
    return added, conflicts


def add_block_mapping(boq_item_id: int, sheet_id: int, block_name: str) -> tuple:
    """按块名映射：同名牌引用全部关联，自动设为 count 规则"""
    entities = db.get_entities(sheet_id, block=block_name)
    ids = [e.id for e in entities]
    added, conflicts = add_entity_mapping(boq_item_id, sheet_id, ids)
    if added:
        db.add_mapping(boq_item_id, sheet_id, "block", block_name=block_name)
        db.update_boq_item(boq_item_id, rule_type="count")
    return added, conflicts


def mapped_entity_ids(boq_item_id: int, sheet_id: int) -> list:
    """某条目已映射的实体 id 列表（entity 模式逐条 + layer/block 展开）"""
    ids = []
    for m in db.get_mappings(boq_item_id, sheet_id):
        if m.mode == "entity" and m.entity_id:
            ids.append(m.entity_id)
        elif m.mode == "layer" and m.layer_name:
            ids.extend(db.get_entity_ids_by_layer(sheet_id, m.layer_name))
        elif m.mode == "block" and m.block_name:
            ids.extend(db.get_entity_ids_by_block(sheet_id, m.block_name))
    # 去重（保持顺序）
    seen = set()
    uniq = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return uniq


def mapping_count(boq_item_id: int, sheet_id: int) -> int:
    return len(mapped_entity_ids(boq_item_id, sheet_id))


def resolve_entity_ids(sheet_id: int, mapping: Mapping) -> list:
    if mapping.mode == "entity" and mapping.entity_id:
        return [mapping.entity_id]
    if mapping.mode == "layer":
        return db.get_entity_ids_by_layer(sheet_id, mapping.layer_name)
    if mapping.mode == "block":
        return db.get_entity_ids_by_block(sheet_id, mapping.block_name)
    return []
