"""v1.0 §19 规格匹配 5 状态（v2：转发 app.binding.spec_match 实现）

EXACT / NORMALIZED_EQUAL / COMPATIBLE / UNKNOWN / CONFLICT

不能让 LLM 的文字理由覆盖硬冲突（needs_review = true）

实现位于业务层 app/binding/spec_match.py（#19：业务逻辑归 app/，webapi 只包装）；
本模块保留旧 import 路径（tests/webapi 服务层组件直接导入），转发全部公开符号。
"""

from app.binding.spec_match import (  # noqa: F401
    KEY_PARAM_PATTERNS,
    SpecMatchResult,
    SpecMatchStatus,
    match_spec,
)

__all__ = ["SpecMatchStatus", "SpecMatchResult", "match_spec", "KEY_PARAM_PATTERNS"]
