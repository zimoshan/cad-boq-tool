"""智能聚合：DWG/DXF 解析结果 → 图层级 + 空间分区级 汇总。

Phase 22A-1：
- 输入：ParsedDrawing（已有 parser.parse_dxf 的输出）
- 输出：dict {layers: [...], regions: [...], typical_sizes: [...], drawing_bbox}
- 0 依赖 0 GPU，秒级出结果
- 用于喂给 LLM 做分类/命名（不让 LLM 算数值）
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from ..cad.cad_parser import ParsedDrawing


@dataclass
class LayerSummary:
    """单图层汇总"""
    name: str
    entity_count: int = 0
    type_breakdown: dict = field(default_factory=dict)   # {"LWPOLYLINE": 65, "LINE": 22}
    total_length_mm: float = 0.0
    total_area_mm2: float = 0.0
    bbox: tuple = (0, 0, 0, 0)                           # (min_x, min_y, max_x, max_y) mm
    sample_texts: list = field(default_factory=list)       # 典型尺寸文本
    sample_handles: list = field(default_factory=list)     # 样例 handle（debug 用）


@dataclass
class RegionSummary:
    """空间分区汇总（50m × 50m 网格）"""
    grid_id: tuple = (0, 0)            # (gx, gy) 网格坐标
    bbox: tuple = (0, 0, 0, 0)
    layer_summaries: dict = field(default_factory=dict)    # layer_name -> LayerSummary
    block_inserts: dict = field(default_factory=dict)      # block_name -> count


@dataclass
class AggregatedDrawing:
    """全图汇总（喂 LLM 用）"""
    drawing_bbox: tuple = (0, 0, 0, 0)
    layers: list = field(default_factory=list)              # list[LayerSummary]
    regions: list = field(default_factory=list)             # list[RegionSummary]
    block_inserts: dict = field(default_factory=dict)      # block_name -> count
    typical_sizes: list = field(default_factory=list)       # ["DN100", "Φ50", ...]
    project_name: str = ""

    def to_llm_dict(self) -> dict:
        """序列化为可喂 LLM 的 dict"""
        return {
            "drawing_bbox": self.drawing_bbox,
            "layers": [
                {
                    "name": l.name,
                    "entity_count": l.entity_count,
                    "type_breakdown": l.type_breakdown,
                    "total_length_m": round(l.total_length_mm / 1000, 2),
                    "total_area_m2": round(l.total_area_mm2 / 1_000_000, 2),
                    "sample_texts": l.sample_texts[:10],
                }
                for l in self.layers
            ],
            "block_inserts": self.block_inserts,
            "typical_sizes": self.typical_sizes,
        }


# 典型尺寸正则：DN100 / DN150 / Φ50 / 1000x500 / 800X400 等
SIZE_PATTERNS = [
    # 电缆型号 + 芯数×截面积（如 NHXMH 4x1.5 / NH-YJV 3x35+1x16），放最前优先命中
    re.compile(r"(?:NHXMH|NH-YJV|NH-YJY|WDZ-YJY|WDZ-YJE|ZR-YJV|ZR-YJY|YJV|YJY|BVR|BYJ|RVVP|RVV|RVS|KYJV|KVV|DJYPVP)"
               r"\s*\d{1,2}\s*[xX×]\s*\d{1,2}(?:\.\d+)?"
               r"(?:\s*\+\s*\d{1,2}\s*[xX×]\s*\d{1,2}(?:\.\d+)?)*", re.IGNORECASE),
    # 通用 芯数×截面积 NxS（含小数如 4x1.5）；(?<!\d)/(?!\d) 防止把 1000x500 误切为 10x50
    re.compile(r"(?<!\d)(\d{1,2})\s*[xX×]\s*(\d{1,2}(?:\.\d+)?)(?!\d)", re.IGNORECASE),
    re.compile(r"DN\s*(\d{2,4})", re.IGNORECASE),     # DN100
    re.compile(r"Φ\s*(\d{2,4})"),                     # Φ50
    re.compile(r"(\d{2,4})\s*[xX×]\s*(\d{2,4})"),      # 1000x500
    re.compile(r"(\d{2,4})mm"),                        # 100mm
    re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})"),          # 100/150 (管径/长度)
    re.compile(r"SC\s*(\d{1,3})", re.IGNORECASE),     # SC20 (电气导管)
    re.compile(r"(\d{2,4})mm\s*²", re.IGNORECASE),    # 100mm²
]


def extract_typical_sizes(texts: Iterable[str]) -> list:
    """从尺寸文本中提取典型规格（去重保序）"""
    seen = set()
    out = []
    for t in texts:
        if not t or not isinstance(t, str):
            continue
        for pat in SIZE_PATTERNS:
            for m in pat.finditer(t):
                full = m.group(0).strip()
                # 标准化（统一空格、大写）
                norm = re.sub(r"\s+", "", full.upper())
                if norm not in seen:
                    seen.add(norm)
                    out.append(full)
                break  # 每条文本只匹配第一个
    return out[:50]  # 上限 50


def _map_chunk(entities, grid_size_mm: float):
    """Map 阶段：对实体分块，各自产出 (layer_acc, region_acc, drawing_bbox, texts)。

    返回可被 _reduce 合并的中间态（纯累加结构，无全局二次扫描）。
    """
    layer_acc: dict = defaultdict(lambda: LayerSummary(name=""))
    region_acc: dict = {}
    drawing_bbox = [float("inf"), float("inf"), float("-inf"), float("-inf")]

    for e in entities:
        ls = layer_acc[e.layer]
        if not ls.name:
            ls.name = e.layer
        ls.entity_count += 1
        ls.type_breakdown[e.dxf_type] = ls.type_breakdown.get(e.dxf_type, 0) + 1
        ls.total_length_mm += e.length or 0
        ls.total_area_mm2 += e.area or 0
        bx0, by0, bx1, by1 = e.bbox
        if bx0 < drawing_bbox[0]: drawing_bbox[0] = bx0
        if by0 < drawing_bbox[1]: drawing_bbox[1] = by0
        if bx1 > drawing_bbox[2]: drawing_bbox[2] = bx1
        if by1 > drawing_bbox[3]: drawing_bbox[3] = by1
        # 采样尺寸文本（TEXT/MTEXT）
        if e.dxf_type in ("TEXT", "MTEXT"):
            import json
            try:
                g = json.loads(e.geom_json)
                if "text" in g and g["text"]:
                    ls.sample_texts.append(g["text"])
            except Exception:
                pass
        # 采样 handle
        if len(ls.sample_handles) < 5:
            ls.sample_handles.append(e.handle)

        # 空间分区（单遍：同一次遍历累加区域 bbox，不再二次全表扫描）
        if e.bbox != (0, 0, 0, 0):
            cx = (e.bbox[0] + e.bbox[2]) / 2
            cy = (e.bbox[1] + e.bbox[3]) / 2
            key = (int(cx // grid_size_mm), int(cy // grid_size_mm))
            rs = region_acc.get(key)
            if rs is None:
                rs = RegionSummary(grid_id=key)
                region_acc[key] = rs
            rx0, ry0, rx1, ry1 = rs.bbox
            if rs.bbox == (0, 0, 0, 0):
                rs.bbox = (bx0, by0, bx1, by1)
            else:
                if bx0 < rx0: rs.bbox = (bx0, rs.bbox[1], rs.bbox[2], rs.bbox[3])
                if by0 < ry0: rs.bbox = (rs.bbox[0], by0, rs.bbox[2], rs.bbox[3])
                if bx1 > rx1: rs.bbox = (rs.bbox[0], rs.bbox[1], bx1, rs.bbox[3])
                if by1 > ry1: rs.bbox = (rs.bbox[0], rs.bbox[1], rs.bbox[2], by1)
            rls = rs.layer_summaries.get(e.layer)
            if rls is None:
                rls = LayerSummary(name=e.layer)
                rs.layer_summaries[e.layer] = rls
            rls.entity_count += 1
            rls.total_length_mm += e.length or 0
            rls.total_area_mm2 += e.area or 0
            if e.dxf_type == "INSERT":
                rs.block_inserts[e.block_name] = rs.block_inserts.get(e.block_name, 0) + 1

    return layer_acc, region_acc, drawing_bbox


def _merge_accumulators(accumulators):
    """Reduce 阶段：合并多个 chunk 的 (layer_acc, region_acc, drawing_bbox)。"""
    layer_acc: dict = defaultdict(lambda: LayerSummary(name=""))
    region_acc: dict = {}
    drawing_bbox = [float("inf"), float("inf"), float("-inf"), float("-inf")]

    for la, ra, bb in accumulators:
        # 合并图层
        for name, ls in la.items():
            tgt = layer_acc.get(name)
            if tgt is None:
                tgt = LayerSummary(name=name)
                layer_acc[name] = tgt
            tgt.entity_count += ls.entity_count
            for t, c in ls.type_breakdown.items():
                tgt.type_breakdown[t] = tgt.type_breakdown.get(t, 0) + c
            tgt.total_length_mm += ls.total_length_mm
            tgt.total_area_mm2 += ls.total_area_mm2
            tgt.sample_texts.extend(ls.sample_texts[:10])
            tgt.sample_handles.extend(ls.sample_handles[:5 - len(tgt.sample_handles)])
        # 合并区域
        for key, rs in ra.items():
            tgt = region_acc.get(key)
            if tgt is None:
                tgt = RegionSummary(grid_id=key)
                region_acc[key] = tgt
            # bbox 合并
            if rs.bbox != (0, 0, 0, 0):
                if tgt.bbox == (0, 0, 0, 0):
                    tgt.bbox = rs.bbox
                else:
                    tgt.bbox = (min(tgt.bbox[0], rs.bbox[0]),
                                min(tgt.bbox[1], rs.bbox[1]),
                                max(tgt.bbox[2], rs.bbox[2]),
                                max(tgt.bbox[3], rs.bbox[3]))
            for layer_name, rls in rs.layer_summaries.items():
                tgt_rls = tgt.layer_summaries.get(layer_name)
                if tgt_rls is None:
                    tgt_rls = LayerSummary(name=layer_name)
                    tgt.layer_summaries[layer_name] = tgt_rls
                tgt_rls.entity_count += rls.entity_count
                tgt_rls.total_length_mm += rls.total_length_mm
                tgt_rls.total_area_mm2 += rls.total_area_mm2
            for bname, c in rs.block_inserts.items():
                tgt.block_inserts[bname] = tgt.block_inserts.get(bname, 0) + c
        # 合并全图 bbox
        if bb[0] < drawing_bbox[0]: drawing_bbox[0] = bb[0]
        if bb[1] < drawing_bbox[1]: drawing_bbox[1] = bb[1]
        if bb[2] > drawing_bbox[2]: drawing_bbox[2] = bb[2]
        if bb[3] > drawing_bbox[3]: drawing_bbox[3] = bb[3]

    return layer_acc, region_acc, drawing_bbox


def aggregate(drawing: ParsedDrawing, grid_size_mm: float = 50_000,
              chunk_size: int = 20_000) -> AggregatedDrawing:
    """主入口：ParsedDrawing → AggregatedDrawing

    P2-6 分块 map-reduce：实体按 chunk 切分各自统计（_map_chunk），再合并
    （_merge_accs）。单遍遍历 O(N)，区域 bbox 在 chunk 内一次累加完成，消除了
    旧实现的「区域×全实体」二次扫描（大图掉帧主因）。

    Args:
        drawing: parser.parse_dxf 的输出
        grid_size_mm: 空间网格大小（默认 50m × 50m）
        chunk_size: 单块最大实体数（>1 才分块，小图直接单块）

    Returns:
        AggregatedDrawing: 含 layers/regions/block_inserts/typical_sizes
    """
    entities = drawing.entities
    chunk_size = max(chunk_size, 1)

    if chunk_size == 1 or len(entities) <= chunk_size:
        accum = _map_chunk(entities, grid_size_mm)
        layer_acc, region_acc, bbox = accum
    else:
        chunks = [entities[i:i + chunk_size] for i in range(0, len(entities), chunk_size)]
        layer_acc, region_acc, bbox = _merge_accumulators(
            [_map_chunk(c, grid_size_mm) for c in chunks])

    drawing_bbox = tuple(bbox) if bbox[0] != float("inf") else (0, 0, 0, 0)

    # 2. 块引用统计
    block_inserts = dict(drawing.block_refs)

    # 3. 典型尺寸（合并所有图层采样文本）
    all_texts = []
    for ls in layer_acc.values():
        all_texts.extend(ls.sample_texts)
    typical_sizes = extract_typical_sizes(all_texts)

    return AggregatedDrawing(
        drawing_bbox=drawing_bbox,
        layers=sorted(layer_acc.values(), key=lambda x: -x.entity_count),
        regions=sorted(region_acc.values(), key=lambda x: x.grid_id),
        block_inserts=block_inserts,
        typical_sizes=typical_sizes,
    )
