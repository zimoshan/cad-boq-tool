"""上下文推断：文件夹/文件名 → trade/floor。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List


# 推断 trade（按优先级匹配，先匹配先返回）
TRADE_HINTS: Dict[str, List[str]] = {
    "给排水":   ["给排水", "给水", "排水", "WATER", "DRAIN", "PLUMBING", "WS-", "P-", "W-"],
    "暖通":     ["暖通", "通风", "空调", "HVAC", "风", "Duct", "AHU", "FCU", "H-", "T-"],
    "电气-强电": ["电气", "强电", "配电", "照明", "ELEC", "POWER", "LIGHT", "E-", "LITE"],
    "电气-弱电": ["弱电", "通讯", "电话", "网络", "监控", "BA", "FA", "TELE", "DATA", "T-", "D-"],
    "消防":     ["消防", "喷淋", "消火栓", "FIRE", "SPRINKLER", "FP-", "F-", "SP-"],
    "电气":     ["电气", "电施", "ELEC", "E-", "POWER"],  # 通用（catch-all）
}

FLOOR_PATTERNS = [
    (re.compile(r"地\s*下\s*层?|B\d+|B1F|地下\d*|BASEMENT", re.IGNORECASE), "地下"),
    (re.compile(r"屋\s*顶|ROOF|顶层"), "屋顶"),
    (re.compile(r"(\d+)\s*[fF层]"), None),  # 数字层 → 1F, 2F
    (re.compile(r"[一二三四五六七八九十]+\s*层"), None),  # 中文层 → 一层、二层
]


def scan_folder(folder: Path, extensions=(".dxf", ".dwg")) -> List[Path]:
    """扫描文件夹下所有 DWG/DXF，按自然顺序排序（01 < 02 < 10）。

    同名 DWG 与 DXF 并存时只保留 DWG（与 import_folder.scan_drawings 一致，
    避免同一张图被算量两次）。
    """
    files = []
    if not folder.is_dir():
        return files
    for ext in extensions:
        files.extend(folder.glob(f"*{ext}"))
        files.extend(folder.glob(f"*{ext.upper()}"))
    # 去重
    seen = set()
    unique = []
    for f in files:
        if f.resolve() not in seen:
            seen.add(f.resolve())
            unique.append(f)
    # 同名优先 DWG：同目录下同名文件，若存在 .dwg 则丢弃 .dxf
    dwg_names = {f.stem.lower() for f in unique if f.suffix.lower() == ".dwg"}
    unique = [f for f in unique
              if f.suffix.lower() != ".dxf" or f.stem.lower() not in dwg_names]
    # 自然序排序（数字感知）
    def natural_key(p: Path) -> list:
        parts = re.split(r"(\d+)", p.name.lower())
        return [int(t) if t.isdigit() else t for t in parts]
    unique.sort(key=natural_key)
    return unique


def infer_trade(name: str) -> str:
    """从名称推断 trade（中文/英文/前缀混合）"""
    if not name:
        return "综合"
    name_lower = name.lower()
    for trade, kws in TRADE_HINTS.items():
        if any(kw.lower() in name_lower for kw in kws):
            return trade
    return "综合"


def infer_floor(filename: str) -> str:
    """从文件名推断楼层"""
    if not filename:
        return ""
    for pat, fixed in FLOOR_PATTERNS:
        m = pat.search(filename)
        if m:
            if fixed is not None:
                return fixed
            else:
                # 提取数字
                num = m.group(1) if m.groups() else ""
                if num and num.isdigit():
                    return f"{num}F"
                return m.group(0)
    return ""


def infer_context(folder_name: str, file_name: str = "") -> dict:
    """从文件夹/文件名推断上下文"""
    return {
        "trade": infer_trade(folder_name),
        "floor": infer_floor(file_name),
    }
