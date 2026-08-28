"""P1-3 大图 LOD（2026-08-28）：INSERT 块定义合并为单 path item 的单元测试。

验证 make_block_lod_item 与 make_block_group / 文本退化叉号三条路径：
- 子几何合并为单个 QGraphicsPathItem，ENTITY_ID 保留在 item 上
- 全部为文本（无可合并几何）的块 → 退化叉号标记，不崩
- 分组版行为不变（子项数量 = 块定义子项数）
"""
from __future__ import annotations

import sys

import pytest
from PySide6.QtWidgets import QApplication, QGraphicsItemGroup, QGraphicsPathItem

from app.ui import canvas as C

# 每个测试进程复用同一个 QApplication（Qt 只允许一个实例）
_APP = QApplication.instance() or QApplication(sys.argv)


def _sample_block() -> dict:
    return {
        "EQ-FAN": [
            {"type": "line", "start": [-2, -2], "end": [2, 2]},
            {"type": "line", "start": [-2, 2], "end": [2, -2]},
            {"type": "circle", "center": [0, 0], "radius": 1},
        ],
    }


def _insert(block: str) -> dict:
    return {"type": "insert", "block": block, "insert": [100, 50],
            "scale": [1.0, 1.0], "rotation": 45.0}


def test_lod_merges_block_into_single_path():
    item = C.make_block_lod_item(_insert("EQ-FAN"), 42, (255, 0, 0), _sample_block())  # noqa: _insert 无 eid
    assert isinstance(item, QGraphicsPathItem)
    assert not item.path().isEmpty()
    assert item.data(C.DATA_ENTITY_ID) == 42
    item.setData(C.DATA_ENTITY_ID, None)  # 残渣清理防泄漏（无场景父级）


def test_lod_text_only_block_falls_back_to_cross():
    """全文本块（无可合并几何）→ 退化叉号，不崩、可拾取。"""
    tx_geoms = {"TXT": [{"type": "text", "pos": [0, 0], "text": "LABEL"}]}
    item = C.make_block_lod_item({"type": "insert", "block": "TXT", "insert": [1, 1]},
                                 7, (0, 0, 255), tx_geoms)
    assert isinstance(item, QGraphicsPathItem)
    assert not item.path().isEmpty()          # 叉号路径非空
    assert item.path().elementCount() > 2     # 有线段而不是单点


def test_group_render_unchanged():
    """非 LOD（小图）路径仍走分组版，子项数等于块定义子项数。"""
    g = C.make_block_group(_insert("EQ-FAN"), 9, (0, 255, 0), _sample_block(), None)  # noqa: _insert 无 eid
    assert isinstance(g, QGraphicsItemGroup)
    assert len(g.childItems()) == 3
    assert g.data(C.DATA_ENTITY_ID) == 9