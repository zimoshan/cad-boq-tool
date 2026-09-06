"""extraction 域 schema"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    project_id: int
    sheet_id: int
    layer_rules: dict[str, Any] = Field(default_factory=dict)


class ExtractionResponse(BaseModel):
    project_id: int
    sheet_id: int
    created: int
    stats: dict[str, Any] = Field(default_factory=dict)
    object_ids: list[int] = Field(default_factory=list)


class EngineeringObjectRead(BaseModel):
    id: int
    project_id: int
    sheet_id: int | None = None
    object_type: str = ""
    discipline: str = ""
    system: str = ""
    block_name: str = ""
    layer_name: str = ""
    specification: str = ""
    unit: str = ""
    quantity_rule: str = "count"
    confidence: float = 0.0
    source: str = ""
