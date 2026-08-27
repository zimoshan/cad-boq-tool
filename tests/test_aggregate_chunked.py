"""takeoff aggregate 分块 map-reduce 等价性测试（P2-6）。

分块聚合（chunk_size>1）必须与单块产出一致：图层计数/长度、区域 bbox、
块引用、典型尺寸逐项相等。
"""
from __future__ import annotations

import json
import unittest

from app.cad.cad_parser import ParsedDrawing
from app.models import Entity
from app.takeoff.aggregate import aggregate


def _make_entities(n: int):
    def mk(i):
        layer = f"L{i % 5}"
        if i % 11 == 0:
            gt = {"type": "text", "pos": [i, 0], "text": f"DN{80 + i % 100} 4x{i % 10 + 1}"}
            dxf = "TEXT"
        elif i % 7 == 0:
            gt = {"type": "insert", "insert": [i, 0], "block": f"B{i % 4}",
                  "scale": [1, 1], "rotation": 0}
            dxf = "INSERT"
            layer = "layer0"
        else:
            gt = {"type": "line", "start": [i, 0], "end": [i + 10, 0]}
            dxf = "LINE"
        return Entity(handle=str(i), dxf_type=dxf, layer=layer,
                      block_name=gt.get("block", ""),
                      bbox=(max(i - 30, 0), -10, i + 10, 10),
                      geom_json=json.dumps(gt), length=i % 5, area=0.0,
                      color=(255, 255, 255))
    return [mk(i) for i in range(n)]


def _canon(res):
    return (
        res.drawing_bbox,
        tuple(sorted((l.name, l.entity_count, round(l.total_length_mm, 4))
                     for l in res.layers)),
        tuple(sorted((r.grid_id, r.bbox) for r in res.regions)),
        tuple(sorted(res.block_inserts.items())),
        tuple(res.typical_sizes),
    )


class AggregateChunkedTest(unittest.TestCase):
    def test_chunked_equals_single(self):
        d = ParsedDrawing(entities=_make_entities(2000), layers={}, layer_colors={},
                          blocks={}, block_refs={"B0": 2})
        full = aggregate(d, chunk_size=1)
        for chunk in (2, 500, 2000):
            self.assertEqual(_canon(full), _canon(aggregate(d, chunk_size=chunk)),
                             f"chunk={chunk} 与单块不一致")

    def test_chunked_region_bbox_single_pass(self):
        # 多区块：实体散布在两块 50m×50m 电网内，区域 bbox 应各归其位
        d = ParsedDrawing(entities=_make_entities(2000), layers={}, layer_colors={},
                          blocks={}, block_refs={})
        res = aggregate(d, chunk_size=400)
        # 所有实体 x∈[0,2009] → 全部落入 gx=0；y∈[-10,10] → gy=0
        self.assertEqual([r.grid_id for r in res.regions if r.grid_id],
                         [(0, 0)])


if __name__ == "__main__":
    unittest.main()