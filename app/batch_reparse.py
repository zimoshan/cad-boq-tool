"""批量重新解析编排器：三阶段并行流水线。

阶段1 转换：全部 DWG 分组 → 多 ODA 实例并行批量转换（消除每张一次启动的开销）
阶段2 解析：ProcessPoolExecutor 进程池并行 parse_dxf（纯 Python CPU 密集，
            受 GIL 限制线程无加速，必须进程并行）；worker 只解析 + 写 parse_cache，
            不碰数据库（SQLite 单写者，入库由主进程串行完成）
阶段3 入库：主进程流式收回结果 → update_sheet_parse + replace_entities

进度回调：progress_cb(done, total, filename, status)，status ∈
  convert/parse/db/ok/error/missing
协作取消：cancel_event.set() 后在文件边界停止，进程池 shutdown(cancel_futures=True)
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from . import db
from .cad import parse_cache


def _parse_worker(dxf_path: str, src_path: str):
    """进程池 worker（Windows spawn：必须是模块级函数，仅依赖标准参数）。

    解析 DXF → 以源文件路径为 key 写解析缓存 → 返回轻量摘要。
    不触碰数据库；主进程稍后从缓存载入完整数据入库。
    """
    from .cad.cad_parser import parse_dxf
    try:
        drawing = parse_dxf(dxf_path)
        parse_cache.cache_drawing(src_path, drawing)
        return (src_path, dxf_path, len(drawing.entities), len(drawing.layers), None)
    except Exception as e:  # noqa: BLE001
        return (src_path, dxf_path, 0, 0, f"{e}")


def default_workers() -> int:
    """解析进程数：留 4 核给 UI/ODA/入库，下限 2。"""
    return max(2, min(10, (os.cpu_count() or 8) - 4))


class BatchReparseJob:
    """一次批量重解析任务（在后台 QThread 中调用 run()）。"""

    def __init__(self, project_id: int, progress_cb=None,
                 cancel_event: threading.Event | None = None,
                 workers: int | None = None):
        self.project_id = project_id
        self.progress_cb = progress_cb
        self.cancel_event = cancel_event or threading.Event()
        self.workers = workers or default_workers()

    # ---------- 内部工具 ----------
    def _report(self, done: int, total: int, filename: str, status: str):
        if self.progress_cb:
            try:
                self.progress_cb(done, total, filename, status)
            except Exception:
                pass

    def _cancelled(self) -> bool:
        return self.cancel_event.is_set()

    # ---------- 主流程 ----------
    def run(self) -> dict:
        """Returns: {"total", "ok", "error", "skipped", "errors": [str],
                    "cancelled": bool, "elapsed": float}"""
        t0 = time.perf_counter()
        sheets = db.get_sheets(self.project_id)
        total = len(sheets)
        stats = {"total": total, "ok": 0, "error": 0, "skipped": 0,
                 "errors": [], "cancelled": False, "elapsed": 0.0}
        if total == 0:
            stats["elapsed"] = time.perf_counter() - t0
            return stats

        # ---- 收集源文件：缺失的立即标记，其余按 DWG/DXF 分流 ----
        jobs = []              # [(sheet, dxf_path, src_path)]
        dwg_srcs = []          # 需 ODA 转换的 (sheet, src_path)
        done = 0
        for s in sheets:
            src = s.src_path or s.dxf_path
            if not src or not os.path.isfile(src):
                done += 1
                stats["error"] += 1
                stats["errors"].append(f"{s.filename}: 源文件不存在（{src}）")
                self._report(done, total, s.filename, "missing")
                continue
            if src.lower().endswith(".dwg"):
                dwg_srcs.append((s, src))
            else:
                jobs.append((s, src, src))

        # ---- 阶段1：DWG 批量并行转换 ----
        if dwg_srcs:
            if self._cancelled():
                stats["cancelled"] = True
                stats["elapsed"] = time.perf_counter() - t0
                return stats
            self._report(done, total, f"转换 {len(dwg_srcs)} 张 DWG…", "convert")
            conv_dir = tempfile.mkdtemp(prefix="cadboq_reparse_")
            try:
                from .cad.dwg import convert_dwgs_batch
                # 已有可用 DXF（dxf_path 仍存在）的直接复用，避免重复转换
                need_conv, dxf_map = [], {}
                for s, src in dwg_srcs:
                    old_dxf = s.dxf_path
                    if old_dxf and os.path.isfile(old_dxf) and \
                            Path(old_dxf).suffix.lower() == ".dxf":
                        dxf_map[src] = old_dxf
                    else:
                        need_conv.append(src)
                if need_conv:
                    converted = convert_dwgs_batch(need_conv, conv_dir,
                                                   parallel=min(4, self.workers))
                    dxf_map.update(converted)
                for s, src in dwg_srcs:
                    dxf = dxf_map.get(src)
                    if dxf:
                        jobs.append((s, dxf, src))
                    else:
                        done += 1
                        stats["error"] += 1
                        stats["errors"].append(f"{s.filename}: DWG→DXF 转换失败")
                        self._report(done, total, s.filename, "error")
            finally:
                # 转换产物放 temp，由系统清理；不删 dxf（入库前还要用）
                pass

        if self._cancelled():
            stats["cancelled"] = True
            stats["elapsed"] = time.perf_counter() - t0
            return stats

        # ---- 阶段2+3：进程池并行解析，主进程流式入库 ----
        src_to_sheet = {src: s for s, _, src in jobs}
        if jobs:
            with ProcessPoolExecutor(max_workers=min(self.workers, len(jobs))) as pool:
                futures = {pool.submit(_parse_worker, dxf, src): src
                           for s, dxf, src in jobs}
                for fut in as_completed(futures):
                    if self._cancelled():
                        pool.shutdown(wait=True, cancel_futures=True)
                        break
                    src, dxf, ent_cnt, layer_cnt, err = fut.result()
                    sheet = src_to_sheet.get(src)
                    if sheet is None:
                        continue
                    if err:
                        done += 1
                        stats["error"] += 1
                        stats["errors"].append(f"{sheet.filename}: 解析失败 {err}")
                        self._report(done, total, sheet.filename, "error")
                        continue
                    # 主进程从缓存载入完整数据入库（缓存由 worker 刚写入）
                    drawing = parse_cache.get_cached_drawing(src)
                    if drawing is None:
                        done += 1
                        stats["error"] += 1
                        stats["errors"].append(f"{sheet.filename}: 缓存回读失败")
                        self._report(done, total, sheet.filename, "error")
                        continue
                    self._report(done, total, sheet.filename, "db")
                    try:
                        import json
                        db.update_sheet_parse(
                            sheet.id, dxf, len(drawing.entities),
                            len(drawing.layers),
                            json.dumps(drawing.blocks, ensure_ascii=False))
                        db.replace_entities(sheet.id, drawing.entities)
                        done += 1
                        stats["ok"] += 1
                        self._report(done, total, sheet.filename, "ok")
                    except Exception as e:  # noqa: BLE001
                        done += 1
                        stats["error"] += 1
                        stats["errors"].append(f"{sheet.filename}: 入库失败 {e}")
                        self._report(done, total, sheet.filename, "error")

        stats["skipped"] = stats["total"] - stats["ok"] - stats["error"]
        stats["cancelled"] = self._cancelled()
        stats["elapsed"] = time.perf_counter() - t0
        return stats
