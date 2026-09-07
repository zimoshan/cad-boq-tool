"""P6-1 版本冲突 + P6-2 重复计价检测 测试（v2.0 §6.4 四能力 ①②）"""
from __future__ import annotations

from app.binding.duplicate_pricing import build_duplicates
from app.binding.version_gate import _normalize_filename, build_version_report


class TestVersionConflict:
    """P6-1 版本冲突检测（纯逻辑 build_version_report）"""

    def test_stale_old_revision_detected(self):
        """同 filename 多 revision → 旧版 stale、最新保留（验收①）"""
        rows = [
            {"sheet_id": 1, "filename": "AP-01.dxf", "revision": "R1"},
            {"sheet_id": 2, "filename": "AP-01.dxf", "revision": "R2"},
            {"sheet_id": 3, "filename": "AP-01.dxf", "revision": "R3"},
        ]
        r = build_version_report(rows)
        assert r["versioned_groups"] == 1
        stale_ids = {s.sheet_id for s in r["stale_sheets"]}
        assert stale_ids == {1, 2}  # R1/R2 stale, R3 latest
        latest = [s for s in r["stale_sheets"][:0]]  # placeholder
        for s in r["stale_sheets"]:
            assert s.is_stale and s.latest_revision == "R3"

    def test_filename_normalization_groups_variants(self):
        """文件名变体（-/_/大小写）归为同组（P6-1 跨变体识别）"""
        rows = [
            {"sheet_id": 1, "filename": "AP-01.dxf", "revision": "R1"},
            {"sheet_id": 2, "filename": "AP_01.DWG", "revision": "R2"},
            {"sheet_id": 3, "filename": "ap01.dxf", "revision": "R3"},
        ]
        r = build_version_report(rows)
        assert r["multi_sheet_groups"] == 1
        assert r["versioned_groups"] == 1
        assert len(r["stale_sheets"]) == 2

    def test_natural_order_r10_after_r2(self):
        """自然序：R10 > R2（不按字典序 R10 < R2 误判）"""
        rows = [
            {"sheet_id": 1, "filename": "MT-02.dxf", "revision": "R10"},
            {"sheet_id": 2, "filename": "MT-02.dxf", "revision": "R2"},
        ]
        r = build_version_report(rows)
        latest = [s for s in r["stale_sheets"]]
        assert latest and latest[0].sheet_id == 2  # R2 stale, R10 latest
        assert latest[0].latest_revision == "R10"

    def test_natural_revision_order(self):
        """_normalize_filename 口径：去扩展名 + 仅字母数字"""
        assert _normalize_filename("AP-01.dxf") == "ap01"
        assert _normalize_filename("AP_01.DWG") == "ap01"
        assert _normalize_filename("Sched 2-B.dxf") == "sched2b"
        assert _normalize_filename("") == ""


class TestVersionNoRevisionTolerance:
    """P6-1 验收②：无 revision 列（SQLite）→ 不报错、报告空 stale"""

    def test_empty_revision_rows(self):
        rows = [
            {"sheet_id": 1, "filename": "A.dxf", "revision": ""},
            {"sheet_id": 2, "filename": "B.dxf", "revision": ""},
        ]
        r = build_version_report(rows)
        assert r["has_revision_info"] is False
        assert r["stale_sheets"] == []
        assert r["versioned_groups"] == 0

    def test_mixed_revision_presence(self):
        rows = [
            {"sheet_id": 1, "filename": "A.dxf", "revision": "R1"},
            {"sheet_id": 2, "filename": "B.dxf", "revision": ""},
        ]
        r = build_version_report(rows)
        assert r["has_revision_info"] is True
        assert r["multi_sheet_groups"] == 0  # 各 key 单 sheet，无冲突

    def test_same_key_revision_only_one(self):
        rows = [
            {"sheet_id": 1, "filename": "A.dxf", "revision": "R1"},
            {"sheet_id": 2, "filename": "A.dxf", "revision": ""},
        ]
        r = build_version_report(rows)
        # 只有 1 个非空 revision：latest=R1；空 rev 同 key 图纸版本未知 →
        # 保守标记 stale（宁可提示复核，不可漏报旧版数据）
        assert r["stale_sheets"] and r["stale_sheets"][0].sheet_id == 2
        assert r["has_revision_info"] is True


class TestDuplicatePricing:
    """P6-2 重复计价检测（纯逻辑 build_duplicates）"""

    def test_same_block_two_boq_items(self):
        """同 block 锚点绑定 2 个 BOQ → 1 条候选（P6-2 验收①）"""
        mappings = [
            {"mode": "block", "block_name": "FAN-01", "layer_name": "MECH", "boq_item_id": 10, "sheet_id": 1},
            {"mode": "block", "block_name": "FAN-01", "layer_name": "MECH", "boq_item_id": 11, "sheet_id": 2},
        ]
        boq_index = {10: {"code": "A-1", "description": "风机"}, 11: {"code": "A-2", "description": "风机B"}}
        out = build_duplicates(mappings, boq_index)
        assert len(out) == 1
        d = out[0]
        assert d["anchor"] == "block:fan01"
        assert d["needs_review"] is True
        assert [i["boq_item_id"] for i in d["boq_items"]] == [10, 11]

    def test_layer_anchor_duplicate_across_sheets(self):
        """同 layer 跨图纸绑定 2 个 BOQ → 候选包含 sheet_ids 全集"""
        mappings = [
            {"mode": "layer", "layer_name": "L-ELE", "boq_item_id": 20, "sheet_id": 3},
            {"mode": "layer", "layer_name": "L-ELE", "boq_item_id": 21, "sheet_id": 4},
        ]
        out = build_duplicates(mappings)
        assert len(out) == 1
        assert out[0]["kind"] == "layer"
        assert set(out[0]["sheet_ids"]) == {3, 4}
        # 无 boq_index → 只出 id
        assert all("code" in i and "description" in i for i in out[0]["boq_items"])

    def test_single_binding_not_flagged(self):
        """锚点只有 1 个 BOQ → 不产生候选"""
        mappings = [
            {"mode": "block", "block_name": "UNIQUE", "boq_item_id": 30, "sheet_id": 4},
        ]
        assert build_duplicates(mappings) == []

    def test_layer_fallback_only_when_no_block(self):
        """block 模式有 block_name → 用 block 锚点（不误判为 layer 重复）"""
        mappings = [
            {"mode": "block", "block_name": "FAN-01", "layer_name": "MECH", "boq_item_id": 10, "sheet_id": 1},
            # 同一 layer 但不同 block 的实体 → 不构成 layer 重复
            {"mode": "layer", "layer_name": "MECH", "boq_item_id": 12, "sheet_id": 2},
        ]
        assert build_duplicates(mappings) == []