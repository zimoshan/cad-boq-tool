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
    func_name: str = ""  # 注册表任务名（webapi/jobs/tasks.py TASKS），必填
    payload: dict = {}


@router.get("")
@requires("jobs:read")
async def list_jobs(status: str | None = None) -> dict:
    """列出 Jobs（按状态过滤）"""
    s = JobStatus(status) if status else None
    jobs = job_manager.list_jobs(s)
    return {"jobs": [j.to_dict() for j in jobs], "total": len(jobs)}


@router.get("/stats")
@requires("jobs:read")
async def get_stats() -> dict:
    """按状态统计 job 数（Round 7 增强：监控/管理面板）"""
    return job_manager.stats()


@router.get("/tasks")
@requires("jobs:read")
async def list_tasks() -> dict:
    """列出可提交的任务名（func_name 注册表）"""
    from webapi.jobs.tasks import list_task_names

    names = list_task_names()
    return {"tasks": names, "total": len(names)}


@router.post("/cleanup")
@requires("jobs:write")
async def cleanup_jobs(keep_completed: int = 50) -> dict:
    """清理旧 completed/failed/cancelled jobs（避免内存无限增长）

    keep_completed: 保留最近 N 个 completed（默认 50）
    """
    deleted = job_manager.cleanup(keep_completed=keep_completed)
    return {"deleted": deleted, "remaining": len(job_manager._jobs)}


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
    """提交一个 Job（Phase 2：按注册表 func_name 提交真实业务任务）

    func_name 取值（webapi/jobs/tasks.py TASKS）：
      - boq.parse        解析 BOQ Excel
      - cad.parse         解析 CAD/DWG 文件
      - extraction.run   工程对象提取（设备/线性/面积）
      - takeoff.sheet     单图 takeoff（6 阶段管线）
      - takeoff.folder    文件夹 takeoff（多图聚合）
      - binding.generate  生成绑定候选（4 层）
    """
    if not req.func_name:
        raise HTTPException(status_code=422, detail="func_name required (see webapi/jobs/tasks.py TASKS)")
    try:
        job = await job_manager.submit_by_name(req.name, req.func_name, req.payload, created_by="sysadmin")
    except KeyError:
        from webapi.jobs.tasks import list_task_names

        raise HTTPException(
            status_code=404,
            detail=f"Unknown task: {req.func_name}. Available: {', '.join(list_task_names())}",
        ) from None
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
