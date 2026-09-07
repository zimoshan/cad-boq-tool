"""CAD 域 schema"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ParseRequest(BaseModel):
    project_id: int
    file_path: str = Field(..., description="DWG/DXF 绝对路径（先上传到 DRAWING_CACHE_DIR）")


class ParseResponse(BaseModel):
    project_id: int
    file_path: str
    entity_count: int
    layer_count: int


class ViewportEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    handle: str
    dxf_type: str
    layer: str
    block_name: str = ""
    geom_wkt: str | None = None
    length: float = 0.0
    area: float = 0.0


class ViewportQuery(BaseModel):
    """B4 空间查询请求"""

    sheet_id: int
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    limit: int = Field(default=10000, le=50000)
    include_geom: bool = Field(
        default=True,
        description="LOD0 概览时为 false：不回 geom_json/geom_wkt，只回 bbox 元数据（大图 payload 减半）",
    )
