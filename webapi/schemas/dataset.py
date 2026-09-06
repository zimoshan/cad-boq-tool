"""测试数据通路 schema（P0-22）"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TestDataEntry(BaseModel):
    """单条测试数据登记"""
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=128, description="测试数据名（如 'LBH-电气-37图'）")
    project_id: int
    file_path: str = Field(..., description="DWG/DXF/Excel 文件绝对路径")
    data_type: str = Field(..., description="drawing / boq / json")
    note: str = ""
    is_active: bool = True
    created_at: Optional[datetime] = None


class TestDataRegistry(BaseModel):
    """测试数据注册表（P0-22 占位，Phase 1 完整实现）"""
    entries: list[TestDataEntry]
    total: int
    registry_path: str
