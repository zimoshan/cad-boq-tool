"""/health 健康检查 + / 根"""
from __future__ import annotations

from fastapi import APIRouter

from webapi.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """健康检查（Docker HEALTHCHECK 用）"""
    settings = get_settings()
    return {
        "status": "ok",
        "version": "0.2.0-webify",
        "auth_mode": settings.auth_mode,
        "app_env": settings.app_env,
    }


@router.get("/")
async def root() -> dict:
    return {
        "name": "cad-boq-tool Web API",
        "version": "0.2.0-webify",
        "docs": "/docs",
        "health": "/health",
    }
