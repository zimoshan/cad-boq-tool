"""/api/dataset 路由（P0-22，#3 测试数据通路占位）"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from webapi.auth.decorators import requires
from webapi.config import get_settings
from webapi.db import get_db
from webapi.schemas.dataset import TestDataEntry
from webapi.services import dataset as dataset_service

router = APIRouter(prefix="/api/dataset", tags=["dataset"])


class MarkRequest(BaseModel):
    name: str
    project_id: int
    file_path: str
    data_type: str
    note: str = ""


class DeactivateRequest(BaseModel):
    entry_id: str


@router.get("")
@requires("dataset:read")
async def list_entries() -> dict:
    """列出已标记的测试数据"""
    entries = dataset_service.list_entries()
    return {
        "entries": entries,
        "total": len(entries),
        "registry_path": get_settings().test_data_registry_path,
    }


@router.post("/mark")
@requires("dataset:write")
async def mark(req: MarkRequest) -> dict:
    """手动标记一条测试数据（#3 决策：开发完用户手动标记作为测试数据输入）"""
    entry = dataset_service.mark_entry(
        name=req.name,
        project_id=req.project_id,
        file_path=req.file_path,
        data_type=req.data_type,
        note=req.note,
    )
    return entry


@router.post("/deactivate")
@requires("dataset:write")
async def deactivate(req: DeactivateRequest) -> dict:
    """停用一条测试数据"""
    ok = dataset_service.deactivate_entry(req.entry_id)
    return {"ok": ok, "entry_id": req.entry_id}
