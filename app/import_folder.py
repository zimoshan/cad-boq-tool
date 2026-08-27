"""批量导入图纸文件夹（递归子目录）→ 解析缓存 + 入库。

V2 工作流第一步：整个 electrical 文件夹（含各系统子文件夹）一次导入，
每张图解析结果持久化到 SQLite（entity 表）+ 解析缓存（parse_cache），
后续核对/绑定直接从缓存与数据库读取，无需重新解析。

三阶段并行流水线（与 batch_reparse 同架构）：
  阶段1 分流：DWG 先 ezdwg 秒级探测，可直读的直接解析；探测失败的才分组
          → 多 ODA 实例并行批量转换
  阶段2 解析：ProcessPoolExecutor 进程池并行 parse_dxf（CPU 密集，GIL 限制线程无加速）
  阶段3 入库：主进程流式收回结果 → add_sheet + replace_entities
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from . import db
from .cad import dwg as dwg_svc
from .cad import parse_cache
from .cad import reader as cad_reader


def scan_drawings(folder: str, extensions=(".dwg", ".dxf")) -> list:
    """递归扫描文件夹下所有 DWG/DXF（自然排序）。

    同名 DWG 与 DXF 同时存在时，优先保留 DWG（DWG 信息更完整）。
    """
    root = Path(folder)
    if not root.is_dir():
        return []
    files = []
    for ext in extensions:
        files.extend(root.rglob(f"*{ext}"))
        files.extend(root.rglob(f"*{ext.upper()}"))
    seen, uniq = set(), []
    for f in files:
        rp = str(f.resolve())
        if rp not in seen:
            seen.add(rp)
            uniq.append(f)
    # 同名优先 DWG：同目录下同名文件，若存在 .dwg 则丢弃 .dxf
    dwg_names = {f.stem.lower() for f in uniq if f.suffix.lower() == ".dwg"}
    uniq = [f for f in uniq
            if f.suffix.lower() != ".dxf" or f.stem.lower() not in dwg_names]
    import re
    uniq.sort(key=lambda p: [int(t) if t.isdigit() else t
                             for t in re.split(r"(\d+)", p.name.lower())])
    return uniq


def _parse_worker(dxf_path: str, src_path: str):
    """进程池 worker（Windows spawn：模块级函数，仅依赖标准参数）。

    解析 DXF → 写解析缓存 → 返回轻量摘要。
    不触碰数据库；主进程稍后从缓存载入完整数据入库。
    """
    from .cad.cad_parser import parse_dxf
    try:
        drawing = parse_dxf(dxf_path)
        parse_cache.cache_drawing(src_path, drawing)
        return (src_path, dxf_path, len(drawing.entities), len(drawing.layers), None)
    except Exception as e:  # noqa: BLE001
        return (src_path, dxf_path, 0, 0, f"{e}")


def _default_workers() -> int:
    """解析进程数：留核心给 UI/ODA/入库，下限 2。"""
    return max(2, min(10, (os.cpu_count() or 8) - 4))


def sheet_exists(project_id: int, src_path: str) -> bool:
    """该源文件是否已导入（避免重复导入）"""
    for s in db.get_sheets(project_id):
        if s.src_path and Path(s.src_path).resolve() == Path(src_path).resolve():
            return True
    return False


def import_folder(project_id: int, folder: str,
                  progress_cb: Callable[[int, int, str, str], None] = None,
                  skip_existing: bool = True,
                  workers: int | None = None,
                  cancel_event=None) -> dict:
    """批量导入文件夹（递归）— 三阶段并行流水线。

    Args:
        progress_cb: (done, total, filename, status) status ∈ ok/error/skip/convert/parse/db
        skip_existing: 跳过已导入的图纸
        workers: 并行进程数（默认自动）
        cancel_event: threading.Event；设置后停止接收新任务（正在跑的会先完成）
    Returns:
        {"imported": int, "errors": [str], "skipped": int, "total": int, "elapsed": float,
         "cancelled": bool}
    """
    t0 = time.perf_counter()
    workers = workers or _default_workers()

    def _cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    # ===== 阶段 0：扫描 + 过滤已导入 =====
    files = scan_drawings(folder)
    todo = []       # [(Path, src_path)]  待处理
    stats = {"imported": 0, "errors": [], "skipped": 0, "total": len(files),
             "elapsed": 0.0, "parse_failed": 0}
    done = 0

    for f in files:
        if _cancelled():
            stats["cancelled"] = True
            stats["elapsed"] = time.perf_counter() - t0
            return stats
        src = str(f)
        if skip_existing and sheet_exists(project_id, src):
            stats["skipped"] += 1
            done += 1
            if progress_cb:
                progress_cb(done, len(files), f.name, "skip")
            continue
        todo.append((f, src))

    if not todo:
        stats.setdefault("cancelled", False)
        stats["elapsed"] = time.perf_counter() - t0
        return stats

    # ===== 阶段 1：DWG 批量并行转换 → DXF =====
    dwg_files = [(f, src) for f, src in todo if src.lower().endswith(".dwg")]
    dxf_files = [(f, src) for f, src in todo if not src.lower().endswith(".dwg")]

    # src_path → dxf_path 映射（DXF 文件自身就是 dxf）
    dxf_map = {src: src for _, src in dxf_files}

    if dwg_files:
        if progress_cb:
            progress_cb(done, len(files),
                        f"探测 {len(dwg_files)} 张 DWG 可读性…", "convert")

        # 优先 ezdwg 直读，失败的才走 ODA
        ezdwg_ok = []
        need_oda = []
        for f, src in dwg_files:
            probe_err = cad_reader.probe_dwg_support(src)
            if not probe_err:
                ezdwg_ok.append((f, src))
            else:
                need_oda.append((f, src))

        if progress_cb and (ezdwg_ok or need_oda):
            progress_cb(done, len(files),
                        f"直读 {len(ezdwg_ok)} 张 / 需转换 {len(need_oda)} 张",
                        "convert")

        # ezdwg 可读的直接作为 dxf_path（parse_dxf 内部按扩展名自动选 backend）
        for f, src in ezdwg_ok:
            dxf_map[src] = src

        # ODA 批量转换
        if need_oda:
            exe = dwg_svc.find_oda_converter()
            if exe:
                conv_dir = tempfile.mkdtemp(prefix="cadboq_import_")
                try:
                    from .cad.dwg import convert_dwgs_batch
                    converted = convert_dwgs_batch(
                        [src for _, src in need_oda], conv_dir,
                        parallel=min(4, workers))
                    dxf_map.update(converted)
                except Exception:
                    pass
            # 没有 ODA 的文件在解析阶段会报错

    # ===== 阶段 2+3：进程池并行解析，主进程流式入库 =====
    parse_jobs = []   # [(src_path, dxf_path)]
    for f, src in todo:
        dxf = dxf_map.get(src)
        if dxf:
            parse_jobs.append((src, dxf))
        else:
            done += 1
            stats["parse_failed"] += 1
            stats["errors"].append(f"{f.name}: DWG→DXF 转换失败（ezdwg 不支持且 ODA 不可用）")
            if progress_cb:
                progress_cb(done, len(files), f.name, "error")

    if parse_jobs:
        with ProcessPoolExecutor(max_workers=min(workers, len(parse_jobs))) as pool:
            futures = {pool.submit(_parse_worker, dxf, src): src
                       for src, dxf in parse_jobs}
            for fut in as_completed(futures):
                if _cancelled():
                    stats["cancelled"] = True
                    # 放弃剩余任务（with 块会 await 已完成任务，未开始的释放）
                    futures = {}
                    break
                src, dxf, ent_cnt, layer_cnt, err = fut.result()
                fname = Path(src).name
                if err:
                    done += 1
                    stats["errors"].append(f"{fname}: {err}")
                    if progress_cb:
                        progress_cb(done, len(files), fname, "error")
                    continue

                # 主进程从缓存载入完整数据入库
                if progress_cb:
                    progress_cb(done, len(files), fname, "db")
                try:
                    drawing = parse_cache.get_cached_drawing(src)
                    if drawing is None:
                        done += 1
                        stats["errors"].append(f"{fname}: 缓存回读失败")
                        if progress_cb:
                            progress_cb(done, len(files), fname, "error")
                        continue
                    sid = db.add_sheet(
                        project_id, fname, src,
                        status="ready", entity_count=len(drawing.entities),
                        layer_count=len(drawing.layers),
                        blocks_json=json.dumps(drawing.blocks, ensure_ascii=False))
                    db.replace_entities(sid, drawing.entities)
                    stats["imported"] += 1
                    done += 1
                    if progress_cb:
                        progress_cb(done, len(files), fname, "ok")
                except Exception as e:  # noqa: BLE001
                    done += 1
                    stats["errors"].append(f"{fname}: 入库失败 {e}")
                    if progress_cb:
                        progress_cb(done, len(files), fname, "error")

    stats.setdefault("cancelled", False)
    stats["elapsed"] = time.perf_counter() - t0
    return stats
