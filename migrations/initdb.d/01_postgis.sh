#!/bin/bash
# cad-boq-tool 启动初始化
# 2026-09-06 Web 化 Phase 0
# 由 postgis 容器首次启动时执行（/docker-entrypoint-initdb.d/）

set -e

echo "== 启用 PostGIS 扩展"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS postgis;"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'

echo "== PostGIS 版本："
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT PostGIS_Version();"

echo "== 准备 alembic 迁移（容器 webapi 启动时自动跑）"
# 实际 alembic upgrade head 由 webapi 容器 lifespan 触发
# 这里仅确保 PG 就绪

echo "== 初始化完成"
