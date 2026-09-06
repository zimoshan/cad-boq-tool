"""v1.0 §20 Confidence Calibration 5 维综合

不能直接信任模型自报 confidence。

最终置信度综合：
    LLM confidence
    + Rule score
    + Embedding similarity
    + Spec score (v1.0 §19 5 状态)
    + Historical accuracy
    + Top1-Top2 margin
    + Conflict flag

初始可采用加权平均 + sigmoid 归一化
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CalibrationInput:
    """5 维输入"""

    llm_confidence: float = 0.0  # 0~1，模型自报
    rule_score: float = 0.0  # 0~1，规则匹配
    embedding_similarity: float = 0.0  # 0~1，cosine
    spec_match_score: float = 0.0  # 0~1（EXACT=1.0 / NORMALIZED=0.95 / COMPATIBLE=0.7 / UNKNOWN=0.5 / CONFLICT=0.0）
    historical_accuracy: float = 0.0  # 0~1，历史类似样本准确率
    top1_top2_margin: float = 0.0  # 0~1，top1 与 top2 差距
    has_conflict: bool = False  # 规格冲突


# 默认权重（v1.0 §20 建议"按 discipline+system 分层校准"，Phase 5 实现）
DEFAULT_WEIGHTS = {
    "llm_confidence": 0.25,
    "rule_score": 0.20,
    "embedding_similarity": 0.15,
    "spec_match_score": 0.20,
    "historical_accuracy": 0.10,
    "top1_top2_margin": 0.10,
}


def calibrate(inp: CalibrationInput, weights: dict | None = None) -> dict[str, Any]:
    """v1.0 §20 5 维综合（加权平均 + conflict 抑制）

    返回 {final_confidence, needs_review, breakdown}
    """
    w = weights or DEFAULT_WEIGHTS
    score = (
        inp.llm_confidence * w["llm_confidence"]
        + inp.rule_score * w["rule_score"]
        + inp.embedding_similarity * w["embedding_similarity"]
        + inp.spec_match_score * w["spec_match_score"]
        + inp.historical_accuracy * w["historical_accuracy"]
        + inp.top1_top2_margin * w["top1_top2_margin"]
    )
    # 冲突抑制：规格冲突时整体降权 0.5
    if inp.has_conflict:
        score *= 0.5

    needs_review = inp.has_conflict or score < 0.6

    return {
        "final_confidence": round(score, 4),
        "needs_review": needs_review,
        "breakdown": {
            "weighted_score": round(score, 4),
            "weights": w,
            "conflict_penalty": 0.5 if inp.has_conflict else 1.0,
        },
    }
