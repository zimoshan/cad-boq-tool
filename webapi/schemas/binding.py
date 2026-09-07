"""绑定域 schema"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GenerateCandidatesRequest(BaseModel):
    project_id: int
    sheet_id: int | None = None
    use_llm: bool = True
    top_n: int = Field(default=5, ge=1, le=20)


class GenerateCandidatesResponse(BaseModel):
    project_id: int
    sheet_id: int | None = None
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


# ===== Phase 5: Negative Sample + Evaluation =====


class NegativeSampleRead(BaseModel):
    """v1.0 §17 负样本记录"""
    id: int
    project_id: int
    engineering_object_id: int
    boq_item_id: int
    reason: str = ""
    confidence_at_reject: float = 0.0
    method: str = ""
    rejected_by: str = ""
    created_at: str = ""


class EvaluationReport(BaseModel):
    """v1.0 §20 评测报告：按方法分层 precision/recall"""
    project_id: int
    total_candidates: int
    total_confirmed: int
    total_rejected: int
    by_method: dict = Field(default_factory=dict)
    # {method: {candidates, confirmed, rejected, precision, recall}}
    overall_precision: float = 0.0
    generated_at: str = ""
