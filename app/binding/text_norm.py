"""字段规范化（LLM_ACCURACY 调研 P0）：统一文本比对口径。

做三件事：
1. 全角→半角（ＦＵＲＮ 等日文/中文全角字母数字在 CAD/BOQ 里常见）。
2. 大小写统一（engineering/筛查默认 UPPER，规则/语义统一走 UPPER）。
3. 规格紧凑化：去掉空格/连接符，`4 MP` == `4MP` == `4-MP`，`DN 100` == `DN100`，
   解决"子串启发式"因中间隔符漏/误判（调研 3.2 第 4 条）。

约定：所有公开函数输入 str|None 输出 str（空输入 → ""）。
"""
from __future__ import annotations

import re

# 全角 → 半角（覆盖 ASCII 区间与常用日文标点）
_FULLWIDTH = {}
for _c in range(0xFF01, 0xFF5F):
    _FULLWIDTH[chr(_c)] = chr(_c - 0xFEE0)
_FULLWIDTH["　"] = " "  # 全角空格


def to_halfwidth(s: str) -> str:
    """全角 → 半角（字母/数字/标点），全角空格 → 半角空格。"""
    if not s:
        return ""
    return "".join(_FULLWIDTH.get(c, c) for c in s)


def compact(s: str) -> str:
    """规格紧凑：大写 + 去任意空白 + 去 `-_/.,·` 连接符。

    ``4 MP`` / ``4MP`` / ``4-MP`` / ``4.MP`` 归一为 ``4MP``。
    用于规格/关键词比对（子串启发式对"数值+单位"极易因一个空格失配）。
    """
    if not s:
        return ""
    return re.sub(r"[\s\-_/.,·`（）()\[\]【】]+", "", to_halfwidth(s).upper())


def normalize(s: str) -> str:
    """通用规范：半角 + 大写 + 压缩空白（保留词间空格）。

    用于 BOQ code/description/unit 与 EO block/layer/system 的规范比对。
    """
    if not s:
        return ""
    return re.sub(r"\s+", " ", to_halfwidth(s).upper()).strip()


def boq_searchable(item) -> str:
    """把一条 BOQ 规整为可检索文本（含紧凑规格，供规则/embedding 复用）。

    返回 ``"{code} {desc} {unit} @@紧凑版(去空格)"``：
    - 前半段保留原始行业写法（`DN100` 直接可子串）；
    - 后半段 `@@` 后是去空格紧凑版，`4 MP`、`4-MP` 都可命中。
    """
    code = normalize(getattr(item, "code", "") or "")
    desc = normalize(getattr(item, "description", "") or "")
    unit = normalize(getattr(item, "unit", "") or "")
    comp = compact(f"{desc} {unit}")
    base = " ".join(x for x in (code, desc, unit) if x)
    return f"{base} @@ {comp}" if comp else base


def contains_spec(full: str, spec: str) -> bool:
    """规格级命中：在 full（可含 @@ 紧凑段）中查 spec（中是否带/不带空格 / 连接符差异）。

    按『两个口径』测：原始子串 + 紧凑子串。任一命中即 True。
    """
    if not full or not spec:
        return False
    s = spec.strip()
    if not s:
        return False
    if s in full:
        return True
    comp = compact(s)
    return bool(comp) and comp in compact(full)


def _lcs_len(a: str, b: str) -> int:
    """最长公共子序列长度（DP，O(len(a)*len(b)））。

    用于整串相似度兜底：分隔符差异已被 compact 归一，剩余差异多为
    词序/删词/增词，LCS 比例对这类差异比编辑距离更稳健。
    """
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0
    if la == lb and a == b:
        return la
    prev = [0] * (lb + 1)
    for i in range(1, la + 1):
        cur = [0] * (lb + 1)
        ai = a[i - 1]
        for j in range(1, lb + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = prev[j] if prev[j] >= cur[j - 1] else cur[j - 1]
        prev = cur
    return prev[lb]


def string_similarity(a: str, b: str) -> float:
    """整串归一化相似度 0~1（2026-08-28 绑定候选增强 P0）。

    输入 block_name / BOQ description（原始带分隔符写法），比较前先
    ``compact`` 去分隔符/大小写，然后按三档打分：

    1. 完全一致 → 1.0（``CAM_DOME_4MP`` vs ``CAM DOME 4MP`` 同串）；
    2. 一方整串包含另一方 → ``0.7 + 0.3 * 短/长长度比``（含串越长贴近 1；
       长整串互相构成时 ≥0.85，纯短 token 如单个规格字不会误触）；
    3. 其余 → 最长公共子序列比例 ``LCS / max(len)``。

    ≥0.85 视为「块名≈清单描述」强匹配（rule_matcher 用它给强分）。
    """
    if not a or not b:
        return 0.0
    A, B = compact(a), compact(b)
    if not A or not B:
        return 0.0
    if A == B:
        return 1.0
    la, lb = len(A), len(B)
    # 子串包含
    short, long = (A, B) if la <= lb else (B, A)
    if short in long:
        ratio = len(short) / len(long)
        return round(0.7 + 0.3 * ratio, 3)
    # LCS 比例兜底
    lcs = _lcs_len(A, B)
    denom = max(la, lb)
    return round(lcs / denom, 3) if denom else 0.0