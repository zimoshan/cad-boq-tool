"""/api/boq 路由（Excel 解析 + 回写 + 导出）"""

# Pydantic 2.8 + FastAPI 0.115 解析 type hints 时 namespace 不含 forward ref 名称，
# 即时求值 annotation 避免 _PydanticUndefinedAnnotation。
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from webapi.auth.decorators import requires
from webapi.db import get_db
from webapi.schemas.boq import (
    ExportBoqRequest,
    ExportBoqResponse,
    ParseBoqRequest,
    ParseBoqResponse,
    WritebackRequest,
    WritebackResponse,
    WritebackToExcelRequest,
    WritebackToExcelResponse,
)
from webapi.services import boq as boq_service

router = APIRouter(prefix="/api/boq", tags=["boq"])


@router.post("/parse", response_model=ParseBoqResponse)
@requires("boq:parse")
async def parse_boq(req: ParseBoqRequest, db: AsyncSession = Depends(get_db)) -> ParseBoqResponse:
    """解析 BOQ Excel（B1 修复：4 种表头识别，A.2 第 2 批 P0-6 落实）"""
    result = await boq_service.parse_boq_excel(db, req.project_id, req.file_path)
    return ParseBoqResponse(**result)


@router.post("/writeback", response_model=WritebackResponse)
@requires("boq:writeback")
async def writeback(req: WritebackRequest, db: AsyncSession = Depends(get_db)) -> WritebackResponse:
    """回写 measured_qty（B5 S7 Excel 保真回写，P0-15 落实）"""
    result = await boq_service.writeback_quantities(db, req.project_id, req.project_scale)
    return WritebackResponse(**result)


@router.post("/writeback-to-excel", response_model=WritebackToExcelResponse)
@requires("boq:writeback")
async def writeback_to_excel(req: WritebackToExcelRequest) -> WritebackToExcelResponse:
    """P4 v1.0 §6.4 W1-W6 Excel 保真回写：
    W1 保公式加载 → W2 只写新增列 → W3 新表头样式 → W4 完整性校验 → W5 锁文件回退 → W6 审计
    """
    result = await boq_service.writeback_to_original_excel(
        None, req.project_id, req.source_file_path, req.project_scale
    )
    return WritebackToExcelResponse(**result)


# P4 v1.0 §6.4 完整 Excel 保真回写契约
class WritebackAuditedRequest(WritebackRequest):
    """回写 + 源文件 SHA-256 审计（v1.0 §6.4 防 tamper）"""

    source_file_path: str = ""  # BOQ 源 Excel 路径


class WritebackAuditedResponse(WritebackResponse):
    file_sha256: str = ""  # 源文件 SHA-256
    audited_rows: int = 0  # 成功审计行数


@router.post("/writeback-audited", response_model=WritebackAuditedResponse)
@requires("boq:writeback")
async def writeback_audited(
    req: WritebackAuditedRequest, db: AsyncSession = Depends(get_db)
) -> WritebackAuditedResponse:
    """v1.0 §6.4 完整 Excel 保真回写契约：
    1. 算 source_file_path 的 SHA-256
    2. 写回 measured_qty（不动 original_qty / bill_qty / formula / merge_cells）
    3. writeback_audit.file_sha256 记录 SHA-256
    4. 返回 SHA-256 + audited_rows（人工可对比校验）
    """
    from app.boq.writeback import compute_file_sha256

    file_sha = compute_file_sha256(req.source_file_path) if req.source_file_path else ""
    result = await boq_service.writeback_quantities(db, req.project_id, req.project_scale, req.source_file_path)
    return WritebackAuditedResponse(
        project_id=result.get("project_id", req.project_id),
        written=result.get("written", 0),
        failed=result.get("failed", 0),
        file_sha256=file_sha,
        audited_rows=result.get("written", 0),
    )


@router.post("/export", response_model=ExportBoqResponse)
@requires("boq:export")
async def export_boq(req: ExportBoqRequest, db: AsyncSession = Depends(get_db)) -> ExportBoqResponse:
    """v1.0 §15 工程量回写：导出实测值到 Excel（overwrite_original=False 保留对照列）"""
    result = await boq_service.export_boq_to_excel(db, req.project_id, req.output_path, req.overwrite_original)
    return ExportBoqResponse(**result)
