"""数据库瘦身脚本：分析孤儿数据 + VACUUM。

用法：python cleanup_db.py [--dry-run]
  --dry-run  只分析不清理（默认行为）
  无参数      执行清理 + VACUUM
"""
import sqlite3
import sys
import os
from pathlib import Path

DB_PATH = Path.home() / ".cad-boq-tool" / "projects.db"


def analyze(conn):
    """分析数据库状态，返回报告"""
    report = {}
    cur = conn.cursor()

    # 基础统计
    report["db_size_mb"] = round(os.path.getsize(DB_PATH) / 1024 / 1024, 2)
    report["entity_rows"] = cur.execute("SELECT COUNT(*) FROM entity").fetchone()[0]
    report["sheet_rows"] = cur.execute("SELECT COUNT(*) FROM sheet").fetchone()[0]
    report["project_rows"] = cur.execute("SELECT COUNT(*) FROM project").fetchone()[0]

    # 孤儿实体（sheet_id 指向不存在的图纸）
    report["orphan_entities"] = cur.execute(
        "SELECT COUNT(*) FROM entity WHERE sheet_id NOT IN (SELECT id FROM sheet)"
    ).fetchone()[0]

    # 孤儿图纸（project_id 指向不存在的项目）
    report["orphan_sheets"] = cur.execute(
        "SELECT COUNT(*) FROM sheet WHERE project_id NOT IN (SELECT id FROM project)"
    ).fetchone()[0]

    # 孤儿 BOQ 条目
    report["orphan_boq"] = cur.execute(
        "SELECT COUNT(*) FROM boq_item WHERE project_id NOT IN (SELECT id FROM project)"
    ).fetchone()[0]

    # 孤儿映射
    report["orphan_mappings"] = cur.execute(
        "SELECT COUNT(*) FROM mapping WHERE boq_item_id NOT IN (SELECT id FROM boq_item)"
    ).fetchone()[0]

    # geom_json 大小分析（采样前 1000 条）
    rows = cur.execute(
        "SELECT LENGTH(geom_json) FROM entity WHERE geom_json != '' LIMIT 1000"
    ).fetchall()
    if rows:
        sizes = [r[0] for r in rows]
        report["geom_json_avg_bytes"] = round(sum(sizes) / len(sizes), 0)
        report["geom_json_max_bytes"] = max(sizes)
        report["geom_json_total_est_mb"] = round(
            sum(sizes) / len(sizes) * report["entity_rows"] / 1024 / 1024, 2)

    # 按图纸统计实体数
    sheet_stats = cur.execute(
        "SELECT s.filename, COUNT(e.id) as cnt FROM sheet s "
        "LEFT JOIN entity e ON e.sheet_id = s.id "
        "GROUP BY s.id ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    report["top_sheets"] = [(r[0], r[1]) for r in sheet_stats]

    return report


def cleanup(conn):
    """清理孤儿数据"""
    cur = conn.cursor()
    deleted = {}

    # 1. 清理孤儿实体
    cur.execute("DELETE FROM entity WHERE sheet_id NOT IN (SELECT id FROM sheet)")
    deleted["orphan_entities"] = cur.rowcount

    # 2. 清理孤儿映射
    cur.execute("DELETE FROM mapping WHERE boq_item_id NOT IN (SELECT id FROM boq_item)")
    deleted["orphan_mappings"] = cur.rowcount

    # 3. 清理孤儿 BOQ
    cur.execute("DELETE FROM boq_item WHERE project_id NOT IN (SELECT id FROM project)")
    deleted["orphan_boq"] = cur.rowcount

    # 4. 清理孤儿工程对象
    cur.execute("DELETE FROM engineering_object WHERE project_id NOT IN (SELECT id FROM project)")
    deleted["orphan_eo"] = cur.rowcount

    # 5. 清理孤儿绑定候选
    cur.execute("DELETE FROM binding_candidate WHERE project_id NOT IN (SELECT id FROM project)")
    deleted["orphan_candidates"] = cur.rowcount

    # 6. 清理孤儿 LLM 审计
    cur.execute("DELETE FROM llm_run WHERE project_id NOT IN (SELECT id FROM project)")
    deleted["orphan_llm_runs"] = cur.rowcount

    conn.commit()
    return deleted


def main():
    dry_run = "--dry-run" in sys.argv
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    print("=== 数据库分析 ===")
    report = analyze(conn)
    print(f"文件大小: {report['db_size_mb']} MB")
    print(f"实体行数: {report['entity_rows']:,}")
    print(f"图纸数量: {report['sheet_rows']}")
    print(f"项目数量: {report['project_rows']}")
    print(f"\n--- 孤儿数据 ---")
    print(f"孤儿实体: {report['orphan_entities']:,}")
    print(f"孤儿图纸: {report['orphan_sheets']}")
    print(f"孤儿 BOQ: {report['orphan_boq']}")
    print(f"孤儿映射: {report['orphan_mappings']}")
    if "geom_json_avg_bytes" in report:
        print(f"\n--- geom_json 分析 ---")
        print(f"平均大小: {report['geom_json_avg_bytes']} bytes")
        print(f"最大大小: {report['geom_json_max_bytes']} bytes")
        print(f"估算总占用: {report['geom_json_total_est_mb']} MB")
    print(f"\n--- 实体数最多的图纸 ---")
    for fname, cnt in report["top_sheets"]:
        print(f"  {fname}: {cnt:,}")

    if dry_run:
        print("\n[dry-run] 不执行清理。去掉 --dry-run 参数可执行清理。")
        conn.close()
        return

    # 执行清理
    has_orphans = any([
        report["orphan_entities"],
        report["orphan_sheets"],
        report["orphan_boq"],
        report["orphan_mappings"],
    ])

    if not has_orphans:
        print("\n没有孤儿数据，无需清理。")
        conn.close()
        return

    print(f"\n=== 执行清理 ===")
    deleted = cleanup(conn)
    for k, v in deleted.items():
        if v > 0:
            print(f"  删除 {k}: {v:,}")

    # VACUUM 压缩数据库文件
    print(f"\n=== VACUUM 压缩 ===")
    size_before = os.path.getsize(DB_PATH)
    conn.execute("VACUUM")
    size_after = os.path.getsize(DB_PATH)
    saved_mb = round((size_before - size_after) / 1024 / 1024, 2)
    print(f"清理前: {round(size_before / 1024 / 1024, 2)} MB")
    print(f"清理后: {round(size_after / 1024 / 1024, 2)} MB")
    print(f"释放空间: {saved_mb} MB")

    conn.close()
    print("\n完成！")


if __name__ == "__main__":
    main()
