"""app 层关键模块单测（boq_parser / cross_sheet_dedup / llm runner/schema）"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# app/boq/boq_parser.py（P0-6 B1 改后无单测，补）
# ============================================================


def _make_xlsx(rows: list[list]) -> str:
    """写 xlsx 到 temp 目录，返回路径（调用方负责清理）"""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "test_boq.xlsx")
    wb.save(path)
    wb.close()
    return path, tmpdir


class TestBoqParserB1:
    """B1 4 种 BOQ 表头识别 + B2 6 字段填充"""

    def test_header_row_detection_electrical_row1(self):
        """BOQ-001 Rev1：表头 row 1（Item / Description / Unit）"""
        path, tmpdir = _make_xlsx([
            ["Item", "Description", "Unit", "Qty", "Rate", "Amount"],
            ["r1", "4MP Dome Camera", "No.", 10, 100, 1000],
        ])
        try:
            from app.boq.boq_parser import parse_boq
            items, mapping = parse_boq(path)
            assert len(items) == 1
            assert items[0].code == "r1"
            assert "Dome Camera" in items[0].description
            assert items[0].unit == "No."
            # B2 新字段
            assert items[0].item_key == "r1"
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_header_row_detection_electrical_row11(self):
        """BOQ-001 原版：表头 row 11（前 10 行合同声明）"""
        rows = []
        for i in range(10):
            rows.append([f"Contract clause {i}", "Quantities are taken from drawings", "Contractor", "", "", ""])
        rows.append(["Item", "Description", "Unit", "Bill qty", "Installed", "Qty remaining"])
        rows.append(["r1", "Cable", "m", 100, 50, 50])
        path, tmpdir = _make_xlsx(rows)
        try:
            from app.boq.boq_parser import parse_boq
            items, _ = parse_boq(path)
            assert len(items) == 1
            assert items[0].item_key == "r1"
            assert items[0].unit == "m"
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_item_key_extraction(self):
        from app.boq.boq_parser import _extract_item_key
        assert _extract_item_key("r123") == "r123"
        assert _extract_item_key("M-r5") == "M-r5"
        assert _extract_item_key("S-r1") == "S-r1"
        assert _extract_item_key("A-r12") == "A-r12"
        assert _extract_item_key("item-1") == ""  # 不匹配 rNNN 模式

    def test_section_detection(self):
        """B2 _detect_section：reverse 取前 3 行内第一个含 KW 的（最右）"""
        from app.boq.boq_parser import _detect_section
        # prev: 3 行；reverse 顺序 → POWER / CABLE / CONDUIT
        # _detect_section 取 reversed 第 1 个含 KW 的 → "POWER"
        prev = [("CONDUIT",), ("CABLE - LIGHTING",), ("POWER",)]
        section = _detect_section(prev, ("r1", "Cable", "m"))
        assert "POWER" in section  # reverse 后第 1 个含 KW 的

        # 边界：3 行全无 KW
        section2 = _detect_section([("foo",), ("bar",), ("baz",)], ("r1", "x", "m"))
        assert section2 == ""

    def test_parse_boq_empty_file(self):
        from openpyxl import Workbook
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "empty.xlsx")
        wb = Workbook()
        wb.save(path)
        wb.close()
        try:
            from app.boq.boq_parser import parse_boq
            items, mapping = parse_boq(path)
            assert items == []
            assert mapping == {}
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================
# app/engineering/cross_sheet_dedup.py
# ============================================================


class TestCrossSheetDedup:
    """B5 S5 跨图去重并集"""

    def test_bbox_overlap_full(self):
        from app.engineering.cross_sheet_dedup import _bbox_overlap_ratio
        ratio = _bbox_overlap_ratio((0, 0, 10, 10), (0, 0, 10, 10))
        assert ratio == 1.0

    def test_bbox_overlap_contains(self):
        """(0,0,10,10) vs (5,5,15,15)：重叠 5x5=25 / min(100, 100)=100 = 0.25"""
        from app.engineering.cross_sheet_dedup import _bbox_overlap_ratio
        ratio = _bbox_overlap_ratio((0, 0, 10, 10), (5, 5, 15, 15))
        # 实际是部分重叠（5x5=25），不是完全包含
        assert 0.2 < ratio < 0.3

    def test_bbox_overlap_partial_50pct(self):
        """(0,0,10,10) vs (5,0,15,10)：右半重叠 5x10=50 / 小面积 100 = 0.5"""
        from app.engineering.cross_sheet_dedup import _bbox_overlap_ratio
        ratio = _bbox_overlap_ratio((0, 0, 10, 10), (5, 0, 15, 10))
        assert 0.4 < ratio < 0.6

    def test_bbox_overlap_none(self):
        from app.engineering.cross_sheet_dedup import _bbox_overlap_ratio
        ratio = _bbox_overlap_ratio((0, 0, 10, 10), (20, 20, 30, 30))
        assert ratio == 0.0

    def test_bbox_overlap_invalid(self):
        from app.engineering.cross_sheet_dedup import _bbox_overlap_ratio
        assert _bbox_overlap_ratio(None, (0, 0, 10, 10)) == 0.0
        assert _bbox_overlap_ratio((1, 2), (0, 0, 10, 10)) == 0.0
        assert _bbox_overlap_ratio("invalid", (0, 0, 10, 10)) == 0.0

    def test_dedup_engineering_objects_empty(self):
        from app.engineering.cross_sheet_dedup import dedup_engineering_objects
        result = dedup_engineering_objects(project_id=1, eos=[])
        assert result["stats"]["input_eos"] == 0
        assert result["dedup_records"] == []

    def test_dedup_no_duplicate(self):
        """不同 block_name 不会去重"""
        from app.engineering.cross_sheet_dedup import dedup_engineering_objects

        @dataclass
        class FakeEO:
            id: int = 0
            block_name: str = ""
            sheet_id: int = 1
            entity_ids: list = field(default_factory=list)
            confidence: float = 1.0
            bbox: tuple = (0, 0, 10, 10)

        eos = [FakeEO(id=1, block_name="A"), FakeEO(id=2, block_name="B"), FakeEO(id=3, block_name="C")]
        result = dedup_engineering_objects(project_id=1, eos=eos)
        assert result["stats"]["input_eos"] == 3
        assert result["stats"]["merged_eos"] == 0
        assert result["stats"]["dedup_clusters"] == 0


# ============================================================
# app/llm/runner.py
# ============================================================


class TestLlmRunner:
    """Pydantic schema 校验 + retry 逻辑"""

    def _validator(self, raw: str):
        """validator 解析 raw JSON → BindingSuggestion"""
        from app.llm.schema import parse_binding_suggestion
        return parse_binding_suggestion(raw)

    def test_run_llm_with_retry_success(self):
        """成功路径不重试（mock _resolve_backend + _audit_run）"""
        from app.llm import runner as runner_mod
        mock_backend = MagicMock()
        # runner 内部：resp["content"]，所以 backend.chat 返回 dict 而非字符串
        mock_backend.chat.return_value = {
            "content": json.dumps({
                "selected_boq_id": "1", "confidence": 0.9,
                "reason": "match", "no_match": False,
            }),
            "tokens_in": 100, "tokens_out": 50,
        }
        with patch.object(runner_mod, "_resolve_backend", return_value=mock_backend), \
             patch.object(runner_mod, "_audit_run", return_value=1):
            result = runner_mod.run_llm_with_retry(
                project_id=1, task_type="binding",
                system="sys", user="user",
                validator=self._validator,
            )
        assert result["parsed"].selected_boq_id == "1"
        assert mock_backend.chat.call_count == 1

    def test_run_llm_with_retry_recoverable_then_succeed(self):
        """第一次失败 + 第二次成功"""
        from app.llm import runner as runner_mod
        mock_backend = MagicMock()
        mock_backend.chat.side_effect = [
            {"content": "invalid json{{{", "tokens_in": 10, "tokens_out": 5},
            {"content": json.dumps({
                "selected_boq_id": "2", "confidence": 0.7, "no_match": False,
            }), "tokens_in": 100, "tokens_out": 50},
        ]
        with patch.object(runner_mod, "_resolve_backend", return_value=mock_backend), \
             patch.object(runner_mod, "_audit_run", return_value=1):
            result = runner_mod.run_llm_with_retry(
                project_id=1, task_type="binding",
                system="sys", user="user",
                validator=self._validator,
                retries=2,
            )
        assert mock_backend.chat.call_count == 2
        assert result["parsed"].selected_boq_id == "2"

    def test_run_llm_with_retry_all_fail(self):
        """N 次都失败 → 返回 ok=False + error 字段（不抛异常）"""
        from app.llm import runner as runner_mod
        mock_backend = MagicMock()
        mock_backend.chat.return_value = {"content": "always invalid", "tokens_in": 0, "tokens_out": 0}

        with patch.object(runner_mod, "_resolve_backend", return_value=mock_backend), \
             patch.object(runner_mod, "_audit_run", return_value=1):
            result = runner_mod.run_llm_with_retry(
                project_id=1, task_type="binding",
                system="sys", user="user",
                validator=self._validator,
                retries=1,
            )
        assert result["ok"] is False
        assert "error" in result


# ============================================================
# app/llm/schema.py
# ============================================================


class TestLlmSchema:
    """BindingSuggestion / ClassificationResult Pydantic schema"""

    def test_binding_suggestion_valid(self):
        from app.llm.schema import BindingSuggestion
        sug = BindingSuggestion(
            selected_boq_id="1",
            confidence=0.9,
            reason="4MP match",
            needs_review=False,
            no_match=False,
        )
        assert sug.selected_boq_id == "1"
        assert sug.confidence == 0.9
        assert sug.no_match is False

    def test_binding_suggestion_no_match(self):
        from app.llm.schema import BindingSuggestion
        sug = BindingSuggestion(no_match=True, confidence=1.0, reason="none fit")
        assert sug.no_match is True
        assert sug.selected_boq_id is None

    def test_binding_suggestion_confidence_out_of_range(self):
        from app.llm.schema import BindingSuggestion
        with pytest.raises(ValueError):
            BindingSuggestion(confidence=1.5)  # > 1.0

    def test_classification_result_valid(self):
        from app.llm.schema import ClassificationResult
        cr = ClassificationResult(
            discipline="ELV", system="CCTV", spec="4MP",
            quantity_rule="count", confidence=0.9, reason="4MP dome"
        )
        assert cr.discipline == "ELV"
        assert cr.confidence == 0.9

    def test_classification_result_invalid_discipline(self):
        from app.llm.schema import ClassificationResult
        with pytest.raises(ValueError):
            ClassificationResult(discipline="MECHANICAL", confidence=0.9)  # 不在枚举

    def test_parse_classification_valid(self):
        from app.llm.schema import parse_classification
        raw = json.dumps({
            "discipline": "ELV", "system": "CCTV",
            "spec": "4MP", "quantity_rule": "count",
            "confidence": 0.85, "reason": "dome",
        })
        cr = parse_classification(raw)
        assert cr.discipline == "ELV"

    def test_parse_classification_invalid_json(self):
        from app.llm.schema import parse_classification, SchemaError
        with pytest.raises(SchemaError):
            parse_classification("not json")
