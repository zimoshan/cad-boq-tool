"""P0-2: Refusal 策略单元测试 —— no_match 结构化拒绝原因

验收标准：
1. BOQ 为空 → code=BOQ_EMPTY
2. EO 无文本 → code=EO_NO_TEXT
3. 关键词无交集 → code=NO_KEYWORD
4. 正常有交集 → code=UNKNOWN（兜底）
5. _log_refusal 正确追加到 stats['refusals']
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


class TestDiagnoseNoMatch:
    """_diagnose_no_match 返回正确的拒绝原因码"""

    def _make_eo(self, block_name="FAN-01", layer_name="E-Lighting", tag="Fan"):
        eo = SimpleNamespace(
            id=42,
            block_name=block_name,
            layer_name=layer_name,
            tag=tag,
        )
        return eo

    @patch("app.binding.matcher.enriched_eo_text", return_value="")
    def test_boq_empty(self, _mock_eo_text):
        from app.binding.matcher import _diagnose_no_match

        eo = self._make_eo()
        result = _diagnose_no_match(project_id=1, eo=eo, boq_items=[])
        assert result["code"] == "BOQ_EMPTY"
        assert "无 BOQ" in result["reason"]

    @patch("app.binding.matcher.enriched_eo_text", return_value="")
    def test_eo_no_text(self, _mock_eo_text):
        from app.binding.matcher import _diagnose_no_match

        eo = self._make_eo(block_name="", layer_name="", tag="")
        fake_boq = [SimpleNamespace(id=1, code="BOQ-001", description="风扇")]
        result = _diagnose_no_match(project_id=1, eo=eo, boq_items=fake_boq)
        # EO 无文本时即使 boq 非空也返回 EO_NO_TEXT（先于关键词检查）
        assert result["code"] == "EO_NO_TEXT"
        assert "block_name=" in result["detail"]

    @patch("app.binding.matcher.boq_searchable", return_value="完全无关文本XYZ")
    @patch("app.binding.matcher.enriched_eo_text", return_value="FAN 通风设备")
    def test_no_keyword(self, _mock_eo_text, _mock_boq_search):
        from app.binding.matcher import _diagnose_no_match

        eo = self._make_eo()
        fake_boq = [SimpleNamespace(id=1, code="BOQ-001", description="无关")]
        result = _diagnose_no_match(project_id=1, eo=eo, boq_items=fake_boq)
        assert result["code"] == "NO_KEYWORD"
        assert "关键词" in result["reason"]

    @patch("app.binding.matcher.boq_searchable", return_value="FAN 通风 风扇")
    @patch("app.binding.matcher.enriched_eo_text", return_value="FAN 通风设备")
    def test_has_keyword(self, _mock_eo_text, _mock_boq_search):
        from app.binding.matcher import _diagnose_no_match

        eo = self._make_eo()
        fake_boq = [SimpleNamespace(id=1, code="BOQ-001", description="FAN 风扇")]
        result = _diagnose_no_match(project_id=1, eo=eo, boq_items=fake_boq)
        # 有交集 → UNKNOWN（兜底，不是真正的 no_match）
        assert result["code"] == "UNKNOWN"

    @patch("app.binding.matcher.boq_searchable", return_value="完全无关文本XYZ")
    @patch("app.binding.matcher.enriched_eo_text", return_value="FAN 通风设备")
    def test_no_keyword_multiple_boq(self, _mock_eo_text, _mock_boq_search):
        """多条 BOQ 均无交集"""
        from app.binding.matcher import _diagnose_no_match

        eo = self._make_eo()
        fake_boq = [
            SimpleNamespace(id=1, code="BOQ-001", description="无关A"),
            SimpleNamespace(id=2, code="BOQ-002", description="无关B"),
        ]
        result = _diagnose_no_match(project_id=1, eo=eo, boq_items=fake_boq)
        assert result["code"] == "NO_KEYWORD"
        assert "2 条 BOQ" in result["detail"]


class TestLogRefusal:
    """_log_refusal 正确追加记录到 stats['refusals']"""

    def test_appends_to_stats(self):
        from app.binding.matcher import _log_refusal

        eo = SimpleNamespace(id=42, tag="Fan", block_name="FAN-01", layer_name="E-Light")
        stats: dict = {}
        diagnosis = {"code": "BOQ_EMPTY", "reason": "无 BOQ", "detail": "空"}
        _log_refusal(stats, eo, diagnosis)

        assert "refusals" in stats
        assert len(stats["refusals"]) == 1
        r = stats["refusals"][0]
        assert r["eo_id"] == 42
        assert r["code"] == "BOQ_EMPTY"
        assert r["eo_tag"] == "Fan"

    def test_multiple_appends(self):
        from app.binding.matcher import _log_refusal

        stats: dict = {}
        for i in range(3):
            eo = SimpleNamespace(id=i, tag=f"EO-{i}", block_name=f"B-{i}", layer_name=f"L-{i}")
            _log_refusal(stats, eo, {"code": "UNKNOWN", "reason": "test", "detail": ""})
        assert len(stats["refusals"]) == 3
        assert stats["refusals"][2]["eo_id"] == 2
