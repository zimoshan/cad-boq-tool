"""LLM 输出 schema 单测（P0）：no_match/review 拒答 + 业务校验。"""
from __future__ import annotations

import unittest

from app.llm.schema import parse_binding_suggestion, BindingSuggestion


class BindingSchemaTest(unittest.TestCase):
    def _parse(self, **fields):
        base = {"selected_boq_id": "A-01", "confidence": 0.9,
                "reason": "r", "needs_review": False, "no_match": False}
        base.update(fields)
        return base

    def test_normal(self):
        s = parse_binding_suggestion(
            '{"selected_boq_id":"A-01","confidence":0.9,"no_match":false}',
            allowed_boq_ids=["A-01"])
        self.assertEqual(s.selected_boq_id, "A-01")
        self.assertFalse(s.no_match)

    def test_no_match_rejects_all(self):
        """"no_match=true + selected=null" 是合法拒答（跳过候选集校验）"""
        js = '{"selected_boq_id":null,"confidence":0.1,"needs_review":true,' \
             '"no_match":true,"alternative_boq_ids":[]}'
        s = parse_binding_suggestion(js, allowed_boq_ids=["A-01", "B-02"])
        self.assertTrue(s.no_match)
        self.assertIsNone(s.selected_boq_id)

    def test_no_match_with_selected_invalid(self):
        """no_match=true 却还给出 selected/备选 → 拒绝"""
        js = '{"selected_boq_id":"A-01","confidence":0.1,"no_match":true,"alternative_boq_ids":["B-02"]}'
        with self.assertRaises(Exception):
            parse_binding_suggestion(js, allowed_boq_ids=["A-01", "B-02"])

    def test_selected_not_in_allowed_rejected(self):
        """selected 不在候选集 → 拒绝（no_match=false 时）"""
        js = '{"selected_boq_id":"Z-99","confidence":0.9,"no_match":false}'
        with self.assertRaises(Exception) as ctx:
            parse_binding_suggestion(js, allowed_boq_ids=["A-01"])
        self.assertIn("不在候选集", str(ctx.exception))

    def test_needs_review_is_optional_flag(self):
        """needs_review 是可选标记（默认 False，模型显式置 True）"""
        s = parse_binding_suggestion(
            '{"selected_boq_id":"A-01","confidence":0.6,"needs_review":true}',
            allowed_boq_ids=["A-01"])
        self.assertTrue(s.needs_review)
        s2 = parse_binding_suggestion(
            '{"selected_boq_id":"A-01","confidence":0.9}', allowed_boq_ids=["A-01"])
        self.assertFalse(s2.needs_review)

    def test_selected_or_no_match_helper(self):
        self.assertTrue(BindingSuggestion(
            no_match=True, selected_boq_id=None, confidence=0.1).selected_or_no_match())
        self.assertFalse(BindingSuggestion(
            no_match=True, selected_boq_id="A-01", confidence=0.1).selected_or_no_match())
        self.assertTrue(BindingSuggestion(
            no_match=False, selected_boq_id="A-01", confidence=0.9).selected_or_no_match())
        self.assertFalse(BindingSuggestion(
            no_match=False, confidence=0.9).selected_or_no_match())


if __name__ == "__main__":
    unittest.main()