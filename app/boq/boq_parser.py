"""BOQ 清单解析：openpyxl 读取 xlsx/xls → BoqItem[]

B1 修复（v2.0 §2.1，2026-09-06）：
  4 种专业 BOQ 表头识别（电气/机械/建筑/结构），每种表头所在行号不同。
  实测 4 份清单（[v2.0 §1.3](docs/CAD_BOQ_Web化_架构设计_v2.0.md)）：
    - BOQ-001 电气：表头 row 11（冻结 A12）
    - BOQ-001 Rev1：表头 row 1（冻结 A2）
    - BOQ-002 机械：表头 row 13（冻结 A13）
    - BOQ-003 建筑：表头 row 13（冻结 A13）
    - BOQ-004 结构：表头 row 10（冻结 A10）

B2 扩展（v2.0 §2.2）：解析时填 6 个新字段
  - section: 分部名（如 "CABLE" / "LIGHTING"）
  - item_key: 主键（如 "r123"）
  - brand: 品牌
  - bill_qty: 招标数量（F 列）
  - installed_qty: 已安装数量（G 列）
  - qty_remaining: 剩余数量（H 列 = bill - installed）
"""
from __future__ import annotations

import re

import openpyxl

from ..config import BOQ_HEADER_CANDIDATES
from ..models import BoqItem


# =============================================================================
# B1 修复：4 种专业 BOQ 表头识别
# =============================================================================

# 电气 BOQ-001: 表头 row 1 或 row 11（两个版本都识别）
# 机械 BOQ-002: 表头 row 13
# 建筑 BOQ-003: 表头 row 13
# 结构 BOQ-004: 表头 row 10
# （每种表头行含 Item / Description / Unit / 等关键词）

# 表头行探测器：在前 16 行（含冻结分页）寻找含 "Item" + "Description" 的行
HEADER_PROBE_ROWS = 16

# 关键表头标识（出现任一即视为表头行）
HEADER_KEYWORDS = (
    "item", "description", "unit", "qty", "bill",
    "section", "subtotal", "total", "amount",
)


def _normalize(s: str) -> str:
    return str(s).strip().lower().replace(" ", "")


def _row_looks_like_header(row_values: tuple) -> bool:
    """判断一行是否像 BOQ 表头（含 Item + Description 等关键词）"""
    norm_cells = [_normalize(v) for v in row_values if v is not None]
    text = " ".join(norm_cells)
    has_item = any("item" in c for c in norm_cells)
    has_desc = any("description" in c or "desc" in c for c in norm_cells)
    return has_item and has_desc


def _detect_headers(row_values: tuple) -> dict:
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


# BOQ_HEADER_CANDIDATES 增强（v2.0 §2.1）：把"item_key / section / bill_qty / installed_qty / qty_remaining" 5 个新字段加入
# （用户实际扩展在 app/config.py BOQ_HEADER_CANDIDATES；这里仅 reference）
# 注：app/config.py BOQ_HEADER_CANDIDATES 由 P0-6 + P0-7 配套扩展


def _to_float(v) -> float:
    if v is None:
        return 0.0
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except (ValueError, TypeError):
        return 0.0


def _is_skippable_contract_text(text: str) -> bool:
    """合同声明段落特征：超长文本 + 含 'Contractor/Rates/Items' 等条款词"""
    if not text:
        return False
    t = text.strip()
    if len(t) < 100:
        return False
    cues = ("Contractor", "Quantities are taken", "Qty remaining", "Material status",
            "Brand is", "Brand has", "Item descriptions", "Rates are to include",
            "Overhead, profit", "design drawings form part of this Bill")
    return any(c in t for c in cues)


# =============================================================================
# B2 扩展：item_key 提取（rNNN 格式）
# =============================================================================

# BOQ-001: rNNN (e.g. r123)
# BOQ-002: M-rNN (e.g. M-r5)
# BOQ-003: A-rNN / rNN（建筑）
# BOQ-004: S-rN (e.g. S-r1)
ITEM_KEY_PATTERN = re.compile(r"\b([A-Z]?-?r\d{1,4})\b", re.IGNORECASE)


def _extract_item_key(code: str) -> str:
    """从 code 字段提取 item_key（如 r123 / M-r5）"""
    if not code:
        return ""
    m = ITEM_KEY_PATTERN.search(code)
    return m.group(1) if m else ""


def _detect_section(prev_rows: list[tuple], current_row: tuple) -> str:
    """简易分部检测：若当前行有 SUBTOTAL/TOTAL 且前面有分部名，取之

    真实 BOQ 分部通常在数据上方有 "Cable / Lighting / Conduit" 标题行（合并格），
    简化策略：取当前行前 3 行内的非空文本作为 section 候选
    """
    for prev in reversed(prev_rows[-3:]):
        text = " ".join(str(c).strip() for c in prev if c is not None).strip()
        if 3 < len(text) < 50 and not _row_looks_like_header(prev):
            # 可能是分部标题
            if any(kw in text.upper() for kw in (
                "CABLE", "LIGHTING", "CONDUIT", "FIRE", "HVAC", "PLUMBING",
                "POWER", "EARTHING", "CONCRETE", "STEEL", "MASONRY", "FINISHES",
                "MECHANICAL", "ELECTRICAL", "DRAINAGE", "WIRING",
            )):
                return text
    return ""


def parse_boq(path: str) -> tuple[list, dict]:
    """解析 BOQ → (BoqItem[], 表头映射)

    B1 修复：在前 16 行探测表头（覆盖 4 种专业的不同表头行号）
    B2 扩展：解析时填 section / item_key / brand / bill_qty / installed_qty / qty_remaining 6 字段
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], {}

    # B1 修复：在前 HEADER_PROBE_ROWS 行探测表头
    header_idx = None
    mapping = {}
    for i, row in enumerate(rows[:HEADER_PROBE_ROWS]):
        m = _detect_headers(row)
        if len(m) >= 2 and _row_looks_like_header(row):
            header_idx = i
            mapping = m
            break
    if header_idx is None:
        # 无表头：按第一列为编号、第二列为描述、第三列为单位（兜底）
        header_idx = 0
        mapping = {"code": 0, "description": 1, "unit": 2}

    items = []
    for row_idx, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        # 跳过全空行
        if all(v is None or str(v).strip() == "" for v in row):
            continue

        def _cell(field, default=""):
            idx = mapping.get(field)
            if idx is not None and idx < len(row):
                v = row[idx]
                if v is None:
                    return default
                return str(v).strip() if isinstance(v, str) else v
            return default

        code = _cell("code", "")
        desc = _cell("description", "")
        unit = _cell("unit", "")
        qty = _to_float(_cell("original_qty", 0))

        if not code and not desc:
            continue

        # 列错位自愈（沿用原启发式）
        if unit and desc and len(desc) < 30 and re.search(r"[A-Z0-9._-]{4,}", str(unit)):
            desc, unit = str(unit), desc

        # 合同声明段落过滤
        full_text = " ".join(filter(None, [code, desc, str(unit) if unit else ""]))
        if _is_skippable_contract_text(full_text):
            continue

        # B2 扩展：6 个新字段
        item_key = _extract_item_key(code)
        brand = _cell("brand", "")
        bill_qty = _to_float(_cell("bill_qty", 0)) or qty  # 缺省回退到 original_qty
        installed_qty = _to_float(_cell("installed_qty", 0))
        qty_remaining = _to_float(_cell("qty_remaining", 0)) or (bill_qty - installed_qty)
        # 分部检测（前 3 行）
        section = _detect_section(rows[max(0, row_idx - 3 - 1):row_idx - 1], row)

        items.append(BoqItem(
            row_index=row_idx,
            code=code or f"item-{len(items) + 1}",
            description=desc,
            unit=str(unit) if unit else "",
            original_qty=qty,
            section=section,
            item_key=item_key,
            brand=brand,
            bill_qty=bill_qty,
            installed_qty=installed_qty,
            qty_remaining=qty_remaining,
        ))

    return items, mapping
