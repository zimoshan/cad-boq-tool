"""旧 SQLite projects.db → PostgreSQL 一次性数据迁移

使用：
    python -m migrations.sqlite_to_pg \\
        --sqlite /c/Users/Solomon/.cad-boq-tool/projects.db \\
        --pg-dsn postgresql://cadboq:cadboq_dev@localhost:5432/cadboq

设计：
- 读 SQLite 12 张业务表
- 写 PG（schema 已由 alembic upgrade head 创建）
- 字段映射：bboxes 解析、entity_ids 解析、JSON 字段保留为 TEXT
- B2 新字段（section/bill_qty/installed_qty/qty_remaining/item_key/brand）从 description/code 推默认值
- B4 entity.bbox TEXT(JSON) → min_x/min_y/max_x/max_y + geometry
- 事务批量提交（每表 1000 行一 commit）

注意：迁移前必须 alembic upgrade head 跑通
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import psycopg


# 表迁移顺序（FK 依赖）
TABLE_ORDER = [
    "project",
    "sheet",
    "entity",
    "boq_item",
    "mapping",
    "block_legend",
    "engineering_object",
    "llm_run",
    "project_config",
    "binding_candidate",
    "llm_settings",
    "symbol_library",
]


def parse_bbox(bbox_text: str) -> tuple[float | None, float | None, float | None, float | None]:
    """SQLite bbox TEXT(可能 4-tuple 或 JSON) → (min_x, min_y, max_x, max_y)"""
    if not bbox_text:
        return None, None, None, None
    try:
        # 尝试 JSON
        v = json.loads(bbox_text)
        if isinstance(v, (list, tuple)) and len(v) == 4:
            return float(v[0]), float(v[1]), float(v[2]), float(v[3])
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    # 尝试 "(x1, y1, x2, y2)" 字符串
    try:
        parts = bbox_text.strip("()[] ").split(",")
        if len(parts) == 4:
            return float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
    except (ValueError, IndexError):
        pass
    return None, None, None, None


def build_wkt_polygon(min_x, min_y, max_x, max_y) -> str | None:
    if None in (min_x, min_y, max_x, max_y):
        return None
    return f"POLYGON(({min_x} {min_y},{max_x} {min_y},{max_x} {max_y},{min_x} {max_y},{min_x} {min_y}))"


def migrate_table(sqlite_conn, pg_conn, table: str, batch: int = 1000) -> int:
    """迁移一张表，返回写入行数"""
    cur = sqlite_conn.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    if not rows:
        return 0

    inserted = 0
    with pg_conn.cursor() as pg_cur:
        for i in range(0, len(rows), batch):
            batch_rows = rows[i : i + batch]
            for row in batch_rows:
                # entity 表特殊处理：B4 字段提取 + geometry
                if table == "entity":
                    row_dict = dict(zip(cols, row))
                    bbox = row_dict.pop("bbox", "")
                    min_x, min_y, max_x, max_y = parse_bbox(bbox)
                    row_dict["min_x"] = min_x
                    row_dict["min_y"] = min_y
                    row_dict["max_x"] = max_x
                    row_dict["max_y"] = max_y
                    wkt = build_wkt_polygon(min_x, min_y, max_x, max_y)
                    placeholders = ",".join(["%s"] * (len(row_dict) + (1 if wkt else 0)))
                    col_names = list(row_dict.keys()) + (["geometry"] if wkt else [])
                    sql = f"INSERT INTO entity ({','.join(col_names)}) VALUES ({placeholders})"
                    params = list(row_dict.values())
                    if wkt:
                        params.append(wkt)
                    pg_cur.execute(sql, params)
                # boq_item 表特殊处理：B2 新字段填默认值
                elif table == "boq_item":
                    row_dict = dict(zip(cols, row))
                    row_dict.setdefault("section", "")
                    row_dict.setdefault("item_key", "")
                    row_dict.setdefault("brand", "")
                    row_dict.setdefault("bill_qty", row_dict.get("original_qty", 0))
                    row_dict.setdefault("installed_qty", 0)
                    row_dict.setdefault("qty_remaining", row_dict.get("original_qty", 0))
                    placeholders = ",".join(["%s"] * len(row_dict))
                    sql = f"INSERT INTO boq_item ({','.join(row_dict.keys())}) VALUES ({placeholders})"
                    pg_cur.execute(sql, list(row_dict.values()))
                # llm_run 表特殊处理：v2.0 加 input_text/output_text
                elif table == "llm_run":
                    row_dict = dict(zip(cols, row))
                    row_dict.setdefault("input_text", "")
                    row_dict.setdefault("output_text", "")
                    placeholders = ",".join(["%s"] * len(row_dict))
                    sql = f"INSERT INTO llm_run ({','.join(row_dict.keys())}) VALUES ({placeholders})"
                    pg_cur.execute(sql, list(row_dict.values()))
                else:
                    placeholders = ",".join(["%s"] * len(cols))
                    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
                    pg_cur.execute(sql, list(row))
            inserted += len(batch_rows)
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite → PostgreSQL 一次性数据迁移")
    parser.add_argument("--sqlite", required=True, help="SQLite db path (e.g. projects.db)")
    parser.add_argument("--pg-dsn", required=True, help="psycopg sync DSN (e.g. postgresql://user:pass@host:5432/db)")
    parser.add_argument("--batch", type=int, default=1000)
    args = parser.parse_args()

    if not Path(args.sqlite).exists():
        print(f"ERROR: SQLite file not found: {args.sqlite}", file=sys.stderr)
        return 1

    print(f"== 打开 SQLite: {args.sqlite}")
    sqlite_conn = sqlite3.connect(args.sqlite)
    sqlite_conn.row_factory = sqlite3.Row

    print(f"== 连接 PG: {args.pg_dsn}")
    pg_conn = psycopg.connect(args.pg_dsn, autocommit=False)

    total = 0
    try:
        for table in TABLE_ORDER:
            try:
                count = migrate_table(sqlite_conn, pg_conn, table, args.batch)
                print(f"  ✓ {table}: {count} 行")
                total += count
            except Exception as e:
                print(f"  ✗ {table}: {e}", file=sys.stderr)
                pg_conn.rollback()
                return 1
        pg_conn.commit()
        print(f"\n== 迁移完成：{total} 行")
    finally:
        sqlite_conn.close()
        pg_conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
