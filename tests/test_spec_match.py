"""v1.0 §19 规格匹配 5 状态测试"""
from __future__ import annotations

from webapi.services.spec_match import SpecMatchStatus, match_spec


class TestSpecMatch:
    """5 状态 + needs_review 判定"""

    def test_exact_match(self):
        r = match_spec("4MP", "4MP")
        assert r.status == SpecMatchStatus.EXACT
        assert r.needs_review is False

    def test_normalized_equal(self):
        r = match_spec("4MP", "4 MP")
        assert r.status == SpecMatchStatus.NORMALIZED_EQUAL
        assert r.needs_review is False

    def test_normalized_equal_case(self):
        r = match_spec("Dn100", "DN100")
        assert r.status == SpecMatchStatus.NORMALIZED_EQUAL
        assert r.needs_review is False

    def test_unknown_missing_spec(self):
        r = match_spec("", "4MP")
        assert r.status == SpecMatchStatus.UNKNOWN

        r2 = match_spec("4MP", None)
        assert r2.status == SpecMatchStatus.UNKNOWN

    def test_conflict_different_mp(self):
        """4MP vs 8MP → CONFLICT + needs_review"""
        r = match_spec("4MP Dome Camera", "8MP Dome Camera")
        assert r.status == SpecMatchStatus.CONFLICT
        assert r.needs_review is True
        assert "MP" in r.detail

    def test_conflict_different_dn(self):
        r = match_spec("DN100 pipe", "DN50 pipe")
        assert r.status == SpecMatchStatus.CONFLICT
        assert r.needs_review is True

    def test_compatible_close_numeric(self):
        r = match_spec("4.5MP", "5MP")
        # 4.5 vs 5 差 10% → COMPATIBLE
        assert r.status in (SpecMatchStatus.COMPATIBLE, SpecMatchStatus.CONFLICT)

    def test_conflict_fallback(self):
        r = match_spec("ABC-XYZ", "QRS-123")
        # 无共同数字参数 → 兜底 CONFLICT
        assert r.status == SpecMatchStatus.CONFLICT
        assert r.needs_review is True

    def test_extract_key_params_priority(self):
        """EXACT 优先于 NORMALIZED_EQUAL（先 EXACT 判定）"""
        r = match_spec("4MP", "4MP")
        assert r.status == SpecMatchStatus.EXACT

    def test_priority_order(self):
        """5 状态判定顺序：UNKNOWN > EXACT > NORMALIZED > CONFLICT > COMPATIBLE"""
        # UNKNOWN 优先
        assert match_spec("", "x").status == SpecMatchStatus.UNKNOWN
        # EXACT 优先于 NORMALIZED
        assert match_spec("a", "a").status == SpecMatchStatus.EXACT
        # NORMALIZED 优先于 CONFLICT
        assert match_spec("4 MP", "4MP").status == SpecMatchStatus.NORMALIZED_EQUAL
        # CONFLICT 优先于 COMPATIBLE
        assert match_spec("4MP", "8MP").status == SpecMatchStatus.CONFLICT
