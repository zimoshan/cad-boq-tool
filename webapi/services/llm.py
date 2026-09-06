"""LLM 域 Service（包装 app/llm 业务函数）

Phase 0：
  - GET  /api/llm/settings：读 llm_settings 单例
  - PUT  /api/llm/settings：更新（#9 后端转发 5 后端抽象）
  - POST /api/llm/chat：通用 chat（5 后端统一接口）
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.runner import run_llm_with_retry
from app.takeoff.llm_backends import LLMConfig, create_backend
from webapi.config import get_settings
from webapi.services.base import ServiceError


async def get_llm_settings(db: AsyncSession) -> dict[str, Any]:
    """读 llm_settings 单例（PK=1）"""
    result = await db.execute(select_from_table_one(db))
    row = result.first()
    if not row:
        # 初始化默认
        from sqlalchemy import insert
        from app.db import _SCHEMA  # noqa: F401  复用旧 schema
        # 实际 schema 由 PG 建好，PG 端会预置默认行
        raise ServiceError("llm_settings not initialized", code="llm_settings_missing")
    return dict(row._mapping)


async def chat(
    db: AsyncSession,
    system: str,
    user: str,
    images: list[bytes] | None = None,
    task_type: str = "chat",
) -> dict[str, Any]:
    """Phase 0 占位：LLM 通用 chat（#9 后端转发 5 后端）"""
    settings = get_settings()
    try:
        config = LLMConfig(
            active_backend="ollama",
            ollama_host=settings.ollama_host,
            ollama_model=settings.ollama_model,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout,
            max_tokens=settings.llm_max_tokens,
        )
        backend = create_backend(config)
        result = backend.chat(system=system, user=user, images=images or [])
        return {
            "task_type": task_type,
            "model": config.ollama_model,
            "output": result,
        }
    except Exception as e:
        raise ServiceError(f"LLM chat failed: {e}", code="llm_chat_error")


def select_from_table_one(db: AsyncSession):
    """内部辅助：select * from llm_settings where id=1"""
    from sqlalchemy import text
    return db.execute(text("SELECT * FROM llm_settings WHERE id = 1"))
