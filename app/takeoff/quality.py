"""质量检测 + 跨图去重（23-4）。"""
from __future__ import annotations

from typing import List, Dict, Tuple

from .orchestrator import TakeoffItem


def reconcile_across_files(items: List[TakeoffItem]) -> List[TakeoffItem]:
    """跨图/跨层去重：相同 code+unit 合并为 1 条（数值累加）"""
    merged: Dict[Tuple[str, str], TakeoffItem] = {}
    for it in items:
        key = (it.code, it.unit)
        if key in merged:
            ex = merged[key]
            # 数值累加
            ex.quantity = ex.quantity + it.quantity
            # 置信度取低
            ex.confidence = min(ex.confidence, it.confidence)
            ex.reasoning += f" | 合并: {it.reasoning}"
        else:
            merged[key] = it
    return list(merged.values())


def detect_conflicts(items: List[TakeoffItem], threshold: float = 0.10) -> List[TakeoffItem]:
    """检测同 code+unit 但数值差异 > threshold 的冲突项，标记 conflict=True

    Args:
        items: TakeoffItem 列表
        threshold: 差异阈值（默认 10%）

    Returns:
        标记后的 items（新增 .raw['_conflict'] 字段）
    """
    # 按 code+unit 分组
    groups: Dict[Tuple[str, str], List[TakeoffItem]] = {}
    for it in items:
        key = (it.code, it.unit)
        groups.setdefault(key, []).append(it)

    for grp_items in groups.values():
        if len(grp_items) < 2:
            continue
        # 计算平均
        avg = sum(i.quantity for i in grp_items) / len(grp_items)
        for it in grp_items:
            if avg > 0:
                diff = abs(it.quantity - avg) / avg
                if diff > threshold:
                    it.raw["_conflict"] = True
                    it.raw["_conflict_avg"] = round(avg, 2)
                    it.raw["_conflict_diff"] = round(diff * 100, 1)
                    it.confidence = min(it.confidence, 0.5)  # 冲突降权
    return items
