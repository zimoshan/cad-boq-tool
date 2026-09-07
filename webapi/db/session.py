"""async SQLAlchemy engine + session"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from webapi.config import get_settings

_settings = get_settings()

# asyncpg（PG 生产）：线程池友好 + WAL-ready
# sqlite+aiosqlite（本地开发）：不支持 pool_size/max_overflow（NullPool），跳过池参数
_engine_kwargs: dict[str, Any] = {
    "echo": (_settings.app_env == "dev"),
}
if not _settings.database_url.startswith("sqlite"):
    _engine_kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=3600)

engine: AsyncEngine = create_async_engine(_settings.database_url, **_engine_kwargs)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, Any]:
    """FastAPI Depends：每个请求一个 session，请求结束关闭"""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
