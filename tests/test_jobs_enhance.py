"""jobs 增强测试（stats + cleanup）"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from webapi.jobs.manager import JobManager
from webapi.jobs.models import Job, JobProgress, JobStatus


@pytest.fixture
def jm() -> JobManager:
    return JobManager(max_workers=0)


def _make_job(jid, status, created_at):
    return Job(id=jid, name="t", status=status, progress=JobProgress(), created_at=created_at)


class TestJobsStats:
    def test_empty_stats(self, jm):
        assert jm.stats() == {"PENDING": 0, "RUNNING": 0, "COMPLETED": 0, "FAILED": 0, "CANCELLED": 0}

    def test_stats_counts_by_status(self, jm):
        now = datetime.now()
        for i, st in enumerate([JobStatus.PENDING, JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]):
            jm._jobs[f"j{i}"] = _make_job(f"j{i}", st, now)
        stats = jm.stats()
        assert stats["PENDING"] == 2
        assert stats["RUNNING"] == 1
        assert stats["COMPLETED"] == 1
        assert stats["FAILED"] == 1
        assert stats["CANCELLED"] == 1


class TestJobsCleanup:
    def test_cleanup_keeps_recent_completed(self, jm):
        now = datetime.now()
        for i in range(60):
            jm._jobs[f"j{i}"] = _make_job(f"j{i}", JobStatus.COMPLETED, now - timedelta(minutes=i))
        deleted = jm.cleanup(keep_completed=50)
        assert deleted == 10
        assert len(jm._jobs) == 50

    def test_cleanup_keeps_only_5_failed_cancelled(self, jm):
        now = datetime.now()
        for i in range(10):
            jm._jobs[f"f{i}"] = _make_job(f"f{i}", JobStatus.FAILED, now - timedelta(minutes=i))
            jm._jobs[f"c{i}"] = _make_job(f"c{i}", JobStatus.CANCELLED, now - timedelta(minutes=i))
        deleted = jm.cleanup(keep_completed=50)
        assert deleted == 10
        assert len(jm._jobs) == 10

    def test_cleanup_preserves_running_pending(self, jm):
        now = datetime.now()
        for i in range(3):
            jm._jobs[f"r{i}"] = _make_job(f"r{i}", JobStatus.RUNNING, now)
            jm._jobs[f"p{i}"] = _make_job(f"p{i}", JobStatus.PENDING, now)
        deleted = jm.cleanup()
        assert deleted == 0
        assert len(jm._jobs) == 6

    def test_cleanup_no_jobs(self, jm):
        assert jm.cleanup() == 0


class TestJobsEndpoints:
    def test_stats_endpoint(self):
        from webapi.main import app
        from fastapi.testclient import TestClient
        from webapi.jobs import manager as mgr_mod

        original = mgr_mod.job_manager.stats
        mgr_mod.job_manager.stats = lambda: {"PENDING": 1, "RUNNING": 0, "COMPLETED": 0, "FAILED": 0, "CANCELLED": 0}
        try:
            client = TestClient(app)
            r = client.get("/api/jobs/stats")
            assert r.status_code == 200
            assert r.json()["PENDING"] == 1
        finally:
            mgr_mod.job_manager.stats = original

    def test_cleanup_endpoint(self):
        from webapi.main import app
        from fastapi.testclient import TestClient
        from webapi.jobs import manager as mgr_mod

        original = mgr_mod.job_manager.cleanup
        mgr_mod.job_manager.cleanup = lambda keep_completed=50: 5
        try:
            client = TestClient(app)
            r = client.post("/api/jobs/cleanup", json={"keep_completed": 10})
            assert r.status_code == 200
            assert r.json()["deleted"] == 5
        finally:
            mgr_mod.job_manager.cleanup = original
