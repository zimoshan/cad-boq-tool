"""DWG 直读优先回归测试。

验证批量重新解析的分流策略：
- ezdwg 探测可读的 DWG → 直接解析（不入库任何 DXF 路径，dxf_path 置空）
- 探测失败的 DWG → 复用已有 DXF 或 ODA 批量转换
- 无 DXF 可用且转换失败 → 记入 errors

全部依赖（probe/转换/解析/缓存/DB）均为替身，不触碰真实文件与库。
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.models import Entity


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    """指向独立临时库，避免碰真实 ~/.cad-boq-tool/projects.db"""
    import app.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_projects.db")
    db._thread_local.conn = None   # 清掉线程级连接缓存
    db.init_db()
    yield db
    db._thread_local.conn = None


def _make_file(p) -> str:
    p.write_text("dummy", encoding="utf-8")
    return str(p)


def test_reparse_prefers_direct_dwg_read(monkeypatch, temp_db, tmp_path):
    """探测通过的 DWG 直读；失败的才走转换/复用。"""
    from app import batch_reparse
    from app.cad import reader as cad_reader
    from app.cad import dwg as dwg_svc

    pid = temp_db.create_project("t")

    # s1: ezdwg 可直读；s2/s3/s4: 探测失败（分别走 转换 / 复用旧DXF / 全部失败）
    s1_src = _make_file(tmp_path / "ok.dwg")
    s2_src = _make_file(tmp_path / "conv.dwg")
    s2_conv = _make_file(tmp_path / "conv_converted.dxf")
    s3_src = _make_file(tmp_path / "reuse.dwg")
    s3_old = _make_file(tmp_path / "reuse_old.dxf")
    s4_src = _make_file(tmp_path / "hopeless.dwg")

    s1 = temp_db.add_sheet(pid, "ok.dwg", s1_src)
    s2 = temp_db.add_sheet(pid, "conv.dwg", s2_src, dxf_path=str(tmp_path / "missing.dxf"))
    s3 = temp_db.add_sheet(pid, "reuse.dwg", s3_src, dxf_path=s3_old)

    # 秒级探测替身：只有 s1 的源可读
    monkeypatch.setattr(cad_reader, "probe_dwg_support",
                        lambda p: None if p == s1_src else "format error")

    # ODA 批量转换替身：记录被转换清单，只为 s2 产出 DXF
    converted_calls = []
    monkeypatch.setattr(dwg_svc, "convert_dwgs_batch",
                        lambda paths, out_dir, parallel=4, version="ACAD2018":
                        (converted_calls.append(list(paths)) or
                         ({p: s2_conv for p in paths if p == s2_src})))

    # 解析进程池 → 同步线程池；worker 与缓存打桩（不真实解析）
    monkeypatch.setattr(batch_reparse, "ProcessPoolExecutor", ThreadPoolExecutor)
    monkeypatch.setattr(batch_reparse, "_parse_worker",
                        lambda dxf, src: (src, dxf, 10, 5, None))
    monkeypatch.setattr(batch_reparse.parse_cache, "get_cached_drawing",
                        lambda src: type("D", (), {
                            "entities": [Entity(handle=f"h{i}", dxf_type="LINE",
                                                layer="0", length=1.0)
                                         for i in range(10)],
                            "layers": {k: 0 for k in range(5)},
                            "blocks": {}})())

    stats = batch_reparse.BatchReparseJob(pid, cancel_event=threading.Event()).run()

    assert stats["error"] == 0 and stats["cancelled"] is False
    # 只把探测失败的 s2 送进 ODA（s1 直读、s3 复用旧 DXF）
    assert converted_calls == [[s2_src]]

    rows = {r.filename: r for r in temp_db.get_sheets(pid)}
    # 直读成功 → 不落任何 DXF 路径（与 import_folder 直读约定一致）
    assert rows["ok.dwg"].dxf_path == ""
    assert rows["ok.dwg"].status == "ready"
    # 探测失败且无旧 DXF → 用转换产物
    assert rows["conv.dwg"].dxf_path == s2_conv
    # 探测失败但旧 DXF 仍在 → 直接复用，不重复转换
    assert rows["reuse.dwg"].dxf_path == s3_old


def test_reparse_reports_conversion_failure(monkeypatch, temp_db, tmp_path):
    """探测失败且 ODA 不可用 → 单张报错，不影响其他图。"""
    from app import batch_reparse
    from app.cad import reader as cad_reader
    from app.cad import dwg as dwg_svc

    pid = temp_db.create_project("t")
    bad_src = _make_file(tmp_path / "bad.dwg")
    good_src = _make_file(tmp_path / "good.dwg")     # 直读路径，不受影响
    temp_db.add_sheet(pid, "bad.dwg", bad_src)
    temp_db.add_sheet(pid, "good.dwg", good_src)

    monkeypatch.setattr(cad_reader, "probe_dwg_support",
                        lambda p: None if p == good_src else "boom")
    monkeypatch.setattr(dwg_svc, "convert_dwgs_batch",
                        lambda paths, out_dir, parallel=4, version="ACAD2018": {})
    monkeypatch.setattr(batch_reparse, "ProcessPoolExecutor", ThreadPoolExecutor)
    monkeypatch.setattr(batch_reparse, "_parse_worker",
                        lambda dxf, src: (src, dxf, 10, 5, None))
    monkeypatch.setattr(batch_reparse.parse_cache, "get_cached_drawing",
                        lambda src: type("D", (), {
                            "entities": [Entity(handle=f"h{i}", dxf_type="LINE",
                                                layer="0", length=1.0)
                                         for i in range(10)],
                            "layers": {}, "blocks": {}})())

    stats = batch_reparse.BatchReparseJob(pid, cancel_event=threading.Event()).run()

    assert stats["error"] == 1
    assert any("DWG→DXF 转换失败" in e for e in stats["errors"])
    rows = {r.filename: r for r in temp_db.get_sheets(pid)}
    assert rows["good.dwg"].status == "ready"
