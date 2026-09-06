"""/api/audit 路由（Phase 2.2）"""
# 不使用 from __future__ import annotations：Pydantic 2.8 + FastAPI 0.115 forward ref 解析问题
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from webapi.auth.decorators import requires
from webapi.db import get_db
from webapi.schemas.audit import OverviewResponse
from webapi.services import audit as audit_service

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/llm-runs")
@requires("audit:read")
async def list_llm_runs(
    project_id: int,
    task_type: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """读 llm_run 审计表（按 project_id + task_type 过滤）"""
    rows = await audit_service.list_llm_runs(db, project_id, task_type, limit)
    return {"items": rows, "total": len(rows)}


@router.get("/overview", response_model=OverviewResponse)
@requires("audit:read")
async def get_overview(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> OverviewResponse:
    """项目总览（boq_count / eo_breakdown / writeback_by_takability / llm_runs_by_task）"""
    data = await audit_service.get_overview(db, project_id)
    return OverviewResponse(**data)
