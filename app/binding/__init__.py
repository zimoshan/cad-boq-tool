"""BOQ 绑定管线（V2 模式A/B 的绑定层）。

- candidate: 候选状态机（AI/规则只写 PENDING）
- rule_matcher: 确定性规则 + 历史确认复用
- matcher: 优先级编排（确认 > 规则 > Embedding > LLM）
- reviewer: 人工确认/拒绝 → 正式 mapping（唯一通道）
- resolver: 确定性计量 + BOQ 溯源
"""
from .candidate import (STATUS_PENDING, STATUS_ACCEPTED, STATUS_REJECTED,
                        STATUS_SUPERSEDED, METHOD_RULE, METHOD_EMBEDDING,
                        METHOD_LLM, METHOD_MANUAL)
from .matcher import generate_candidates, create_manual_candidate
from .reviewer import confirm_binding, reject_binding, auto_confirm_rule_candidates
from .resolver import recompute, trace_quantity
from .embedding_matcher import semantic_candidates
from .llm_matcher import llm_rerank

__all__ = [
    "STATUS_PENDING", "STATUS_ACCEPTED", "STATUS_REJECTED", "STATUS_SUPERSEDED",
    "METHOD_RULE", "METHOD_EMBEDDING", "METHOD_LLM", "METHOD_MANUAL",
    "generate_candidates", "create_manual_candidate",
    "confirm_binding", "reject_binding", "auto_confirm_rule_candidates",
    "recompute", "trace_quantity",
    "semantic_candidates", "llm_rerank",
]
