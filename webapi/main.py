"""FastAPI 应用入口

启动：uvicorn webapi.main:app --host 0.0.0.0 --port 8521
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from webapi.config import get_settings
from webapi.db import async_session_factory
from webapi.auth.service import get_or_create_admin
from webapi.routers import audit, binding, boq, cad, cad_standard, dataset, extraction, health, jobs, llm, takeoff

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭钩子"""
    async with async_session_factory() as db:
        try:
            await get_or_create_admin(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"启动期 admin 初始化跳过：{e}")
    # Phase 2: 启动 JobManager worker 池
    from webapi.jobs import job_manager
    await job_manager.start()
    yield
    # 关闭
    await job_manager.stop()
    from webapi.db import engine
    await engine.dispose()


app = FastAPI(
    title="cad-boq-tool Web API",
    version="0.2.0-webify",
    description="""
CAD·BOQ 工程量算量工具 Web API（2026-09-06 Web 化 Phase 0）。

## 模块
- **health** — 健康检查 / 根端点
- **cad** — CAD 解析 + 视口查询（PostGIS GIST 索引）
- **binding** — 绑定候选生成（4 层）+ 确认/拒绝（跨图 SUPERSEDED）
- **boq** — BOQ Excel 解析（B1 4 表头 + B2 6 字段）+ 回写（B5 S7 takability 6 状态）
- **dataset** — 测试数据通路（#3 手动标记）
- **jobs** — 进程内 JobManager + SSE 实时进度（v2.0 ADR-05）
- **extraction** — 工程对象提取（三类 EO）
- **takeoff** — AI 算量触发（单图/文件夹）
- **llm** — LLM 配置中心 + 5 后端 chat 代理（#9）
- **audit** — llm_run 审计 + 跨维统计

## 认证
默认 `AUTH_MODE=no_login`（Phase 0 阶段），所有端点放行。
未来切 `login` 模式：JWT + Casbin 策略生效。

## 性能
- FastAPI 30 routes（单进程模块化单体）
- JobManager 默认 2 worker（`JOB_MAX_WORKERS` env 调）
- 视口查询毫秒级（PostGIS GIST 索引）
""",
    lifespan=lifespan,
    contact={
        "name": "cad-boq-tool",
        "url": "https://github.com/zimoshan/cad-boq-tool",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=[
        {"name": "health", "description": "健康检查 + 根端点"},
        {"name": "cad", "description": "CAD 解析 + 视口查询"},
        {"name": "binding", "description": "绑定候选生成 / 确认 / 拒绝"},
        {"name": "boq", "description": "BOQ Excel 解析 + 回写"},
        {"name": "dataset", "description": "测试数据通路（手动标记）"},
        {"name": "jobs", "description": "异步任务 + SSE 实时进度"},
        {"name": "extraction", "description": "工程对象提取"},
        {"name": "takeoff", "description": "AI 算量触发"},
        {"name": "llm", "description": "LLM 配置 + 5 后端 chat"},
        {"name": "audit", "description": "审计 + 跨维统计"},
    ],
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册（Phase 0 + Phase 2 全域：10 域）
app.include_router(health.router)
app.include_router(cad.router)
app.include_router(binding.router)
app.include_router(boq.router)
app.include_router(dataset.router)
app.include_router(jobs.router)
# Phase 2.2 新增 4 域
app.include_router(extraction.router)
app.include_router(takeoff.router)
app.include_router(llm.router)
app.include_router(audit.router)
# Round 3 commit 2 新增
app.include_router(cad_standard.router)


# ---------- Phase 0 占位端点 ----------
@app.get("/api/dataset")
async def dataset_placeholder() -> dict:
    """P0-22 测试数据通路占位（Phase 1 实现）"""
    return {
        "status": "placeholder",
        "message": "测试数据通路占位端点。Phase 1 期间实现手动标记 + 自动加载机制。",
        "registry_path": settings.test_data_registry_path,
    }
