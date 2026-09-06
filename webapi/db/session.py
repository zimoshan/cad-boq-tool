"""async SQLAlchemy engine + session"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from webapi.config import get_settings

_settings = get_settings()

# asyncpg engine：线程池友好 + WAL-ready
engine: AsyncEngine = create_async_engine(
    _settings.database_url,
    echo=(_settings.app_env == "dev"),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

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
