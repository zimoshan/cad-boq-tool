"""CAD 域 Service（包装 app/cad 业务函数）

Phase 0：
  - POST /api/cad/parse：上传 DWG/DXF → 解析 → 入库
  - GET  /api/cad/viewport?bbox=...：B4 空间查询
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cad.cad_parser import parse_dxf
from app.cad.reader import read_cad
from webapi.config import get_settings
from webapi.services.base import NotFoundError, ServiceError


async def parse_cad_file(
    db: AsyncSession,
    project_id: int,
    file_path: str,
) -> dict[str, Any]:
    """Phase 0 占位：解析 CAD 文件并入库

    #19 选 A：算法保留（read_cad + parse_dxf），入口重写
    完整实现待 A.2 第 2 批 P0-6~P0-9 落地
    """
    settings = get_settings()
    if not Path(file_path).exists():
        raise NotFoundError("File", file_path)

    try:
        # 包装 app/cad/reader.read_cad
        doc = read_cad(file_path)
        # 包装 app/cad/cad_parser.parse_dxf
        parsed = parse_dxf(file_path)
    except Exception as e:
        raise ServiceError(f"CAD parse failed: {e}", code="cad_parse_error")

    return {
        "project_id": project_id,
        "file_path": file_path,
        "entity_count": len(parsed.entities),
        "layer_count": len(parsed.layers),
    }


async def query_viewport(
    db: AsyncSession,
    sheet_id: int,
    bbox: tuple[float, float, float, float],  # (min_x, min_y, max_x, max_y)
    limit: int = 10000,
) -> list[dict[str, Any]]:
    """B4 空间查询：返回 bbox 内的 entity

    利用 PostGIS geometry GIST 索引（B4 修正）
    """
    min_x, min_y, max_x, max_y = bbox
    sql = text("""
        SELECT id, handle, dxf_type, layer, block_name,
               ST_AsText(geometry) AS geom_wkt,
               length, area
        FROM entity
        WHERE sheet_id = :sheet_id
          AND geometry && ST_MakeEnvelope(:min_x, :min_y, :max_x, :max_y, 0)
        LIMIT :limit
    """)
    result = await db.execute(
        sql,
        {"sheet_id": sheet_id, "min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y, "limit": limit},
    )
    return [dict(row._mapping) for row in result]
