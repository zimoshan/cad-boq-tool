"""JobManager 单例（Phase 2）

设计：
  - 进程内 asyncio.Queue 任务队列
  - 启动时启动 N 个 worker 协程（后台任务）
  - 任务回调 progress_cb(done, total, message) 更新 Job.progress
  - JobState 通过 threading/asyncio 双支持（readers 锁 + writers 锁）
  - SSE 订阅：每 Job 维护一个 asyncio.Queue[int]（event 计数），SSE 端点轮询差异推送

Phase 2 简化：单进程 asyncio，job 状态在内存；进程重启会丢（Phase 3 持久化到 PG job 表）
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

from webapi.jobs.models import Job, JobProgress, JobStatus

logger = logging.getLogger(__name__)


# 任务签名：async (job, progress_cb) -> result
JobFunc = Callable[[Job, Callable[[JobProgress], None]], Awaitable[Any]]


class JobManager:
    """单例 JobManager（Phase 2 内存版）"""

    def __init__(self, max_workers: int = 2) -> None:
        self._jobs: dict[str, Job] = {}
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._max_workers = max_workers
        self._started = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """启动 worker 池（app lifespan 调用）"""
        if self._started:
            return
        self._started = True
        for i in range(self._max_workers):
            t = asyncio.create_task(self._worker_loop(i), name=f"job-worker-{i}")
            self._workers.append(t)
        logger.info(f"JobManager started with {self._max_workers} workers")

    async def stop(self, timeout: float = 2.0) -> None:
        """停止 worker（app lifespan 关闭 / 测试 fixture）

        带 timeout 避免 worker 在 _execute 中阻塞时 hang 住。
        """
        for t in self._workers:
            t.cancel()
        # 给 worker 一点时间响应 cancel
        try:
            await asyncio.wait_for(
                asyncio.gather(*list(self._workers), return_exceptions=True),
                timeout=timeout,
            )
        except TimeoutError:
            logger.warning(f"JobManager stop 超时 {timeout}s，强制结束")
        self._workers.clear()
        self._started = False
        logger.info("JobManager stopped")

    async def submit(self, name: str, func: JobFunc, payload: dict | None = None, created_by: str = "sysadmin") -> Job:
        """提交一个 Job：自动把 func 注入到 payload['__func__']"""
        merged = dict(payload or {})
        merged["__func__"] = func  # worker 取出执行
        job = Job(name=name, payload=merged, created_by=created_by)
        self._jobs[job.id] = job
        await self._queue.put(job)
        logger.info(f"Job submitted: {job.id} {name}")
        return job

    async def submit_by_name(
        self, name: str, func_name: str, payload: dict | None = None, created_by: str = "sysadmin"
    ) -> Job:
        """按注册表名提交真实业务任务（Phase 2：/api/jobs/submit 接线）

        func_name 必须是 webapi.jobs.tasks.TASKS 中登记的键，
        否则抛 KeyError（router 层转 404）。
        """
        from webapi.jobs.tasks import TASKS

        if func_name not in TASKS:
            raise KeyError(f"Unknown task: {func_name}")
        return await self.submit(name=name, func=TASKS[func_name], payload=payload, created_by=created_by)

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self, status: JobStatus | None = None) -> list[Job]:
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def stats(self) -> dict[str, int]:
        """按状态统计 job 数（Round 7 增强）"""
        counts = {s.value: 0 for s in JobStatus}
        for job in self._jobs.values():
            counts[job.status.value] += 1
        return counts

    def cleanup(self, keep_completed: int = 50) -> int:
        """清理旧 completed/failed/cancelled jobs，保留最近 N 个 completed

        Returns: 删除的 job 数
        """
        to_delete: list[str] = []
        for status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            jobs = [j for j in self._jobs.values() if j.status == status]
            jobs.sort(key=lambda j: j.created_at, reverse=True)
            keep = keep_completed if status == JobStatus.COMPLETED else 5
            for j in jobs[keep:]:
                to_delete.append(j.id)
        for jid in to_delete:
            del self._jobs[jid]
        return len(to_delete)

    async def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False
        job.status = JobStatus.CANCELLED
        job.finished_at = job.finished_at or job.started_at or job.created_at
        return True

    async def _worker_loop(self, worker_id: int) -> None:
        """worker 主循环：从 queue 拿 job 执行"""
        while True:
            try:
                job = await self._queue.get()
            except asyncio.CancelledError:
                break
            if job.status == JobStatus.CANCELLED:
                continue
            try:
                await self._execute(job)
            except asyncio.CancelledError:
                # job 执行中被 cancel：标 CANCELLED 并退出 worker
                if job.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
                    job.status = JobStatus.CANCELLED
                break

    async def _execute(self, job: Job) -> None:
        """执行单个 job"""
        job.status = JobStatus.RUNNING
        from datetime import datetime

        job.started_at = datetime.now()
        try:
            func = job.payload.pop("__func__")

            def _progress(p: JobProgress) -> None:
                job.progress = p

            result = await func(job, _progress)
            job.result = result
            job.status = JobStatus.COMPLETED
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
        except Exception as e:
            job.error = f"{type(e).__name__}: {e}"
            job.status = JobStatus.FAILED
            logger.error(f"Job {job.id} failed: {e}\n{traceback.format_exc()}")
        finally:
            from datetime import datetime

            job.finished_at = datetime.now()


# ---------- 单例 ----------

job_manager = JobManager(max_workers=2)
