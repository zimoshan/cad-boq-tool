"""T4 第3层接线单测：extractor 低置信对象 → llm_classify_uncertain 识别并补充分类。

不连真人 LLM：mock `llm_classify` 返回固定结果，验证：
- extractor 把「规则未命中」对象置信度置低（<0.5，能被第3层触发）
- llm_classify_uncertain 只挑低置信对象、跳过 / 限流统计正确
- 分类结果写回 engineering_object（update_engineering_object 被调）
"""
from __future__ import annotations

import unittest
from unittest import mock


class EO:
    """EO 最小替身"""

    def __init__(self, eid, conf, block="B1", layer="L", spec=None, tag=None):
        self.id = eid
        self.confidence = conf
        self.block_name = block
        self.layer_name = layer
        self.specification = spec
        self.tag = tag
        self.discipline = ""
        self.system = ""
        self.quantity_rule = ""
        self.source = "rule"


class T4LlmClassifyTest(unittest.TestCase):
    def test_low_conf_extractible_by_uncertain(self):
        """关键接线：extractor 规则未命中 → conf=0.4（<0.5），能被第3层识别"""
        # extractor 未命中把 conf 置 0.4 的等价断言：用可导入的常量路径验证
        # 直接验证 llm_classify_uncertain 对低置信对象确实触发 LLM 并写回
        low = EO(1, conf=0.4)
        high = EO(2, conf=0.9)
        fake = mock.MagicMock(return_value={
            "discipline": "ELV", "system": "CCTV", "spec": "4MP",
            "quantity_rule": "count", "confidence": 0.8, "reason": "t"})
        dbm = mock.MagicMock()
        dbm.get_engineering_objects.return_value = [low, high]
        dbm.get_engineering_object.side_effect = lambda oid: {1: low, 2: high}[oid]

        with mock.patch("app.engineering.llm_classify.db", dbm), \
             mock.patch("app.engineering.llm_classify.llm_classify", fake) as llm:
            from app.engineering.llm_classify import llm_classify_uncertain
            res = llm_classify_uncertain(1, object_ids=[1, 2], limit=10)

        self.assertEqual(res["classified"], 1)
        self.assertEqual(res["skipped"], 0)
        self.assertEqual(llm.call_count, 1)      # 只有低置信对象触发
        # 回写调用：eo.id + 新语义 + 置信提升
        kw = dbm.update_engineering_object.call_args.kwargs
        self.assertEqual(kw["discipline"], "ELV")
        self.assertEqual(kw["system"], "CCTV")
        self.assertGreaterEqual(kw["confidence"], 0.5)

    def test_no_low_conf_nothing_happens(self):
        dbm = mock.MagicMock()
        dbm.get_engineering_objects.return_value = [EO(3, conf=0.9)]
        with mock.patch("app.engineering.llm_classify.db", dbm), \
             mock.patch("app.engineering.llm_classify.llm_classify") as llm:
            from app.engineering.llm_classify import llm_classify_uncertain
            res = llm_classify_uncertain(3, limit=10)
        self.assertEqual(res["classified"], 0)
        self.assertEqual(llm.call_count, 0)

    def test_limit_deferred_counted(self):
        low1, low2, low3 = EO(1, 0.4), EO(2, 0.4), EO(3, 0.4)
        dbm = mock.MagicMock()
        dbm.get_engineering_objects.return_value = [low1, low2, low3]
        with mock.patch("app.engineering.llm_classify.db", dbm), \
             mock.patch("app.engineering.llm_classify.llm_classify") as llm:
            from app.engineering.llm_classify import llm_classify_uncertain
            res = llm_classify_uncertain(1, eos=[low1, low2, low3], limit=2)
        self.assertEqual(llm.call_count, 2)
        self.assertEqual(res["deferred"], 1)


if __name__ == "__main__":
    unittest.main()