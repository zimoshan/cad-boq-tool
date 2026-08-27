"""绑定候选状态机：常量与状态流转校验。

BindingCandidate 本体在 app/models.py（与表结构对应），此处定义
状态/方法常量，并保证只有人工确认或确定性规则（reviewer）能
把候选转为正式 mapping——AI 只能写 PENDING。
"""
from __future__ import annotations

# 状态
STATUS_PENDING = "PENDING"          # 待审核
STATUS_ACCEPTED = "ACCEPTED"        # 已确认 → 已写 mapping
STATUS_REJECTED = "REJECTED"        # 已拒绝（记录原因，后续不推荐同组合）
STATUS_SUPERSEDED = "SUPERSEDED"    # 被新候选取代

# 生成方法
METHOD_RULE = "RULE"                # 确定性规则 / 历史确认复用
METHOD_EMBEDDING = "EMBEDDING"      # 语义召回
METHOD_LLM = "LLM"                  # Qwen 重排序
METHOD_MANUAL = "MANUAL"            # 人工直接选择

STATUSES = (STATUS_PENDING, STATUS_ACCEPTED, STATUS_REJECTED, STATUS_SUPERSEDED)
METHODS = (METHOD_RULE, METHOD_EMBEDDING, METHOD_LLM, METHOD_MANUAL)

# 可终态：确认 / 拒绝
TERMINAL_STATUSES = (STATUS_ACCEPTED, STATUS_REJECTED)

# 规则候选自动通过的最低置信（P3 保留人工确认，RULE 也先进审核队列）
RULE_AUTO_CONFIRM_THRESHOLD = 1.0   # 仅历史确认复用（score=1.0）可自动通过
