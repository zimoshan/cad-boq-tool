"""绑定域 Service（包装 app/binding 业务函数）

Phase 0：
  - POST /api/binding/generate：生成候选（matcher.generate_candidates）
  - POST /api/binding/confirm：确认（reviewer.confirm_binding）
  - POST /api/binding/reject：拒绝（reviewer.reject_binding）

#19 选 A：app/binding 业务函数保留，Service 层包装
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.binding.matcher import generate_candidates
from app.binding.reviewer import confirm_binding as _confirm_binding
from app.binding.reviewer import reject_binding as _reject_binding
from webapi.services.base import NotFoundError, ServiceError


async def generate_candidates_for_project(
    db: AsyncSession,
    project_id: int,
    sheet_id: int | None = None,
    use_llm: bool = True,
    top_n: int = 5,
) -> dict[str, Any]:
    """包装 app/binding/matcher.generate_candidates"""
    try:
        # matcher.generate_candidates 当前用同步 DB conn；Phase 0 业务层保持同步
        # Service 层将同步结果包装为 Pydantic-friendly dict
        result = generate_candidates(
            project_id=project_id,
            sheet_id=sheet_id,
            use_llm=use_llm,
            top_n=top_n,
        )
        return {
            "project_id": project_id,
            "sheet_id": sheet_id,
            "use_llm": use_llm,
            "candidates_created": result.get("candidates", 0),
            "stats": result.get("stats", {}),
        }
    except Exception as e:
        raise ServiceError(f"Generate candidates failed: {e}", code="binding_generate_error")


async def confirm_binding(
    db: AsyncSession,
    candidate_id: int,
    by_user: str = "sysadmin",
) -> dict[str, Any]:
    """包装 app/binding/reviewer.confirm_binding"""
    try:
        result = _confirm_binding(candidate_id=candidate_id, by_user=by_user)
        return result
    except Exception as e:
        # _accepted_block_boq 抛 ReviewError（已绑定其他 BOQ）→ 409 Conflict
        if "已绑定" in str(e) or "already bound" in str(e).lower():
            raise ServiceError(str(e), status_code=409, code="duplicate_binding")
        raise NotFoundError("Candidate", candidate_id)


async def reject_binding(
    db: AsyncSession,
    candidate_id: int,
    reason: str = "",
    by_user: str = "sysadmin",
) -> dict[str, Any]:
    """包装 app/binding/reviewer.reject_binding"""
    try:
        return _reject_binding(candidate_id=candidate_id, reason=reason, by_user=by_user)
    except Exception as e:
        raise ServiceError(f"Reject binding failed: {e}", code="binding_reject_error")
