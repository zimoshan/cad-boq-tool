"""工程量回写：把项目级计量结果写入 BOQ 实测数量列（measured_qty）。

B5 S7 可核性 + Excel 保真回写（v2.0 §2.5 / §5.3，2026-09-06）：
- takability 6 状态：
  MEASURABLE: 可精确计量
  GROUP_ONLY: 只能按组合计量
  NOT_MEASURABLE: 暂不可计量（图层黑名单 / 块未识别）
  NO_DRAWING: BOQ 项无对应图纸
  VERSION_CONFLICT: 多图版本冲突需人工
  PROVISIONAL: 暂定值（人工标注）
- writeback_audit 表（alembic 0002 创建）：保真回写审计
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from .. import db
from ..binding.resolver import recompute


class Takability(StrEnum):
    """B5 S7 可核性 6 状态"""

    MEASURABLE = "MEASURABLE"
    GROUP_ONLY = "GROUP_ONLY"
    NOT_MEASURABLE = "NOT_MEASURABLE"
    NO_DRAWING = "NO_DRAWING"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    PROVISIONAL = "PROVISIONAL"


def classify_takability(
    boq_item_id: int,
    mapping_count: int,
    sheet_drawing_types: list[str] | None = None,
    has_provisional_flag: bool = False,
) -> Takability:
    """P1-1 完整 6 状态判定（v2.0 §2.5 takability）

    判定优先级（从高到低）：
      1. has_provisional_flag → PROVISIONAL（人工标注）
      2. 任意 sheet 在黑名单 drawing_type（detail/legend/schedule） → NOT_MEASURABLE
      3. 跨图 drawing_type 不一致 → VERSION_CONFLICT
      4. mapping_count == 0 → NO_DRAWING（无图纸对应）
      5. mapping_count ≤ 2 → MEASURABLE（可精确计量）
      6. mapping_count ≥ 3 → GROUP_ONLY（按组计量，需人工核对）
    """
    if has_provisional_flag:
        return Takability.PROVISIONAL

    if sheet_drawing_types:
        if any(dt in ("detail", "legend", "schedule") for dt in sheet_drawing_types):
            return Takability.NOT_MEASURABLE
        if len(set(sheet_drawing_types)) > 1:
            return Takability.VERSION_CONFLICT

    if mapping_count == 0:
        return Takability.NO_DRAWING
    if mapping_count <= 2:
        return Takability.MEASURABLE
    return Takability.GROUP_ONLY


# 黑名单 drawing_type（不参与精确计量）
BLACKLIST_DRAWING_TYPES = ("detail", "legend", "schedule")


def _log_writeback_audit(
    project_id: int,
    boq_item_id: int,
    original_qty: float,
    measured_qty: float,
    takability: str,
    file_sha256: str = "",
) -> None:
    """B5 S7：写 writeback_audit（保真回写审计）

    P4 增强：file_sha256 是源 BOQ Excel 的 SHA-256（防 tamper 检测）
    """
    try:
        with db.get_conn() as conn:
            conn.execute(
                "INSERT INTO writeback_audit(project_id, boq_item_id, original_qty, "
                "measured_qty, takability, file_sha256) VALUES(?,?,?,?,?,?)",
                (project_id, boq_item_id, original_qty, measured_qty, takability, file_sha256),
            )
    except Exception:
        pass


def compute_file_sha256(file_path: str) -> str:
    """P4 v1.0 §6.4：算源文件 SHA-256（防 tamper 检测）"""
    import hashlib

    try:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def _collect_sheet_drawing_types(boq_item_id: int) -> list[str]:
    """P1-1：收集某 BOQ item 的 mapping → sheet 的 drawing_type 列表"""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT s.drawing_type FROM mapping m JOIN sheet s ON s.id = m.sheet_id WHERE m.boq_item_id = ?",
                (boq_item_id,),
            ).fetchall()
        return [r["drawing_type"] or "plan" for r in rows]
    except Exception:
        return []


def write_back_quantities(project_id: int, project_scale: float = 1.0) -> dict:
    """项目内全部 BOQ 子项计量 → 写回 measured_qty 列 + writeback_audit 审计

    P1-1 增强：6 状态 takability 完整判定（黑名单 + 版本冲突 + 暂定标注）

    Returns:
        {
            "written": int, "total": int,
            "by_takability": {state: count},
            "by_item": {boq_item_id: {"qty", "count", "takability"}}
        }
    """
    items = db.get_boq_items(project_id)
    res = recompute(project_id, project_scale=project_scale)
    by_item: dict[int, dict[str, Any]] = {}
    by_takability: dict[str, int] = {}
    written = 0
    for it in items:
        r = res.get(it.id, {"qty": 0.0, "count": 0})
        qty = round(r.get("qty") or 0.0, 4)
        count = r.get("count") or 0
        # P1-1：收集 sheet drawing_types 用于黑名单 + 版本冲突判定
        sheet_dts = _collect_sheet_drawing_types(it.id)
        takability = classify_takability(it.id, count, sheet_dts)
        db.update_boq_item(it.id, measured_qty=qty)
        _log_writeback_audit(project_id, it.id, it.original_qty or 0.0, qty, takability.value)
        by_item[it.id] = {"qty": qty, "count": count, "takability": takability.value}
        by_takability[takability.value] = by_takability.get(takability.value, 0) + 1
        if qty:
            written += 1
    return {
        "written": written,
        "total": len(items),
        "by_takability": by_takability,
        "items": by_item,
    }


def set_provisional_flag(boq_item_id: int, provisional: bool = True) -> None:
    """P1-1：人工标记某 BOQ item 为暂定值（PROVISIONAL）

    实现：boq_item.remark 字段追加 "[PROVISIONAL]" 标记（避免新加字段）
    """
    try:
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT remark FROM boq_item WHERE id = ?",
                (boq_item_id,),
            ).fetchone()
            current_remark = (row["remark"] if row else "") or ""
            has_flag = "[PROVISIONAL]" in current_remark
            if provisional and not has_flag:
                new_remark = f"{current_remark} [PROVISIONAL]".strip()
            elif not provisional and has_flag:
                new_remark = current_remark.replace("[PROVISIONAL]", "").strip()
            else:
                new_remark = current_remark
            conn.execute(
                "UPDATE boq_item SET remark = ? WHERE id = ?",
                (new_remark, boq_item_id),
            )
    except Exception:
        pass


def reset_measured_qty(project_id: int) -> int:
    """清空某项目全部实测数量（回写入口失效/撤销时调用）。返回清零行数。"""
    with db.get_conn() as conn:
        cur = conn.execute("UPDATE boq_item SET measured_qty=0 WHERE project_id=?", (project_id,))
        return cur.rowcount


# =============================================================================
# W1-W6 Excel 保真回写（v2.0 §6.4，Phase 4）
# =============================================================================

MEASURED_COL_TEXT = "measured_qty"  # 新增列表头（已存在则复用，幂等）


def _count_formulas(ws) -> int:
    """统计工作表公式数（cell.value 以 '=' 开头）—— W4 完整性校验用"""
    n = 0
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                n += 1
    return n


def _verify_integrity(ws, snapshot_meta: dict, snapshot_cells: dict, target_col: int) -> dict:
    """W4：保存前校验 —— 公式数/合并格/冻结窗格与写前一致，且原列值 diff=0

    Args:
        ws: openpyxl worksheet（已写完新列）
        snapshot_meta: 写前 {formula_count, merged_ranges, freeze_panes}
        snapshot_cells: 写前 {col_idx: [r1..rN 的值]}（仅原列）
        target_col: 本次写入的新列（跳过对比；新列允许变化）
    Returns:
        {"ok", "formula_count", "merged_ranges", "freeze_panes", "diffs"}
    """
    actual = {
        "formula_count": _count_formulas(ws),
        "merged_ranges": len(ws.merged_cells.ranges),
        "freeze_panes": ws.freeze_panes,
    }
    diffs = []
    for key, now in actual.items():
        if snapshot_meta.get(key) != now:
            diffs.append(f"{key}: {snapshot_meta.get(key)} -> {now}")
    # 原列 diff=0（只允许 target_col 变化）
    for col, vals in snapshot_cells.items():
        if col == target_col:
            continue
        for r, v in enumerate(vals, start=1):
            if ws.cell(row=r, column=col).value != v:
                diffs.append(f"col{col}r{r}: {v!r} 被改动")
    return {
        "ok": not diffs,
        "formula_count": actual["formula_count"],
        "merged_ranges": actual["merged_ranges"],
        "freeze_panes": actual["freeze_panes"],
        "diffs": diffs[:5],
    }


def _safe_save(workbook, source_path: str) -> str:
    """W5：文件被占用 → 回退 <原目录>/_takeoff/<文件名>，返回实际保存路径"""
    import os

    try:
        workbook.save(source_path)
        return source_path
    except PermissionError:
        alt_dir = os.path.join(os.path.dirname(os.path.abspath(source_path)), "_takeoff")
        os.makedirs(alt_dir, exist_ok=True)
        alt_path = os.path.join(alt_dir, os.path.basename(source_path))
        workbook.save(alt_path)
        return alt_path


def writeback_to_excel(
    source_file_path: str,
    project_id: int,
    project_scale: float = 1.0,
) -> dict:
    """W1-W6 Excel 保真回写（v2.0 §6.4）：打开原 Excel → 新增列 → 校验 → 保存

    W1: openpyxl.load_workbook(data_only=False) —— 保公式（不落缓存值）
    W2: 只写新增列（max_col+1，或已存在的 measured_qty 列），不碰原表已有列
    W3: 新增表头不克隆 StyleProxy，直接 new Font/Fill/Alignment 样式对象
    W4: _verify_integrity 保存前校验公式数/合并格/冻结窗格 + 原列 diff=0
    W5: _safe_save 文件被占用 → 回退 <原目录>/_takeoff/ 并告知
    W6: writeback_audit 记录 file_sha256 + written 行数

    行匹配顺序：row_index（解析时 Excel 行号）→ item_key（r123/M-r5）→ code 精确
    """
    import os

    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    from .boq_parser import HEADER_PROBE_ROWS, _detect_headers, _extract_item_key, _row_looks_like_header

    if not os.path.exists(source_file_path):
        raise FileNotFoundError(f"BOQ Excel 不存在: {source_file_path}")

    # W1: 保公式加载
    wb = openpyxl.load_workbook(source_file_path, data_only=False)
    ws = wb.active

    # 表头探测（与 boq_parser B1 同款：前 16 行找 Item+Description）
    header_idx, mapping = 0, {"code": 0, "description": 1, "unit": 2}
    for i, row in enumerate(ws.iter_rows(max_row=HEADER_PROBE_ROWS, values_only=True)):
        m = _detect_headers(row)
        if len(m) >= 2 and _row_looks_like_header(row):
            header_idx, mapping = i, m
            break
    code_col = mapping.get("code", 0) + 1  # 1-based

    # W2: 已有 measured_qty 列 → 复用（幂等）；否则 max_col+1 新增
    measured_col = None
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=header_idx + 1, column=c).value
        if v is not None and MEASURED_COL_TEXT in str(v).strip().lower().replace(" ", ""):
            measured_col = c
            break
    target_col = measured_col or (ws.max_column + 1)

    # 写前快照（W4 校验基准）
    snapshot_cells = {
        c: [ws.cell(row=r, column=c).value for r in range(1, ws.max_row + 1)] for c in range(1, ws.max_column + 1)
    }
    snapshot_meta = {
        "formula_count": _count_formulas(ws),
        "merged_ranges": len(ws.merged_cells.ranges),
        "freeze_panes": ws.freeze_panes,
    }

    items = db.get_boq_items(project_id)
    by_row = {it.row_index: it for it in items if it.row_index}
    by_key = {it.item_key: it for it in items if it.item_key}
    by_code = {it.code: it for it in items if it.code}

    # W3: 新表头（不克隆 StyleProxy，新样式对象）
    header_cell = ws.cell(row=header_idx + 1, column=target_col)
    if not measured_col:
        header_cell.value = MEASURED_COL_TEXT
        header_cell.font = Font(bold=True)
        header_cell.fill = PatternFill("solid", fgColor="D9E2F3")
        header_cell.alignment = Alignment(horizontal="center", vertical="center")

    # 逐行匹配 + 写入 measured_qty
    file_sha256 = compute_file_sha256(source_file_path)  # W6
    written = 0
    for r in range(header_idx + 2, ws.max_row + 1):
        code_val = ws.cell(row=r, column=code_col).value
        item = by_row.get(r)
        if item is None and code_val is not None:
            text = str(code_val)
            item = by_key.get(_extract_item_key(text)) or by_code.get(text.strip())
        if item is None:
            continue
        ws.cell(row=r, column=target_col, value=round(float(item.measured_qty or 0.0), 4))
        # W6: 逐行审计（含源文件 SHA-256）
        _log_writeback_audit(
            project_id, item.id, item.original_qty or 0.0, item.measured_qty or 0.0, "MEASURABLE", file_sha256
        )
        written += 1

    integrity = _verify_integrity(ws, snapshot_meta, snapshot_cells, target_col)
    output_path = _safe_save(wb, source_file_path)  # W5
    return {
        "project_id": project_id,
        "source_file_path": source_file_path,
        "output_path": output_path,
        "written": written,
        "failed": 0,
        "total_items": len(items),
        "verified": integrity["ok"],
        "target_col": target_col,
        "file_sha256": file_sha256,
        "integrity": integrity,
    }
