"""流式聚合：单文件不持 raw entities + 跨文件累计 + 智能分块。

Phase 23-1：
- aggregate_file_streaming() 单文件 → FileSummary（轻量）
- AggregatedProject 跨文件累计 layer/block/floor
- to_llm_chunks() 智能分块（24K token 上限）
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterator

from ..cad import cad_parser as cad_parser
from .aggregate import aggregate as aggregate_full


# 1 token ≈ 1.5 字符（中文估算）
CHARS_PER_TOKEN = 1.5
DEFAULT_MAX_TOKENS = 24_000


@dataclass
class FileSummary:
    """单文件聚合（轻量：~10 KB/文件）"""
    path: str
    floor: str = ""
    section: str = ""
    layer_count: int = 0
    block_count: int = 0
    block_inserts: dict = field(default_factory=dict)
    parse_error: str = ""
    entity_count: int = 0


@dataclass
class AggregatedProject:
    """全项目聚合（跨文件累计）"""
    project_name: str
    layers: dict = field(default_factory=dict)        # layer_name -> LayerAccumulator
    block_inserts: dict = field(default_factory=dict) # block_name -> total count
    files: list = field(default_factory=list)         # list[FileSummary]
    typical_sizes: list = field(default_factory=list)
    trade: str = ""

    def add_file(self, file_summary: FileSummary, agg_full: dict):
        """吸收一个文件的完整聚合结果"""
        self.files.append(file_summary)
        for layer_dict in agg_full.get("layers", []):
            name = layer_dict["name"]
            acc = self.layers.setdefault(name, LayerAccumulator(name=name))
            acc.entity_count += layer_dict.get("entity_count", 0)
            acc.total_length_mm += (layer_dict.get("total_length_m", 0) or 0) * 1000
            acc.total_area_mm2 += (layer_dict.get("total_area_m2", 0) or 0) * 1_000_000
            # type_breakdown 累加
            for t, c in (layer_dict.get("type_breakdown") or {}).items():
                acc.type_breakdown[t] = acc.type_breakdown.get(t, 0) + c
            for txt in (layer_dict.get("sample_texts") or []):
                acc.sample_texts.append(txt)
            acc.floors.add(file_summary.floor)
            acc.files.add(file_summary.path)
        for bname, count in agg_full.get("block_inserts", {}).items():
            self.block_inserts[bname] = self.block_inserts.get(bname, 0) + count
        # 收集 typical_sizes
        for sz in agg_full.get("typical_sizes", []):
            if sz not in self.typical_sizes:
                self.typical_sizes.append(sz)

    def to_llm_dict(self) -> dict:
        """序列化为可喂 LLM 的 dict"""
        return {
            "project_name": self.project_name,
            "trade": self.trade,
            "files": [
                {
                    "filename": f.path,
                    "floor": f.floor,
                    "section": f.section,
                    "layer_count": f.layer_count,
                    "block_count": f.block_count,
                }
                for f in self.files
            ],
            "layers": [
                {
                    "name": acc.name,
                    "entity_count": acc.entity_count,
                    "type_breakdown": acc.type_breakdown,
                    "total_length_m": round(acc.total_length_mm / 1000, 2),
                    "total_area_m2": round(acc.total_area_mm2 / 1_000_000, 2),
                    "sample_texts": acc.sample_texts[:10],
                    "files": list(acc.files),
                    "floors": sorted(acc.floors),
                }
                for acc in sorted(self.layers.values(), key=lambda x: -x.entity_count)
            ],
            "block_inserts": self.block_inserts,
            "typical_sizes": self.typical_sizes[:30],
        }

    def estimate_tokens(self) -> int:
        """粗估总 token 数"""
        return int(len(json.dumps(self.to_llm_dict(), ensure_ascii=False)) / CHARS_PER_TOKEN)

    def to_llm_chunks(self, max_tokens: int = DEFAULT_MAX_TOKENS) -> Iterator[dict]:
        """智能分块：按 trade × floor_group

        策略：
        1. 总 token ≤ max_tokens → 单 chunk
        2. 否则按 trade 分组
        3. 单 trade 还大 → 按 floor 分组
        """
        total = self.estimate_tokens()
        if total <= max_tokens:
            yield self.to_llm_dict()
            return

        # 按 trade 分组
        trade_layers = defaultdict(list)
        for acc in self.layers.values():
            t = self.trade or "综合"
            trade_layers[t].append(acc)

        for trade, accs in trade_layers.items():
            sub = AggregatedProject(project_name=f"{self.project_name}-{trade}", trade=trade)
            sub.layers = {a.name: a for a in accs}
            sub.typical_sizes = list(self.typical_sizes)
            sub.block_inserts = dict(self.block_inserts)
            sub.files = list(self.files)
            sub_tokens = sub.estimate_tokens()
            if sub_tokens <= max_tokens:
                yield sub.to_llm_dict()
            else:
                # 单 trade 还大，按 floor 分
                floor_layers = defaultdict(list)
                for a in accs:
                    for f in a.floors or ["默认"]:
                        floor_layers[f].append(a)
                for floor, faccs in floor_layers.items():
                    fsub = AggregatedProject(project_name=f"{self.project_name}-{trade}-{floor}", trade=trade)
                    fsub.layers = {a.name: a for a in faccs}
                    fsub.typical_sizes = list(self.typical_sizes)
                    fsub.block_inserts = dict(self.block_inserts)
                    fsub.files = [f for f in self.files if f.floor == floor]
                    yield fsub.to_llm_dict()


@dataclass
class LayerAccumulator:
    """跨文件累计的图层数据"""
    name: str
    entity_count: int = 0
    total_length_mm: float = 0.0
    total_area_mm2: float = 0.0
    type_breakdown: dict = field(default_factory=dict)
    sample_texts: list = field(default_factory=list)
    files: set = field(default_factory=set)
    floors: set = field(default_factory=set)


def aggregate_file_streaming(file_path: str, floor: str = "",
                            section: str = "") -> FileSummary:
    """单文件聚合（不持有 raw entities，靠 cad_parser 流式生成结果）

    实际上 cad_parser.parse_dxf 已经是流式（内部只持有 layer/block 索引），
    aggregate() 也只生成汇总。内存峰值 = 1 张图大小。
    """
    fs = FileSummary(path=file_path, floor=floor, section=section)
    try:
        from ..cad import parse_cache
        drawing = parse_cache.get_cached_drawing(file_path)
        if drawing is None:
            drawing = cad_parser.parse_dxf(file_path)
            parse_cache.cache_drawing(file_path, drawing)
        agg = aggregate_full(drawing)
        agg_dict = agg.to_llm_dict()
        fs.entity_count = len(drawing.entities)
        fs.layer_count = len(agg_dict["layers"])
        fs.block_count = len(agg_dict["block_inserts"])
        fs.block_inserts = dict(agg_dict["block_inserts"])
        # 把 agg_dict 暂存到 FileSummary（通过 _agg_dict 私有字段，folder_pipeline 会提取）
        fs._agg_dict = agg_dict
    except Exception as e:
        fs.parse_error = str(e)
    return fs
