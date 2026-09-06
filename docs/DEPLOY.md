# cad-boq-tool 部署指南

> 2026-09-06 Web 化 Phase 0 完成版。配套 [WEB_MIGRATION_PLAN.md](WEB_MIGRATION_PLAN.md) + [CHANGELOG.md](../CHANGELOG.md)。

## 1. 部署模式

| 模式 | 场景 | 复杂度 |
|---|---|---|
| **A. Docker Compose（推荐）** | 单机/局域网，Phase 0 默认 | 🟢 一键起 |
| **B. Linux 物理机** | 7×24 生产，#4 决策推荐 | 🟡 中等 |
| **C. 开发模式** | 本地改代码 | 🟢 简单 |

## 2. 环境要求

### 2.1 通用
- Python 3.11 / 3.12（pyproject.toml 锁定 3.12，3.11 兼容）
- PostgreSQL 16 + PostGIS 3.4（`postgis/postgis:16-3.4` Docker 镜像）
- 2 GB RAM 最低 / 4 GB 推荐（SBERT embedding + LLM 调用）
- 20 GB 磁盘（CAD 缓存 + embedding 缓存 + 备份）

### 2.2 桌面端
- ❌ **不再需要 PySide6 / Qt**（#15 决策 2026-09-06 直接废弃）

### 2.3 外部依赖
- **ODA File Converter**（DWG 无头转换，B5 S1）：
  - Linux: `apt install oda-file-converter` 或下载 https://www.opendesign.com/guestfiles/oda_file_converter
  - Windows: `choco install odafileconverter` 或下载
  - 路径通过 `ODA_FILE_CONVERTER` env 或 `app/config.py:ODA_INSTALL_HINTS` 探测
- **可选 LLM 后端**（5 选 1）：
  - Ollama（本地，#4 推荐）：`ollama pull qwen2.5:7b`
  - OpenAI / DeepSeek / DashScope / Custom OpenAI 兼容（API Key）

## 3. 模式 A · Docker Compose（推荐）

### 3.1 一键起
```bash
git clone https://github.com/zimoshan/cad-boq-tool.git
cd cad-boq-tool
cp env.example .env  # 改 ODA_FILE_CONVERTER / LLM_API_KEY 等
docker compose up -d
```

### 3.2 验证
```bash
# webapi 健康
curl http://localhost:8521/health
# {"status":"ok","version":"0.2.0-webify","auth_mode":"no_login","app_env":"dev"}

# OpenAPI 文档
open http://localhost:8521/docs

# 启动 LLM
docker compose --profile with-llm up -d
```

### 3.3 数据迁移（首次）
```bash
# alembic 已在 webapi 启动时自动跑 upgrade head
# 旧 SQLite 数据手动导入：
docker compose exec webapi python -m migrations.sqlite_to_pg \
  --sqlite /var/lib/cad-boq/projects.db \
  --pg-dsn postgresql://cadboq:cadboq_dev@postgis:5432/cadboq
```

### 3.4 备份策略
```bash
# 自动备份（alembic 0.5% 表 + 增量）
docker compose exec postgis pg_dump -U cadboq cadboq | gzip > backups/cadboq_$(date +%Y%m%d).sql.gz

# 块几何外置目录（BLOCK_GEOMETRY_DIR）独立备份
tar czf backups/block_geometry_$(date +%Y%m%d).tar.gz /var/lib/cad-boq/block_geometry/

# 建议 cron：
# 0 3 * * * /opt/cad-boq-tool/backup.sh
```

## 4. 模式 B · Linux 物理机（#4 推荐生产）

### 4.1 系统初始化
```bash
# Ubuntu 24.04 LTS
sudo apt update
sudo apt install -y python3.12 python3.12-venv postgresql-16 postgresql-16-postgis-3 \
  oda-file-converter nginx certbot python3-certbot-nginx

# 创建用户
sudo useradd -m -s /bin/bash cadboq
sudo su - cadboq
```

### 4.2 PG + PostGIS
```bash
sudo -u postgres psql -c "CREATE USER cadboq WITH PASSWORD 'YOUR_PASSWORD' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE cadboq OWNER cadboq;"
sudo -u postgres psql -d cadboq -c "CREATE EXTENSION postgis;"
sudo -u postgres psql -d cadboq -c 'CREATE EXTENSION "uuid-ossp";'
```

### 4.3 部署代码
```bash
cd /opt
sudo git clone https://github.com/zimoshan/cad-boq-tool.git
sudo chown -R cadboq:cadboq cad-boq-tool
sudo su - cadboq
cd /opt/cad-boq-tool

python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 环境配置
cp env.example .env
$EDITOR .env  # 设置 ODA_FILE_CONVERTER / LLM_API_KEY / DATABASE_URL 等
```

### 4.4 alembic 迁移
```bash
source .venv/bin/activate
alembic upgrade head
```

### 4.5 systemd 服务
`/etc/systemd/system/cadboq-webapi.service`：
```ini
[Unit]
Description=cad-boq-tool Web API
After=network.target postgresql.service

[Service]
Type=simple
User=cadboq
Group=cadboq
WorkingDirectory=/opt/cad-boq-tool
Environment="PATH=/opt/cad-boq-tool/.venv/bin:/usr/bin"
EnvironmentFile=/opt/cad-boq-tool/.env
ExecStart=/opt/cad-boq-tool/.venv/bin/uvicorn webapi.main:app --host 0.0.0.0 --port 8521 --workers 2
Restart=always
RestartSec=5
StandardOutput=append:/var/log/cad-boq/webapi.log
StandardError=append:/var/log/cad-boq/webapi.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cadboq-webapi
sudo systemctl status cadboq-webapi
```

### 4.6 nginx 反向代理（局域网可选）
`/etc/nginx/sites-available/cadboq`：
```nginx
upstream cadboq_webapi {
    server 127.0.0.1:8521;
}

server {
    listen 80;
    server_name cadboq.local;

    location / {
        proxy_pass http://cadboq_webapi;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # SSE 长连接支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/cadboq /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 5. 模式 C · 开发模式

```bash
# 后端
source .venv/bin/activate  # 或 source .venv-webapi/bin/activate
uvicorn webapi.main:app --reload --port 8521

# 前端（另开终端，需 Node 18+）
cd webui
npm install
npm run dev  # http://localhost:5173（Vite dev proxy 自动转 /api → :8521）
```

## 6. 验证清单

启动后验证：

```bash
# 1. 健康检查
curl -s http://localhost:8521/health
# {"status":"ok","version":"0.2.0-webify","auth_mode":"no_login"}

# 2. OpenAPI 文档
open http://localhost:8521/docs

# 3. alembic 状态
alembic current
# 0003 (head)

# 4. PostGIS
psql -d cadboq -c "SELECT PostGIS_Version();"

# 5. 5 关键端点
curl -s http://localhost:8521/api/dataset
curl -X POST -H "Content-Type: application/json" \
  -d '{"project_id":1,"file_path":"D:/test.dxf"}' \
  http://localhost:8521/api/cad/parse
# 预期 404 not_found（file not exist → ServiceError）

# 6. 提交 Job
curl -X POST -H "Content-Type: application/json" \
  -d '{"name":"test","payload":{}}' \
  http://localhost:8521/api/jobs/submit
# {"id":"xxxx","status":"PENDING",...}
curl http://localhost:8521/api/jobs/xxxx/stream
# event: status / progress / final
```

## 7. 监控 / 日志

| 项 | 路径 |
|---|---|
| webapi stdout/stderr | systemd: `/var/log/cad-boq/webapi.log` |
| 应用日志 | `LOG_DIR`（env，默认 `/var/log/cad-boq/`）|
| PG 慢查询 | `log_min_duration_statement = 1000`（postgresql.conf）|
| alembic 版本 | `alembic current` |
| 块几何外置 | `BLOCK_GEOMETRY_DIR`（默认 `/var/lib/cad-boq/block_geometry/`）|
| 解析缓存 | `DRAWING_CACHE_DIR`（默认 `/var/lib/cad-boq/drawing_cache/`）|

## 8. 升级流程

```bash
cd /opt/cad-boq-tool
git pull
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart cadboq-webapi
sudo journalctl -u cadboq-webapi -f
```

## 9. 故障排查

| 症状 | 排查 |
|---|---|
| webapi 起不来，PG 错误 | `alembic current` + `psql -d cadboq -c "\dt"` 检查 schema |
| ODA 转换失败 | 检查 `ODA_FILE_CONVERTER` env + 路径权限 + DWG 文件可读 |
| LLM 调用 401 | 检查 `OPENAI_API_KEY` / `OLLAMA_HOST` 等 |
| 块几何找不到 | 检查 `BLOCK_GEOMETRY_DIR` 路径 + `sheets.blocks_json` 引用（DB）|
| SSE 不推送 | 检查 nginx `proxy_buffering off` + nginx 版本 |

## 10. 相关文档

- [WEB_MIGRATION_PLAN.md](WEB_MIGRATION_PLAN.md) — 7 阶段路线 + 技术栈
- [DESKTOP_TO_WEB_MAPPING.md](DESKTOP_TO_WEB_MAPPING.md) — 删除/重写/保留三段式
- [BUILD_STATUS.md](../BUILD_STATUS.md) — 本机验证方式
- [DATAVIZ_INTEGRATION.md](DATAVIZ_INTEGRATION.md) — Phase 5/6 跨专业总览
- GitHub Actions CI: [`.github/workflows/test.yml`](../.github/workflows/test.yml)
