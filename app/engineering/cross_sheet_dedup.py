"""B5 S5 跨图去重并集（v2.0 §2.5 / §5.3，2026-09-06）

思路（参考 [v2.0 §1.3](docs/CAD_BOQ_Web化_架构设计_v2.0.md) _tray_pts.json）：
  - 同一项目多张图共享同一图块（INSERT 块名相同）
  - 跨图块按 block_name 分组，按 entity_ids 集合判断是否同一物理对象
  - 同 block_name + 位置 bbox 重叠 ≥50% → 视为同一对象，只计量一次

存储：cross_sheet_dedup 表（alembic 0002 迁移）
  - project_id, block_name, sheet_ids[], merged_entity_ids[], dedup_method, confidence

接口：
  - dedup_engineering_objects(project_id) → dict: 跨图去重结果 + 合并 EO
  - add_dedup_record(...)
  - get_dedup_records(project_id) → list
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


def _bbox_overlap_ratio(b1, b2) -> float:
    """两个 bbox (min_x, min_y, max_x, max_y) 重叠面积 / 较小面积"""
    if not b1 or not b2 or len(b1) < 4 or len(b2) < 4:
        return 0.0
    try:
        x1 = max(b1[0], b2[0])
        y1 = max(b1[1], b2[1])
        x2 = min(b1[2], b2[2])
        y2 = min(b1[3], b2[3])
        if x2 <= x1 or y2 <= y1:
            return 0.0
        overlap = (x2 - x1) * (y2 - y1)
        a1 = max(1e-6, (b1[2] - b1[0]) * (b1[3] - b1[1]))
        a2 = max(1e-6, (b2[2] - b2[0]) * (b2[3] - b2[1]))
        return overlap / min(a1, a2)
    except (TypeError, ValueError, IndexError):
        return 0.0


def dedup_engineering_objects(project_id: int, eos: list | None = None) -> dict[str, Any]:
    """B5 S5：跨图去重并集（EO 是 app.engineering.object_model.EngineeringObject 列表）

    简化实现：按 block_name 分组，组内两两比较 bbox 重叠率。
    重叠 ≥0.5 → 视为同一对象，归入 dedup 集合（合并 entity_ids + 选最高 confidence）。
    """
    if eos is None:
        from .object_model import get_engineering_objects
        eos = get_engineering_objects(project_id)

    # 按 block_name 分组
    groups: dict[str, list] = defaultdict(list)
    for eo in eos:
        if eo.block_name:
            groups[eo.block_name].append(eo)

    dedup_records: list[dict[str, Any]] = []
    kept_eos: list = []
    merged_eo_ids: set[int] = set()

    for block_name, group in groups.items():
        if len(group) < 2:
            # 单一图块无需去重
            kept_eos.extend(group)
            continue

        # 简化聚类：贪心按 bbox 相似度合并
        clusters: list[list] = []
        for eo in sorted(group, key=lambda e: (-e.confidence, e.id)):
            placed = False
            for cluster in clusters:
                # 簇内任意一个 bbox 与当前重叠 ≥0.5 → 归入同簇
                if any(_bbox_overlap_ratio(getattr(c, "bbox", None) or _extract_bbox(c), _extract_bbox(eo)) >= 0.5
                       for c in cluster):
                    cluster.append(eo)
                    placed = True
                    break
            if not placed:
                clusters.append([eo])

        for cluster in clusters:
            if len(cluster) == 1:
                kept_eos.append(cluster[0])
                continue
            # 合并：选 confidence 最高为 canonical，entity_ids 合并
            canonical = max(cluster, key=lambda e: e.confidence)
            merged_ids = []
            sheet_ids = set()
            for c in cluster:
                merged_ids.extend(c.entity_ids or [])
                sheet_ids.add(c.sheet_id)
            merged_ids = list(set(merged_ids))
            canonical.entity_ids = merged_ids
            kept_eos.append(canonical)
            for c in cluster:
                if c.id != canonical.id:
                    merged_eo_ids.add(c.id)
            dedup_records.append({
                "project_id": project_id,
                "block_name": block_name,
                "sheet_ids": sorted(sheet_ids),
                "merged_entity_ids": merged_ids,
                "merged_eo_count": len(cluster),
                "canonical_eo_id": canonical.id,
                "dedup_method": "bbox_overlap",
                "confidence": canonical.confidence,
            })

    return {
        "project_id": project_id,
        "kept_eos": kept_eos,
        "merged_eo_ids": list(merged_eo_ids),
        "dedup_records": dedup_records,
        "stats": {
            "input_eos": len(eos),
            "kept_eos": len(kept_eos),
            "merged_eos": len(merged_eo_ids),
            "dedup_clusters": len(dedup_records),
        },
    }


def _extract_bbox(eo) -> tuple:
    """从 EO 提取 bbox（EO 无独立 bbox 字段，从 entity_ids 反查 entity 表）"""
    if hasattr(eo, "bbox") and eo.bbox:
        return eo.bbox
    if not eo.entity_ids:
        return ()
    from .. import db
    rows = db.get_entities_by_ids(eo.entity_ids)
    if not rows:
        return ()
    xs, ys = [], []
    for r in rows:
        b = r.get("bbox") if isinstance(r, dict) else None
        if not b:
            continue
        try:
            v = json.loads(b) if isinstance(b, str) else b
            if len(v) == 4:
                xs.extend([v[0], v[2]])
                ys.extend([v[1], v[3]])
        except (json.JSONDecodeError, TypeError):
            continue
    if not xs:
        return ()
    return (min(xs), min(ys), max(xs), max(ys))


def get_dedup_records(project_id: int) -> list[dict[str, Any]]:
    """读 cross_sheet_dedup 表（Phase 0 占位，DB 表由 alembic 0002 创建）"""
    try:
        from .. import db
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM cross_sheet_dedup WHERE project_id=?",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
