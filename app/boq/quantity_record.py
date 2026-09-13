"""P1-1: CIR（Confidence & Provenance）统一 Schema

QuantityRecord 捕获每条工程量的完整溯源链：
  - value / unit：计量结果
  - method：计算方法（rule / llm / manual / ocr）
  - confidence：校准后置信度（0~1）
  - provenance[]：溯源步骤（规则命中 / LLM 调用 / OCR 识别 / 人工复核）
  - source_sheet_id / source_entity_ids：来源图纸和实体

设计目标（v1.0 §20 评审 §五-③）：
  审核层可展开 provenance，查看置信度从何而来。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class ProvenanceStep:
    """溯源链中的单一步骤"""

    step: str  # 规则命中 / LLM 精排 / Embedding 语义 / OCR 识别 / 人工复核
    method: str = ""  # rule / llm / embedding / ocr / manual
    confidence: float = 0.0  # 该步骤的原始置信度
    detail: str = ""  # 附加说明（规则名 / LLM prompt 摘要 / OCR 置信度）
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class QuantityRecord:
    """结构化溯源链（CIR）：一条工程量的完整计量上下文"""

    object_id: int  # engineering_object.id
    value: float  # 计量结果（measured_qty）
    unit: str = ""  # 计量单位（个/m/套）
    method: str = ""  # 最终计算方法
    confidence: float = 0.0  # 校准后置信度
    provenance: list[ProvenanceStep] = field(default_factory=list)  # 溯源步骤
    source_sheet_id: int | None = None  # 来源图纸 ID
    source_entity_ids: list[int] = field(default_factory=list)  # 来源实体 ID 列表

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON-friendly dict"""
        d = asdict(self)
        return d

    @classmethod
    def from_binding_candidate(cls, candidate: Any, eo: Any = None) -> QuantityRecord:
        """从 binding_candidate 构建（兼容对象和 dict）"""
        # 兼容对象/dict
        def _get(obj, key, default=""):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        eo_id = _get(candidate, "engineering_object_id", 0)
        confidence = _get(candidate, "confidence", 0.0)
        method = _get(candidate, "method", "")
        reason = _get(candidate, "reason", "")

        # 构建溯源步骤
        provenance: list[ProvenanceStep] = []
        if method == "rule":
            provenance.append(ProvenanceStep(
                step="规则命中", method="rule",
                confidence=confidence, detail=reason,
            ))
        elif method == "embedding":
            provenance.append(ProvenanceStep(
                step="Embedding 语义", method="embedding",
                confidence=confidence, detail=reason,
            ))
        elif method == "llm":
            provenance.append(ProvenanceStep(
                step="LLM 精排", method="llm",
                confidence=confidence, detail=reason,
            ))
        else:
            provenance.append(ProvenanceStep(
                step="其他", method=method,
                confidence=confidence, detail=reason,
            ))

        return cls(
            object_id=eo_id,
            value=0.0,  # 待计量后填充
            unit="",
            method=method,
            confidence=confidence,
            provenance=provenance,
        )
