"""SSE 端点支持（Server-Sent Events）"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from webapi.jobs.manager import job_manager
from webapi.jobs.models import JobStatus


async def job_event_stream(job_id: str, poll_interval: float = 0.5) -> AsyncGenerator[str, None]:
    """SSE 流：每 poll_interval 秒检查 job 状态变化并推送。

    终止条件：job.status ∈ {COMPLETED, FAILED, CANCELLED}
    """
    last_status: str | None = None
    last_progress_done: int = -1
    last_progress_total: int | None = None
    while True:
        job = job_manager.get(job_id)
        if not job:
            yield f"event: error\ndata: {json.dumps({'message': 'job not found'})}\n\n"
            return

        # 状态变化
        if job.status.value != last_status:
            yield f"event: status\ndata: {json.dumps({'status': job.status.value})}\n\n"
            last_status = job.status.value

        # 进度变化
        if job.progress.done != last_progress_done or job.progress.total != last_progress_total:
            yield f"event: progress\ndata: {json.dumps(job.progress.to_dict())}\n\n"
            last_progress_done = job.progress.done
            last_progress_total = job.progress.total

        # 终态：补一发 final 事件后退出
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            final = {
                "status": job.status.value,
                "result": job.result,
                "error": job.error,
            }
            yield f"event: final\ndata: {json.dumps(final, default=str)}\n\n"
            return

        await asyncio.sleep(poll_interval)
