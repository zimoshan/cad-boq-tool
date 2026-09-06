"""audit 域 schema"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class LlmRunRead(BaseModel):
    model_config = {"protected_namespaces": ()}  # 允许 model_version 字段
    id: int
    project_id: int
    task_type: str
    model: str
    model_version: str = ""
    prompt_version: str = ""
    temperature: float = 0.0
    duration_ms: int = 0
    token_input: int = 0
    token_output: int = 0
    status: str = "ok"
    error: str = ""
    created_at: datetime


class OverviewResponse(BaseModel):
    model_config = {"protected_namespaces": ()}  # 允许 model_* 字段（未来扩展）
    project_id: int
    boq_count: int
    mapping_count: int
    eo_breakdown: list[dict[str, Any]]
    writeback_by_takability: list[dict[str, Any]]
    llm_runs_by_task: list[dict[str, Any]]
