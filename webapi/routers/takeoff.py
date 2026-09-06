"""/api/takeoff 路由（Phase 2.2）"""

# 不使用 from __future__ import annotations：Pydantic 2.8 + FastAPI 0.115 forward ref 解析问题
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from webapi.auth.decorators import requires
from webapi.db import get_db
from webapi.schemas.takeoff import TakeoffRequest, TakeoffResponse
from webapi.services import takeoff as takeoff_service

router = APIRouter(prefix="/api/takeoff", tags=["takeoff"])


@router.post("/run", response_model=TakeoffResponse)
@requires("takeoff:run")
async def run_takeoff(req: TakeoffRequest, db: AsyncSession = Depends(get_db)) -> TakeoffResponse:
    """触发 AI 算量（单图或文件夹维度）"""
    if req.folder_path:
        result = await takeoff_service.run_folder_takeoff(db, req.project_id, req.folder_path)
    else:
        result = await takeoff_service.run_single_sheet_takeoff(db, req.project_id, req.sheet_id or 0)
    return TakeoffResponse(**result)
