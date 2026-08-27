"""Excel 报表导出：依据图纸的算量清单（与原 BOQ 对比）"""
from __future__ import annotations

import logging
import time

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import db, measure

logger = logging.getLogger(__name__)


def export_report(project_id: int, sheet_id: int, out_path: str,
                  sheet_scale: float = 1.0, project_scale: float = 1.0) -> int:
    """导出算量清单。返回导出行数"""
    started = time.perf_counter()
    items = db.get_boq_items(project_id)
    wb = Workbook()
    ws = wb.active
    ws.title = "算量清单"

    headers = ["编号", "描述", "单位", "图纸计量数量", "原清单数量", "差值", "映射方式", "比例因子"]
    header_fill = PatternFill("solid", fgColor="D9E2F3")
    header_font = Font(bold=True)
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    red_fill = PatternFill("solid", fgColor="F8CBAD")   # 超出 → 红
    green_fill = PatternFill("solid", fgColor="C6EFCE") # 不足 → 绿

    row = 2
    for item in items:
        result = measure.compute_item(item, sheet_id, sheet_scale, project_scale)
        qty = result["qty"]
        orig = item.original_qty or 0.0
        diff = round(qty - orig, 4)
        modes = sorted({m.mode for m in db.get_mappings(item.id, sheet_id)})
        mode_str = ",".join(modes) if modes else ""

        vals = [item.code, item.description, item.unit, qty, orig if orig else "", diff,
                mode_str, result["factor"]]
        for c, v in enumerate(vals, start=1):
            ws.cell(row=row, column=c, value=v)

        diff_cell = ws.cell(row=row, column=6)
        if diff > 0:
            diff_cell.fill = red_fill
        elif diff < 0:
            diff_cell.fill = green_fill
        row += 1

    # 列宽
    widths = [14, 48, 8, 16, 14, 12, 12, 10]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    wb.save(out_path)
    elapsed = (time.perf_counter() - started) * 1000
    logger.info("export_report: project_id=%s sheet_id=%s items=%d elapsed_ms=%.1f", project_id, sheet_id, row - 2, elapsed)
    return row - 2


def export_items_to_excel(items: list, out_path: str) -> int:
    """导出 AI 算量结果（TakeoffItem 列表）到 Excel。

    22C-2 配套函数：被 ai_results_dialog 调用
    items: list[TakeoffItem]（来自 app.takeoff.orchestrator.TakeoffItem）
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "AI 算量结果"

    headers = ["编号", "描述", "单位", "数量", "置信度", "来源", "理由", "冲突"]
    header_fill = PatternFill("solid", fgColor="D9E2F3")
    header_font = Font(bold=True)
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # 颜色：按置信度 + 冲突
    high_fill = PatternFill("solid", fgColor="C6EFCE")
    mid_fill = PatternFill("solid", fgColor="FFEB9C")
    low_fill = PatternFill("solid", fgColor="FFC7CE")
    conflict_fill = PatternFill("solid", fgColor="F8CBAD")

    row = 2
    for it in items:
        conf = it.confidence
        is_conflict = it.raw.get("_conflict", False)
        vals = [
            it.code, it.description, it.unit, round(it.quantity, 4),
            f"{conf:.0%}", it.source_layer or it.source_block or "-",
            (it.reasoning or "")[:200],
            "是" if is_conflict else "",
        ]
        for c, v in enumerate(vals, start=1):
            ws.cell(row=row, column=c, value=v)
        # 整行染色
        if is_conflict:
            for c in range(1, len(headers) + 1):
                ws.cell(row=row, column=c).fill = conflict_fill
        elif conf >= 0.7:
            for c in range(1, len(headers) + 1):
                ws.cell(row=row, column=c).fill = high_fill
        elif conf >= 0.5:
            for c in range(1, len(headers) + 1):
                ws.cell(row=row, column=c).fill = mid_fill
        else:
            for c in range(1, len(headers) + 1):
                ws.cell(row=row, column=c).fill = low_fill
        row += 1

    # 列宽
    widths = [14, 40, 8, 12, 10, 24, 50, 8]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    wb.save(out_path)
    return row - 2
