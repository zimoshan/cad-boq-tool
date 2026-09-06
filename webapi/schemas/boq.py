"""BOQ 域 schema"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ParseBoqRequest(BaseModel):
    project_id: int
    file_path: str = Field(..., description="xlsx/xls 绝对路径")


class ParseBoqResponse(BaseModel):
    project_id: int
    file_path: str
    item_count: int
    meta: dict = Field(default_factory=dict)


class WritebackRequest(BaseModel):
    project_id: int
    project_scale: float = 1.0


class WritebackResponse(BaseModel):
    project_id: int
    written: int
    failed: int = 0


class ExportBoqRequest(BaseModel):
    """v1.0 §15 工程量回写：导出实测值到 Excel"""

    project_id: int
    output_path: str = Field(..., description="输出 xlsx 绝对路径")
    overwrite_original: bool = Field(default=False, description="是否覆盖原 BOQ 数量列（默认保留对照）")


class ExportBoqResponse(BaseModel):
    project_id: int
    output_path: str
    written_rows: int
    skipped_rows: int = 0
    by_takability: dict = Field(default_factory=dict)


class BoqItemRead(BaseModel):
    """B2 扩展后 BoqItem"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    row_index: int
    section: str = ""  # B2 新增
    item_key: str = ""  # B2 新增
    code: str = ""
    description: str = ""
    brand: str = ""  # B2 新增
    unit: str = ""
    bill_qty: float = 0.0  # B2 新增
    installed_qty: float = 0.0  # B2 新增
    qty_remaining: float = 0.0  # B2 新增
    original_qty: float = 0.0  # 兼容旧
    rule_type: str = "length"
    scale_factor: float = 1.0
    measured_qty: float = 0.0
