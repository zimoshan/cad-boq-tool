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
from app.boq.writeback import write_back_quantities
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
        raise ServiceError(f"BOQ parse failed: {e}", code="boq_parse_error")


async def writeback_quantities(
    db: AsyncSession,
    project_id: int,
    project_scale: float = 1.0,
) -> dict[str, Any]:
    """包装 app/boq/writeback.write_back_quantities

    P0-15 B5 S7 Excel 保真回写（写回 boq_item.measured_qty 不动原 original_qty）
    """
    try:
        return write_back_quantities(project_id=project_id, project_scale=project_scale)
    except Exception as e:
        raise ServiceError(f"Writeback failed: {e}", code="boq_writeback_error")
