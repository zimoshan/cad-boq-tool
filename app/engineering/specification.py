"""规格提取：从实体/图层文本中抽取典型规格（DN100 / Φ50 / 4MP 等）。"""
from __future__ import annotations

from ..takeoff.aggregate import extract_typical_sizes


def extract_specifications(texts: list) -> list:
    """从文本列表抽取规格（去重保序，上限 50），复用 aggregate 的正则库。

    Args:
        texts: 图层/近旁 TEXT 样本
    Returns:
        ["DN100", "Φ50", ...]
    """
    return extract_typical_sizes(texts or [])


def infer_spec_from_block(block_name: str) -> str:
    """从块名直接提取规格片段（如 CAM_4MP_DOME → '4MP'），无则空串"""
    if not block_name:
        return ""
    import re
    specs = []
    for pat in (re.compile(r"\d{1,4}\s*MP", re.IGNORECASE),      # 4MP / 8MP
                re.compile(r"\d{2,4}mm", re.IGNORECASE),         # 100mm
                re.compile(r"\d{3,4}\s*[xX×]\s*\d{3,4}"),        # 1920x1080
                re.compile(r"\d{2,4}\s*W", re.IGNORECASE)):      # 30W
        m = pat.search(block_name)
        if m:
            specs.append(re.sub(r"\s+", "", m.group(0)).upper())
    return " ".join(dict.fromkeys(specs))  # 去重保序
