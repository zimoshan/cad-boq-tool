"""v1.0 §18/§20/§22 测试：Candidate Union + Confidence Calibration + 几何优化"""
from __future__ import annotations

import math

import pytest

from app.binding.candidate_union import union_candidates, lexical_layer
from app.binding.calibration import CalibrationInput, calibrate
from app.cad.geometry_optimizer import (
    hatch_polygon_area,
    parallel_line_centerline,
    spline_arc_length,
)


class TestCandidateUnion:
    """v1.0 §18 5 层 union + 去重"""

    def test_union_dedup_by_boq_id(self):
        historical = [{"boq_item_id": 1, "score": 0.9}, {"boq_item_id": 2, "score": 0.8}]
        rule = [{"boq_item_id": 1, "score": 0.7}, {"boq_item_id": 3, "score": 0.6}]
        embedding = [{"boq_item_id": 2, "score": 0.95}, {"boq_item_id": 3, "score": 0.5}]
        lexical = [{"boq_item_id": 1, "score": 0.4}, {"boq_item_id": 4, "score": 0.3}]

        result = union_candidates(historical, rule, embedding, lexical, top_n=10)
        ids = [c["boq_item_id"] for c in result]
        # 4 个不同 boq_id
        assert set(ids) == {1, 2, 3, 4}
        # top1 应该是 score 最高的 boq=2 (embedding 0.95)
        top1 = result[0]
        assert top1["boq_item_id"] == 2
        assert top1["score"] == 0.95
        assert top1["source"] == "embedding"
        # boq=1 (historical 0.9) 应为 top2
        second = result[1]
        assert second["boq_item_id"] == 1
        assert second["score"] == 0.9
        assert second["source"] == "historical"

    def test_union_top_n_truncation(self):
        items = [{"boq_item_id": i, "score": 1.0 - i * 0.1} for i in range(50)]
        result = union_candidates([], [], items, [], top_n=10)
        assert len(result) == 10

    def test_union_empty_inputs(self):
        result = union_candidates([], [], [], [], top_n=10)
        assert result == []


class TestLexicalLayer:
    """P0-33 新增 Lexical 层"""

    def test_lexical_jaccard_match(self):
        boq_items = [
            {"id": 1, "description": "4MP Dome Camera", "spec": "", "code": "r1"},
            {"id": 2, "description": "Speaker", "spec": "", "code": "r2"},
            {"id": 3, "description": "Cable Tray", "spec": "", "code": "r3"},
        ]
        result = lexical_layer("4MP Dome Camera CCTV", boq_items, top_n=5)
        assert result[0]["boq_item_id"] == 1  # 最高 Jaccard
        assert result[0]["source"] == "lexical"
        assert result[0]["score"] > 0

    def test_lexical_no_match(self):
        boq_items = [{"id": 1, "description": "完全无关内容", "spec": "", "code": "x"}]
        result = lexical_layer("4MP Dome Camera", boq_items, top_n=5)
        # Jaccard 很低，但仍可能 > 0
        if result:
            assert result[0]["score"] < 0.5

    def test_lexical_empty_text(self):
        result = lexical_layer("", [{"id": 1, "description": "x"}], top_n=5)
        assert result == []


class TestConfidenceCalibration:
    """v1.0 §20 5 维综合"""

    def test_high_all_dimensions(self):
        inp = CalibrationInput(
            llm_confidence=0.9, rule_score=0.8, embedding_similarity=0.85,
            spec_match_score=1.0, historical_accuracy=0.95, top1_top2_margin=0.7,
            has_conflict=False,
        )
        r = calibrate(inp)
        assert r["final_confidence"] > 0.8
        assert r["needs_review"] is False

    def test_conflict_penalty(self):
        inp = CalibrationInput(
            llm_confidence=0.9, rule_score=0.9, embedding_similarity=0.9,
            spec_match_score=0.0, historical_accuracy=0.9, top1_top2_margin=0.9,
            has_conflict=True,  # 关键参数冲突
        )
        r_conflict = calibrate(inp)
        inp_no_conflict = CalibrationInput(
            llm_confidence=0.9, rule_score=0.9, embedding_similarity=0.9,
            spec_match_score=0.0, historical_accuracy=0.9, top1_top2_margin=0.9,
            has_conflict=False,
        )
        r_no = calibrate(inp_no_conflict)
        # 冲突抑制：conflict 分数 < no_conflict
        assert r_conflict["final_confidence"] < r_no["final_confidence"]
        assert r_conflict["needs_review"] is True
        assert r_no["needs_review"] is False

    def test_low_score_triggers_review(self):
        inp = CalibrationInput(llm_confidence=0.3, rule_score=0.3, embedding_similarity=0.3)
        r = calibrate(inp)
        assert r["needs_review"] is True


class TestGeometryOptimizer:
    """v1.0 §22 几何优化"""

    def test_spline_arc_length_cubic(self):
        """3 次 Bezier 4 控制点：直线 → 弧长 = 直线长"""
        length = spline_arc_length([(0, 0), (1, 0), (2, 0), (3, 0)], iterations=3)
        assert abs(length - 3.0) < 0.01

    def test_spline_arc_length_curve(self):
        """曲线弧长 > 控制点首尾距离"""
        length = spline_arc_length([(0, 0), (1, 1), (2, 1), (3, 0)], iterations=3)
        chord = math.hypot(3 - 0, 0 - 0)
        assert length > chord

    def test_spline_fallback_for_non_4_points(self):
        length = spline_arc_length([(0, 0), (1, 0), (2, 0)], iterations=3)
        assert abs(length - 2.0) < 0.01  # 退化为折线长度

    def test_parallel_line_centerline(self):
        """2 条平行线 → 中心线"""
        line1 = ((0, 0), (10, 0))           # 水平 1
        line2 = ((0, 10), (10, 10))          # 水平 2（上方 10）
        result = parallel_line_centerline(line1, line2)
        assert result is not None
        # 中心线应在 y=5
        assert abs(result[0][1] - 5.0) < 0.5
        assert abs(result[1][1] - 5.0) < 0.5

    def test_parallel_line_non_parallel(self):
        """非平行线 → None"""
        line1 = ((0, 0), (10, 0))
        line2 = ((0, 0), (5, 10))  # 斜线
        result = parallel_line_centerline(line1, line2)
        assert result is None

    def test_hatch_polygon_area_simple(self):
        """单环多边形：4x4 矩形 → 16"""
        area = hatch_polygon_area([[(0, 0), (4, 0), (4, 4), (0, 4)]])
        assert abs(area - 16.0) < 0.01

    def test_hatch_polygon_with_hole(self):
        """外环 6x6=36，内环 2x2=4 孔洞 → 32"""
        outer = [(0, 0), (6, 0), (6, 6), (0, 6)]
        hole = [(2, 2), (4, 2), (4, 4), (2, 4)]
        area = hatch_polygon_area([outer, hole])
        assert abs(area - 32.0) < 0.5

    def test_hatch_polygon_empty(self):
        assert hatch_polygon_area([]) == 0.0
        assert hatch_polygon_area([[]]) == 0.0
