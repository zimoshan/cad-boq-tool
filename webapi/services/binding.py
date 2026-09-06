"""绑定域 Service（包装 app/binding 业务函数）

Phase 0：
  - POST /api/binding/generate：生成候选（matcher.generate_candidates）
  - POST /api/binding/confirm：确认（reviewer.confirm_binding）
  - POST /api/binding/reject：拒绝（reviewer.reject_binding）→ v1.0 §17 写 negative_sample

#19 选 A：app/binding 业务函数保留，Service 层包装
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.binding.matcher import generate_candidates
from app.binding.reviewer import confirm_binding as _confirm_binding
from app.binding.reviewer import reject_binding as _reject_binding
from webapi.services.base import NotFoundError, ServiceError


def _log_negative_sample(
    db: AsyncSession,
    project_id: int,
    candidate_id: int,
    reason: str = "",
) -> None:
    """v1.0 §17：reject 时自动写 negative_sample（正负样本）"""
    try:
        # 从 binding_candidate 取字段
        row = db.execute(
            text("SELECT engineering_object_id, boq_item_id, method, confidence FROM binding_candidate WHERE id = :id"),
            {"id": candidate_id},
        ).first()
        if not row:
            return
        # 写 negative_sample（alembic 0005 表）
        from app.db import _SCHEMA  # noqa: F401

        try:
            db.execute(
                text("""INSERT INTO negative_sample(project_id, engineering_object_id, boq_item_id, reason, confidence_at_reject, method, rejected_by, created_at)
                       VALUES(:pid, :eoid, :boqid, :reason, :conf, :method, :rej_by, :ts)"""),
                {
                    "pid": project_id,
                    "eoid": row[0],
                    "boqid": row[1],
                    "reason": reason,
                    "conf": row[2] or 0,
                    "method": row[3] or "LLM",
                    "rej_by": "sysadmin",
                    "ts": "",
                },
            )
        except Exception:
            pass  # 表不存在静默（Phase 0 早期）
    except Exception:
        pass


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
        raise ServiceError(f"Generate candidates failed: {e}", code="binding_generate_error") from e


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
    """包装 app/binding/reviewer.reject_binding

    v1.0 §17：reject 时自动写 negative_sample 表
    """
    try:
        result = _reject_binding(candidate_id=candidate_id, reason=reason, by_user=by_user)
        # 写 negative_sample（best-effort，失败不影响主流程）
        try:
            from app import db as app_db

            with app_db.get_conn() as conn:
                row = conn.execute(
                    "SELECT project_id, engineering_object_id, boq_item_id, method, confidence FROM binding_candidate WHERE id=?",
                    (candidate_id,),
                ).fetchone()
            if row:
                project_id = row["project_id"]
                with app_db.get_conn() as conn:
                    conn.execute(
                        "INSERT INTO negative_sample(project_id, engineering_object_id, boq_item_id, reason, confidence_at_reject, method, rejected_by) VALUES(?,?,?,?,?,?,?)",
                        (
                            project_id,
                            row["engineering_object_id"],
                            row["boq_item_id"],
                            reason,
                            row["confidence"] or 0,
                            row["method"] or "LLM",
                            by_user,
                        ),
                    )
        except Exception:
            pass
        return result
    except Exception as e:
        raise ServiceError(f"Reject binding failed: {e}", code="binding_reject_error") from e
