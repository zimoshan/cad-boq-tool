"""BOQ 域 Service（包装 app/boq 业务函数）

Phase 0：
  - POST /api/boq/parse：解析 BOQ Excel（app/boq/boq_parser.parse_boq + B1 4 种表头识别）
  - POST /api/boq/writeback：回写 measured_qty（app/boq/writeback.write_back_quantities）

B1 修复：BOQ-001 4 种表头识别（v2.0 §2.1，PHASE 0 第 2 批 P0-6 落实）
B2 扩展：boq_item 模型加 section/item_key/brand/bill_qty/installed_qty/qty_remaining（已在 P0-5 schema 完成）
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.boq.boq_parser import parse_boq
from webapi.services.base import NotFoundError, ServiceError


async def parse_boq_excel(
    db: AsyncSession,
    project_id: int,
    file_path: str,
) -> dict[str, Any]:
    """包装 app/boq/boq_parser.parse_boq

    B1 修复：4 种 BOQ 表头识别（电气/机械/建筑/结构）
    完整实现待 P0-6 落实，Phase 0 阶段先用 app/boq/boq_parser.py 的 BOQ_HEADER_CANDIDATES
    """
    try:
        items, meta = parse_boq(file_path)
        return {
            "project_id": project_id,
            "file_path": file_path,
            "item_count": len(items),
            "meta": meta,
        }
    except FileNotFoundError:
        raise NotFoundError("BOQ file", file_path)
    except Exception as e:
        raise ServiceError(f"BOQ parse failed: {e}", code="boq_parse_error") from e


async def writeback_quantities(
    db: AsyncSession,
    project_id: int,
    project_scale: float = 1.0,
    source_file_path: str = "",
) -> dict[str, Any]:
    """包装 app/boq/writeback.write_back_quantities

    P0-15 B5 S7 Excel 保真回写（写回 boq_item.measured_qty 不动原 original_qty）
    P4 增强：source_file_path 传入后算 SHA-256 写到 writeback_audit.file_sha256
    """
    from app.boq.writeback import compute_file_sha256
    from app.boq.writeback import write_back_quantities as _write_back

    try:
        file_sha = compute_file_sha256(source_file_path) if source_file_path else ""
        # Phase 4 增强：通过 monkey-patch _log_writeback_audit 注入 file_sha256
        import app.boq.writeback as wb_mod

        original_log = wb_mod._log_writeback_audit

        def _patched_log(project_id, boq_item_id, original_qty, measured_qty, takability, file_sha256=""):
            return original_log(
                project_id, boq_item_id, original_qty, measured_qty, takability, file_sha256 or file_sha
            )

        wb_mod._log_writeback_audit = _patched_log
        try:
            result = _write_back(project_id=project_id, project_scale=project_scale)
        finally:
            wb_mod._log_writeback_audit = original_log
        return result
    except Exception as e:
        raise ServiceError(f"Writeback failed: {e}", code="boq_writeback_error") from e


async def export_boq_to_excel(
    db: AsyncSession,
    project_id: int,
    output_path: str,
    overwrite_original: bool = False,
) -> dict[str, Any]:
    """v1.0 §15 工程量回写：导出实测值到 Excel

    包装 app/report.py export_report + app/boq/writeback.py：
    - 读 boq_item.measured_qty + original_qty
    - 写 xlsx（保留对照列）
    - overwrite_original=False 时：原数量列保留，新增 measured_qty 列
    - overwrite_original=True 时：measured_qty 覆盖 original_qty
    """
    import os

    from app.report import export_report

    if not output_path:
        raise ServiceError("output_path required", code="invalid_input") from None
    if not output_path.endswith((".xlsx", ".xls")):
        raise ServiceError("output_path must be .xlsx or .xls", code="invalid_input") from None

    # 确保目录存在
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    try:
        # export_report 实际签名：export_report(project_id, sheet_id, out_path, sheet_scale, project_scale, use_measured)
        # Phase 0: sheet_id 传 0（导出全项目），use_measured 反映 overwrite_original
        rows_written = export_report(
            project_id=project_id,
            sheet_id=0,
            out_path=output_path,
            use_measured=overwrite_original,
        )
        return {
            "project_id": project_id,
            "output_path": output_path,
            "written_rows": rows_written,
            "skipped_rows": 0,
            "by_takability": {},
        }
    except Exception as e:
        raise ServiceError(f"Export BOQ failed: {e}", code="boq_export_error") from e
