"""v1.0 §19 规格匹配 5 状态

EXACT / NORMALIZED_EQUAL / COMPATIBLE / UNKNOWN / CONFLICT

不能让 LLM 的文字理由覆盖硬冲突（needs_review = true）
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class SpecMatchStatus(StrEnum):
    """v1.0 §19 5 状态"""

    EXACT = "EXACT"
    NORMALIZED_EQUAL = "NORMALIZED_EQUAL"
    COMPATIBLE = "COMPATIBLE"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


# 关键参数（CONFLICT 判定用）：MP/DN/size/voltage/current 等
KEY_PARAM_PATTERNS = [
    re.compile(r"(\d+)\s*MP\b", re.IGNORECASE),
    re.compile(r"DN\s*(\d+)", re.IGNORECASE),
    re.compile(r"(\d+)\s*AWG\b", re.IGNORECASE),
    re.compile(r"(\d+)\s*V\b", re.IGNORECASE),
    re.compile(r"(\d+)\s*A\b", re.IGNORECASE),
]


@dataclass
class SpecMatchResult:
    """规格匹配结果"""

    status: SpecMatchStatus
    needs_review: bool
    detail: str = ""


def _normalize(s: str) -> str:
    """归一化：小写 + 去空格 + 去单位后缀"""
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"\b(mm|cm|m|inch|pc|pcs|ea|ea\.|set)\b", "", s)
    return s


def _extract_key_params(spec: str) -> dict[str, str]:
    """提取关键参数"""
    params = {}
    for pat in KEY_PARAM_PATTERNS:
        m = pat.search(spec or "")
        if m:
            params[pat.pattern] = m.group(1)
    return params


def match_spec(spec_a: str, spec_b: str) -> SpecMatchResult:
    """v1.0 §19 5 状态匹配

    判定优先级：
      1. 任一缺失 → UNKNOWN
      2. 完全相等 → EXACT
      3. 归一化相等 → NORMALIZED_EQUAL
      4. 关键参数不同 → CONFLICT（needs_review=True）
      5. 数值差 ≤10% → COMPATIBLE
      6. 其他 → CONFLICT（兜底）
    """
    if not spec_a or not spec_b:
        return SpecMatchResult(SpecMatchStatus.UNKNOWN, needs_review=False, detail="spec 缺失")

    if spec_a == spec_b:
        return SpecMatchResult(SpecMatchStatus.EXACT, needs_review=False)

    if _normalize(spec_a) == _normalize(spec_b):
        return SpecMatchResult(SpecMatchStatus.NORMALIZED_EQUAL, needs_review=False)

    # 关键参数对比（v1.0 §19：4MP vs 8MP → CONFLICT）
    params_a = _extract_key_params(spec_a)
    params_b = _extract_key_params(spec_b)
    for key in params_a:
        if key in params_b and params_a[key] != params_b[key]:
            return SpecMatchResult(
                SpecMatchStatus.CONFLICT,
                needs_review=True,
                detail=f"关键参数 {key} 不一致: {params_a[key]} vs {params_b[key]}",
            )

    # 数值差 ≤10% → COMPATIBLE
    nums_a = re.findall(r"[\d.]+", spec_a)
    nums_b = re.findall(r"[\d.]+", spec_b)
    if nums_a and nums_b:
        try:
            for na, nb in zip(nums_a, nums_b, strict=False):
                a, b = float(na), float(nb)
                if a > 0 and b > 0:
                    diff = abs(a - b) / max(a, b)
                    if diff <= 0.1:
                        return SpecMatchResult(SpecMatchStatus.COMPATIBLE, needs_review=False)
        except (ValueError, ZeroDivisionError):
            pass

    # 兜底：CONFLICT
    return SpecMatchResult(SpecMatchStatus.CONFLICT, needs_review=True, detail="规格不同")
