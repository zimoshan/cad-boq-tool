"""webapi/jobs: 进程内 JobManager + SSE（v2.0 ADR-05）

Phase 2 启动：单进程异步任务队列（不引入 Celery/Redis，保持模块化单体）。
"""

from webapi.jobs.manager import JobManager, JobStatus, job_manager
from webapi.jobs.models import Job, JobProgress

__all__ = ["JobManager", "job_manager", "JobStatus", "Job", "JobProgress"]
