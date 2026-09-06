"""Alembic env.py：async + sync 模式双支持"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from webapi.config import get_settings

# 导入 webapi Base 让 autogenerate 识别所有 ORM model
from webapi.db.base import Base
# 业务模型先不导入（Phase 0 业务层重写后才会有 webapi.db.models）
# Phase 0 占位：0001_initial 手工建业务表
# 鉴权模型
from webapi.auth.models import SysDict, SysMenu, SysRole, SysUser, SysUserRole

config = context.config

# 用 settings.database_url_sync 覆盖 alembic.ini
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# 日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式（生成 SQL 脚本）"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式（直连 DB）"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
