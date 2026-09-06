"""/api/extraction 路由（Phase 2.2）"""

# 不使用 from __future__ import annotations：Pydantic 2.8 + FastAPI 0.115 forward ref 解析问题
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from webapi.auth.decorators import requires
from webapi.db import get_db
from webapi.schemas.extraction import EngineeringObjectRead, ExtractionRequest, ExtractionResponse
from webapi.services import extraction as extraction_service

router = APIRouter(prefix="/api/extraction", tags=["extraction"])


@router.post("/run", response_model=ExtractionResponse)
@requires("extraction:run")
async def run_extraction(req: ExtractionRequest, db: AsyncSession = Depends(get_db)) -> ExtractionResponse:
    """触发工程对象提取（设备/线性/面积 三类）"""
    result = await extraction_service.run_extraction(db, req.project_id, req.sheet_id, req.layer_rules)
    return ExtractionResponse(**result)


@router.get("/eos", response_model=list[EngineeringObjectRead])
@requires("extraction:read")
async def list_eos(
    project_id: int,
    sheet_id: int | None = None,
    object_type: str | None = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """列出工程对象（可按 sheet_id / object_type 过滤）"""
    rows = await extraction_service.list_engineering_objects(db, project_id, sheet_id, object_type, limit)
    return rows
