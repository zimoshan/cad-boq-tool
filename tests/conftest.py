"""pytest 全局 fixture + 环境变量注入

确保 webapi 配置在测试时不会去读真实 env.example（用空 env）
"""
from __future__ import annotations

import os

# 测试期用最小 env：避免触发真实 .env / env.example
os.environ.setdefault("AUTH_MODE", "no_login")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("LOG_DIR", "/tmp/cad-boq-test-logs")
os.environ.setdefault("DRAWING_CACHE_DIR", "/tmp/cad-boq-test-cache")
os.environ.setdefault("EMBEDDING_CACHE_DIR", "/tmp/cad-boq-test-cache")
os.environ.setdefault("BLOCK_GEOMETRY_DIR", "/tmp/cad-boq-test-cache")
