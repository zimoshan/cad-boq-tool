"""Takability 6 状态判定测试（P1-1）"""
from __future__ import annotations

from app.boq.writeback import (
    BLACKLIST_DRAWING_TYPES,
    Takability,
    classify_takability,
)


class TestClassifyTakability:
    """classify_takability 6 状态判定（v2.0 §2.5）"""

    def test_no_mapping_returns_no_drawing(self):
        assert classify_takability(1, 0) == Takability.NO_DRAWING

    def test_few_mappings_returns_measurable(self):
        assert classify_takability(1, 1) == Takability.MEASURABLE
        assert classify_takability(1, 2) == Takability.MEASURABLE

    def test_many_mappings_returns_group_only(self):
        assert classify_takability(1, 3) == Takability.GROUP_ONLY
        assert classify_takability(1, 10) == Takability.GROUP_ONLY

    def test_provisional_flag_takes_priority(self):
        """PROVISIONAL 优先级最高（人工标注）"""
        assert classify_takability(1, 5, sheet_drawing_types=["plan"], has_provisional_flag=True) == Takability.PROVISIONAL
        assert classify_takability(1, 0, has_provisional_flag=True) == Takability.PROVISIONAL

    def test_blacklist_drawing_type_returns_not_measurable(self):
        """任意 sheet drawing_type 在黑名单 → NOT_MEASURABLE"""
        for dt in BLACKLIST_DRAWING_TYPES:
            assert classify_takability(1, 2, sheet_drawing_types=[dt]) == Takability.NOT_MEASURABLE
        assert classify_takability(1, 1, sheet_drawing_types=["plan", "detail"]) == Takability.NOT_MEASURABLE

    def test_version_conflict_when_drawing_types_differ(self):
        """跨图 drawing_type 不一致 → VERSION_CONFLICT"""
        assert classify_takability(1, 2, sheet_drawing_types=["plan", "schematic"]) == Takability.VERSION_CONFLICT
        assert classify_takability(1, 4, sheet_drawing_types=["plan", "schematic", "plan"]) == Takability.VERSION_CONFLICT

    def test_priority_order_provisional_over_blacklist(self):
        """PROVISIONAL > 黑名单 > 版本冲突 > count"""
        # 即使黑名单命中，PROVISIONAL 优先
        assert classify_takability(1, 1, sheet_drawing_types=["detail"], has_provisional_flag=True) == Takability.PROVISIONAL

    def test_priority_order_blacklist_over_count(self):
        """黑名单 > count（即使 mapping 多也是 NOT_MEASURABLE）"""
        assert classify_takability(1, 10, sheet_drawing_types=["legend"]) == Takability.NOT_MEASURABLE

    def test_priority_order_version_conflict_over_count(self):
        """版本冲突 > count"""
        assert classify_takability(1, 10, sheet_drawing_types=["plan", "schematic"]) == Takability.VERSION_CONFLICT

    def test_empty_drawing_types_falls_through_to_count(self):
        """sheet_drawing_types=None 或 [] 走 count 路径"""
        assert classify_takability(1, 1, sheet_drawing_types=None) == Takability.MEASURABLE
        assert classify_takability(1, 1, sheet_drawing_types=[]) == Takability.MEASURABLE

    def test_blacklist_keywords(self):
        """黑名单 drawing_type 集合正确"""
        assert BLACKLIST_DRAWING_TYPES == ("detail", "legend", "schedule")
