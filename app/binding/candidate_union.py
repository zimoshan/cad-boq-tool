"""v1.0 §18 Candidate Union 5 层 + 去重 + Top N 召回

推荐形成 Candidate Union：
    Historical
    + Rule
    + Embedding
    + Lexical  ← P0-33 新增
    ↓
    去重
    ↓
    Top 15~30
    ↓
    Qwen Top 5

不要过早硬截断（v1.0 §18）
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def union_candidates(
    historical: list[dict[str, Any]],
    rule: list[dict[str, Any]],
    embedding: list[dict[str, Any]],
    lexical: list[dict[str, Any]],
    top_n: int = 30,
) -> list[dict[str, Any]]:
    """v1.0 §18 5 层 union + 去重（按 boq_item_id 合并，score 取最高 + 来源标记）

    每层输入元素形如：{boq_item_id, score, source, ...}
    """
    by_boq: dict[int, dict[str, Any]] = {}

    for src_name, items in [
        ("historical", historical),
        ("rule", rule),
        ("embedding", embedding),
        ("lexical", lexical),
    ]:
        for item in items:
            boq_id = item.get("boq_item_id")
            if boq_id is None:
                continue
            score = item.get("score", 0.0) or 0.0
            existing = by_boq.get(boq_id)
            if existing is None or score > existing.get("score", 0):
                merged = dict(item)
                merged["source"] = src_name
                by_boq[boq_id] = merged

    # 排序：按 score 降序，截 top_n（v1.0 §18 保留 15-30）
    sorted_candidates = sorted(
        by_boq.values(), key=lambda c: c.get("score", 0), reverse=True
    )
    return sorted_candidates[:top_n]


def lexical_layer(
    engineering_object_text: str,
    boq_items: list[dict[str, Any]],
    top_n: int = 15,
) -> list[dict[str, Any]]:
    """P0-33 新增 Lexical 层：spec/description 关键词 TF-IDF 风格匹配

    engineering_object_text: EO 的 description + spec 拼接
    boq_items: [{id, code, description, spec, ...}]
    返回：[{boq_item_id, score, source='lexical'}]
    """
    if not engineering_object_text or not boq_items:
        return []
    eo_tokens = set(engineering_object_text.lower().split())
    if not eo_tokens:
        return []

    scored: list[dict[str, Any]] = []
    for boq in boq_items:
        boq_text = " ".join([
            str(boq.get("description", "")),
            str(boq.get("spec", "")),
            str(boq.get("code", "")),
        ]).lower()
        boq_tokens = set(boq_text.split())
        if not boq_tokens:
            continue
        # Jaccard 相似度
        intersection = eo_tokens & boq_tokens
        union = eo_tokens | boq_tokens
        score = len(intersection) / len(union) if union else 0.0
        if score > 0:
            scored.append({
                "boq_item_id": boq.get("id"),
                "score": score,
                "source": "lexical",
            })

    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_n]
