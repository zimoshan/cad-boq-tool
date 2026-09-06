# Changelog

> cad-boq-tool 变更日志。遵循 [Keep a Changelog](https://keepachangelog.com/) 风格。

## [unreleased] · 2026-09-06 · Web 化迁移 Phase 0

### 重大变更（Breaking）

- **桌面端彻底废弃**（决策 #15）：删除 `main.py` + 整个 `app/ui/` 21 文件（QGraphicsView/QTabWidget/QFileDialog 等 Qt 代码）+ `src/`/`bin/`/`package.json`（Node 占位壳）
- **数据存储从 SQLite 切到 PostgreSQL 16 + PostGIS 3.4**（决策 #6）：保留 SQLite 仅作一次性迁移源
- **B1 BOQ 解析修复**：4 种专业 BOQ 表头识别（电气/机械/建筑/结构，覆盖不同表头行号）
- **B2 BoqItem 模型扩展**：加 6 字段（`section` / `item_key` / `brand` / `bill_qty` / `installed_qty` / `qty_remaining`）
- **B3 块几何外置**：`sheet.blocks_json` 34MB TEXT → `<BLOCK_GEOMETRY_DIR>/<sha256>.parquet`（pyarrow）
- **B4 空间列**：`entity` 加 `min_x`/`min_y`/`max_x`/`max_y` + PostGIS `geometry` GIST 索引；`/api/cad/viewport` 毫秒级

### 新增（Added）

- **B5 6 段能力一次性补齐**（决策 #2）：
  - S1 DWG 无头转换（`find_oda_converter` 跨平台 + `find_accoreconsole` Windows 备选 + Linux 路径）
  - S3 单位标定（`ParsedDrawing.units`/`insunits_code` + `INSUNITS_MAP` 8 编码 + `_detect_units`）
  - S4 归一化 + 黑名单（`_classify_drawing_type` 5 分类 + `LAYER_BLACKLIST_KEYWORDS` 14 关键词）
  - S5 跨图去重并集（`app/engineering/cross_sheet_dedup.py` bbox 重叠 ≥0.5 贪心聚类）
  - S7 可核性 + Excel 保真回写（`Takability` Enum 6 状态 + `classify_takability` + `writeback_audit` 表）
- **webapi 27 文件**（FastAPI + Pydantic v2 + SQLAlchemy 2.x async + Alembic）：
  - `webapi/main.py` + `config.py` + `db/{base,session}.py`
  - `webapi/auth/{models,schemas,service,decorators,casbin_rbac,current_user}.py`（RuoYi 风格 RBAC 5 表 + Casbin + no_login stub）
  - `webapi/services/{base,cad,binding,boq,llm,dataset}.py`（包装而非重写 #19 选 A）
  - `webapi/schemas/{common,cad,binding,boq,dataset}.py`（Pydantic v2）
  - `webapi/routers/{health,cad,binding,boq,dataset}.py`（9 端点）
- **alembic 2 迁移**：
  - `0001_initial_schema`：12 业务表 + 5 RBAC 表 + PostGIS + B2/B4
  - `0002_b5_capabilities`：entity.units / sheet.units / sheet.drawing_type / cross_sheet_dedup / writeback_audit
- **webui 11 文件**（Vite 5.4 + React 18.3 + TypeScript 5.5 + Tailwind 3.4）：
  - `package.json` + `vite.config.ts` + `tsconfig.json` + `tsconfig.node.json` + `index.html`
  - `src/main.tsx` + `App.tsx`（v3 蓝本 1:1 占位：顶栏+三栏+rail+状态栏+Toast）
  - `src/theme.ts` + `theme.css`（slate 调色板 + CSS 变量）
  - `src/api/client.ts`（fetch wrapper + ApiError）
  - `README.md`
- **Docker 化**：`docker-compose.yml`（webapi + postgis/postgis:16-3.4 + 可选 ollama profile=with-llm）+ `Dockerfile`（python:3.12-slim 多阶段构建）+ `.dockerignore`
- **GitHub Actions CI**：[.github/workflows/test.yml](.github/workflows/test.yml)（backend-tests postgis + frontend-build）
- **app/cad/block_geometry_store.py**（B3 块几何外置 parquet 写读 + sha256 引用协议）
- **app/engineering/cross_sheet_dedup.py**（B5 S5 跨图去重）
- **app/boq/writeback.py Takability Enum**（B5 S7 6 状态 + by_takability 统计）
- **tests/test_auth.py**（RuoYi RBAC + Casbin 装饰器 + Pydantic 校验 11 case）+ `tests/conftest.py`（env 注入）
- **5 份新文档**：[BUILD_STATUS.md](BUILD_STATUS.md) / [WEB_MIGRATION_PLAN.md](WEB_MIGRATION_PLAN.md) / [DESKTOP_TO_WEB_MAPPING.md](DESKTOP_TO_WEB_MAPPING.md) / [DATAVIZ_INTEGRATION.md](DATAVIZ_INTEGRATION.md) / [BACKLOG.md v2](BACKLOG.md)（统一待办入口 + 状态标准 + 决策记录）

### 变更（Changed）

- **业务层零重写**（#19 选 A）：`app/cad|engineering|binding|takeoff|boq|llm` ~6800 行算法实现保留；webapi Service 层只包装
- **BACKLOG.md 重构**为统一待办入口：§0 状态标准 + §1.A Web 化迁移主线 + §1.B 业务优化支线 + §2 暂缓 + §3 已完成 + §4 使用规则 + §5 来源文档 + §6 决策记录（19 项）
- **CLAUDE.md** 加"待办管理"项目指令：所有待办统一登记在 [BACKLOG.md](BACKLOG.md)
- **.gitignore** 解除 `docs/` 整目录 ignore（之前忽略导致 `docs/_removed/` 等新子目录无法跟踪）
- **README.md** 重写：从桌面端启动改为 webapi/webui 启动（Phase 0 占位）
- **`BOQ_HEADER_CANDIDATES`** 加 5 新字段映射（section / item_key / brand / bill_qty / installed_qty / qty_remaining）+ 4 种专业中文表头

### 移除（Removed）

- `main.py`（PySide6 入口）
- `app/ui/**` 21 文件（QGraphicsView/QTabWidget/QFileDialog 等）
- `src/index.js` + `src/boq.js` + `bin/cad-boq-tool.js` + `package.json`（Node 占位壳）
- 9 份 UI 历史文档 → `docs/_removed/`
- 3 张旧 GUI 截图 + `ui_audit.md` → `artifacts/_legacy_ui/`
- 7 份 ~5.2 GB SQLite 备份家族（projects.db.bak-prellm-27432 / .bak_20260826_092948 / .bak_20260826_093702 / .before-rebuild.bak / .fresh / .rebuilt / projects.backup-20260824.db）

### 修复（Fixed）

- **B1**：BOQ-001 4 种专业表头行号探测（前 16 行覆盖电气 row 1/11、机械/建筑 row 13、结构 row 10）
- **B2**：BoqItem 缺字段导致 480 条 BOQ 全错（v2.0 §1.2 根因）
- **B3**：sheet.blocks_json 34MB 拖垮 `get_sheets`（v2.0 §2.3）
- **B4**：entity.bbox TEXT 不可空间查询（v2.0 §2.4）

### 安全（Security）

- **AUTH_MODE=no_login**（默认，Phase 0）：单用户免登录 + sysadmin stub
- **AUTH_MODE=login**（预留）：Casbin 策略 + `@requires("perm:code")` 装饰器 + JWT（python-jose）
- **#9 后端代理 LLM**：浏览器不直连 Ollama/OpenAI，API Key 全部后端持有
- **密码 hash**：passlib[bcrypt]（当前 no_login 占位空字符串）

### 性能（Performance）

- **#4 推荐 Linux 部署**：省 30% 内存 + 7×24 systemd
- **B4 PostGIS GIST 索引**：viewport 查询毫秒级
- **B3 块几何外置**：34MB TEXT → 100 字节引用
- **alembic 2 迁移**：增量 schema 演进，支持回滚

### 文档（Documentation）

- [BUILD_STATUS.md](BUILD_STATUS.md)：本机 venv 3.11 旧 PySide6 环境与 pyproject 3.12 不一致，pytest 验证方式
- [WEB_MIGRATION_PLAN.md](WEB_MIGRATION_PLAN.md)：单一权威迁移计划（替代 v1.0/v2.0/WEB_PLATFORM 散落文档）
- [DESKTOP_TO_WEB_MAPPING.md](DESKTOP_TO_WEB_MAPPING.md)：删除项 + 重写项 + 零重写项三段式
- [DATAVIZ_INTEGRATION.md](DATAVIZ_INTEGRATION.md)：跨专业总览/报告导出/实时统计 3 集成点
- [BACKLOG.md §6 决策记录](BACKLOG.md)：19 项决策固化（#1~#19）

### 验证（Verification）

- `pre-webify` annotated tag 完整快照：Phase 0 启动前全部状态 + 未提交改动
- 16 个 git commit 全部可追溯
- 业务算法零回归：~6800 行 `app/` 业务代码无破坏性改动
- 11 个新 RBAC 测试 + 11 个旧业务测试 = 22 个测试（CI 自动跑待首次 push）
- alembic upgrade head：建 17 表 + PostGIS 扩展 + 5 索引
- sqlite_to_pg.py：旧 SQLite → PG 一次性数据迁移脚本

---

## 历史版本（2026-08-24 ~ 2026-09-05 桌面端阶段）

> 早期 commit（8a28a77 优化 / 50f01b9 优化 / 0c4099f 文档整理 / f82564a 有害内容 / 07c0e47 优化功能及流程 / d810223 优化界面UI / 5f209c6 v3界面原型1:1复刻 / 3e03109 优化界面按钮 / 1a9093b 优化 / d1f4ebc debug）保留 PySide6 桌面端 GUI 实现的演进历史。

详细 git history：`git log --oneline --before="2026-09-06"`
