"""Phase 4 单测：Excel 保真回写 W1-W6 契约（v2.0 §6.4 / v1.0 §6.4）

覆盖：
  W1  load_workbook(data_only=False) 保公式
  W2  只写新增列（max_col+1）或复用已有 measured_qty 列，不碰原表
  W3  新增表头不克隆 StyleProxy（新样式对象）
  W4  保存前完整性校验（公式数/合并格/冻结窗格 + 原列 diff=0）
  W5  文件被占用 → 回退 <原目录>/_takeoff/
  W6  writeback_audit 逐行记录（file_sha256）

测试数据用 openpyxl 现场生成（结构同 BOQ-004 回填清单），不依赖真实 xlsx。
"""
from __future__ import annotations

import hashlib
import sqlite3

import pytest
from openpyxl import Workbook, load_workbook


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """测试用临时 SQLite DB（与 test_phase4_excel_audit 同款，隔离真实库）"""
    from app import config as cfg_mod
    from app import db as app_db

    test_db_path = tmp_path / "test.db"
    test_conn = sqlite3.connect(str(test_db_path), check_same_thread=False)
    test_conn.row_factory = sqlite3.Row
    test_conn.executescript(app_db._SCHEMA)
    app_db._migrate(test_conn)
    test_conn.commit()

    def _mock_get_conn():
        c = sqlite3.connect(str(test_db_path), check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(app_db, "get_conn", _mock_get_conn)
    monkeypatch.setattr(cfg_mod, "DB_PATH", test_db_path)
    if hasattr(app_db, "_thread_local"):
        app_db._thread_local = app_db.threading.local()

    yield app_db, tmp_path

    test_conn.close()


def _make_test_xlsx(path: str, n_rows: int = 3, with_formula: bool = True):
    """生成 BOQ 风格 xlsx：表头 Item/Description/Unit/Qty + 合并 A1:B1 + 公式"""
    wb = Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append(["Item", "Description", "Unit", "Qty", "Amount"])
    ws.merge_cells("A1:B1")  # 合并格（W4 校验保留）
    ws.freeze_panes = "A2"  # 冻结窗格（小结 W4 校验保留）
    for i in range(1, n_rows + 1):
        row = [f"r{i}", f"Item {i} desc", "No.", 10 * i, None]
        if with_formula:
            row[4] = f"=D{i + 1}*100"  # 公式（W1 校验保留）
        ws.append(row)
    wb.save(path)


def _seed_items(app_db, xlsx_path: str, n: int = 3, measured: float = 42.5):
    """插入 project + boq_item（row_index 与 xlsx 数据行对齐：表头 row1 → 数据从 row2）"""
    with app_db.get_conn() as conn:
        for t in ["writeback_audit", "boq_item", "project"]:
            conn.execute(f"DELETE FROM {t}")
        conn.execute(
            "INSERT INTO project(id, name, created_at, boq_path) VALUES(1, 'test', '2026-09-06', ?)",
            (str(xlsx_path),),
        )
        for i in range(1, n + 1):
            conn.execute(
                "INSERT INTO boq_item(id, project_id, row_index, code, description, unit, "
                "original_qty, bill_qty, measured_qty) VALUES(?, 1, ?, ?, ?, 'No.', ?, ?, ?)",
                (i, i + 1, f"r{i}", f"Item {i}", 10 * i, 10 * i, measured),
            )


# ============================================================
# W1-W6 单条契约
# ============================================================


class TestWritebackContracts:
    def test_w1_preserves_formulas(self, tmp_path, fresh_db):
        """W1：data_only=False 保公式（写回后 D 列公式仍在）"""
        from app.boq.writeback import writeback_to_excel

        xlsx = tmp_path / "boq.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=3)
        _seed_items(fresh_db[0], str(xlsx))

        res = writeback_to_excel(str(xlsx), project_id=1)
        assert res["written"] == 3
        wb = load_workbook(str(xlsx), data_only=False)
        assert wb.active.cell(row=2, column=5).value == "=D2*100"  # 公式原样保留

    def test_w2_only_adds_new_column(self, tmp_path, fresh_db):
        """W2：只新增一列（F），原 A-E 列内容不变"""
        from app.boq.writeback import writeback_to_excel

        xlsx = tmp_path / "boq.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=3)
        _seed_items(fresh_db[0], str(xlsx))
        before = load_workbook(str(xlsx)).active

        res = writeback_to_excel(str(xlsx), project_id=1)
        assert res["target_col"] == 6  # A..E 原 5 列 → 新增 F
        wb = load_workbook(str(xlsx))
        ws = wb.active
        assert ws.max_column == 6  # 先查 max_column（openpyxl cell() 读会顶高它）
        assert ws.cell(row=1, column=6).value == "measured_qty"
        assert ws.cell(row=1, column=7).value is None  # 没有多写
        # 6 列之外无任何非空格
        assert not any(
            ws.cell(row=r, column=7).value is not None for r in range(1, ws.max_row + 1)
        )
        # 原列逐格不变
        for r in range(1, 5):
            for c in range(1, 6):
                assert ws.cell(row=r, column=c).value == before.cell(row=r, column=c).value

    def test_w2_reuses_existing_measured_col(self, tmp_path, fresh_db):
        """W2 幂等：已存在 measured_qty 列 → 复用，不再新增列"""
        from app.boq.writeback import writeback_to_excel

        xlsx = tmp_path / "boq.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=3)
        _seed_items(fresh_db[0], str(xlsx))

        first = writeback_to_excel(str(xlsx), project_id=1)
        second = writeback_to_excel(str(xlsx), project_id=1)
        assert second["target_col"] == first["target_col"] == 6
        wb = load_workbook(str(xlsx))
        assert wb.active.max_column == 6  # 仍是 6 列，未追加

    def test_w3_header_fresh_style(self, tmp_path, fresh_db):
        """W3：新增表头用新样式对象（bold + 填充），不克隆原表样式"""
        from app.boq.writeback import writeback_to_excel

        xlsx = tmp_path / "boq.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=2)
        _seed_items(fresh_db[0], str(xlsx), n=2)
        writeback_to_excel(str(xlsx), project_id=1)
        wb = load_workbook(str(xlsx))
        ws = wb.active
        hdr = ws.cell(row=1, column=6)
        assert hdr.value == "measured_qty"
        assert hdr.font.bold is True
        assert hdr.fill.fgColor.rgb in ("00D9E2F3", "FFD9E2F3")
        # 原表头 A1（合并格）的样式未被克隆成同一对象
        assert hdr.font is not ws.cell(row=1, column=1).font

    def test_w4_verify_ok(self, tmp_path, fresh_db):
        """W4：保存前校验通过（公式数/合并格/冻结窗格一致 + 原列 diff=0）"""
        from app.boq.writeback import writeback_to_excel

        xlsx = tmp_path / "boq.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=3, with_formula=True)
        _seed_items(fresh_db[0], str(xlsx))
        res = writeback_to_excel(str(xlsx), project_id=1)
        assert res["verified"] is True
        assert res["integrity"]["formula_count"] == 3
        assert res["integrity"]["merged_ranges"] == 1
        assert res["integrity"]["freeze_panes"] == "A2"
        assert res["integrity"]["diffs"] == []

    def test_verify_integrity_detects_tamper(self, tmp_path):
        """W4 阴性：写入后原列被改 → verified False + diffs 非空"""
        from app.boq.writeback import _verify_integrity

        xlsx = tmp_path / "t.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=2)
        wb = load_workbook(str(xlsx), data_only=False)
        ws = wb.active
        meta = {"formula_count": 2, "merged_ranges": 1, "freeze_panes": "A2"}
        snap = {c: [ws.cell(row=r, column=c).value for r in range(1, 4)] for c in range(1, 6)}
        # 篡改 B2 原列
        ws.cell(row=2, column=2).value = "HACKED!"
        res = _verify_integrity(ws, meta, snap, target_col=6)
        assert res["ok"] is False
        assert any("col2r2" in d for d in res["diffs"])

    def test_w5_permission_error_fallback(self, tmp_path, fresh_db, monkeypatch):
        """W5：文件被占用 → 回退 <原目录>/_takeoff/ 并告知实际路径"""
        from app.boq.writeback import writeback_to_excel

        xlsx = tmp_path / "boq.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=2)
        _seed_items(fresh_db[0], str(xlsx), n=2)

        import openpyxl.workbook.workbook as wb_mod

        real_save = wb_mod.Workbook.save

        def locked_save(self, filename):
            if filename != str(tmp_path / "_takeoff" / "boq.xlsx"):
                raise PermissionError("file locked by Excel")
            return real_save(self, filename)

        monkeypatch.setattr(wb_mod.Workbook, "save", locked_save)
        res = writeback_to_excel(str(xlsx), project_id=1)
        assert "_takeoff" in res["output_path"]
        assert res["output_path"].endswith("boq.xlsx")
        assert (tmp_path / "_takeoff" / "boq.xlsx").exists()

    def test_w6_audit_with_sha(self, tmp_path, fresh_db):
        """W6：writeback_audit 逐行记录 + file_sha256"""
        from app.boq.writeback import compute_file_sha256, writeback_to_excel

        xlsx = tmp_path / "boq.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=3)
        _seed_items(fresh_db[0], str(xlsx))
        expected_sha = compute_file_sha256(str(xlsx))  # 写前源文件哈希
        res = writeback_to_excel(str(xlsx), project_id=1)
        assert res["file_sha256"] == expected_sha
        # 回写后文件已修改（新增列）→ 哈希必然变化（防 tamper 语义）
        assert compute_file_sha256(str(xlsx)) != expected_sha
        with fresh_db[0].get_conn() as conn:
            rows = conn.execute(
                "SELECT boq_item_id, file_sha256, measured_qty, takability FROM writeback_audit ORDER BY boq_item_id"
            ).fetchall()
        assert len(rows) == 3
        assert all(r["file_sha256"] == res["file_sha256"] for r in rows)
        assert [r["measured_qty"] for r in rows] == [42.5, 42.5, 42.5]
        assert all(r["takability"] == "MEASURABLE" for r in rows)


# ============================================================
# 行匹配 + 边界
# ============================================================


class TestWritebackMatching:
    def test_match_by_item_key_fallback(self, tmp_path, fresh_db):
        """row_index 失配 → 按 item_key 匹配（r2 在 code 列 = 原样）"""
        from app.boq.writeback import writeback_to_excel

        xlsx = tmp_path / "boq.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=3)
        with fresh_db[0].get_conn() as conn:
            for t in ["writeback_audit", "boq_item", "project"]:
                conn.execute(f"DELETE FROM {t}")
            conn.execute(
                "INSERT INTO project(id, name, created_at, boq_path) VALUES(1, 'test', '2026-09-06', '')"
            )
            # row_index=999 失配；item_key 命中 Excel 第 3 行（row4, code='r3'）→ sheet 第 2 行 code='r2' 不中
            conn.execute(
                "INSERT INTO boq_item(id, project_id, row_index, code, item_key, description, unit, "
                "original_qty, measured_qty) VALUES(1, 1, 999, 'r3', 'r3', 'x', 'No.', 10, 7.7)"
            )
        res = writeback_to_excel(str(xlsx), project_id=1)
        assert res["written"] == 1
        assert load_workbook(str(xlsx)).active.cell(row=4, column=6).value == 7.7

    def test_match_by_code_exact(self, tmp_path, fresh_db):
        """row_index 失配 + item_key 缺失 → code 精确匹配"""
        from app.boq.writeback import writeback_to_excel

        xlsx = tmp_path / "boq.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=3)
        with fresh_db[0].get_conn() as conn:
            for t in ["writeback_audit", "boq_item", "project"]:
                conn.execute(f"DELETE FROM {t}")
            conn.execute(
                "INSERT INTO project(id, name, created_at, boq_path) VALUES(1, 'test', '2026-09-06', '')"
            )
            conn.execute(
                "INSERT INTO boq_item(id, project_id, row_index, code, description, unit, "
                "original_qty, measured_qty) VALUES(1, 1, 999, 'r3', 'desc', 'No.', 10, 77.0)"
            )
        res = writeback_to_excel(str(xlsx), project_id=1)
        assert res["written"] == 1
        assert load_workbook(str(xlsx)).active.cell(row=4, column=6).value == 77.0  # r3 = Excel row 4

    def test_writeback_skips_unmatched_rows(self, tmp_path, fresh_db):
        """无匹配的 Excel 行不写（无 None 值注入新列）"""
        from app.boq.writeback import writeback_to_excel

        xlsx = tmp_path / "boq.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=5)
        with fresh_db[0].get_conn() as conn:
            for t in ["writeback_audit", "boq_item", "project"]:
                conn.execute(f"DELETE FROM {t}")
            conn.execute("INSERT INTO project(id, name, created_at, boq_path) VALUES(1, 't', '2026-09-06', '')")
            # 只登记 r1/r3/r5 → 只写这 3 行
            for i, rid in enumerate([1, 3, 5], start=1):
                conn.execute(
                    "INSERT INTO boq_item(id, project_id, row_index, code, measured_qty) "
                    "VALUES(?, 1, ?, ?, 9.9)",
                    (i, rid + 1, f"r{rid}"),
                )
        res = writeback_to_excel(str(xlsx), project_id=1)
        assert res["written"] == 3
        ws = load_workbook(str(xlsx)).active
        assert ws.cell(row=2, column=6).value == 9.9
        assert ws.cell(row=3, column=6).value is None  # r2 未登记 → 不写
        assert ws.cell(row=4, column=6).value == 9.9

    def test_missing_file_raises(self, tmp_path, fresh_db):
        """源文件不存在 → FileNotFoundError"""
        from app.boq.writeback import writeback_to_excel

        with pytest.raises(FileNotFoundError):
            writeback_to_excel(str(tmp_path / "nope.xlsx"), project_id=1)

    def test_recompute_zero_measured_no_write_twice(self, tmp_path, fresh_db):
        """measured_qty=0 仍写 0（保持幂等，重复执行不报错）"""
        from app.boq.writeback import writeback_to_excel

        xlsx = tmp_path / "boq.xlsx"
        _make_test_xlsx(str(xlsx), n_rows=2)
        _seed_items(fresh_db[0], str(xlsx), n=2, measured=0.0)
        res1 = writeback_to_excel(str(xlsx), project_id=1)
        res2 = writeback_to_excel(str(xlsx), project_id=1)
        assert res1["written"] == 2 and res2["written"] == 2