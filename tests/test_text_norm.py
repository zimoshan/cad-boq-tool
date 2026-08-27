"""字段规范化单测（P1）：全角/半角、大小写、规格隔符归一、substring 容差。"""
from __future__ import annotations

import unittest

from app.binding.text_norm import (to_halfwidth, compact, normalize,
                                   boq_searchable, contains_spec)


class _Item:
    def __init__(self, code, desc, unit):
        self.code = code
        self.description = desc
        self.unit = unit


class TextNormTest(unittest.TestCase):
    def test_halfwidth(self):
        self.assertEqual(to_halfwidth("４ＭＰ１９"), "4MP19")
        self.assertEqual(to_halfwidth("ｆｕｒｎ．ｄ"), "furn.d")
        self.assertEqual(to_halfwidth("ａ　ｂ"), "a b")

    def test_compact(self):
        self.assertEqual(compact("4 MP"), "4MP")
        self.assertEqual(compact("4-MP"), "4MP")
        self.assertEqual(compact("DN 100"), "DN100")
        self.assertEqual(compact("2 x 1.5 mm2"), "2X15MM2")
        self.assertEqual(compact(""), "")

    def test_normalize(self):
        self.assertEqual(normalize("ｃａｍ　ｄｏｍｅ"), "CAM DOME")

    def test_boq_searchable_has_compact_suffix(self):
        s = boq_searchable(_Item("A-01", "CCTV CAMERA 4 MP", "EA"))
        self.assertIn("A-01 CCTV CAMERA 4 MP EA", s)
        self.assertIn("@@", s)
        self.assertIn("CCTVCAMERA4MPEA", s)

    def test_contains_spec_spacing_tolerance(self):
        # BOQ 文本里 4 MP（带空格），spec 4MP → 命中
        full = boq_searchable(_Item("A-01", "CCTV CAMERA 4 MP", "EA"))
        self.assertTrue(contains_spec(full, "4MP"))
        self.assertTrue(contains_spec(full, "4 MP"))
        # DN100 vs DN 100
        full2 = boq_searchable(_Item("P-02", "PIPE DN100", "M"))
        self.assertTrue(contains_spec(full2, "DN 100"))

    def test_contains_spec_negative(self):
        full = boq_searchable(_Item("A-01", "CCTV CAMERA", "EA"))
        self.assertFalse(contains_spec(full, "4MP"))
        self.assertFalse(contains_spec("", "4MP"))
        self.assertFalse(contains_spec(full, ""))

    def test_halfwidth_noop_on_ascii(self):
        self.assertEqual(to_halfwidth("CAM-4MP"), "CAM-4MP")


if __name__ == "__main__":
    unittest.main()