"""LLM 域 service（Phase 2.2 包装 app.llm + app.takeoff.llm_backends）

#9 决策：后端代理 5 后端（Ollama/DashScope/OpenAI/DeepSeek/Custom）
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.takeoff.llm_backends import LLMConfig, create_backend
from webapi.config import get_settings
from webapi.services.base import ServiceError


async def get_llm_settings(db: AsyncSession) -> dict[str, Any]:
    """读 llm_settings 单例表（PK=1）"""
    from sqlalchemy import text

    try:
        result = await db.execute(text("SELECT * FROM llm_settings WHERE id = 1"))
        row = result.first()
        if not row:
            raise ServiceError("llm_settings not initialized", code="llm_settings_missing")
        return dict(row._mapping)
    except ServiceError:
        raise
    except Exception as e:
        raise ServiceError(f"Failed to read llm_settings: {e}", code="db_error")


async def update_llm_settings(db: AsyncSession, updates: dict[str, Any]) -> dict[str, Any]:
    """更新 llm_settings（部分字段更新）"""
    from sqlalchemy import text

    if not updates:
        return await get_llm_settings(db)
    # 构造 SET 子句
    allowed_keys = {
        "active_backend",
        "ollama_host",
        "ollama_model",
        "dashscope_api_key",
        "dashscope_model",
        "openai_api_key",
        "openai_model",
        "deepseek_api_key",
        "deepseek_model",
        "custom_base_url",
        "custom_api_key",
        "custom_model",
        "custom_embedding_model",
        "fallback_enabled",
        "fallback_backend",
        "quality_threshold",
        "temperature",
        "timeout",
        "max_tokens",
    }
    set_clauses = [f"{k} = :{k}" for k in updates if k in allowed_keys]
    if not set_clauses:
        return await get_llm_settings(db)
    set_clauses.append("updated_at = now()")
    sql = f"UPDATE llm_settings SET {', '.join(set_clauses)} WHERE id = 1"
    params = {k: v for k, v in updates.items() if k in allowed_keys}
    try:
        await db.execute(text(sql), params)
        await db.commit()
        return await get_llm_settings(db)
    except Exception as e:
        await db.rollback()
        raise ServiceError(f"Failed to update llm_settings: {e}", code="db_error")


async def chat_completion(
    db: AsyncSession,
    system: str,
    user: str,
    images: list[bytes] | None = None,
    task_type: str = "chat",
) -> dict[str, Any]:
    """Phase 2.2 通用 chat（#9 后端转发 5 后端）"""
    settings = get_settings()
    try:
        config = LLMConfig(
            active_backend=settings.llm_fallback_backend or "ollama",
            ollama_host=settings.ollama_host,
            ollama_model=settings.ollama_model,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout,
            max_tokens=settings.llm_max_tokens,
        )
        backend = create_backend(config)
        output = backend.chat(system=system, user=user, images=images or [])
        return {
            "task_type": task_type,
            "model": config.ollama_model,
            "output": output,
        }
    except Exception as e:
        raise ServiceError(f"LLM chat failed: {e}", code="llm_chat_error")
