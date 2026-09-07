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


async def list_binding_candidates(
    db: AsyncSession,
    project_id: int,
    status: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Phase 4：候选列表（UI 确认/拒绝工作台用）

    join engineering_object / boq_item 取展示字段（tag/block_name/description/code）；
    表不存在或列缺失 → 返回 []（跨 schema 容错，同双引擎策略）。
    """
    sql = """
        SELECT bc.id, bc.project_id, bc.engineering_object_id, bc.boq_item_id,
               bc.method, bc.score, bc.confidence, bc.reason, bc.status, bc.created_at,
               eo.tag AS eo_tag, eo.block_name AS eo_block,
               bi.description AS boq_description, bi.code AS boq_code, bi.unit AS boq_unit
        FROM binding_candidate bc
        LEFT JOIN engineering_object eo ON eo.id = bc.engineering_object_id
        LEFT JOIN boq_item bi ON bi.id = bc.boq_item_id
        WHERE bc.project_id = :pid
    """
    args: dict[str, Any] = {"pid": project_id}
    if status:
        sql = sql + " AND bc.status = :status"
        args["status"] = status
    sql += f" ORDER BY bc.id DESC LIMIT {int(limit)}"
    try:
        result = await db.execute(text(sql), args)
        return [dict(row._mapping) for row in result]
    except Exception:
        # binding_candidate 表缺失（fresh sqlite / PG 未迁移）→ 空列表
        return []


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
            raise ServiceError(str(e), status_code=409, code="duplicate_binding") from e
        raise NotFoundError("Candidate", candidate_id) from e


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


# ===== Phase 5: Negative Sample Query + Evaluation =====


async def list_negative_samples(
    db: AsyncSession,
    project_id: int,
    method: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """v1.0 §17 查询负样本（拒绝的绑定记录）

    用于 UI 展示 + 评测闭环（precision/recall 计算）。
    """
    sql = "SELECT * FROM negative_sample WHERE project_id = :pid"
    args: dict[str, Any] = {"pid": project_id}
    if method:
        sql += " AND method = :method"
        args["method"] = method
    sql += f" ORDER BY id DESC LIMIT {int(limit)}"
    try:
        result = await db.execute(text(sql), args)
        return [dict(row._mapping) for row in result]
    except Exception:
        return []


async def get_evaluation_report(db: AsyncSession, project_id: int) -> dict[str, Any]:
    """v1.0 §20 评测报告：按方法分层 precision/recall

    数据源：
    - binding_candidate（PENDING/ACCEPTED/REJECTED）
    - negative_sample（reject 时自动写入）
    - mapping（confirm 时写入）

    precision = confirmed / (confirmed + rejected) per method
    recall = confirmed / total_eo per method（近似：有候选的 EO 数）
    """
    from datetime import datetime

    # 统计各方法的候选/确认/拒绝数
    stats_sql = """
        SELECT method,
               COUNT(*) AS total,
               SUM(CASE WHEN status='ACCEPTED' THEN 1 ELSE 0 END) AS confirmed,
               SUM(CASE WHEN status='REJECTED' THEN 1 ELSE 0 END) AS rejected,
               SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) AS pending
        FROM binding_candidate
        WHERE project_id = :pid
        GROUP BY method
    """
    try:
        result = await db.execute(text(stats_sql), {"pid": project_id})
        rows = [dict(row._mapping) for row in result]
    except Exception:
        rows = []

    by_method = {}
    total_confirmed = 0
    total_rejected = 0
    total_candidates = 0

    for r in rows:
        method = r["method"] or "unknown"
        confirmed = r["confirmed"] or 0
        rejected = r["rejected"] or 0
        total = r["total"] or 0
        # precision = confirmed / (confirmed + rejected)（排除 PENDING）
        judged = confirmed + rejected
        precision = confirmed / judged if judged > 0 else 0.0
        by_method[method] = {
            "candidates": total,
            "confirmed": confirmed,
            "rejected": rejected,
            "pending": r["pending"] or 0,
            "precision": round(precision, 4),
        }
        total_confirmed += confirmed
        total_rejected += rejected
        total_candidates += total

    overall_judged = total_confirmed + total_rejected
    overall_precision = total_confirmed / overall_judged if overall_judged > 0 else 0.0

    return {
        "project_id": project_id,
        "total_candidates": total_candidates,
        "total_confirmed": total_confirmed,
        "total_rejected": total_rejected,
        "by_method": by_method,
        "overall_precision": round(overall_precision, 4),
        "generated_at": datetime.now().isoformat(),
    }
