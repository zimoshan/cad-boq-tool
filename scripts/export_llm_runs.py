"""导出 LLM 调用记录（含完整 prompt / 输出全文）→ JSONL，用于 prompt 分析优化。

数据来源：llm_run 表（audit 模块逐次落库，binding 调用同时有 binding_candidate.llm_run_id
关联到人工确认/拒绝结果）。

用法（在项目根目录、用 .venv 的 python）：
  # 导出全部项目的 binding 调用
  python scripts/export_llm_runs.py --task binding -o llm_binding_runs.jsonl

  # 只导出某个项目最近 200 条
  python scripts/export_llm_runs.py --project-id 1 --task binding --limit 200

  # 只要失败的（排查 schema 校验不过的 case）
  python scripts/export_llm_runs.py --task binding --status error

每行一个 JSON 对象：
  {id, created_at, task_type, prompt_version, model, status, error,
   temperature, duration_ms, token_input, token_output,
   input_text(system+user), output_text(模型原始输出)}

配合分析：
  - 按 prompt_version 分组对比新旧 prompt 的 ok 率 / 平均时长 / retry 率；
  - output_text 解析 JSON 后与 input_text 中候选对照，找出误选案例。

可选关联人工结果：--with-binding 把同 project 的 binding_candidate 按
llm_run_id 反查，附 accepted/rejected/pending 字段。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402


def _binding_outcome_by_run(project_id: int) -> dict:
    """{llm_run_id: "ACCEPTED"/"REJECTED"/"PENDING"}（取该 run 最新一条候选状态）"""
    try:
        rows = db.get_candidates(project_id)
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for c in rows:
        if getattr(c, "llm_run_id", None):
            out[c.llm_run_id] = c.status
    return out


def main():
    ap = argparse.ArgumentParser(description="导出 llm_run 全文记录 → JSONL")
    ap.add_argument("--project-id", type=int, default=None, help="只导该项目")
    ap.add_argument("--task", default="binding", help="task_type 过滤（binding/classify/legend…）")
    ap.add_argument("--status", default=None, choices=["ok", "error", "retried"],
                    help="状态过滤")
    ap.add_argument("--limit", type=int, default=1000, help="最多导出条数")
    ap.add_argument("--with-binding", action="store_true",
                    help="绑定类调用附带人工确认结果（accepted/rejected）")
    ap.add_argument("-o", "--out", default="llm_runs.jsonl", help="输出 JSONL 路径")
    args = ap.parse_args()

    con = db.get_conn()
    sql = ("SELECT * FROM llm_run WHERE 1=1")
    params: list = []
    if args.project_id is not None:
        sql += " AND project_id=?"
        params.append(args.project_id)
    if args.task:
        sql += " AND task_type LIKE ?"
        params.append(f"{args.task}%")     # 覆盖 binding-fallback 等变体
    if args.status:
        sql += " AND status=?"
        params.append(args.status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(args.limit)

    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    outcome = _binding_outcome_by_run(args.project_id) \
        if (args.with_binding and args.project_id is not None) else {}

    out_path = Path(args.out)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            if args.with_binding and r["id"] in outcome:
                r["human_result"] = outcome[r["id"]]
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 终端摘要：按 prompt_version 分组的命中率，直观对比新旧 prompt 效果
    groups = defaultdict(lambda: {"n": 0, "ok": 0, "retried": 0, "err": 0,
                                  "tok_in": 0, "dur": 0})
    for r in rows:
        g = groups[(r["task_type"], r["prompt_version"], r.get("model", ""))]
        g["n"] += 1
        g[{"ok": "ok", "retried": "retried", "error": "err"}.get(r["status"], "ok")] += 1
        g["tok_in"] += r["token_input"] or 0
        g["dur"] += r["duration_ms"] or 0

    print(f"导出 {len(rows)} 条 → {out_path}\n")
    print(f"{'task':<18} {'prompt_ver':<14} {'model':<20} {'次数':>5} {'ok率':>7} "
          f"{'重试率':>7} {'平均耗时ms':>10}")
    for (task, ver, model), g in sorted(groups.items()):
        n = max(g["n"], 1)
        print(f"{task:<18} {ver:<14} {(model or '-')[:20]:<20} {g['n']:>5} "
              f"{g['ok'] / n:>6.0%} {(g['retried'] + g['err']) / n:>6.0%} "
              f"{g['dur'] // n:>10}")


if __name__ == "__main__":
    main()
