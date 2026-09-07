"""Job 任务注册表（Phase 2 缺口补齐：/api/jobs/submit 接真实业务）

每个任务包装为 JobFunc = async (job, progress_cb) -> result：
  - 自建 AsyncSession（worker 协程内不共享请求会话）
  - service 层已自行包装业务异常 → 抛 ServiceError → JobManager 捕获标 FAILED
  - 进度：阶段式上报（started → completed）

新增业务任务：写一个 wrapper 函数 + 在 TASKS 注册表登记
（name 即 /api/jobs/submit 的 func_name）。
"""

from __future__ import annotations

from typing import Any

from webapi.db import async_session_factory
from webapi.jobs.models import Job, JobProgress
from webapi.services import binding as binding_service
from webapi.services import boq as boq_service
from webapi.services import cad as cad_service
from webapi.services import extraction as extraction_service
from webapi.services import takeoff as takeoff_service


def _report(progress_cb, task_type: str, done: int, total: int | None = None, message: str = "") -> None:
    progress_cb(JobProgress(task_type=task_type, done=done, total=total, message=message))


# ---------------------------------------------------------------------------
# 单个任务实现（各自包装一个 service 函数）
# ---------------------------------------------------------------------------


async def task_boq_parse(job: Job, progress_cb) -> dict[str, Any]:
    """解析 BOQ Excel（async 长任务版）"""
    payload = job.payload or {}
    _report(progress_cb, "boq_parse", 0, 2, "解析 BOQ Excel...")
    async with async_session_factory() as db:
        result = await boq_service.parse_boq_excel(
            db, payload.get("project_id", 0), payload.get("file_path", "")
        )
    count = result.get("item_count", 0)
    _report(progress_cb, "boq_parse", 2, 2, f"完成：{count} 项")
    return result


async def task_cad_parse(job: Job, progress_cb) -> dict[str, Any]:
    """解析 CAD 文件（DWG 无头转换 + ezdxf 解析）"""
    payload = job.payload or {}
    _report(progress_cb, "cad_parse", 0, 2, "解析 CAD...")
    async with async_session_factory() as db:
        result = await cad_service.parse_cad_file(
            db, payload.get("project_id", 0), payload.get("file_path", "")
        )
    entity_count = result.get("entity_count", 0)
    _report(progress_cb, "cad_parse", 2, 2, f"完成：{entity_count} 实体")
    return result


async def task_extraction_run(job: Job, progress_cb) -> dict[str, Any]:
    """工程对象提取（设备/线性/面积三类）"""
    payload = job.payload or {}
    _report(progress_cb, "extraction", 0, 2, "提取工程对象...")
    async with async_session_factory() as db:
        result = await extraction_service.run_extraction(
            db,
            payload.get("project_id", 0),
            payload.get("sheet_id", 0),
            payload.get("layer_rules"),
        )
    created = result.get("created", 0)
    _report(progress_cb, "extraction", 2, 2, f"完成：{created} 个对象")
    return result


async def task_takeoff_sheet(job: Job, progress_cb) -> dict[str, Any]:
    """单图 takeoff（6 阶段管线）"""
    payload = job.payload or {}
    _report(progress_cb, "takeoff", 0, 2, "单图算量中...")
    result = await takeoff_service.run_single_sheet_takeoff(
        None, payload.get("project_id", 0), payload.get("sheet_id", 0)
    )
    _report(progress_cb, "takeoff", 2, 2, "单图 takeoff 完成")
    return result


async def task_takeoff_folder(job: Job, progress_cb) -> dict[str, Any]:
    """文件夹 takeoff（多图聚合）"""
    payload = job.payload or {}
    folder_path = payload.get("folder_path", "")
    _report(progress_cb, "takeoff", 0, 2, "文件夹 takeoff 中...")
    result = await takeoff_service.run_folder_takeoff(None, payload.get("project_id", 0), folder_path)
    _report(progress_cb, "takeoff", 2, 2, "文件夹 takeoff 完成")
    return result


async def task_binding_generate(job: Job, progress_cb) -> dict[str, Any]:
    """生成绑定候选（4 层：历史→规则→语义→LLM 精排）"""
    payload = job.payload or {}
    _report(progress_cb, "binding", 0, 2, "生成绑定候选...")
    async with async_session_factory() as db:
        result = await binding_service.generate_candidates_for_project(
            db,
            payload.get("project_id", 0),
            payload.get("sheet_id"),
            payload.get("use_llm", True),
            payload.get("top_n", 5),
        )
    created = result.get("candidates_created", 0)
    _report(progress_cb, "binding", 2, 2, f"完成：{created} 个候选")
    return result


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

TASKS: dict[str, Any] = {
    "boq.parse": task_boq_parse,
    "cad.parse": task_cad_parse,
    "extraction.run": task_extraction_run,
    "takeoff.sheet": task_takeoff_sheet,
    "takeoff.folder": task_takeoff_folder,
    "binding.generate": task_binding_generate,
}


def list_task_names() -> list[str]:
    return sorted(TASKS.keys())
