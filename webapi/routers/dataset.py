"""/api/dataset 路由（P0-22 + P1-2，#3 测试数据通路）

P1-2 增强：DB 后端（alembic 0003 test_data_registry）优先，JSON 本地 fallback
由 TEST_DATA_BACKEND env 切换（默认 json，向后兼容）
"""
# 不使用 from __future__ import annotations：Pydantic 2.8 + FastAPI 0.115 forward ref 解析问题
import os

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
    entry_id: int  # P1-2 改 int（DB 主键）


def _use_db() -> bool:
    return os.environ.get("TEST_DATA_BACKEND", "json").lower() == "db"


@router.get("")
@requires("dataset:read")
async def list_entries(db: AsyncSession = Depends(get_db)) -> dict:
    """列出已标记的测试数据（P1-2 支持 DB）"""
    if _use_db():
        entries = await dataset_service.list_entries_db(db)
    else:
        entries = dataset_service.list_entries_json()
    return {
        "entries": entries,
        "total": len(entries),
        "registry_path": get_settings().test_data_registry_path,
        "backend": "db" if _use_db() else "json",
    }


@router.post("/mark")
@requires("dataset:write")
async def mark(req: MarkRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """手动标记一条测试数据（#3 决策）"""
    if _use_db():
        return await dataset_service.mark_entry_db(
            db, req.name, req.project_id, req.file_path, req.data_type, req.note
        )
    return dataset_service.mark_entry_json(
        req.name, req.project_id, req.file_path, req.data_type, req.note
    )


@router.post("/deactivate")
@requires("dataset:write")
async def deactivate(req: DeactivateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """停用一条测试数据"""
    if _use_db():
        ok = await dataset_service.deactivate_entry_db(db, req.entry_id)
    else:
        ok = dataset_service.deactivate_entry_json(req.entry_id)
    return {"ok": ok, "entry_id": req.entry_id}
