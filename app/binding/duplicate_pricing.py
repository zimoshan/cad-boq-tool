"""P6-2 跨专业/跨清单重复计价检测（v2.0 §6.4 四能力 ②）

同一 block/layer 锚点被绑定到 ≥2 个不同 BOQ 子项 → 重复计价候选
（可能合法：同类设备按规格分条目，但需要人工确认 → needs_review 标记）。

与 2.3.2 唯一性校验的关系：
  - reviewer._accepted_block_boq 在"确认动作"时拦截 同 block/layer → 另一 BOQ；
  - 本模块做**事后检查**：存量 mapping 中的重复锚点全部列出（含历史遗留、
    跨图纸、跨专业清单），供闸门/总览页提示，不阻断已确认数据。

架构（#19 业务逻辑归 app 层 + 双引擎容错）：
  - 输入行兼容 dict/对象（mapping 行须含 mode/block_name/layer_name/boq_item_id/sheet_id）。
  - 纯逻辑函数 build_duplicates()（SQL 无关）+ db 路径 detect_duplicate_pricing()。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def _field(row: Any, name: str, default: Any = ""):
    """兼容 dict / dataclass 形态的字段读取"""
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def _anchor_key(mode: str, block_name: str, layer_name: str) -> tuple[str, str]:
    """锚点 key：(kind, 名称)。只统计命中的维度（block 优先于 layer）。

    名称归一化：仅保留字母数字（连字符/下划线/空白均等价），与
    version_gate._normalize_filename 同一口径（FAN-01 == fan_01）。
    """
    if mode == "block" and block_name:
        return ("block", re.sub(r"[^a-z0-9]+", "", block_name.lower()))
    if layer_name:
        return ("layer", re.sub(r"[^a-z0-9]+", "", layer_name.lower()))
    return ("", "")


@dataclass
class _Anchor:
    """锚点聚合中间态"""

    anchor: str
    kind: str  # block / layer
    block_name: str = ""
    layer_name: str = ""
    boq_item_ids: set = field(default_factory=set)
    sheet_ids: set = field(default_factory=set)


def build_duplicates(mappings: list[Any], boq_index: dict[int, Any] | None = None) -> list[dict]:
    """纯逻辑：把 mapping 行按锚点分组，输出 ≥2 个不同 BOQ 明细的组。

    Args:
        mappings: mapping 行（dict/对象，须含 mode/block_name/layer_name/boq_item_id/sheet_id）。
        boq_index: {boq_item_id: boq行} → 输出 code/description（可空，缺省只给 id）。

    Returns:
        候选列表（按 boq_items 数降序），每项：
        {anchor, kind, block_name, layer_name, boq_items:[{boq_item_id,code,description}],
         sheet_ids, needs_review:True}
    """
    groups: dict[tuple[str, str], _Anchor] = {}

    for m in mappings:
        mode = str(_field(m, "mode", "") or "")
        block = str(_field(m, "block_name", "") or "")
        layer = str(_field(m, "layer_name", "") or "")
        boq_id = _field(m, "boq_item_id", 0)
        sheet_id = _field(m, "sheet_id", 0)
        kind, key = _anchor_key(mode, block, layer)
        if not key:
            continue
        g = groups.setdefault(
            (kind, key),
            _Anchor(
                anchor=f"{kind}:{key}",
                kind=kind,
                block_name=block if kind == "block" else "",
                layer_name=layer if kind == "layer" else "",
            ),
        )
        g.boq_item_ids.add(boq_id)
        g.sheet_ids.add(sheet_id)

    out = []
    for g in groups.values():
        if len(g.boq_item_ids) < 2:
            continue
        items = []
        for b in sorted(g.boq_item_ids):
            if boq_index and b in boq_index:
                bi = boq_index[b]
                items.append(
                    {
                        "boq_item_id": b,
                        "code": str(_field(bi, "code", "") or ""),
                        "description": str(_field(bi, "description", "") or ""),
                    }
                )
            else:
                items.append({"boq_item_id": b, "code": "", "description": ""})
        out.append(
            {
                "anchor": g.anchor,
                "kind": g.kind,
                "block_name": g.block_name,
                "layer_name": g.layer_name,
                "boq_items": items,
                "sheet_ids": sorted(g.sheet_ids),
                "needs_review": True,
            }
        )
    out.sort(key=lambda d: -len(d["boq_items"]))
    return out


def detect_duplicate_pricing(project_id: int) -> list[dict]:
    """SQLite 路径：从 app.db 读 mapping + boq → 重复计价候选列表。"""
    from .. import db

    try:
        mappings = db.get_mappings()
        boqs = db.get_boq_items(project_id)
    except Exception:
        return []
    boq_index = {b.id: b for b in boqs} if boqs else {}
    return build_duplicates(mappings, boq_index)
