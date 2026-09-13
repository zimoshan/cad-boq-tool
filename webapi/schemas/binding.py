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
    refusals: list[dict] = Field(default_factory=list, description="P0-2 no_match 结构化拒绝原因列表")


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
    """v1.0 §20 评测报告：按方法分层 precision/recall + P1-2 增强"""

    project_id: int
    total_candidates: int
    total_confirmed: int
    total_rejected: int
    total_eo: int = 0  # P1-2: 全部工程对象数
    by_method: dict = Field(default_factory=dict)
    by_discipline: dict = Field(default_factory=dict)  # P1-2: 按专业分层
    spec_match_distribution: dict = Field(default_factory=dict)  # P1-2: spec_match 状态分布
    overall_precision: float = 0.0
    accuracy: float = 0.0  # P1-2: confirmed / total_eo
    generated_at: str = ""


# ===== P0-2: Refusal 策略 =====


class BindingRefusalRead(BaseModel):
    """no_match 拒绝诊断记录"""

    eo_id: int | None = None
    eo_tag: str = ""
    block_name: str = ""
    layer_name: str = ""
    code: str  # BOQ_EMPTY / EO_NO_TEXT / NO_KEYWORD / ALL_REJECTED / UNKNOWN
    reason: str  # 中文短描述
    detail: str = ""  # 附加信息
