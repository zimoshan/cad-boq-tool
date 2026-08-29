"""候选聚合模块：按块名聚合候选，按置信度排序，支持相似度加权。

解决 60+ 块产生 400+ 候选难以选择的问题：
1. 按 block_name 聚合同名块的所有候选
2. 按置信度降序排列（最高置信候选优先）
3. 块名与 BOQ 描述相似度高的候选提升排名
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .. import db
from ..models import BindingCandidate, EngineeringObject, BoqItem
from .text_norm import normalize, compact, string_similarity


@dataclass
class AggregatedCandidate:
    """聚合后的候选组"""
    block_name: str
    layer_name: str
    object_type: str
    candidates: list[BindingCandidate] = field(default_factory=list)
    engineering_objects: list[EngineeringObject] = field(default_factory=list)
    max_confidence: float = 0.0
    avg_confidence: float = 0.0
    similarity_score: float = 0.0  # 块名与最佳 BOQ 描述的相似度
    best_boq_item: Optional[BoqItem] = None
    sheet_names: list[str] = field(default_factory=list)
    total_count: int = 0  # 该块在图纸中的总出现次数


def calculate_name_similarity(block_name: str, boq_description: str) -> float:
    """计算块名与 BOQ 描述的相似度（0-1）。

    考虑因素：
    1. 整串相似度（最高权重）
    2. 关键词重叠度
    3. 编号匹配（如 AL-01 ↔ 配电箱 AL-01）
    """
    if not block_name or not boq_description:
        return 0.0

    # 规范化文本
    bn = normalize(block_name)
    desc = normalize(boq_description)

    # 1. 整串相似度（权重 0.6）
    full_sim = string_similarity(bn, desc)

    # 2. 关键词重叠（权重 0.3）
    bn_words = set(re.split(r"[\s_\-/\\.,()\[\]]+", bn))
    desc_words = set(re.split(r"[\s_\-/\\.,()\[\]]+", desc))
    bn_words = {w for w in bn_words if len(w) >= 2}
    desc_words = {w for w in desc_words if len(w) >= 2}
    if bn_words and desc_words:
        overlap = len(bn_words & desc_words) / max(len(bn_words), len(desc_words))
    else:
        overlap = 0.0

    # 3. 编号匹配（权重 0.1）
    # 提取块名中的编号（如 AL-01 中的 01）
    bn_num = re.search(r"(\d+)$", bn)
    desc_num = re.search(r"(\d+)$", desc)
    num_match = 1.0 if (bn_num and desc_num and bn_num.group(1) == desc_num.group(1)) else 0.0

    # 加权计算
    score = full_sim * 0.6 + overlap * 0.3 + num_match * 0.1
    return min(1.0, score)


def aggregate_candidates(
    project_id: int,
    status: str = "PENDING",
    sheet_id: int = None,
    limit: int = 100
) -> list[AggregatedCandidate]:
    """按块名聚合候选，返回排序后的聚合列表。

    排序规则：
    1. 块名与 BOQ 描述相似度高的优先（similarity_score 降序）
    2. 同等相似度下，最高置信度高的优先（max_confidence 降序）
    3. 同等置信度下，候选数量多的优先（total_count 降序）

    Args:
        project_id: 项目 ID
        status: 候选状态过滤（默认 PENDING）
        sheet_id: 可选，只聚合特定图纸的候选
        limit: 返回数量上限
    Returns:
        聚合后的候选组列表
    """
    # 获取所有候选
    candidates = db.get_candidates(project_id, status=status)

    # 获取所有工程对象
    eos = {eo.id: eo for eo in db.get_engineering_objects(project_id)}

    # 获取所有 BOQ 条目
    boq_items = {it.id: it for it in db.get_boq_items(project_id)}

    # 获取图纸名称映射
    sheets = {s.id: s.filename for s in db.get_sheets(project_id)}

    # 按块名聚合
    block_groups: dict[str, AggregatedCandidate] = {}

    for c in candidates:
        eo = eos.get(c.engineering_object_id)
        if eo is None:
            continue

        # 如果指定了图纸，过滤
        if sheet_id is not None and eo.sheet_id != sheet_id:
            continue

        block_key = eo.block_name or eo.layer_name or f"EO#{eo.id}"

        if block_key not in block_groups:
            block_groups[block_key] = AggregatedCandidate(
                block_name=eo.block_name or "",
                layer_name=eo.layer_name or "",
                object_type=eo.object_type or "",
            )

        group = block_groups[block_key]
        group.candidates.append(c)
        group.engineering_objects.append(eo)
        group.total_count += len(eo.entity_ids) if eo.entity_ids else 1

        # 更新置信度
        if c.confidence > group.max_confidence:
            group.max_confidence = c.confidence

        # 记录图纸名
        sheet_name = sheets.get(eo.sheet_id, "")
        if sheet_name and sheet_name not in group.sheet_names:
            group.sheet_names.append(sheet_name)

    # 计算每个组的平均置信度和相似度
    for group in block_groups.values():
        if group.candidates:
            group.avg_confidence = sum(c.confidence for c in group.candidates) / len(group.candidates)

        # 找到最佳匹配的 BOQ 条目（置信度最高的）
        best_cand = max(group.candidates, key=lambda c: c.confidence, default=None)
        if best_cand and best_cand.boq_item_id in boq_items:
            best_boq = boq_items[best_cand.boq_item_id]
            group.best_boq_item = best_boq

            # 计算块名与 BOQ 描述的相似度
            if group.block_name and best_boq.description:
                group.similarity_score = calculate_name_similarity(
                    group.block_name, best_boq.description)

    # 排序：相似度 > 最高置信度 > 总数
    sorted_groups = sorted(
        block_groups.values(),
        key=lambda g: (-g.similarity_score, -g.max_confidence, -g.total_count)
    )

    return sorted_groups[:limit]


def get_aggregated_summary(groups: list[AggregatedCandidate]) -> dict:
    """获取聚合摘要统计。"""
    total_candidates = sum(len(g.candidates) for g in groups)
    total_blocks = len(groups)
    high_sim_count = sum(1 for g in groups if g.similarity_score >= 0.7)
    high_conf_count = sum(1 for g in groups if g.max_confidence >= 0.9)

    return {
        "total_blocks": total_blocks,
        "total_candidates": total_candidates,
        "high_similarity_blocks": high_sim_count,
        "high_confidence_blocks": high_conf_count,
        "avg_similarity": sum(g.similarity_score for g in groups) / max(1, len(groups)),
        "avg_confidence": sum(g.avg_confidence for g in groups) / max(1, len(groups)),
    }


def filter_groups_by_similarity(
    groups: list[AggregatedCandidate],
    min_similarity: float = 0.5
) -> list[AggregatedCandidate]:
    """过滤相似度低于阈值的组。"""
    return [g for g in groups if g.similarity_score >= min_similarity]


def get_top_candidates_per_group(
    groups: list[AggregatedCandidate],
    top_n: int = 3
) -> list[dict]:
    """获取每个组的前 N 个最佳候选（用于 UI 展示）。"""
    results = []
    for group in groups:
        # 按置信度排序取 top_n
        top_cands = sorted(group.candidates, key=lambda c: -c.confidence)[:top_n]
        results.append({
            "block_name": group.block_name,
            "layer_name": group.layer_name,
            "object_type": group.object_type,
            "total_candidates": len(group.candidates),
            "max_confidence": group.max_confidence,
            "similarity_score": group.similarity_score,
            "best_boq": group.best_boq_item.description if group.best_boq_item else "",
            "top_candidates": top_cands,
            "sheet_names": group.sheet_names,
        })
    return results
