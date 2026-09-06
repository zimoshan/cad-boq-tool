"""JobManager + SSE 单元测试（Phase 2）"""
from __future__ import annotations

import asyncio
import pytest

from webapi.jobs.manager import JobManager
from webapi.jobs.models import JobProgress, JobStatus


@pytest.fixture
def jm() -> JobManager:
    return JobManager(max_workers=2)


class TestJobManager:
    """JobManager 进程内任务队列"""

    @pytest.mark.asyncio
    async def test_submit_and_complete(self, jm):
        await jm.start()
        try:
            async def _task(job, progress_cb):
                progress_cb(JobProgress(task_type="step1", done=1, total=2))
                await asyncio.sleep(0.01)
                progress_cb(JobProgress(task_type="step2", done=2, total=2))
                return {"result": "ok"}

            job = await jm.submit("test_task", _task, payload={"x": 1})
            assert job.status == JobStatus.PENDING
            assert jm.get(job.id) is job

            # 等待完成
            for _ in range(50):
                await asyncio.sleep(0.05)
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    break

            assert job.status == JobStatus.COMPLETED
            assert job.result == {"result": "ok"}
            assert job.started_at is not None
            assert job.finished_at is not None
        finally:
            await jm.stop()

    @pytest.mark.asyncio
    async def test_failed_job_captures_error(self, jm):
        await jm.start()
        try:
            async def _bad_task(job, progress_cb):
                raise ValueError("test error")

            job = await jm.submit("bad", _bad_task)
            for _ in range(50):
                await asyncio.sleep(0.05)
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    break

            assert job.status == JobStatus.FAILED
            assert "ValueError" in job.error
            assert "test error" in job.error
        finally:
            await jm.stop()

    @pytest.mark.asyncio
    async def test_cancel_pending_or_running(self, jm):
        await jm.start()
        try:
            async def _slow(job, progress_cb):
                for i in range(20):
                    progress_cb(JobProgress(done=i, total=20))
                    await asyncio.sleep(0.05)
                return "done"

            job = await jm.submit("slow", _slow)
            await asyncio.sleep(0.05)  # 让 worker 开始执行
            ok = await jm.cancel(job.id)
            assert ok is True
            assert job.status == JobStatus.CANCELLED
        finally:
            await jm.stop()

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status(self, jm):
        await jm.start()
        try:
            async def _noop(job, progress_cb):
                return None

            j1 = await jm.submit("a", _noop)
            j2 = await jm.submit("b", _noop)
            # 等完成
            for _ in range(50):
                await asyncio.sleep(0.05)
                if j1.status in (JobStatus.COMPLETED, JobStatus.FAILED) and j2.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    break

            assert len(jm.list_jobs()) == 2
            assert len(jm.list_jobs(JobStatus.COMPLETED)) == 2
            assert len(jm.list_jobs(JobStatus.PENDING)) == 0
        finally:
            await jm.stop()


class TestJobModels:
    """Job / JobProgress 数据模型"""

    def test_job_to_dict(self):
        from webapi.jobs.models import Job
        job = Job(name="t", payload={"x": 1})
        d = job.to_dict()
        assert d["name"] == "t"
        assert d["status"] == "PENDING"
        assert d["payload"] == {"x": 1}
        assert d["result"] is None
        assert d["error"] == ""

    def test_progress_to_dict(self):
        p = JobProgress(task_type="step", done=2, total=10, message="working")
        d = p.to_dict()
        assert d == {"task_type": "step", "done": 2, "total": 10, "message": "working", "extra": {}}
