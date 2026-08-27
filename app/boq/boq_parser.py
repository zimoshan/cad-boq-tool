"""BOQ 清单解析：openpyxl 读取 xlsx/xls → BoqItem[]"""
from __future__ import annotations

import re

import openpyxl

from ..config import BOQ_HEADER_CANDIDATES
from ..models import BoqItem


def _normalize(s: str) -> str:
    return str(s).strip().lower().replace(" ", "")


def _detect_headers(row_values: list) -> dict:
    """在表头行中探测各列位置"""
    mapping = {}
    for col_idx, val in enumerate(row_values):
        norm = _normalize(val)
        if not norm:
            continue
        for field, candidates in BOQ_HEADER_CANDIDATES.items():
            if field in mapping:
                continue
            if norm in [_normalize(c) for c in candidates]:
                mapping[field] = col_idx
    return mapping


def _to_float(v) -> float:
    if v is None:
        return 0.0
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except (ValueError, TypeError):
        return 0.0


def _is_skippable_contract_text(text: str) -> bool:
    """合同声明段落特征：超长文本 + 含 'Contractor/Rates/Items' 等条款词
    这种行是 Excel 顶部说明，不应入库为 BOQ 条目。"""
    if not text:
        return False
    t = text.strip()
    if len(t) < 100:
        return False
    cues = ("Contractor", "Quantities are taken", "Qty remaining", "Material status",
            "Brand is", "Brand has", "Item descriptions", "Rates are to include",
            "Overhead, profit", "design drawings form part of this Bill")
    return any(c in t for c in cues)


def parse_boq(path: str) -> tuple[list, dict]:
    """解析 BOQ → (BoqItem[], 表头映射)；空表头映射由 UI 提示手动指定"""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], {}

    # 探测表头行：前 5 行内找包含"编号/描述/单位"的行
    header_idx = None
    mapping = {}
    for i, row in enumerate(rows[:5]):
        m = _detect_headers(row)
        if len(m) >= 2:
            header_idx = i
            mapping = m
            break
    if header_idx is None:
        # 无表头：按第一列为编号、第二列为描述、第三列为单位
        header_idx = 0
        mapping = {"code": 0, "description": 1, "unit": 2}

    items = []
    for row_idx, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        # 跳过全空行
        if all(v is None or str(v).strip() == "" for v in row):
            continue
        code = str(row[mapping["code"]]).strip() if mapping.get("code") is not None and mapping["code"] < len(row) else ""
        desc = str(row[mapping["description"]]).strip() if mapping.get("description") is not None and mapping["description"] < len(row) else ""
        unit = str(row[mapping["unit"]]).strip() if mapping.get("unit") is not None and mapping["unit"] < len(row) else ""
        qty = _to_float(row[mapping["original_qty"]]) if mapping.get("original_qty") is not None and mapping["original_qty"] < len(row) else 0.0
        if not code and not desc:
            continue
        # 列错位自愈：当 description 列里大量只含表格头文字（如"分布面板"等分组名短文本）
        # 且 unit 列内容更长像规格——说明表头找错了，3 列布局但 description/unit 互换。
        # 启发式：unit 含 4+ 字母数字大写（型号）而 description 太短且重复。
        if unit and desc and len(desc) < 30 and re.search(r"[A-Z0-9._-]{4,}", unit):
            desc, unit = unit, desc
        # 合同声明段落过滤（顶部说明）
        full_text = " ".join(filter(None, [code, desc, unit]))
        if _is_skippable_contract_text(full_text):
            continue
        items.append(BoqItem(
            row_index=row_idx,
            code=code or f"item-{len(items) + 1}",
            description=desc,
            unit=unit,
            original_qty=qty,
        ))
    # 二次剪裁：boq_item 中 unit 普遍为 None 时（合同格式），保留但加 note 提示
    return items, mapping
