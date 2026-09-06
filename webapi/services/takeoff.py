"""takeoff 域 service（Phase 2.2 包装 app.takeoff）

takeoff 管线：扫描文件夹/单图 → aggregate → LLM 分类 → 跨图去重 → EO 写入
"""

from __future__ import annotations

from typing import Any

from app.takeoff.folder_pipeline import run_folder_pipeline
from app.takeoff.orchestrator import takeoff_pipeline
from webapi.services.base import ServiceError


async def run_single_sheet_takeoff(
    db: Any,
    project_id: int,
    sheet_id: int,
) -> dict[str, Any]:
    """单图 takeoff（6 阶段管线）"""
    try:
        result = takeoff_pipeline(project_id=project_id, sheet_id=sheet_id)
        return {
            "project_id": project_id,
            "sheet_id": sheet_id,
            "result": result,
        }
    except Exception as e:
        raise ServiceError(f"Takeoff failed: {e}", code="takeoff_error")


async def run_folder_takeoff(
    db: Any,
    project_id: int,
    folder_path: str,
) -> dict[str, Any]:
    """文件夹维度 takeoff（多图聚合）"""
    if not folder_path:
        raise ServiceError("folder_path required", code="invalid_input")
    try:
        result = run_folder_pipeline(project_id=project_id, folder_path=folder_path)
        return {
            "project_id": project_id,
            "folder_path": folder_path,
            "result": result,
        }
    except Exception as e:
        raise ServiceError(f"Folder takeoff failed: {e}", code="takeoff_error")
