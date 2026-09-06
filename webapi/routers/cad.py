"""/api/cad 路由（CAD 解析 + 视口查询）"""
# 不使用 from __future__ import annotations：Pydantic 2.8 + FastAPI 0.115 forward ref 解析问题
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from webapi.auth.decorators import requires
from webapi.db import get_db
from webapi.schemas.cad import ParseRequest, ParseResponse, ViewportQuery
from webapi.services import cad as cad_service

router = APIRouter(prefix="/api/cad", tags=["cad"])


@router.post("/parse", response_model=ParseResponse)
@requires("cad:parse")
async def parse_cad(req: ParseRequest, db: AsyncSession = Depends(get_db)) -> ParseResponse:
    """解析 DWG/DXF（Phase 0 占位，完整实现待 A.2 第 2 批）"""
    result = await cad_service.parse_cad_file(db, req.project_id, req.file_path)
    return ParseResponse(**result)


@router.post("/viewport")
@requires("cad:viewport")
async def viewport(query: ViewportQuery, db: AsyncSession = Depends(get_db)) -> dict:
    """B4 空间查询：bbox 范围内 entity 列表"""
    bbox = (query.min_x, query.min_y, query.max_x, query.max_y)
    rows = await cad_service.query_viewport(db, query.sheet_id, bbox, query.limit)
    return {"items": rows, "total": len(rows)}
