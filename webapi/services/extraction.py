"""extraction 域 service（Phase 2.2 包装 app.engineering）"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.engineering.extractor import extract_and_store_engineering_objects
from webapi.services.base import NotFoundError, ServiceError


async def run_extraction(
    db: AsyncSession,
    project_id: int,
    sheet_id: int,
    layer_rules: dict | None = None,
) -> dict[str, Any]:
    """触发工程对象提取（设备/线性/面积 三类）

    包装 app.engineering.extractor.extract_and_store_engineering_objects
    """
    try:
        result = extract_and_store_engineering_objects(
            project_id=project_id,
            sheet_id=sheet_id,
            layer_rules=layer_rules or {},
        )
        return {
            "project_id": project_id,
            "sheet_id": sheet_id,
            "created": result.get("created", 0),
            "stats": result.get("stats", {}),
            "object_ids": result.get("object_ids", []),
        }
    except Exception as e:
        raise ServiceError(f"Extraction failed: {e}", code="extraction_error")


async def list_engineering_objects(
    db: AsyncSession,
    project_id: int,
    sheet_id: int | None = None,
    object_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """列出工程对象（Phase 2 占位：直接读 engineering_object 表）"""
    from sqlalchemy import text

    sql = "SELECT id, project_id, sheet_id, object_type, discipline, system, block_name, layer_name, specification, unit, quantity_rule, confidence, source FROM engineering_object WHERE project_id = :pid"
    args: dict[str, Any] = {"pid": project_id}
    if sheet_id is not None:
        sql += " AND sheet_id = :sid"
        args["sid"] = sheet_id
    if object_type:
        sql += " AND object_type = :ot"
        args["ot"] = object_type
    sql += f" LIMIT {int(limit)}"
    result = await db.execute(text(sql), args)
    return [dict(row._mapping) for row in result]
