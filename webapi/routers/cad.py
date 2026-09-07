"""/api/cad 路由（CAD 解析 + 视口查询 + v1.0 §13 4 端点）"""

# 不使用 from __future__ import annotations：Pydantic 2.8 + FastAPI 0.115 forward ref 解析问题
from fastapi import APIRouter, Depends, HTTPException
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
    """B4 空间查询：bbox 范围内 entity 列表

    include_geom=false（前端 LOD0 概览）：只回 bbox 元数据，payload 减半。
    """
    bbox = (query.min_x, query.min_y, query.max_x, query.max_y)
    rows = await cad_service.query_viewport(db, query.sheet_id, bbox, query.limit, query.include_geom)
    return {"items": rows, "total": len(rows)}


# v1.0 §13 4 端点
@router.get("/sheets")
@requires("cad:read")
async def get_sheets(project_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Phase 3：项目下图纸列表（图纸选择器）"""
    rows = await cad_service.list_sheets(db, project_id)
    return {"items": rows, "total": len(rows)}


@router.get("/metadata")
@requires("cad:read")
async def get_metadata(sheet_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """v1.0 §13 GET /api/cad/metadata：图纸元数据 + drawing_type/units/level/zone/revision"""
    data = await cad_service.get_sheet_metadata(db, sheet_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Sheet {sheet_id} not found")
    return data


@router.get("/layers")
@requires("cad:read")
async def get_layers(sheet_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """v1.0 §13 GET /api/cad/layers：图层列表 + entity_count"""
    rows = await cad_service.get_sheet_layers(db, sheet_id)
    return {"items": rows, "total": len(rows)}


@router.get("/blocks")
@requires("cad:read")
async def get_blocks(sheet_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """v1.0 §13 GET /api/cad/blocks：块列表（INSERT block_name）+ insert_count"""
    rows = await cad_service.get_sheet_blocks(db, sheet_id)
    return {"items": rows, "total": len(rows)}


@router.get("/entities")
@requires("cad:read")
async def get_entities(
    sheet_id: int,
    layer: str | None = None,
    block_name: str | None = None,
    dxf_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """v1.0 §13 GET /api/cad/entities：分页列 entity（layer/block/dxf_type 过滤）"""
    rows = await cad_service.list_entities(db, sheet_id, layer, block_name, dxf_type, limit, offset)
    return {"items": rows, "limit": limit, "offset": offset}
