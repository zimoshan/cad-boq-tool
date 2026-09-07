"""Job 任务注册表测试（Phase 2 缺口：/api/jobs/submit 接真实业务）

覆盖：
- 注册表内容（6 个 func_name + list_task_names 排序）
- JobManager.submit_by_name 提交真实任务 & 未知任务 KeyError
- router /api/jobs/submit：func_name 必填 / 未知 404 / 已知任务提交成功
- router /api/jobs/tasks 列出注册表
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from webapi.jobs.manager import JobManager
from webapi.jobs.tasks import TASKS, list_task_names

EXPECTED_TASKS = {
    "boq.parse",
    "cad.parse",
    "extraction.run",
    "takeoff.sheet",
    "takeoff.folder",
    "binding.generate",
}


class TestTaskRegistry:
    """注册表完整性"""

    def test_all_expected_tasks_registered(self):
        assert set(TASKS.keys()) == EXPECTED_TASKS

    def test_list_task_names_sorted(self):
        assert list_task_names() == sorted(EXPECTED_TASKS)

    def test_each_task_is_callable(self):
        for name, fn in TASKS.items():
            assert callable(fn), f"{name} not callable"


class TestSubmitByName:
    """JobManager.submit_by_name 编排"""

    @pytest.mark.asyncio
    async def test_submit_known_task(self):
        jm = JobManager(max_workers=0)
        job = await jm.submit_by_name("单图算量", "takeoff.sheet", {"project_id": 7, "sheet_id": 3})
        assert job.status.value == "PENDING"
        assert job.payload["project_id"] == 7
        # __func__ 已注入 → worker 可执行
        assert callable(job.payload["__func__"])

    @pytest.mark.asyncio
    async def test_submit_unknown_task_raises(self):
        jm = JobManager(max_workers=0)
        with pytest.raises(KeyError):
            await jm.submit_by_name("x", "no.such.task", {})


class TestTaskExecution:
    """注册表任务真实执行（mock 会话避免 PG 依赖）"""

    @pytest.mark.asyncio
    async def test_boq_parse_task_reports_progress_and_result(self):
        """worker 执行路径：task_boq_parse 调 service → 返回结果 + 上报阶段进度"""
        progress_events: list[str] = []

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        fake_ctx = FakeSession()

        with patch("webapi.jobs.tasks.async_session_factory", return_value=fake_ctx), patch(
            "webapi.jobs.tasks.boq_service.parse_boq_excel",
            new_callable=AsyncMock,
        ) as mock_parse:
            mock_parse.return_value = {"project_id": 1, "item_count": 42, "meta": {}}
            from webapi.jobs.models import Job

            job = Job(name="解析BOQ", payload={"project_id": 1, "file_path": "D:/x.xlsx"})
            result = await TASKS["boq.parse"](
                job, lambda p: progress_events.append(p.message) or progress_events
            )

        assert result["item_count"] == 42
        assert progress_events[0] == "解析 BOQ Excel..."
        assert progress_events[1] == "完成：42 项"
        mock_parse.assert_awaited_once_with(fake_ctx, 1, "D:/x.xlsx")

    @pytest.mark.asyncio
    async def test_unknown_func_name_raises_from_manager(self):
        """submit_by_name 未知任务 → KeyError（router 转 404）"""
        jm = JobManager(max_workers=0)
        with pytest.raises(KeyError):
            await jm.submit_by_name("x", "no.such", {})


class TestRouterSubmit:
    """/api/jobs/submit 接线（mock service 避免真 DB）"""

    def test_submit_missing_func_name_422(self, client):
        r = client.post("/api/jobs/submit", json={"name": "t", "payload": {}})
        assert r.status_code == 422

    def test_submit_unknown_task_404(self, client):
        r = client.post("/api/jobs/submit", json={"name": "t", "func_name": "no.such", "payload": {}})
        assert r.status_code == 404
        assert "no.such" in r.json()["detail"]

    def test_submit_known_task_creates_job(self, client):
        # 提示：worker 未启动（TestClient 无 lifespan 时 job 只入队不执行）
        r = client.post(
            "/api/jobs/submit",
            json={"name": "解析BOQ", "func_name": "boq.parse", "payload": {"project_id": 1, "file_path": "D:/x.xlsx"}},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "PENDING"
        assert data["name"] == "解析BOQ"
        assert data["payload"]["project_id"] == 1
        # 内部 __func__ 函数对象必须被 to_dict 排除（否则 JSON 序列化失败）
        assert "__func__" not in data["payload"]

    def test_list_tasks(self, client):
        r = client.get("/api/jobs/tasks")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == len(EXPECTED_TASKS)
        assert set(data["tasks"]) == EXPECTED_TASKS
