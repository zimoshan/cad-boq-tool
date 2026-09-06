"""audit 域 service（Phase 2.2 包装 app.llm.audit + 业务期统计查询）"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.audit import log_llm_call
from webapi.services.base import ServiceError


async def list_llm_runs(
    db: AsyncSession,
    project_id: int,
    task_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """读 llm_run 审计表"""
    sql = "SELECT id, project_id, task_type, model, model_version, prompt_version, temperature, duration_ms, token_input, token_output, status, error, created_at FROM llm_run WHERE project_id = :pid"
    args: dict[str, Any] = {"pid": project_id}
    if task_type:
        sql += " AND task_type = :tt"
        args["tt"] = task_type
    sql += f" ORDER BY created_at DESC LIMIT {int(limit)}"
    result = await db.execute(text(sql), args)
    return [dict(row._mapping) for row in result]


async def get_overview(
    db: AsyncSession,
    project_id: int,
) -> dict[str, Any]:
    """跨专业总览（Phase 2 占位：基础统计 + by_takability + by_discipline）

    完整 dataviz 集成留 Phase 6 跨专业总览页
    """
    sql_boq = text("SELECT COUNT(*) AS n FROM boq_item WHERE project_id = :pid")
    sql_eo = text("SELECT COUNT(*) AS n, object_type, discipline FROM engineering_object WHERE project_id = :pid GROUP BY object_type, discipline")
    sql_mapping = text("SELECT COUNT(*) AS n FROM mapping WHERE boq_item_id IN (SELECT id FROM boq_item WHERE project_id = :pid)")
    sql_writeback = text("SELECT takability, COUNT(*) AS n FROM writeback_audit WHERE project_id = :pid GROUP BY takability")
    sql_runs = text("SELECT task_type, COUNT(*) AS n, AVG(duration_ms) AS avg_ms FROM llm_run WHERE project_id = :pid GROUP BY task_type")

    boq_count = (await db.execute(sql_boq, {"pid": project_id})).scalar() or 0
    mapping_count = (await db.execute(sql_mapping, {"pid": project_id})).scalar() or 0
    eo_by_type_discipline = [dict(r._mapping) for r in (await db.execute(sql_eo, {"pid": project_id}))]
    writeback_by_takability = [dict(r._mapping) for r in (await db.execute(sql_writeback, {"pid": project_id}))]
    runs_by_task = [dict(r._mapping) for r in (await db.execute(sql_runs, {"pid": project_id}))]

    return {
        "project_id": project_id,
        "boq_count": boq_count,
        "mapping_count": mapping_count,
        "eo_breakdown": eo_by_type_discipline,
        "writeback_by_takability": writeback_by_takability,
        "llm_runs_by_task": runs_by_task,
    }


# v1.0 §29 预检 6 维度
async def get_precheck(
    db: AsyncSession,
    project_id: int,
) -> dict[str, Any]:
    """v1.0 §29 预检页面 6 维度

    1. drawing_type  2. takability  3. coverage  4. granularity  5. version  6. provisional
    """
    # 1. drawing_type 分布
    sql_dt = text("""SELECT drawing_type, COUNT(*) AS n FROM sheet WHERE project_id = :pid GROUP BY drawing_type""")
    drawing_type_breakdown = [dict(r._mapping) for r in (await db.execute(sql_dt, {"pid": project_id}))]

    # 2. takability 6 状态
    sql_tk = text("""SELECT takability, COUNT(*) AS n FROM writeback_audit WHERE project_id = :pid GROUP BY takability""")
    takability_breakdown = [dict(r._mapping) for r in (await db.execute(sql_tk, {"pid": project_id}))]

    # 3. coverage：mapping 数 / boq_item 数
    sql_cov = text("""SELECT
        (SELECT COUNT(*) FROM boq_item WHERE project_id = :pid) AS total_boq,
        (SELECT COUNT(DISTINCT boq_item_id) FROM mapping m JOIN boq_item b ON b.id = m.boq_item_id WHERE b.project_id = :pid) AS mapped_boq,
        (SELECT COUNT(*) FROM engineering_object WHERE project_id = :pid) AS total_eo""")
    cov = (await db.execute(sql_cov, {"pid": project_id})).first()
    coverage = {
        "total_boq": cov[0] if cov else 0,
        "mapped_boq": cov[1] if cov else 0,
        "total_eo": cov[2] if cov else 0,
        "boq_coverage_pct": round(cov[1] / cov[0] * 100, 1) if cov and cov[0] else 0,
        "eo_coverage_pct": round(cov[1] / cov[2] * 100, 1) if cov and cov[2] else 0,
    }

    # 4. granularity：sheet 数 + entity 平均
    sql_gr = text("""SELECT COUNT(*) AS n_sheet, COALESCE(AVG(entity_count), 0) AS avg_entity
                    FROM sheet WHERE project_id = :pid""")
    gr = (await db.execute(sql_gr, {"pid": project_id})).first()
    granularity = {
        "n_sheets": gr[0] if gr else 0,
        "avg_entity_per_sheet": round(gr[1], 1) if gr else 0,
    }

    # 5. version：revision 分布
    sql_ver = text("""SELECT revision, COUNT(*) AS n FROM sheet WHERE project_id = :pid AND revision != '' GROUP BY revision""")
    version_breakdown = [dict(r._mapping) for r in (await db.execute(sql_ver, {"pid": project_id}))]

    # 6. provisional：remark 含 [PROVISIONAL] 的 boq_item 数
    sql_prov = text("""SELECT COUNT(*) AS n FROM boq_item WHERE project_id = :pid AND remark LIKE '%[PROVISIONAL]%'""")
    provisional_count = (await db.execute(sql_prov, {"pid": project_id})).scalar() or 0

    return {
        "project_id": project_id,
        "drawing_type": drawing_type_breakdown,
        "takability": takability_breakdown,
        "coverage": coverage,
        "granularity": granularity,
        "version": version_breakdown,
        "provisional_count": provisional_count,
    }
