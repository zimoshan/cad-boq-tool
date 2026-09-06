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
