"""绑定推荐输出校验：JSON Schema + Pydantic + 业务字段校验（任务十三）。

流程：LLM → JSON 解析 → Pydantic（类型/范围）→ 业务校验（selected_boq_id ∈ 候选集）。
校验失败抛 SchemaError，由 runner 自动重试。
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field, field_validator, ValidationError


class SchemaError(Exception):
    """输出不符合 schema / 业务规则"""


class BindingSuggestion(BaseModel):
    """Qwen 绑定推荐的结构化输出。

    ``no_match``：对候选集明确拒答（没有任何候选匹配）时置 True，
    ``selected_boq_id`` 随之可为空；此时候选不写入，交由人工/后续处理——
    避免模型在"必须选一个"的约束下乱选污染 PENDING 队列。
    """
    selected_boq_id: str | None = Field(default=None,
                                        description="选中的 BOQ 编号（no_match=false 时必须属于候选集）")
    confidence: float = Field(ge=0.0, le=1.0, description="对选中的把握 0~1")
    reason: str = ""
    alternative_boq_ids: list[str] = Field(default_factory=list, description="备选 BOQ 编号")
    needs_review: bool = Field(default=False,
                               description="模型自身不确定时置 True，候选标记「需人工复核」等待人工确认")
    no_match: bool = Field(default=False, description="与所有候选均不匹配时置 True（拒答）")

    @field_validator("selected_boq_id")
    @classmethod
    def _code_not_empty(cls, v: str) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("alternative_boq_ids")
    @classmethod
    def _alts_not_empty(cls, v: list) -> list:
        return [x.strip() for x in v if x and x.strip()]

    def selected_or_no_match(self) -> bool:
        """合规性快查：要么选中有效编号，要么明确 no_match，二选一。"""
        if self.no_match:
            return self.selected_boq_id is None and not self.alternative_boq_ids
        return bool(self.selected_boq_id)


def binding_json_schema() -> dict:
    """导出 JSON Schema（供文档/前端展示）"""
    return BindingSuggestion.model_json_schema()


def parse_binding_suggestion(content: str, allowed_boq_ids: list = None) -> BindingSuggestion:
    """解析 + 校验 LLM 输出。

    Args:
        content: LLM 原始输出（可能带 ```json 围栏/前后缀文字）
        allowed_boq_ids: 允许选中的 BOQ code 列表（业务校验）
    Raises:
        SchemaError: 解析失败或校验失败
    Returns:
        BindingSuggestion
    """
    if not content or not content.strip():
        raise SchemaError("LLM 输出为空")
    text = content.strip()

    # 剥 ```json 围栏
    import re
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()

    # 解析 JSON（找第一个平衡对象）
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise SchemaError("输出中无 JSON 对象") from None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start:i + 1])
                    except json.JSONDecodeError as e:
                        raise SchemaError(f"JSON 解析失败: {e}") from e
                    break
        else:
            raise SchemaError("JSON 对象未闭合（截断）")

    try:
        sug = BindingSuggestion.model_validate(data)
    except ValidationError as e:
        raise SchemaError(f"字段校验失败: {e.errors()[:3]}") from e

    # 合规则：要么选中编号，要么明确 no_match（P0 拒答）
    if not sug.selected_or_no_match():
        raise SchemaError(
            "输出不合规：no_match=True 时不得给出 selected/alternative；"
            "否则 selected_boq_id 必填")
    # 业务校验：选中项必须在候选集内（no_match 跳过）
    if not sug.no_match and allowed_boq_ids and sug.selected_boq_id not in allowed_boq_ids:
        raise SchemaError(
            f"selected_boq_id={sug.selected_boq_id} 不在候选集 {allowed_boq_ids[:5]}")
    return sug


# ===========================================================================
# 语义分类输出（三重兜底第 3 层）
# ===========================================================================
DISCIPLINES = ("ELV", "LV", "FIRE", "HVAC", "PLUMBING", "MEDICAL_GAS", "BUILDING_BG")
QUANTITY_RULES = ("count", "length", "area")


class ClassificationResult(BaseModel):
    """Qwen 语义分类的结构化输出"""
    discipline: str = Field(description="专业：ELV/LV/FIRE/HVAC/PLUMBING/MEDICAL_GAS/BUILDING_BG")
    system: str = Field(default="", description="系统（如 CCTV/FA/LIGHTING）")
    spec: str = Field(default="", description="规格/型号")
    quantity_rule: str = Field(default="count", description="计量规则 count/length/area")
    confidence: float = Field(ge=0.0, le=1.0, description="把握 0~1")
    reason: str = ""

    @field_validator("discipline")
    @classmethod
    def _discipline_valid(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in DISCIPLINES:
            raise ValueError(f"discipline 非法: {v}")
        return v

    @field_validator("quantity_rule")
    @classmethod
    def _rule_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in QUANTITY_RULES:
            raise ValueError(f"quantity_rule 非法: {v}")
        return v


def parse_classification(content: str) -> ClassificationResult:
    """解析 + 校验 LLM 分类输出。"""
    if not content or not content.strip():
        raise SchemaError("LLM 分类输出为空")
    text = content.strip()
    import re
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise SchemaError("分类输出中无 JSON 对象") from None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start:i + 1])
                    except json.JSONDecodeError as e:
                        raise SchemaError(f"JSON 解析失败: {e}") from e
                    break
        else:
            raise SchemaError("JSON 对象未闭合（截断）")
    try:
        return ClassificationResult.model_validate(data)
    except ValidationError as e:
        raise SchemaError(f"分类字段校验失败: {e.errors()[:3]}") from e
