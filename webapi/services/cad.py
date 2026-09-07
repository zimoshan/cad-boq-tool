"""CAD 域 Service（包装 app/cad 业务函数）

Phase 0：
  - POST /api/cad/parse：上传 DWG/DXF → 解析 → 入库
  - GET  /api/cad/viewport?bbox=...：B4 空间查询
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text
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
    get_settings()
    if not Path(file_path).exists():
        raise NotFoundError("File", file_path)

    try:
        # 包装 app/cad/reader.read_cad
        read_cad(file_path)
        # 包装 app/cad/cad_parser.parse_dxf
        parsed = parse_dxf(file_path)
    except Exception as e:
        raise ServiceError(f"CAD parse failed: {e}", code="cad_parse_error") from e

    return {
        "project_id": project_id,
        "file_path": file_path,
        "entity_count": len(parsed.entities),
        "layer_count": len(parsed.layers),
    }


def _bbox_overlaps_cond(min_x: float, min_y: float, max_x: float, max_y: float) -> str:
    """SQLite 兼容 bbox 过滤：bbox 列为 JSON 数组文本 '[min_x,min_y,max_x,max_y]'

    SQLite 无 PostGIS，用 json_extract 取 4 端点做范围相交判定
    （标准 2D 轴对齐包围盒相交：两个矩形有重叠 ⇔ 四个不等式同时成立）。
    """
    return (
        f"json_extract(bbox, '$[0]') <= {max_x} AND json_extract(bbox, '$[2]') >= {min_x} "
        f"AND json_extract(bbox, '$[1]') <= {max_y} AND json_extract(bbox, '$[3]') >= {min_y}"
    )


def _dialect_is_pg(db: AsyncSession) -> bool:
    """判断是否 PG（PostGIS）环境；mock/异常 回退 False（进 SQLite 兼容分支）"""
    try:
        return db.get_bind().dialect.name == "postgresql"
    except Exception:
        return False


async def query_viewport(
    db: AsyncSession,
    sheet_id: int,
    bbox: tuple[float, float, float, float],  # (min_x, min_y, max_x, max_y)
    limit: int = 10000,
) -> list[dict[str, Any]]:
    """B4 空间查询：返回 bbox 内的 entity

    双引擎：
    - PostGIS（PG 生产）：geometry && ST_MakeEnvelope（GIST 索引）
    - SQLite（本地库）：bbox JSON 列 '[min_x,min_y,max_x,max_y]' 相交查询

    返回 snapshot 行（SQLite 含 geom/bbox；PG 含 geom_wkt）。
    """
    import json

    min_x, min_y, max_x, max_y = bbox

    postgres = _dialect_is_pg(db)

    if postgres:
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
        return [dict(r._mapping) for r in result]

    # SQLite 分支：bbox JSON 列范围相交
    sql = text(f"""
        SELECT id, handle, dxf_type, layer, block_name,
               bbox, geom_json, length, area
        FROM entity
        WHERE sheet_id = :sheet_id
          AND {_bbox_overlaps_cond(min_x, min_y, max_x, max_y)}
        LIMIT :limit
    """)
    result = await db.execute(
        sql,
        {"sheet_id": sheet_id, "limit": limit},
    )
    rows = []
    for row in result:
        r = dict(row._mapping)
        try:
            r["geom"] = json.loads(r.pop("geom_json") or "{}")
        except (ValueError, TypeError):
            r["geom"] = {}
        try:
            r["bbox"] = json.loads(r.get("bbox") or "[0,0,0,0]")
        except (ValueError, TypeError):
            r["bbox"] = [0, 0, 0, 0]
        rows.append(r)
    return rows


# =============================================================================
# v1.0 §13 4 端点支撑（metadata / layers / blocks / entities 独立查询）
# =============================================================================


async def list_sheets(db: AsyncSession, project_id: int) -> list[dict[str, Any]]:
    """Phase 3 图纸列表：项目下 sheet 概览（前端图纸选择器用）

    双 schema 兼容（同 get_sheet_metadata）。
    """
    postgres = _dialect_is_pg(db)
    extra = (
        ", units, drawing_type, level, zone, revision, design_stage" if postgres else ""
    )
    result = await db.execute(
        text(f"""SELECT id, project_id, filename, status, scale, entity_count,
                       layer_count, blocks_json{extra}
                FROM sheet WHERE project_id = :pid ORDER BY id"""),
        {"pid": project_id},
    )
    return [dict(row._mapping) for row in result]


async def get_sheet_metadata(db: AsyncSession, sheet_id: int) -> dict[str, Any] | None:
    """v1.0 §13 GET /api/cad/metadata：图纸元数据 + drawing_type/units/level/zone

    双 schema 兼容：
      - PG（生产，v2.0 alembic 0001）：全列（units/drawing_type/level/zone/revision/design_stage）
      - SQLite（本地开发库，桌面旧库）：基础列（无 v2.0 追加列）
    """
    postgres = _dialect_is_pg(db)
    extra = (
        """, units, drawing_type, level, zone, revision, design_stage"""
        if postgres
        else ""
    )
    result = await db.execute(
        text(f"""SELECT id, project_id, filename, src_path, dxf_path, status, scale,
                       entity_count, layer_count{extra}
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
