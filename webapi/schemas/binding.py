"""绑定域 schema"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GenerateCandidatesRequest(BaseModel):
    project_id: int
    sheet_id: Optional[int] = None
    use_llm: bool = True
    top_n: int = Field(default=5, ge=1, le=20)


class GenerateCandidatesResponse(BaseModel):
    project_id: int
    sheet_id: Optional[int] = None
    use_llm: bool
    candidates_created: int
    stats: dict = Field(default_factory=dict)


class ConfirmBindingRequest(BaseModel):
    candidate_id: int
    by_user: str = "sysadmin"


class RejectBindingRequest(BaseModel):
    candidate_id: int
    reason: str = ""
    by_user: str = "sysadmin"


class BindingCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    engineering_object_id: int
    boq_item_id: int
    method: str
    score: float
    confidence: float
    reason: str = ""
    status: str
    created_at: str = ""
