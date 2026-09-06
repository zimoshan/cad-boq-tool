"""/api/boq 路由（Excel 解析 + 回写）"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from webapi.auth.decorators import requires
from webapi.db import get_db
from webapi.schemas.boq import (
    ParseBoqRequest,
    ParseBoqResponse,
    WritebackRequest,
    WritebackResponse,
)
from webapi.services import boq as boq_service

router = APIRouter(prefix="/api/boq", tags=["boq"])


@router.post("/parse", response_model=ParseBoqResponse)
@requires("boq:parse")
async def parse_boq(req: ParseBoqRequest, db: AsyncSession = Depends(get_db)) -> ParseBoqResponse:
    """解析 BOQ Excel（B1 修复：4 种表头识别，A.2 第 2 批 P0-6 落实）"""
    result = await boq_service.parse_boq_excel(db, req.project_id, req.file_path)
    return ParseBoqResponse(**result)


@router.post("/writeback", response_model=WritebackResponse)
@requires("boq:writeback")
async def writeback(req: WritebackRequest, db: AsyncSession = Depends(get_db)) -> WritebackResponse:
    """回写 measured_qty（B5 S7 Excel 保真回写，P0-15 落实）"""
    result = await boq_service.writeback_quantities(db, req.project_id, req.project_scale)
    return WritebackResponse(**result)
