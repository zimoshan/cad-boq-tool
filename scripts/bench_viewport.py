"""P3-4 视口查询性能实测（SQLite 双引擎本地分支）

用法（须在项目根执行，用 webapi 的 venv）：
    DATABASE_URL=sqlite+aiosqlite:///<abs path to projects.db> \
    ./.venv-webapi/Scripts/python.exe scripts/bench_viewport.py

对每个 sheet（73 1.2万 / 74 4万 / 75 7.9万）测三种 bbox：
  - full     全图（fit 后的视口，覆盖全画面）
  - half     1/4 面积（放大一档）
  - pan      局部平移窗口（视口大小 ≈ 屏幕，模拟拖拽时的请求）
目标：p95 < 500ms（BACKLOG A.6 契约：大图视口 <500ms）。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

SHEETS = {73: "1.2万", 74: "4万", 75: "7.9万"}
N_RUNS = 20
LIMIT = 10000
LOD0_LIMIT = 2000  # 前端 LOD0 概览实际 limit（P3-4 对齐）


@dataclass
class Case:
    name: str
    factor: float  # bbox 覆盖全图的区段
    offset: tuple[float, float]  # (dx, dy) 相对全图中点的偏移（全图单位相对）

    @property
    def label(self) -> str:
        return self.name


async def sheet_bounds(engine, sheet_id: int) -> tuple[float, float, float, float]:
    """从 entity 表算整张图 bbox（一次全表扫描，做基准用）

    P3-4 数据异常规避：sheet 74/75 存在污染坐标（FURN-MED 个别 INSERT
    到 2.2e10 级别），全图 bbox 被 outlier 拉爆。此处按常规范围
    ±5e6 过滤后取 MIN/MAX —— 真实绘图区 bbox（前端 fitViewport 也是
    首批实体的 bbox，不走全表，故不受影响）。
    """
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT MIN(json_extract(bbox,'$[0]')), MIN(json_extract(bbox,'$[1]')), "
                    "MAX(json_extract(bbox,'$[2]')), MAX(json_extract(bbox,'$[3]')) "
                    "FROM entity WHERE sheet_id = :sid AND "
                    "json_extract(bbox,'$[0]') >= -500000 AND json_extract(bbox,'$[2]') <= 500000 "
                    "AND json_extract(bbox,'$[1]') >= -500000 AND json_extract(bbox,'$[3]') <= 500000"
                ),
                {"sid": sheet_id},
            )
        ).first()
        return tuple(float(v or 0) for v in row)


def gen_bbox(bounds, case: Case, pan_frac: float) -> tuple[float, float, float, float]:
    min_x, min_y, max_x, max_y = bounds
    w, h = max_x - min_x, max_y - min_y
    cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2
    bw, bh = w * case.factor, h * case.factor
    ox, oy = case.offset
    return (cx + ox * w - bw / 2, cy + oy * h - bh / 2, cx + ox * w + bw / 2, cy + oy * h + bh / 2)


async def bench_sheet(engine, sheet_id: int) -> None:
    bounds = await sheet_bounds(engine, sheet_id)
    min_x, min_y, max_x, max_y = bounds
    w, h = max_x - min_x, max_y - min_y
    print(f"\n=== sheet {sheet_id} ({SHEETS[sheet_id]}) real-content bbox=({min_x:.1f},{min_y:.1f},{max_x:.1f},{max_y:.1f}) w={w:.0f} h={h:.0f} ===")

    cases = [
        Case("full", 1.0, (0.0, 0.0)),
        Case("half", 0.5, (0.0, 0.0)),
        Case("pan", 0.35, (0.25, 0.15)),
    ]

    for use_lod0 in (False, True):
        tag = "LOD0-无geom" if use_lod0 else "LOD1-带geom"
        for case in cases:
            bbox = gen_bbox(bounds, case, 0.35)
            lat: list[float] = []
            n_rows = 0
            cols = (
                "SELECT id, handle, dxf_type, layer, block_name, bbox, length, color FROM entity"
                if use_lod0
                else "SELECT id, handle, dxf_type, layer, block_name, bbox, geom_json, length, color FROM entity"
            )
            cond = (
                " WHERE sheet_id = :sid AND "
                "json_extract(bbox,'$[0]') <= :max_x AND json_extract(bbox,'$[2]') >= :min_x "
                "AND json_extract(bbox,'$[1]') <= :max_y AND json_extract(bbox,'$[3]') >= :min_y "
                "LIMIT :lim"
            )
            # 首跑 warmup（DB 页缓存）
            async with engine.connect() as conn:
                await conn.execute(
                    text(cols + cond),
                    {"sid": sheet_id, "min_x": bbox[0], "min_y": bbox[1], "max_x": bbox[2], "max_y": bbox[3], "lim": LOD0_LIMIT if use_lod0 else LIMIT},
                )
            for _ in range(RE_RUNS):
                t0 = time.perf_counter()
                async with engine.connect() as conn:
                    res = await conn.execute(
                        text(cols + cond),
                        {"sid": sheet_id, "min_x": bbox[0], "min_y": bbox[1], "max_x": bbox[2], "max_y": bbox[3], "lim": LOD0_LIMIT if use_lod0 else LIMIT},
                    )
                    rows = res.fetchall()
                lat.append((time.perf_counter() - t0) * 1000)
                n_rows = len(rows)

            lat.sort()
            p50 = lat[len(lat) // 2]
            p95 = lat[int(len(lat) * 0.95) - 1]
            status = "PASS" if p95 < 500 else "FAIL"
            print(
                f"  [{tag}]  {case.label:5s} bbox=({bbox[0]:.0f},{bbox[1]:.0f},{bbox[2]:.0f},{bbox[3]:.0f}) "
                f"rows={n_rows:>6}  p50={p50:7.1f}ms p95={p95:7.1f}ms max={max(lat):7.1f}ms avg={mean(lat):6.1f}ms {status}"
            )


import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--sheets", default="73,74,75")
parser.add_argument("--runs", type=int, default=20)
args = parser.parse_args()
RE_RUNS = args.runs

RE_RUNS = args.runs


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data/bench.db")
    engine = create_async_engine(db_url)
    try:
        for sid in [int(x) for x in args.sheets.split(",")]:
            await bench_sheet(engine, sid)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())