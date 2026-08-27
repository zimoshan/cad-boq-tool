"""性能基准脚本（P3-1 建档）：度量 解析/聚合/召回/DB 查询 各段耗时。

用法：
  python scripts/bench_perf.py --drawing "path/to/xx.dwg"                              # 解析+聚合
  python scripts/bench_perf.py --project 1                                             # DB 侧
  python scripts/bench_perf.py --project 1 --embed-calls --out bench.json              # 含 embedding 验收

指标与验收对应（PERFORMANCE_OPTIMIZATION.md）：
  embedding.compute_requests ≈ boq_count + sampled_eo（P0-1：而非 EO×BOQ）
  aggregate 单遍 O(N)（P2-6）
  candidate_status_summary 批量预取替代 N+1（P1-2）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402


def _timed(fn):
    t0 = time.perf_counter()
    res = fn()
    return (time.perf_counter() - t0) * 1000, res


def bench_parse_and_aggregate(path: str) -> dict:
    """解析（冷/热两趟）+ 分块聚合 基准。失败返回 {"error": ...}。"""
    from app.cad import parse_cache, cad_parser
    from app.cad.dwg import convert_dwg_to_dxf
    from app.takeoff.aggregate import aggregate

    dxf_path = path
    if str(path).lower().endswith(".dwg"):
        tmp_dir = config.DATA_DIR / "bench_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        dxf_path = convert_dwg_to_dxf(str(path), str(tmp_dir))
        if not dxf_path or not Path(dxf_path).exists():
            return {"error": f"DWG 转换失败（ODA 未安装？）: {path}"}
    if not Path(dxf_path).exists():
        return {"error": f"无法取得可解析文件: {path}"}

    out = {}
    # 冷解析（不走缓存）
    ms, drawing = _timed(lambda: cad_parser.parse_dxf(str(dxf_path)))
    out["parse_cold_ms"] = round(ms, 1)
    out["entities"] = len(drawing.entities)
    out["layers"] = len(drawing.layers or {})
    out["blocks"] = len(drawing.block_refs or {})

    # 写缓存 → 热读（验收 47s→<1s）
    parse_cache.cache_drawing(str(dxf_path), drawing)
    ms, _ = _timed(lambda: parse_cache.get_cached_drawing(str(dxf_path)))
    out["parse_cache_hit_ms"] = round(ms, 1)
    out["cache_entries"] = len(parse_cache.cache_stats().get("entries", []))
    out["parquet"] = parse_cache.cache_stats().get("parquet", False)

    # 分块聚合（P2-6）
    ms, agg = _timed(lambda: aggregate(drawing, chunk_size=20_000))
    out["aggregate_ms"] = round(ms, 1)
    out["agg_layers"] = len(agg.layers)
    out["agg_regions"] = len(agg.regions)
    out["agg_typical_sizes"] = len(agg.typical_sizes)
    return out


def bench_db(project_id: int) -> dict:
    res = {}
    # P1-3：BOQ 全量装载单次化
    ms, _ = _timed(lambda: db.get_boq_items(project_id))
    res["get_boq_items_ms"] = round(ms, 1)
    # P1-2：候选状态批量预取（替代原每行 N+1）
    ms, _ = _timed(lambda: db.candidate_status_summary(project_id))
    res["candidate_status_summary_ms"] = round(ms, 1)
    eos = db.get_engineering_objects(project_id)
    res["engineering_objects"] = len(eos)
    return res


def bench_embed_calls(project_id: int, sample: int = 200) -> dict:
    """P0-1 验收：BOQ 向量进程内/落盘缓存后，embedding 请求数降到 O(1)+EO 级。

    用伪 provider 计数（不真调模型），避免污染 ~/.cad-boq-tool/embedding_cache。
    """
    from app.binding import embedding_matcher as em
    em._clear_embedding_cache()
    boq_items = db.get_boq_items(project_id)
    called = {"n": 0, "texts": 0}

    class _Counting:
        name = "bench-count"
        model = "bench"
        def is_available(self):
            return True
        def embed(self, texts):
            called["n"] += 1
            called["texts"] += len(texts)
            return [[1.0] * 8] * len(texts)

    prov = _Counting()
    eos = db.get_engineering_objects(project_id)[:sample]

    class _EO:
        def __init__(self, eo):
            self.block_name = eo.block_name
            self.layer_name = eo.layer_name
            self.system = eo.system
            self.specification = eo.specification
            self.tag = getattr(eo, "tag", "")

    # 让 semantic_candidates 内部的 create_embedding_provider 也走计数
    em.create_embedding_provider = lambda: prov

    em._get_project_vectors(project_id, prov, boq_items)   # BOQ 1 次
    for eo in eos:
        em.semantic_candidates(project_id, _EO(eo))

    expected_min = (1 if boq_items else 0) + len(eos)
    return {
        "embed_requests": called["n"],
        "embed_texts_total": called["texts"],
        "expected_min": expected_min,
        "within_budget": called["n"] <= expected_min * 2,
        "eo_sampled": len(eos),
        "boq_count": len(boq_items),
    }


def main():
    ap = argparse.ArgumentParser(description="cad-boq-tool 性能基准")
    ap.add_argument("--project", type=int, default=None, help="目标项目 id")
    ap.add_argument("--drawing", type=str, default=None, help="DWG/DXF 路径")
    ap.add_argument("--out", type=str, default="bench-result.json", help="报告输出路径")
    ap.add_argument("--embed-calls", action="store_true",
                    help="含 embedding 请求数验收（伪 provider）")
    args = ap.parse_args()

    report = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
              "project_id": args.project,
              "config": {
                  "LLM_BATCH_WORKERS": getattr(config, "LLM_BATCH_WORKERS", 2),
                  "PARSE_CACHE_MAX_ENTRIES": getattr(config, "PARSE_CACHE_MAX_ENTRIES", 100),
                  "BINDING_TOP_N": getattr(config, "BINDING_TOP_N", 5),
              }}

    if args.drawing:
        report["parse"] = bench_parse_and_aggregate(args.drawing)

    if args.project:
        if args.project not in {p.id for p in db.list_projects()}:
            print(f"项目 {args.project} 不存在"); sys.exit(1)
        report["db"] = bench_db(args.project)
        if args.embed_calls:
            report["embedding"] = bench_embed_calls(args.project)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"\n>>> 报告已写: {args.out}")


if __name__ == "__main__":
    main()