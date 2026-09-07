"""/api/binding 路由（候选生成 + 确认/拒绝 + Phase 5 负样本/评测）"""

# 不使用 `from __future__ import annotations`：Pydantic 2.8 + FastAPI 0.115 解析
# type hints 时 namespace 不含 forward ref 名称（_types_namespace 不取 module globals），
# 即时求值 annotation 可避免此问题。
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from webapi.auth.decorators import requires
from webapi.db import get_db
from webapi.schemas.binding import (
    ConfirmBindingRequest,
    GenerateCandidatesRequest,
    GenerateCandidatesResponse,
    RejectBindingRequest,
)
from webapi.services import binding as binding_service

router = APIRouter(prefix="/api/binding", tags=["binding"])


@router.get("/candidates")
@requires("binding:read")
async def candidates(
    project_id: int,
    status: str | None = None,
    limit: int = 500,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Phase 4：候选列表（join BOQ/工程对象展示字段，status 过滤）"""
    rows = await binding_service.list_binding_candidates(db, project_id, status, limit)
    return {"items": rows, "total": len(rows)}


@router.post("/generate", response_model=GenerateCandidatesResponse)
@requires("binding:generate")
async def generate(req: GenerateCandidatesRequest, db: AsyncSession = Depends(get_db)) -> GenerateCandidatesResponse:
    """生成绑定候选（4 层：历史→规则→语义→LLM 精排）"""
    result = await binding_service.generate_candidates_for_project(
        db, req.project_id, req.sheet_id, req.use_llm, req.top_n
    )
    return GenerateCandidatesResponse(**result)


@router.post("/confirm")
@requires("binding:confirm")
async def confirm(req: ConfirmBindingRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """确认候选 → 写 mapping + 跨图 SUPERSEDED（reviewer.confirm_binding）"""
    return await binding_service.confirm_binding(db, req.candidate_id, req.by_user)


@router.post("/reject")
@requires("binding:reject")
async def reject(req: RejectBindingRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """拒绝候选"""
    return await binding_service.reject_binding(db, req.candidate_id, req.reason, req.by_user)


# ===== Phase 5: Negative Sample + Evaluation =====


@router.get("/negative-samples")
@requires("binding:read")
async def negative_samples(
    project_id: int,
    method: str | None = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """v1.0 §17 查询负样本（拒绝的绑定记录）"""
    items = await binding_service.list_negative_samples(db, project_id, method, limit)
    return {"items": items, "total": len(items)}


@router.get("/evaluation")
@requires("binding:read")
async def evaluation(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """v1.0 §20 评测报告：按方法分层 precision/recall"""
    return await binding_service.get_evaluation_report(db, project_id)


# ===== Phase 6: 闸门（版本冲突 / 重复计价） =====


@router.get("/version-conflicts")
@requires("binding:read")
async def version_conflicts(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """P6-1 版本冲突检测：同图名多 revision → stale 图纸 + 其上 mapping"""
    return await binding_service.get_version_conflicts(db, project_id)


@router.get("/duplicate-pricing")
@requires("binding:read")
async def duplicate_pricing(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """P6-2 重复计价检测：同 block/layer 锚点命中 ≥2 个 BOQ 明细"""
    return await binding_service.get_duplicate_pricing(db, project_id)
