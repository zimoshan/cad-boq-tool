"""/api/jobs 路由（Phase 2 JobManager + SSE）"""
# 不使用 from __future__ import annotations：Pydantic 2.8 + FastAPI 0.115 forward ref 解析问题

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from webapi.auth.decorators import requires
from webapi.jobs.manager import job_manager
from webapi.jobs.models import JobStatus
from webapi.jobs.sse import job_event_stream

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobSubmitRequest(BaseModel):
    name: str
    func_name: str = ""  # 预留：注册的任务名（Phase 2 占位）
    payload: dict = {}


@router.get("")
@requires("jobs:read")
async def list_jobs(status: str | None = None) -> dict:
    """列出 Jobs（按状态过滤）"""
    s = JobStatus(status) if status else None
    jobs = job_manager.list_jobs(s)
    return {"jobs": [j.to_dict() for j in jobs], "total": len(jobs)}


@router.get("/{job_id}")
@requires("jobs:read")
async def get_job(job_id: str) -> dict:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job.to_dict()


@router.post("/submit")
@requires("jobs:write")
async def submit_job(req: JobSubmitRequest) -> dict:
    """提交一个 Job（Phase 2 占位：func_name 路由待 Phase 2 完整实现）"""

    async def _noop(job, progress_cb):
        progress_cb(job.progress.__class__(task_type="noop", done=1, total=1, message="ok"))
        return {"result": "noop done"}

    job = await job_manager.submit(req.name, _noop, req.payload, created_by="sysadmin")
    return job.to_dict()


@router.post("/{job_id}/cancel")
@requires("jobs:write")
async def cancel_job(job_id: str) -> dict:
    ok = await job_manager.cancel(job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot cancel: job not found or already finished")
    return {"ok": ok, "job_id": job_id}


@router.get("/{job_id}/stream")
@requires("jobs:read")
async def stream_job(job_id: str):
    """SSE 端点：实时推送 job 进度 + 终态"""
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        job_event_stream(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 兼容
        },
    )
