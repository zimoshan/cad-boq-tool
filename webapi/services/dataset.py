"""测试数据通路 service（P0-22，#3 决策）

Phase 0 占位：JSON 文件存储 + 内存缓存
Phase 1 完整：DB 表 + 自动化加载

#3 决策：Dataset/DWG 先不入库，开发完用户手动标记作为测试数据。
本 service 提供手动标记/列表/读取接口。
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from webapi.config import get_settings
from webapi.services.base import ServiceError


def _get_registry_path() -> Path:
    settings = get_settings()
    p = Path(settings.test_data_registry_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read_registry() -> dict[str, Any]:
    path = _get_registry_path()
    if not path.exists():
        return {"entries": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"entries": []}


def _write_registry(data: dict[str, Any]) -> None:
    path = _get_registry_path()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_entries() -> list[dict[str, Any]]:
    """列出已标记的测试数据"""
    return _read_registry().get("entries", [])


def mark_entry(name: str, project_id: int, file_path: str, data_type: str, note: str = "") -> dict[str, Any]:
    """手动标记一条测试数据"""
    if data_type not in ("drawing", "boq", "json"):
        raise ServiceError(f"Invalid data_type: {data_type}", code="invalid_data_type")
    if not Path(file_path).exists():
        raise ServiceError(f"File not found: {file_path}", code="file_not_found")

    data = _read_registry()
    entry = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "project_id": project_id,
        "file_path": file_path,
        "data_type": data_type,
        "note": note,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    }
    data["entries"].append(entry)
    _write_registry(data)
    return entry


def deactivate_entry(entry_id: str) -> bool:
    """停用一条测试数据"""
    data = _read_registry()
    for e in data["entries"]:
        if e.get("id") == entry_id:
            e["is_active"] = False
            _write_registry(data)
            return True
    return False


def get_active_entries() -> list[dict[str, Any]]:
    """仅返回启用的测试数据（业务期自动加载用）"""
    return [e for e in list_entries() if e.get("is_active", True)]
