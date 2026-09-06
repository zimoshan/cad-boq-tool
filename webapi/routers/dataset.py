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


# v1.0 §8 manifest 端点
@router.get("/manifests")
@requires("dataset:read")
async def list_manifests() -> dict:
    """v1.0 §8 列出所有 dataset 目录"""
    datasets = dataset_service.list_datasets()
    return {"datasets": datasets, "total": len(datasets)}


@router.get("/manifest")
@requires("dataset:read")
async def get_manifest(dataset_id: str = "lbh") -> dict:
    """v1.0 §8 读指定 dataset 的 manifest.json"""
    manifest = dataset_service.load_manifest(dataset_id)
    if not manifest:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Manifest for {dataset_id} not found")
    missing = dataset_service.validate_manifest(manifest)
    return {"manifest": manifest, "missing_fields": missing, "valid": not missing}


class ManifestUpdateRequest(BaseModel):
    dataset_id: str = "lbh"
    key: str
    value: str  # schema_version / parser_version / source_revision 等字符串


@router.post("/manifest")
@requires("dataset:write")
async def update_manifest(req: ManifestUpdateRequest) -> dict:
    """v1.0 §8 更新 manifest 单字段"""
    try:
        manifest = dataset_service.update_manifest_field(req.dataset_id, req.key, req.value)
    except Exception as e:
        from webapi.services.base import ServiceError
        raise ServiceError(str(e), code="manifest_update_error")
    if not manifest:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Manifest not found")
    return {"updated": True, "manifest": manifest}
