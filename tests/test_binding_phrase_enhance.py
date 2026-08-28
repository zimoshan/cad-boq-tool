"""绑定候选增强（2026-08-28 BACKLOG 2.1.1/2.1.2）单测。

- string_similarity：整串归一化相似度（分隔符/大小写/包含/LCS）
- rule_matcher 短语级加权：块名≈清单描述 → 强分 + reason
```
python -m pytest tests/test_binding_name_enhance.py -q
or python -m unittest tests.test_binding_name_enhance -v
```
"""
from __future__ import annotations

import unittest

from app.binding.text_norm import string_similarity, compact
from app.binding import rule_matcher as rm


class SimilarityTest(unittest.TestCase):
    def test_identical_after_normalization(self):
        """分隔符/大小写差异 → 1.0"""
        self.assertEqual(string_similarity("CAM_DOME_4MP", "CAM DOME 4MP"), 1.0)
        self.assertEqual(string_similarity(" LED Panel ", "led-panel"), 1.0)

    def test_containment(self):
        """一方整串包含另一方 → 高分手"""
        sim = string_similarity("FIRE-ALARM-SPEAKER", "Fire Alarm Speaker 10W")
        self.assertGreaterEqual(sim, 0.85)
        # 短 token 只占小部分 → 不触阈值
        self.assertLess(string_similarity("4MP", "CAMERA DOME 4MP ULTRA"), 0.85)

    def test_lcs_fallback(self):
        """词序/删词 → LCS 比例（中等分）"""
        sim = string_similarity("CAMERA DOME", "DOME CAMERA")
        self.assertGreater(sim, 0.0)
        self.assertLess(sim, 1.0)

    def test_empty(self):
        self.assertEqual(string_similarity("", "abc"), 0.0)
        self.assertEqual(string_similarity("abc", ""), 0.0)
        self.assertEqual(string_similarity(None, "abc"), 0.0)


class RulePhraseWeightTest(unittest.TestCase):
    def _eo(self, block="CAM_DOME_4MP", layer="E-CCTV", system="CCTV", spec="4MP"):
        from types import SimpleNamespace
        return SimpleNamespace(block_name=block, layer_name=layer, system=system,
                               specification=spec, discipline=None, project_id=1, tag="")

    def test_phrase_strong_reason(self):
        """块名与描述整串几乎一致 → 强分≥0.6 且 reason 计入短语命中"""
        eo = self._eo(block="FIRE-ALARM-SPEAKER", spec="10W")
        kws = rm.eo_keywords(eo)
        score, hits = rm._score_boq(
            "FA-01 FIRE ALARM SPEAKER 10W 个",
            kws, "FA", "10W",
            ref_names=[eo.block_name], desc_norm="FIRE ALARM SPEAKER 10W")
        self.assertGreaterEqual(score, 0.6)  # 达 RULE_STRONG_MIN，可跳过 LLM
        self.assertTrue(any("块名≈" in h for h in hits))

    def test_unrelated_no_phrase(self):
        eo = self._eo()
        _, hits = rm._score_boq(
            "PS-01 单相插座 16A 个", ["CAM", "DOME"],
            "CCTV", "4MP",
            ref_names=["CAM4MP"], desc_norm="单相插座16A")
        self.assertFalse(any("块名≈" in h for h in hits))

    def test_match_rule_returns_phrase_candidate(self):
        """match_rule 整链路：近似名称成为规则命中且分高"""
        from types import SimpleNamespace
        class Item:
            def __init__(self, i, code, desc, unit):
                self.id, self.code, self.description, self.unit = i, code, desc, unit
        items = [
            Item(1, "CY-01", "CAMERA DOME 4MP 2MPX", "套"),
            Item(2, "PS-01", "单相插座 16A", "个"),
        ]
        eo = SimpleNamespace(block_name="CAMERA_DOME_4MP", layer_name="L-CCTV",
                             system="", specification="", discipline="", project_id=1)
        res = rm.match_rule(1, eo, items=items)
        self.assertTrue(res)
        best = res[0]
        self.assertEqual(best[0], 1)
        self.assertGreaterEqual(best[1], 0.6)
        self.assertIn("块名≈", best[2])


if __name__ == "__main__":
    unittest.main()