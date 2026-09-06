"""takeoff 域 schema"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TakeoffRequest(BaseModel):
    project_id: int
    sheet_id: int | None = None
    folder_path: str = ""


class TakeoffResponse(BaseModel):
    project_id: int
    sheet_id: int | None = None
    folder_path: str = ""
    result: dict[str, Any] = Field(default_factory=dict)
