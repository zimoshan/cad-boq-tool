"""/api/binding 路由（候选生成 + 确认/拒绝）"""

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
