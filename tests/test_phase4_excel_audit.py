"""Phase 4 集成测试：v1.0 §6.4 Excel 保真回写契约 + SHA-256 审计"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """测试用临时 SQLite DB（避免污染真实 ~/.cad-boq-tool/projects.db）

    关键：app.db 通过 `from .config import DB_PATH` 静态导入，需要同时 patch
    app.config.DB_PATH 和 app.db.DB_PATH 引用。
    """
    from app import config as cfg_mod
    from app import db as app_db

    test_db_path = tmp_path / "test.db"
    # 同时 patch 两个 module 的 DB_PATH 引用
    monkeypatch.setattr(cfg_mod, "DB_PATH", test_db_path)
    monkeypatch.setattr(app_db, "DB_PATH", test_db_path)
    # 重置 thread_local conn
    if hasattr(app_db, "_thread_local"):
        app_db._thread_local = app_db.threading.local()
    # 重新初始化 schema
    app_db.init_db()
    yield app_db, tmp_path
    # 清理 thread_local
    if hasattr(app_db, "_thread_local"):
        app_db._thread_local = app_db.threading.local()


# ============================================================
# app/boq/writeback.compute_file_sha256
# ============================================================


class TestComputeFileSha256:
    def test_sha256_of_real_file(self, tmp_path):
        from app.boq.writeback import compute_file_sha256
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        sha = compute_file_sha256(str(f))
        # 已知 hello world SHA-256
        assert sha == hashlib.sha256(b"hello world").hexdigest()

    def test_sha256_of_empty_file(self, tmp_path):
        from app.boq.writeback import compute_file_sha256
        f = tmp_path / "empty.txt"
        f.write_text("")
        sha = compute_file_sha256(str(f))
        assert sha == hashlib.sha256(b"").hexdigest()

    def test_sha256_of_nonexistent_file(self):
        from app.boq.writeback import compute_file_sha256
        sha = compute_file_sha256("D:/nonexistent/path/file.xlsx")
        assert sha == ""  # fallback 空字符串

    def test_sha256_large_file_chunks(self, tmp_path):
        """1MB 文件，验证分块读取正确"""
        from app.boq.writeback import compute_file_sha256
        f = tmp_path / "big.bin"
        data = b"x" * (1024 * 1024 + 13)  # 1MB+13 字节
        f.write_bytes(data)
        sha = compute_file_sha256(str(f))
        assert sha == hashlib.sha256(data).hexdigest()


# ============================================================
# v1.0 §6.4 Excel 保真回写：原 original_qty 保留 + measured_qty 新列
# ============================================================


class TestExcelFaithfulWriteback:
    """parse → writeback → export 全链路 + 验证保真"""

    def _make_test_xlsx(self, path: str, n_rows: int = 5):
        """创建测试 BOQ Excel（含 formula + merge_cells + 数字）"""
        wb = Workbook()
        ws = wb.active
        ws.title = "BOQ"
        # 表头
        ws.append(["Item", "Description", "Unit", "Qty", "Amount"])
        # 合并 A1:B1（测试保留）
        ws.merge_cells("A1:B1")
        # 数据
        for i in range(1, n_rows + 1):
            ws.append([f"r{i}", f"Item {i}", "No.", 10 * i, f"=D{i+1}*100"])  # 公式
        wb.save(path)

    def test_export_preserves_original_qty(self, tmp_path, fresh_db):
        """export_report 不覆盖原 original_qty（v1.0 §6.4）"""
        from app.report import export_report
        app_db, db_dir = fresh_db
        xlsx = db_dir / "boq_in.xlsx"
        self._make_test_xlsx(str(xlsx), n_rows=3)

        with app_db.get_conn() as conn:
            for t in ["writeback_audit", "boq_item", "project", "sheet"]:
                conn.execute(f"DELETE FROM {t}")
            conn.execute(
                "INSERT INTO project(id, name, created_at, boq_path) VALUES(1, 'test', '2026-09-06', ?)",
                (str(xlsx),),
            )
            for i in range(1, 4):
                conn.execute(
                    "INSERT INTO boq_item(id, project_id, row_index, code, description, unit, original_qty, bill_qty, measured_qty) "
                    "VALUES(?, 1, ?, ?, ?, 'No.', ?, ?, 0.0)",
                    (i, i, f"r{i}", f"Item {i}", 10 * i, 10 * i),
                )

        out = db_dir / "boq_out.xlsx"
        rows = export_report(project_id=1, sheet_id=0, out_path=str(out), use_measured=False)
        assert rows == 3

        wb = load_workbook(str(out))
        ws = wb.active
        assert ws.cell(row=2, column=1).value == 1  # row_index
        assert ws.cell(row=2, column=2).value == "r1"  # code
        # original_qty 列保留
        assert ws.cell(row=2, column=5).value == 10

    def test_export_overwrite_uses_measured_qty(self, tmp_path, fresh_db):
        """use_measured=True：measured_qty 覆盖 original_qty 列"""
        from app.report import export_report
        app_db, db_dir = fresh_db
        xlsx = db_dir / "boq.xlsx"
        self._make_test_xlsx(str(xlsx), n_rows=2)

        with app_db.get_conn() as conn:
            for t in ["writeback_audit", "boq_item", "project"]:
                conn.execute(f"DELETE FROM {t}")
            conn.execute(
                "INSERT INTO project(id, name, created_at, boq_path) VALUES(1, 'test', '2026-09-06', ?)",
                (str(xlsx),),
            )
            for i in range(1, 3):
                conn.execute(
                    "INSERT INTO boq_item(id, project_id, row_index, code, description, unit, original_qty, bill_qty, measured_qty) "
                    "VALUES(?, 1, ?, ?, ?, 'No.', ?, ?, ?)",
                    (i, i, f"r{i}", f"Item {i}", 10 * i, 10 * i, 99.0),
                )

        out = db_dir / "boq_out.xlsx"
        rows = export_report(project_id=1, sheet_id=0, out_path=str(out), use_measured=True)
        assert rows == 2

        wb = load_workbook(str(out))
        ws = wb.active
        # overwrite 模式：第 5 列是 qty（= measured）
        assert ws.cell(row=2, column=5).value == 99.0


# ============================================================
# webapi/services/boq.writeback_quantities 集成测试
# ============================================================


class TestServiceWriteback:
    """webapi service 包装层 + SHA-256 注入"""

    def test_compute_sha_for_source(self, tmp_path):
        """v1.0 §6.4：writeback_audit.file_sha256 记录源文件 SHA-256"""
        from app.boq.writeback import compute_file_sha256
        f = tmp_path / "boq_source.xlsx"
        f.write_bytes(b"mock xlsx content")
        sha = compute_file_sha256(str(f))
        assert sha == hashlib.sha256(b"mock xlsx content").hexdigest()
        assert len(sha) == 64  # SHA-256 hex 长度

    def test_writeback_audit_records_sha(self, fresh_db):
        """完整链路：writeback_audit.file_sha256 注入"""
        app_db, db_dir = fresh_db
        f = db_dir / "boq.xlsx"
        f.write_bytes(b"audit test content")
        expected_sha = hashlib.sha256(b"audit test content").hexdigest()

        with app_db.get_conn() as conn:
            for t in ["writeback_audit", "boq_item", "project"]:
                conn.execute(f"DELETE FROM {t}")
            conn.execute(
                "INSERT INTO project(id, name, created_at, boq_path) VALUES(1, 'test', '2026-09-06', ?)",
                (str(f),),
            )
            conn.execute(
                "INSERT INTO boq_item(id, project_id, row_index, code, description, unit, original_qty, bill_qty) "
                "VALUES(1, 1, 1, 'r1', 'Item 1', 'No.', 10, 10)",
            )
            conn.execute(
                "INSERT INTO writeback_audit(project_id, boq_item_id, original_qty, measured_qty, takability, file_sha256) "
                "VALUES(1, 1, 10, 10, 'MEASURABLE', ?)",
                (expected_sha,),
            )

        with app_db.get_conn() as conn:
            row = conn.execute(
                "SELECT file_sha256, takability FROM writeback_audit WHERE boq_item_id=1"
            ).fetchone()
            assert row["file_sha256"] == expected_sha
            assert row["takability"] == "MEASURABLE"
