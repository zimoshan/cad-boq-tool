# Build & Verify 状态

> 2026-09-06 Web 化 Phase 0 阶段性构建状态。

## 当前环境差异

| 项 | 本机 (.venv) | Docker (推荐) |
|---|---|---|
| Python | 3.11（PySide6 旧 venv）| 3.12（pyproject.toml 锁定）|
| Web 依赖 | ❌ 未装（casbin/fastapi/sqlalchemy 等） | ✅ requirements.txt 完整安装 |
| 桌面端依赖 | ✅ PySide6 + ezdxf 1.4.4 | ❌ 故意不装（#15 桌面端废弃）|
| 数据库 | SQLite（172MB `~/.cad-boq-tool/projects.db`）| PostgreSQL 16 + PostGIS 3.4 |

## 验证 pytest 的两种方式

### 方式 1：在本机 venv 装 webapi 依赖（推荐先试）

```bash
# 1. 创建新的 webapi 专用 venv（避免污染桌面端 .venv）
python3.12 -m venv .venv-webapi
source .venv-webapi/bin/activate   # Windows: .venv-webapi\Scripts\activate

# 2. 装依赖
pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx

# 3. 跑测试
pytest tests/test_auth.py -v
pytest tests/ -v                    # 跑全部（11 旧 + 1 新）
```

预期：tests/test_auth.py 11 个 case 全过（no_login 模式 + admin 放行 + Pydantic 校验）。
注意：tests/test_*.py 其他 10 个是业务层（SQLite 直连），无 webapi 依赖，与新环境兼容。

### 方式 2：Docker 一键起

```bash
docker compose up -d                          # 起 webapi + postgis
docker compose exec webapi pip install -e .[dev]
docker compose exec webapi pytest tests/ -v
```

## 已知限制

1. **本机 venv 是 Python 3.11**（PySide6 残留），与 pyproject.toml requires-python=">=3.12" 不一致
   - 临时方案：创建 .venv-webapi 专用 venv（方式 1）
   - 长期方案：Phase 0 出口后彻底废弃 .venv，统一用 Docker 或 uv
2. **现有 tests/ 11 个 pytest 用 SQLite**（app/db.py），webapi 用 PG + async
   - Phase 0 期间两者并存（业务层独立验证 + webapi 验证）
   - Phase 1 完成后业务层切 webapi/db session，pytest 统一跑 PG test container
3. **本机 .venv 装 webapi 依赖会有 PySide6 与 FastAPI 同存风险**（不是 bug，是设计选择）
   - 推荐**不**在 .venv 混装；用 .venv-webapi 或 Docker

## CI/自动化路径（Phase 0 P0-23 落地）

未来 PR 触发：
```yaml
.github/workflows/test.yml:
  - docker compose up -d postgis
  - pip install -r requirements.txt
  - pytest tests/ -v --cov=webapi
  - docker compose down
```

## 何时 A.1 算"全绿"？

- 方式 1 或 2 跑通，11 个新 + 11 个旧 test 全过
- FastAPI 服务能起：`uvicorn webapi.main:app` 返回 200 OK on /health
- alembic upgrade head 在 Docker postgis 容器里能建 schema
- pytest-asyncio 配置正确识别（`pytest --version` 报 "asyncio: auto"）
