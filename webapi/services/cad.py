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


# =============================================================================
# v1.0 §13 4 端点支撑（metadata / layers / blocks / entities 独立查询）
# =============================================================================


async def get_sheet_metadata(db: AsyncSession, sheet_id: int) -> dict[str, Any] | None:
    """v1.0 §13 GET /api/cad/metadata：图纸元数据 + drawing_type/units/level/zone"""
    result = await db.execute(
        text("""SELECT id, project_id, filename, src_path, dxf_path, status, scale, entity_count, layer_count,
                       units, drawing_type, level, zone, revision, design_stage
                FROM sheet WHERE id = :id"""),
        {"id": sheet_id},
    )
    row = result.first()
    return dict(row._mapping) if row else None


async def get_sheet_layers(db: AsyncSession, sheet_id: int) -> list[dict[str, Any]]:
    """v1.0 §13 GET /api/cad/layers：图层列表 + entity_count + color"""
    result = await db.execute(
        text("""SELECT layer, dxf_type, COUNT(*) AS entity_count
                FROM entity WHERE sheet_id = :id GROUP BY layer, dxf_type ORDER BY entity_count DESC"""),
        {"id": sheet_id},
    )
    return [dict(row._mapping) for row in result]


async def get_sheet_blocks(db: AsyncSession, sheet_id: int) -> list[dict[str, Any]]:
    """v1.0 §13 GET /api/cad/blocks：块列表（INSERT block_name）+ count"""
    result = await db.execute(
        text("""SELECT block_name, COUNT(*) AS insert_count
                FROM entity
                WHERE sheet_id = :id AND block_name != '' AND dxf_type='INSERT'
                GROUP BY block_name ORDER BY insert_count DESC"""),
        {"id": sheet_id},
    )
    return [dict(row._mapping) for row in result]


async def list_entities(
    db: AsyncSession,
    sheet_id: int,
    layer: str | None = None,
    block_name: str | None = None,
    dxf_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """v1.0 §13 GET /api/cad/entities：分页列 entity（layer/block/dxf_type 过滤）"""
    sql = "SELECT id, handle, dxf_type, layer, block_name, length, area FROM entity WHERE sheet_id = :id"
    args: dict[str, Any] = {"id": sheet_id}
    if layer:
        sql += " AND layer = :layer"
        args["layer"] = layer
    if block_name:
        sql += " AND block_name = :bn"
        args["bn"] = block_name
    if dxf_type:
        sql += " AND dxf_type = :dt"
        args["dt"] = dxf_type
    sql += f" ORDER BY id LIMIT {int(limit)} OFFSET {int(offset)}"
    result = await db.execute(text(sql), args)
    return [dict(row._mapping) for row in result]
