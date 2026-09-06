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
from webapi.routers import binding, boq, cad, dataset, health

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
    yield
    from webapi.db import engine
    await engine.dispose()


app = FastAPI(
    title="cad-boq-tool Web API",
    version="0.2.0-webify",
    description="CAD 工程量算量工具 - Web 化迁移 Phase 0（2026-09-06）",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册（A.2 第 1 批：4 域 + health）
app.include_router(health.router)
app.include_router(cad.router)
app.include_router(binding.router)
app.include_router(boq.router)
app.include_router(dataset.router)


# ---------- Phase 0 占位端点 ----------
@app.get("/api/dataset")
async def dataset_placeholder() -> dict:
    """P0-22 测试数据通路占位（Phase 1 实现）"""
    return {
        "status": "placeholder",
        "message": "测试数据通路占位端点。Phase 1 期间实现手动标记 + 自动加载机制。",
        "registry_path": settings.test_data_registry_path,
    }
