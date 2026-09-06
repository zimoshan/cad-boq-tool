"""测试数据通路 service（P1-2 DB 化版本）

Phase 0：JSON 文件存储（向后兼容）
Phase 1：PG test_data_registry 表为主，JSON 作本地 fallback

#3 决策：DWG/数据资产不自动入库，用户手动标记后存此表。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from webapi.config import get_settings
from webapi.services.base import ServiceError


# =============================================================================
# P1-2 ORM Model（同步 alembic 0003 迁移）
# =============================================================================

from webapi.db.base import Base
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class TestDataRegistry(Base):
    """测试数据注册表（alembic 0003）"""
    __tablename__ = "test_data_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    data_type: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), server_default="sysadmin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# =============================================================================
# 存储抽象：自动选 DB 或 JSON（按 TEST_DATA_BACKEND env）
# =============================================================================


def _get_registry_path() -> Path:
    settings = get_settings()
    p = Path(settings.test_data_registry_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read_json() -> dict[str, Any]:
    path = _get_registry_path()
    if not path.exists():
        return {"entries": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"entries": []}


def _write_json(data: dict[str, Any]) -> None:
    _get_registry_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- DB 后端（PG 优先） ----------

async def list_entries_db(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(select(TestDataRegistry).order_by(TestDataRegistry.created_at.desc()))
    return [
        {
            "id": e.id,
            "name": e.name,
            "project_id": e.project_id,
            "file_path": e.file_path,
            "data_type": e.data_type,
            "note": e.note,
            "is_active": e.is_active,
            "created_by": e.created_by,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in result.scalars().all()
    ]


async def mark_entry_db(
    db: AsyncSession,
    name: str,
    project_id: int,
    file_path: str,
    data_type: str,
    note: str = "",
    created_by: str = "sysadmin",
) -> dict[str, Any]:
    if data_type not in ("drawing", "boq", "json"):
        raise ServiceError(f"Invalid data_type: {data_type}", code="invalid_data_type")
    if not Path(file_path).exists():
        raise ServiceError(f"File not found: {file_path}", code="file_not_found")

    entry = TestDataRegistry(
        name=name,
        project_id=project_id,
        file_path=file_path,
        data_type=data_type,
        note=note,
        is_active=True,
        created_by=created_by,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {
        "id": entry.id,
        "name": entry.name,
        "project_id": entry.project_id,
        "file_path": entry.file_path,
        "data_type": entry.data_type,
        "note": entry.note,
        "is_active": entry.is_active,
        "created_by": entry.created_by,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


async def deactivate_entry_db(db: AsyncSession, entry_id: int) -> bool:
    result = await db.execute(select(TestDataRegistry).where(TestDataRegistry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        return False
    entry.is_active = False
    await db.commit()
    return True


async def get_active_entries_db(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(
        select(TestDataRegistry).where(TestDataRegistry.is_active == True).order_by(TestDataRegistry.id)  # noqa: E712
    )
    return [
        {
            "id": e.id,
            "name": e.name,
            "file_path": e.file_path,
            "data_type": e.data_type,
        }
        for e in result.scalars().all()
    ]


# ---------- JSON 后端（本地 fallback，向后兼容） ----------

def list_entries_json() -> list[dict[str, Any]]:
    return _read_json().get("entries", [])


def mark_entry_json(
    name: str, project_id: int, file_path: str, data_type: str, note: str = "", created_by: str = "sysadmin"
) -> dict[str, Any]:
    if data_type not in ("drawing", "boq", "json"):
        raise ServiceError(f"Invalid data_type: {data_type}", code="invalid_data_type")
    if not Path(file_path).exists():
        raise ServiceError(f"File not found: {file_path}", code="file_not_found")
    data = _read_json()
    entry = {
        "id": len(data["entries"]) + 1,
        "name": name,
        "project_id": project_id,
        "file_path": file_path,
        "data_type": data_type,
        "note": note,
        "is_active": True,
        "created_by": created_by,
        "created_at": datetime.now().isoformat(),
    }
    data["entries"].append(entry)
    _write_json(data)
    return entry


def deactivate_entry_json(entry_id: int) -> bool:
    data = _read_json()
    for e in data["entries"]:
        if e.get("id") == entry_id:
            e["is_active"] = False
            _write_json(data)
            return True
    return False


def get_active_entries_json() -> list[dict[str, Any]]:
    return [e for e in list_entries_json() if e.get("is_active", True)]


# ---------- 统一接口（自动选后端，TEST_DATA_BACKEND=db/json，default=json 向后兼容） ----------

import os

def _backend() -> str:
    return os.environ.get("TEST_DATA_BACKEND", "json").lower()


def list_entries(db: AsyncSession | None = None) -> list[dict[str, Any]]:
    if _backend() == "db" and db is not None:
        return []  # async version is list_entries_db; caller uses router async path
    return list_entries_json()


async def list_entries_async(db: AsyncSession) -> list[dict[str, Any]]:
    if _backend() == "db":
        return await list_entries_db(db)
    return list_entries_json()
