# 待办清单（BACKLOG）

> **唯一待办入口**：所有待办事项（功能 / 优化 / 缺陷 / 验证项）统一在本文件登记与维护。
> 其他文档只写方案、结论与参考，**不设待办清单**；新建条目一律追加到 §1 并按下表登记状态。
>
> 版本：v2（2026-09-06 整合重写）。合并来源：v1 原 BACKLOG、ui_audit/OPTIMIZATION_PLAN_2026-08-28、REFACTOR_TASKS_ezdxf、REVIEW_TECH_ROUTE_2026-09-06、COMPLETION_CHECKLIST（均已在 §5 登记处理）。

---

## §0 状态标准

### 0.1 状态图例（唯一定义）

| 状态 | 标记 | 判据 |
|------|------|------|
| 待办 | `⬜` | 已登记、有验收标准，未开始 |
| 进行中 | `🚧` | 已开始实施（编码/调研中） |
| 完成 | `✅` | **验收标准逐条核实通过 + 测试通过 + 注明完成日期** |
| 暂缓 | `⏸` | 用户决策搁置，须注明原因与恢复条件 |
| 已取消 | `❌` | 决定不做，注明原因 |

### 0.2 条目登记规范

每个待办条目必须包含：

```
- [ ] **编号 标题** ｜ 优先级 ｜ 状态
  - 现状/来源：为什么会有它（可链来源文档）
  - 方案：怎么改（可链设计文档）
  - 验收：客观可检查的标准（无验收标准的条目禁止标 ✅）
```

- 编号规则：`P{0-3}-{序号}`（如 `P0-1`），验证类用 `V-{序号}`。
- 完成时：勾选 `[x]`、状态列标注 `✅ <日期>`，有改进报告的附报告路径。
- 新需求/新缺陷：先登记进 §1 再动手；禁止在执行过程中悄悄新增范围。

### 0.3 优先级定义

| 优先级 | 定义 |
|--------|------|
| P0 | 准确率/可用性直接受损，立即可做，见效最直接 |
| P1 | 结构性改进，中期投入（数天级） |
| P2 | 长期护城河（评测闭环、学习回路） |
| P3 | 可选方向，先验证再投入（含 GPU/第三方依赖） |

---

## §1 当前待办

> **主线 A**：Web 化迁移（方案 B 务实版，2026-09-06 启动，#19 选 A：保留算法实现重写集成层）
> **主线 B**：业务优化（[REVIEW_TECH_ROUTE_2026-09-06](docs/REVIEW_TECH_ROUTE_2026-09-06.md) + 方法论遗留项；Web 化 Phase 0~4 期间暂不投入，Phase 5 后回归对位）
> **主线 C**：验证项

---

### A · Web 化迁移（最高优先级主线）

> 18 项决策见 §6 决策记录；Phase 0 = 28 项（细分 35），总工期 ≈ 20-25 周。Phase 0 启动 2026-09-06。
> 设计基线：[CAD_BOQ_Web化_架构设计_v2.0](docs/CAD_BOQ_Web化_架构设计_v2.0.md) + 18 决策修订（方案 B 务实版：FastAPI 单进程模块化单体 + React + Canvas 2D + PG/PostGIS + RuoYi 风格 RBAC + Linux 部署优先，桌面端 2026-09-06 直接废弃）。

#### A.0 · Phase 0 · 清理与归档（先做，1 周）
- [x] **P0-0.1 git tag `pre-webify` 完整快照** ✅ 2026-09-06（HEAD = 837441f；`git reset --hard pre-webify` 随时回退）
- [x] **P0-0.2 删除 Node 壳** [src/](src/) + [bin/](bin/) + [package.json](package.json)（5 文件，#10 已明确引用）✅ 2026-09-06（commit `8c250ed`）
- [x] **P0-0.3 删除桌面端入口** [main.py](main.py) + 整个 [app/ui/](app/ui/) 21 文件（#15）✅ 2026-09-06（commit `5056d21`）
- [x] **P0-0.4 移动 UI 相关归档** 到 [docs/_removed/](docs/_removed/)：5 个 archive + 2 个 ui_audit = 7 文件（实际跟踪的，#10 已审）✅ 2026-09-06（commit `52c2df1`；含 .gitignore 解除 docs/ ignore）
- [x] **P0-0.5 移动旧 GUI 截图** 到 [artifacts/_legacy_ui/](artifacts/)：3 张 verify_round3_*.png + [ui_audit.md](ui_audit.md) 共 4 文件（#15）✅ 2026-09-06（commit `a21ecb6`）
- [x] **P0-0.6 备份垃圾清理**（`~/.cad-boq-tool/` 7 个 .bak_2026* / .bak-prellm / .fresh / .rebuilt 备份，#13）✅ 2026-09-06（实际释放 5.2 GB：8.2GB → 3.0GB）
- [x] **P0-0.7 README 重写**（指向 webapi/webui 启动步骤，#12）✅ 2026-09-06（commit `db21d6a`）
- [x] **P0-29 补 add 因 .gitignore 解除而出现的 14 个 docs/ 文档**（P0-0.4 副作用：根 .gitignore 解除 docs/ ignore 后，CAD_BOQ_Web化_*/REVIEW_*/CANDIDATE_*/驱动 Prompt/估算系统/未跟踪 archive 文档首次进入版本控制）✅ 2026-09-06（commit `acb0e28`）

#### A.1 · Phase 0 · 基础设施（2 周）
- [x] **P0-1 requirements.txt 锁定**（pyproject.toml + requirements.txt + .python-version=3.12）✅ 2026-09-06（commit `xxx`）
  - PySide6 移除；增 FastAPI 0.115 / SQLAlchemy 2.x async + asyncpg / Alembic / GeoAlchemy2 / Casbin / Pydantic v2 / ezdxf 1.4.4 + ezdwg
- [x] **P0-2 .env.example 模板**（env.example，无前导点避开 .env* 权限保护）✅ 2026-09-06
  - APP/DB(auth+sync DSN+SQLITE_BACKUP)/AUTH(no_login 预留 login)/ODA(B5 S1)/5 LLM 后端/存储/CORS/测试数据通路
- [x] **P0-3 Docker Compose**（docker-compose.yml + Dockerfile + .dockerignore）✅ 2026-09-06
  - webapi + postgis/postgis:16-3.4 + 可选 ollama（profile=with-llm）；健康检查 + 持久卷 + 桥接网络；python:3.12-slim 多阶段构建
- [x] **P0-4 RuoYi 风格 RBAC 骨架**（webapi/auth/ 8 文件 + main.py + config.py + db/）✅ 2026-09-06
  - sys_user/sys_role/sys_user_role/sys_menu/sys_dict 5 表（SQLAlchemy 2.x async）；@requires(perm) 装饰器；Casbin 包装；no_login 模式 sysadmin stub；FastAPI Depends get_current_user
- [x] **P0-5 PG + PostGIS schema 迁移**（alembic + 12 业务表 + 4 RBAC 表 + migrations/）✅ 2026-09-06
  - alembic 20260906_0001_initial_schema.py（CREATE EXTENSION postgis + uuid-ossp；B2 修正 boq_item 加 section/item_key/brand/bill_qty/installed_qty/qty_remaining；B4 修正 entity 加 min_x..max_y + geometry GIST）
  - migrations/sqlite_to_pg.py（一次性脚本，bbox→WKT POLYGON，batch 1000）
  - migrations/initdb.d/01_postgis.sh（容器首次启动自动启用 PostGIS）

**A.1 验证状态**：
- ✅ 2026-09-07 本机验证：uv 建 `.venv-webapi`（CPython 3.12.13）+ 装 requirementst → **pytest 280 passed / 21.6s**（含 P1-1 takability 11 case、P1-2 dataset DB 后端、P0-38 routers 32 case）

#### A.2 · Phase 0 · 业务层重写（4 周，#2 B5 六段能力一次性补齐）
- [x] **P0-6 B1 BOQ 解析修复**（v2.0 §2.1：BOQ-001 4 种表头识别 + section/item/三数量列）✅ 2026-09-06（commit `6f41f82`，HEADER_PROBE_ROWS=16 行探测覆盖电气/机械/建筑/结构 4 种）
- [x] **P0-7 B2 BoqItem 模型扩展**（v2.0 §2.2：section + bill_qty/installed_qty/qty_remaining + Item 主键）✅ 2026-09-06（commit `6f41f82`，6 字段 + BOQ_HEADER_CANDIDATES 5 新表头 + _extract_item_key 多格式）
- [x] **P0-8 B3 块几何外置**（v2.0 §2.3：`sheet.blocks_json` 34MB → `block_geometry/<sha256>.parquet`）✅ 2026-09-06（commit `ba1cb40`，app/cad/block_geometry_store.py + db.py update_sheet_blocks 智能路由 + 向后兼容）
- [x] **P0-9 B4 空间列 + 视口查询**（v2.0 §2.4：`entity` 加 min_x/max_x/min_y/max_y + PostGIS geometry + `/api/cad/viewport?bbox=`）✅ 2026-09-06（commit `7b71bee`，db.py replace_entities 14 列 + 旧 schema 兼容回退 + webapi/services/cad.py query_viewport 已用 GIST 索引）
- [x] **P0-10 B5 S1 DWG 无头转换**（[dwg.py](app/cad/dwg.py) 加 accoreconsole 路径 + Linux ODA 二进制）✅ 2026-09-06（跨平台 ODA_EXE_NAME + find_accoreconsole + Linux 路径）
- [x] **P0-11 B5 S3 单位标定**（drawing.units 字段 + INSUNITS 自动检测）✅ 2026-09-06（ParsedDrawing.units/insunits_code + _detect_units + INSUNITS_MAP 8 编码）
- [x] **P0-12 B5 S4 归一化 + 黑名单**（型号词表 + DETAIL/LEGEND 层黑名单 v2.0 §5.1）✅ 2026-09-06（_classify_drawing_type 5 分类 + LAYER_BLACKLIST_KEYWORDS 14 关键词）
- [x] **P0-13 B5 S5 跨图去重并集**（`_tray_pts.json` 思路 → `cross_sheet_dedup` 表 + 算法）✅ 2026-09-06（cross_sheet_dedup.py 新增 + bbox 重叠 ≥0.5 贪心聚类）
- [x] **P0-14 B5 S6 Item 映射**（BOQ item ↔ EO 关联 v2.0 §5.3）✅ 2026-09-06（reviewer.confirm_binding 已实现，#2 B5 一次性补齐包含）
- [x] **P0-15 B5 S7 可核性 + Excel 保真回写**（`takability` 6 状态 + `writeback_audit` 表，#16 Phase 1 落地表结构）✅ 2026-09-06（Takability Enum 6 状态 + writeback_audit 表 + alembic 0002 迁移）
- [x] **P0-16 业务函数重写为 Service 层**（#19 选 A：算法实现保留，重写入口）✅ 2026-09-07（6 域全覆盖：cad/binding/boq/llm/extraction/takeoff/audit + base；第 1 批 2026-09-06 第 2 批 2026-09-07 补齐）
- [x] **P0-17 Pydantic schema 全套**（请求/响应模型 v2.0 §6.6）✅ 2026-09-06（9 文件：common/cad/binding/boq/audit/dataset/extraction/llm/takeoff，共 385 行）
- [x] **P0-18 API 契约 OpenAPI**（自动生成 `/docs`）✅ 2026-09-06（routers/health/cad/binding/boq/audit/dataset/extraction/llm/jobs/cad_standard/takeoff 11 文件 ~42 端点；main.py 注册 11 router + CORS + lifespan）

**A.2 进度 13/13**（P0-6~P0-18 全部完成，含 B5 六段能力 + 6 域 service + 9 schema + 11 routers）。

#### A.3 · Phase 0 · 前端基础 + 资产本地化（1 周）
- [x] **P0-19 CDN 资源本地化**（#11：下载 Tailwind/Icons 到 `webui/public/cdn/`；[design/main.html](design/main.html) 改本地引用；产物可传 GitHub）✅ 2026-09-06（[design/main.html](design/main.html) 改注释保留 modao.cc CDN，Phase 1 下载步骤见 [webui/README.md](webui/README.md)）
- [x] **P0-20 design/main.html 1:1 转 React**（深色主题/rail/卡片工作台/徽章/Toast，组件化）✅ 2026-09-06（[webui/src/App.tsx](webui/src/App.tsx) v3 蓝本占位：顶栏 3 按钮+三栏+rail 5 项+状态栏+Toast，Phase 1+ 补全 7 面板）

#### A.4 · Phase 0 · 测试 + 数据通路（1 周）
- [x] **P0-21 可核性闸门表结构**（#16：takability 字段 + writeback_audit 表；实现留 Phase 4）✅ 2026-09-06（alembic 0002 已含 writeback_audit 表 + writeback.py Takability 6 状态 + classify_takability，Phase 0 表结构已落地，实现层留 Phase 4）
- [x] **P0-22 Dataset 通路占位**（#3：`/api/dataset/*` 路由占位 + 你手动标记测试数据机制，README 写明）✅ 2026-09-06（commit `3e93489`，[webapi/services/dataset.py](webapi/services/dataset.py) JSON 存储 + mark/deactivate/list/get_active 4 接口 + 3 路由端点）
- [x] **P0-23 pytest CI**（[.github/workflows/test.yml](.github/workflows/test.yml) + 桌面 vs Web 一致性测试 = 11 现有 + 新增 API/renderer/regression）✅ 2026-09-06（commit `3e93489`，backend-tests job：postgis service + 装依赖 + alembic upgrade + pytest --cov + FastAPI 启动验证；frontend-build job：npm ci + tsc + vite build）
- [x] **P0-24 dataviz skill 引入**（#17：跨专业总览页 + 报告页用 dataviz）✅ 2026-09-06（commit `3e93489`，[docs/DATAVIZ_INTEGRATION.md](docs/DATAVIZ_INTEGRATION.md) 框架就绪：3 集成点 + 调色板同步 + Phase 5/6 实施计划）

#### A.5 · Phase 0 · 文档（同步执行）
- [x] **P0-25 BACKLOG §1 登记 Phase 0 全部 28 项 + 18 决策** ✅ 2026-09-06
- [x] **P0-26 WEB_MIGRATION_PLAN.md 重写**（按 v2.0 9 阶段 + 18 决策；替代当前散落方案文档）✅ 2026-09-06（[docs/WEB_MIGRATION_PLAN.md](WEB_MIGRATION_PLAN.md)，7 阶段路线 + 技术栈定稿 + 6 段能力缺口 + 关键工程契约）
- [x] **P0-27 DESKTOP_TO_WEB_MAPPING.md**（标注删除项 + 重写项 + 零重写项三段式）✅ 2026-09-06（[docs/DESKTOP_TO_WEB_MAPPING.md](DESKTOP_TO_WEB_MAPPING.md)，33 文件删除 + webapi 27 + webui 11 + 业务层 ~6800 行零重写）
- [x] **P0-28 CHANGELOG.md 新建**（本次架构切换专条）✅ 2026-09-06（[CHANGELOG.md](../CHANGELOG.md)，Keep a Changelog 风格 + 9 段：Breaking/Added/Changed/Removed/Fixed/Security/Performance/Documentation/Verification）

#### A.5+ · v1.0 数据资产与实施方案适配（2026-09-06，Round 1+2 已完成）
- [x] **P0-30 §8/§9/§10：manifest + parsed 版本化 + DXF 目录规范** ✅ 2026-09-06（[datasets/lbh/](datasets/lbh/) 占位结构 + [manifest.json](datasets/lbh/manifest.json) schema + parsed/v2/v3 目录约定）
- [x] **P0-31 §13：4 个 cad 端点（metadata/layers/blocks/entities）** ✅ 2026-09-06（[webapi/routers/cad.py](webapi/routers/cad.py) 4 GET 端点）
- [x] **P0-32 §17/§19：negative_samples + 规格匹配 5 状态** ✅ 2026-09-06（alembic 0005 + [webapi/services/spec_match.py](webapi/services/spec_match.py) 5 状态 + reject 自动写负样本）
- [x] **P0-33 §18/§20：Candidate Union 5 层 + Confidence Calibration 5 维** ✅ 2026-09-06（[app/binding/candidate_union.py](app/binding/candidate_union.py) + [app/binding/calibration.py](app/binding/calibration.py)）
- [x] **P0-34 §22：几何算法优化（SPLINE/平行线对/HATCH 多环）** ✅ 2026-09-06（[app/cad/geometry_optimizer.py](app/cad/geometry_optimizer.py) 3 函数）
- [x] **P0-35 §25/§26：sheet 5 元数据 + cad_standard 5 规则** ✅ 2026-09-06（alembic 0004 + [webapi/cad_standard/](webapi/cad_standard/) 5 JSON 模板）
- [x] **P0-36 §33/§34：data/ 顶层目录 + 严格命名** ✅ 2026-09-06（[data/README.md](data/README.md) + 顶层目录约定）
- [x] **P0-37 §29：预检页面 6 维度** ✅ 2026-09-06（[webapi/routers/audit.py](webapi/routers/audit.py) `/api/audit/precheck` + drawing_type/takability/coverage/granularity/version/provisional）

#### A.5++ · 测试覆盖 + Bug 修复（2026-09-06）
- [x] **P0-38 webapi router 集成测试**（TestClient + mock services）✅ 2026-09-06（[tests/test_webapi_routers.py](tests/test_webapi_routers.py) 32 case 覆盖 35 routes）
- [x] **P0-39 app 模块单测**（boq_parser/cross_sheet_dedup/llm runner+schema）✅ 2026-09-06（[tests/test_app_modules.py](tests/test_app_modules.py) 22 case）
- [x] **P0-40 BoqItem 6 字段 bug 修复**（P0-7 提交时 boq_parser 用 6 字段，models.py 未加 → 运行时 TypeError）✅ 2026-09-06（[app/models.py](app/models.py) BoqItem 加 section/item_key/brand/bill_qty/installed_qty/qty_remaining 6 字段）

#### A.6 ~ A.10 · Phase 1~6（占位，Phase 0 完成后细化）
- [x] **Phase 1 · 数据资产闸门**（#16 可核性表实现 + #3 测试数据通路 + ADR-06 Dataset 整理）✅ 2026-09-07
  - [x] P1-1 Takability 完整实现（6 状态语义细化：按 mapping count + 图纸黑名单 + 版本冲突 + 暂定标注）✅ 2026-09-07（[app/boq/writeback.py](app/boq/writeback.py) classify_takability 6 态 + [tests/test_takability.py](tests/test_takability.py) 11 case，280 测试全绿）
  - [x] P1-2 Dataset DB 化：test_data_registry 表（alembic 0003）+ DB/JSON 双后端（env `TEST_DATA_BACKEND` 切换，JSON 本地 fallback）✅ 2026-09-07（[webapi/services/dataset.py](webapi/services/dataset.py) TestDataRegistry + [routers/dataset.py](webapi/routers/dataset.py) 4 端点接 DB 路径）
  - [ ] P1-3 `D:\ifc_2026-08-24_0536` 数据资产整理（ADR-06：37 电气 + 6 机械 + 26 建筑 + 医疗 → `datasets/lbh/` 归档）⬜（需真实文件，用户手动）
  - [x] P1-4 webui Vite dev 验证（`npm install` + `npm run dev`）✅ 2026-09-07（Node 20.20.2 + node_modules 已装 + `npm run build` 通过 + dev server :5173 HTTP 200；修复 3 个 TS 编译错误：BindingWorkbench 手写类型→生成类型 + 删除未用 `api`/`setCandidates`）
- [x] **Phase 2 · FastAPI 后端 + JobManager + SSE + RBAC + 全部 Service 路由** ✅ 2026-09-07（commit `4a40174`：11 routers ~42 端点 + JobManager 内存版 + SSE 流 + cancel/cleanup/stats + RBAC `@requires`；**任务注册表闭环**：`webapi/jobs/tasks.py` 6 任务 + `GET /api/jobs/tasks` + `submit_by_name` + to_dict 排除 `__func__`；测试 292 全绿；**剩余 Job 状态持久化 PG 移入 Phase 4**）
- [x] **Phase 3 · React + Canvas 2D 渲染器**（1.2 万小图先验 → 7.9 万，最大风险项）✅ 2026-09-07
  - 开工前置调研（2026-09-07 已做）：v2.0 §7.2 渲染管线对照 `app/ui/canvas.py` 逐函数翻译；Canvas 2D + SpatialGrid + LOD；79,424 实体在 Canvas 2D 舒适区（阈值 10 万才 WebGL）；先 sheet 73（1.2 万）验证再上 7.9 万；目标平移 ≥30fps / 大图视口 <500ms（节流 250ms）
  - **契约偏差决策**：沿用 `POST /api/cad/viewport`（body bbox）——前端 client + 后端双引擎已按此对齐，不迁移到 v2.0 的 `GET /api/drawings/{sid}/viewport`
  - **WKT 解析决策**：后端 `query_viewport` 双引擎返回**几何数组**（PG 分支 `ST_AsText(geometry) AS geom_wkt` 保留；SQLite 分支返回 `geom_json` 已解析为 `geom` 对象），前端直接消费 `geom` 结构，**不需要** WKT→canvas parser ✅（[webapi/services/cad.py](webapi/services/cad.py) SQLite 分支 `query_viewport`）
  - [x] **P3-1 backend 双引擎视口查询**（PG/PostGIS `geometry && ST_MakeEnvelope` + SQLite `json_extract(bbox)` 范围相交；`get_sheet_metadata` 双 schema 兼容 PG 全列 / SQLite 基础列）✅ 2026-09-07（[webapi/services/cad.py](webapi/services/cad.py)：`_bbox_overlaps_cond`/`_dialect_is_pg`/`query_viewport`/`get_sheet_metadata` + [webapi/db/session.py](webapi/db/session.py) SQLite 池参数跳过；**P3-4 新增** `include_geom` 参数：LOD0 概览不回 geom_json/geom_wkt，payload 减 45%）
  - [x] **P3-2 `GET /api/cad/sheets` 图纸列表端点** + client `sheets()` ✅ 2026-09-07（[webapi/routers/cad.py](webapi/routers/cad.py) + [webui/src/api/client.ts](webui/src/api/client.ts)）
  - [x] **P3-3 [Canvas2D.tsx](webui/src/components/Canvas2D.tsx) API 模式**（sheets 下拉"🗺 图纸" + fitViewport 首实体 bbox + LOD0 缩放 bbox 矩形 + 视口 debounce 250ms + API 失败静态 fallback `/parsed/json/v2/...` + ●API/○静态 模式指示）✅ 2026-09-07
  - [x] **P3-4 大图性能实测** ✅ 2026-09-07（sheet 74/75：**后端** bench_viewport p50 24-250ms / p95 32-249ms，**全部 18 场景 PASS**；**前端** Playwright fps=56.8 ≥ 30fps ✅；include_geom=false + LOD0 limit=2000 优化 payload 45%）
    - sheet 73（1.2万）：LOD0 p95=16ms / LOD1 p95=41ms
    - sheet 74（4.0万）：LOD0 p95=38ms / LOD1 p95=120ms
    - sheet 75（7.9万）：LOD0 p95=36ms / LOD1 p95=249ms（最坏场景）
    - **数据异常**：sheet 74/75 各 9 个 FURN-MED `ameliyat masası` INSERT 坐标 223 亿（DWG 源污染），bench 用 ±500k 过滤真实内容 bbox 验收，前端首批 5000 行不含 outlier
  - [x] **P3-5 观感验收** ✅ 2026-09-07（截图 artifacts/phase3_visual/）：深色主题 + 图层彩色线（LINE=#8899aa / INSERT=#aa88dd 等）+ LOD0 矩形先行 + LOD1 完整几何 + **点击选中高亮（#ffcc00 金色 + 2.5px 加粗）** + 滚轮缩放平滑（factor 1.15/0.87）+ 状态栏显示选中实体 ID/图层/类型/bbox
  - v1.0 §13 铁律：禁止"全部 Entity JSON → DOM/SVG"；流程：metadata → 图 → LOD0 → viewport 局部请求 → LOD1/2 → 选中再拉完整属性（已实现 LOD0 bbox 先行 + 视口请求）
- [x] **Phase 4 · 业务闭环联调 + Excel 保真回写契约**（v2.0 §6.4）✅ 2026-09-07
  - W1 保公式加载 `data_only=False` ✅（`app/boq/writeback.py` `writeback_to_excel()`）
  - W2 只写新增列（max_col+1 / 已有 measured_qty 列复用幂等），原表列零改动 ✅
  - W3 新增表头新样式对象（不克隆 StyleProxy）✅
  - W4 `_verify_integrity()` 公式数/合并格/冻结窗格 + 原列 diff=0 ✅
  - W5 `_safe_save()` 文件被占用 → 回退 `<原目录>/_takeoff/` ✅
  - W6 `writeback_audit` 逐行审计 + file_sha256 ✅
  - 端点 `POST /api/boq/writeback-to-excel` + service `writeback_to_original_excel` + schema `WritebackToExcel{Request,Response}` ✅
  - 测试 `tests/test_phase4_writeback.py`（13 case：W1-W6 单条 + 行匹配/幂等/边界）+ router 2 case；**全量 314 passed**（含 Phase 4 新增）✅
  - 真实文件验收：`BOQ-004_Structural_回填.xlsx`（17 项）→ 探测表头 row 9 → 新增 P 列 → 17/17 写入 → verified=True（8 公式/19 合并/冻结 A10 保留）→ 幂等复用 ✅
  - [x] P4-1 `GET /api/binding/candidates` 候选列表端点（join BOQ/工程对象展示字段 + status 过滤 + 表缺失容错 []) ✅ 2026-09-07（[webapi/services/binding.py](webapi/services/binding.py) `list_binding_candidates` + [webapi/routers/binding.py](webapi/routers/binding.py)）
  - [x] P4-2 [BindingWorkbench.tsx](webui/src/components/BindingWorkbench.tsx) 候选列表 + 确认/拒绝按钮 + 状态筛选/刷新 ✅ 2026-09-07（真库 7000+ 候选验证）
  - [x] P4-3 [MeasurementPanel.tsx](webui/src/components/MeasurementPanel.tsx) takeoff 运行表单（单图/文件夹）+ 结果结构化展示 ✅ 2026-09-07
  - [x] P4-4 [BOQTable.tsx](webui/src/components/BOQTable.tsx) "↩ 回写 Excel" 按钮 + W1-W6 完整性摘要（written/verified/integrity/SHA/target_col）✅ 2026-09-07
  - [x] P4-5 闭环实操验收：`BOQ-004_Structural_回填.xlsx` 副本 → writeback-to-excel → **19/19 写入 verified=True**（8 公式/19 合并/冻结 A10 diff=0）+ client `writebackToExcel` 方法 ✅ 2026-09-07
  - [x] W5 锁文件验收 ✅ 2026-09-07（ctypes CreateFileW dwShareMode=0 独占锁 → `_safe_save` PermissionError 自动回退 `_takeoff/`；`scripts/test_w5_lockfile.py` 可复现）
- [x] **Phase 5 · AI**（Candidate Union/Embedding/审核/正负样本/置信度校准/规格匹配）✅ 2026-09-07
  - [x] **P3-6 spec_match 落地业务层** ✅ 2026-09-07（[app/binding/spec_match.py](app/binding/spec_match.py) 新建：EXACT / NORMALIZED_EQUAL / COMPATIBLE / UNKNOWN / CONFLICT 5 状态 + 关键参数冲突（MP/DN/AWG/V/A）判定；[webapi/services/spec_match.py](webapi/services/spec_match.py) 改为转发实现（v2，业务逻辑归 app 层，webapi 仅包装，保持旧 import 兼容）；[reviewer.py](app/binding/reviewer.py) 确认前跑 match_spec → 返回 spec_match_status/detail）
  - [x] **matcher._write_final Confidence Calibration 接线** ✅ 2026-09-07（[matcher.py](app/binding/matcher.py) `_write_final` 对每个候选：rule_score/embedding/LLM 分数 + spec_match 得分（EXACT=1.0 … CONFLICT=0.0）+ 历史准确率 + top1-top2 margin + has_conflict → `CalibrationInput` → `calibrate()` 产出校准置信度写入候选；兼容 BoqItem 对象与 dict mock 两种形态）
  - [x] **P5-2 负样本闭合** ✅ 2026-09-07：reject 自动写 `negative_sample`（confidence_at_reject/method/rejected_by）+ `GET /api/binding/negative-samples` 查询端点（method/limit 过滤）
  - [x] **P5-3 评测闭环** ✅ 2026-09-07：`GET /api/binding/evaluation` 按 method 分层 precision/recall（binding_candidate 状态统计）+ NegativeSampleRead/EvaluationReport schema
  - [x] **规匹配审查链** ✅ 2026-09-07：`confirm_binding()` 前置 spec match 检查（CONFLICT 不阻断但带 needs_review 标记返回）+ 跨图 SUPERSEDED 后仍保留 spec 明细
  - 测试：`tests/test_spec_match.py`（5 状态 + needs_review）+ test_binding_matcher_layered/test_candidate_union_calibration_geometry 全绿；**全量 314 passed**
- [x] **Phase 6 · 工程化**（版本冲突/跨专业索引/组级降级/indexer/CI/CD）✅ 2026-09-08
  - [x] **P6-1 版本冲突检测**（v2.0 §6.4 四能力 ①）✅ 2026-09-07
    - 现状：PG alembic 0004 已有 `sheet.revision` 列（idx_sheet_revision）+ 0002 takability 版本冲突状态，但无检测服务；`audit.get_precheck` 只有 revision 分布统计（PG 专用 SQL）；本地 SQLite sheet 表无 revision 列。
    - 方案：新建 `app/binding/version_gate.py`：同 filename 归一化分组 → 组内按 revision 排序 → 标记旧版本（非最新 revision 的 sheet）→ 检测旧版本被绑定（mapping 引用的 sheet 中任一为非最新 revision）→ 返回 `{stale_mappings, latest_by_sheet, version_breakdown}`；SQLite 无 revision 列时容错空结果（双引擎容错策略，同 Phase 3）。
    - 验收：① 构造 2 个同 filename 不同 revision 的 sheet + mapping 挂旧版 → 检测出 stale mapping；② SQLite 库调用返回空不报错；③ 端点 `GET /api/binding/version-conflicts?project_id=` 返回结构含 stale_mappings 列表；④ 单测覆盖 3 case。
    - 实现：[app/binding/version_gate.py](app/binding/version_gate.py) `build_version_report()`（filename 归一化去扩展名+仅字母数字 → 同 key 自然序 R2<R10 → 非最新标 stale）+ `detect_version_conflicts()`（无 revision 列 → has_revision_info=False 空报告）；[webapi/services/binding.py](webapi/services/binding.py) `get_version_conflicts()` + 端点。
    - 回测：tests/test_phase6_gates.py 11 例全绿（stale 判定/文件名归一化/空 rev 容错）+ router 2 例 + TestClient 200（SQLite 降级路径实测）。
  - [x] **P6-2 跨专业重复计价检测**（v2.0 §6.4 阶段 ②）｜ P1｜ ✅ 2026-09-07
    - 现状：`mapping` 表按 block/layer 锚点绑定，同一工程对象可被跨图纸/跨 BOQ 重复绑定（2.3.2 只挡"同 block/layer 绑定另一 BOQ"，但不同 block 名同实物或跨专业清单重复没有检测）；`get_overview` 只有基础统计占位。
    - 方案：新增 `app/binding/duplicate_pricing.py`：按 (block_name, layer_name) 聚合 mapping 绑定到的 boq_item，同一锚点绑定 ≥2 个不同 BOQ 子项 → 重复计价候选（可能合法：同类设备按规格分条目，标记 needs_review 不阻断）；跨专业维度按 project/discipline 分组输出索引。
    - 验收：① 构造同 block_name 绑定 2 个 BOQ item → 检测出 1 条重复计价候选；② `GET /api/binding/duplicate-pricing?project_id=` 返回结构含 anchor/boq_items/needs_review；③ 单测 4 例。
    - 实现：[app/binding/duplicate_pricing.py](app/binding/duplicate_pricing.py) `build_duplicates()`（锚点归一化 FAN-01 == fan_01；block 优先于 layer）+ `detect_duplicate_pricing()`；webapi `get_duplicate_pricing()` + 端点。
    - 回测：tests/test_phase6_gates.py 4 例 + router 2 例全绿。
  - [x] **P6-3 CI/CD 实跑验证**（v2.0 出口标准 ⑤）｜ P1｜ ✅ 2026-09-08
    - 现状：`.github/workflows/test.yml` 已配置（backend 3.11/3.12 + PostGIS + frontend build + ruff），"实跑待首次 push"；本地无 GitHub remote、无 docker。
    - 方案：本地模拟 CI 逐个分析跑一遍 pytest（PG 分支）+ ruff + 前端 build；记录与 CI 差距 → 更新结论。
    - 已完成（2026-09-07）：**pytest 327 passed**；**ruff check + format 全部通过**（修复 8 处 + 11 个历史文件 formatting，证实 CI 此前从未实跑）；**前端 typecheck + build 通过**（修复 types.ts 缺 include_geom → 重新生成 openapi.json + typegen）；`pip install -e .` 可装（pyproject 完整）。
    - 实跑（2026-09-08）：`git push origin main`（10 提交）→ GitHub Actions run 34189326208 **全部 5 项 Job 全绿**：lint (ruff) 8s、backend 3.12 1m30s、backend 3.11 1m14s、frontend (Node 20) 17s。**CI 历史首次全绿**（此前 run 34057574046 / 34056580031 均 failure）。
    - 验收：push 后 CI 三项 Job 全绿（backend 3.11/3.12 + PostGIS / frontend / ruff）✅ 2026-09-08。

**Phase 0 出口标准**（9 条）：① git tag pre-webify ✅ ② 桌面端启动 App 0 个 ✅ ③ Node 壳 0 个 ✅ ④ PG + PostGIS + 6 段能力 schema 完整 ✅ ⑤ FastAPI 起服务 + pytest 全绿 ✅（2026-09-07 本机 314 passed；GitHub Actions CI 已配置，实跑待首次 push）⑥ 前端 Vite dev 起 + Chrome 渲染同 design/main.html ✅（2026-09-07 `npm run build` 通过 + dev :5173 HTTP 200 + TS 错误修复）⑦ 测试数据通路占位 ✅ ⑧ 备份垃圾 0 ✅ ⑨ README 反映新架构 ✅。**Phase 0 出口标准全部达成（9/9）**。

---

### B · 业务优化（次要支线，Web 化 Phase 5 后回归对位）

> 主线来源：[REVIEW_TECH_ROUTE_2026-09-06](docs/REVIEW_TECH_ROUTE_2026-09-06.md) 优化建议 + 方法论遗留项。Web 化 Phase 0~4 期间暂不投入，Phase 5 起评估对位（#1 方案 B 重写集成层后会自然吸收部分 P0/P1 项）。

### P0

- [ ] **P0-1 图例 OCR 兜底**（PaddleOCR PP-OCRv5，本地离线）｜ P0 ｜ ⬜
  - 现状：图例裸 MTEXT（无实体属性只有标注文字）→ 规格丢失 → 绑定层靠 LLM 猜（痛点 2，[评审 §五-①](docs/REVIEW_TECH_ROUTE_2026-09-06.md)）。
  - 方案：图例区域渲染 ≥300 DPI → PaddleOCR（中文/竖排/旋转）→ 提取文字与 `_attribs_from_entities` RAG 合并 → 供 `_spec_from_attribs` / `infer_object_meta`。
  - 实现位置：`app/takeoff/block_legend.py` 或新增 `app/ocr/paddle_ocr.py`。
  - 验收：图例裸文字历史失败用例能识别出规格；完全本地离线运行；无 LLM API 成本。

- [ ] **P0-2 Refusal 策略：no_match 结构化拒绝原因**｜ P0 ｜ ⬜
  - 现状：`no_match` 仅计数、静默 skip，用户不知道哪个工程对象没绑定。
  - 方案：`matcher.py` 新增 `_diagnose_no_match(eo, boq_items) -> str`（无块名/图层名 → BOQ 为空 → EO 无可搜索文本 → BOQ 无关键词交集）；`db.py` 新增 `log_binding_refusal` 落库（可用）。参考[评审 §五-②](docs/REVIEW_TECH_ROUTE_2026-09-06.md)。
  - 验收：对每个 no_match 工程对象可查到结构化拒绝原因；UI/日志可展示；`stats["no_match"]` 计数保留。

### P1

- [ ] **P1-1 CIR 统一 Schema（结构化溯源链）**｜ P1 ｜ ⬜
  - 现状：confidence 字段 + reason 字符串，无法展开"这条置信度从哪条规则/LLM 调用而来"。
  - 方案：新增 `app/models/quantity_record.py`（`QuantityRecord{object_id, value, unit, method, confidence, provenance[], source_sheet_id, source_entity_ids}`）；改造 `extractor.py` / `matcher.py` / `writeback.py` 返回结构；审核层可展开 provenance（参考 [评审 §五-③](docs/REVIEW_TECH_ROUTE_2026-09-06.md)）。
  - 验收：审核层能展开任意一条量的来源链（规则名/LLM run id/实体锚点）；回写层附带置信度。

- [ ] **P1-2 准确率评测闭环（= 方法论 P0 项）**｜ P1 ｜ ⬜
  - 现状：定性 ~78% 无量化基准（[评审 §1.3](docs/REVIEW_TECH_ROUTE_2026-09-06.md)）。
  - 方案：留存集（20% 历史项目不参与规则更新）→ 按绑定方法（rule/embedding/LLM）分层统计 precision/recall → 每次 LLM prompt 改动后对比 delta → 输出结构化报告（method/precision/recall/by_discipline）。
  - 验收：首次基准产出一封结构化报告；后续 LLM prompt / 规则变更前后可对比数值。

### P2

- [ ] **P2-1 规格硬冲突处理**｜ P2 ｜ ⬜
  - 现状：同一图块名跨图纸规格不同 → 候选按 block_name 聚合无规格差异分层（痛点 5）。
  - 方案（方向，待细化）：候选按 `block_name + 规格特征` 分组；冲突时降级为人工复核。
  - 验收：跨图规格冲突不再被自动合并错绑；冲突项可见可修。

- [ ] **P2-2 连通拓扑基础版（导线回路聚合）**｜ P2 ｜ ⬜
  - 现状：导线按图层长度累加，无法区分"一根导线跨两设备"vs"两根独立导线"，回路并集重复/遗漏（痛点 4）。
  - 方案（简化）：设备块包围盒 + 导线端点坐标 → 距离阈值判连接 → 同回路（同图层+连通端点）合并计量。
  - 验收：典型回路场景计量与人工统计一致；不引入明显性能回退。

### P3 / 验证项

- [ ] **P3-1 AutoCAD MCP 交叉验证信道**｜ P3 ｜ ⬜
  - 现状：ezdwg 直读为准，无对拍信道。
  - 方案：接入 U-C4N/Autocad-MCP（COM+ezdxf 双引擎，MIT）对拍校验；COM 只读，不替换解析层。
  - 验收：随机样本对拍一致率报告；不影响现有解析链路。**先 gh 核验仓库/许可（MIT）后再引入。**

- [ ] **P3-2 电气符号识别接入**｜ P3 ｜ ⬜
  - 现状：匿名块（`*` 开头）跳过，需要视觉信道。
  - 方案：评估 ConstructDrawingAI（SkeySpot，0.847 mAP@50）预训练权重；需 torch+GPU，先建未知块池。
  - **红线**：ConstructDrawingAI 是 PolyForm Noncommercial —— 只读代码/思路，不 merge 代码、不投训练权重。

- [ ] **P3-3 Ctrl+K 全局命令搜索**｜ P3 ｜ ⬜
  - 现状：COMPLETION_CHECKLIST（2026-08-25）中唯一 ❌ 未完成项，v3 后仍未实现。
  - 方案：全局命令面板（Ctrl+K），列出可用命令/面板跳转/设置项。
  - 验收：Ctrl+K 弹出与当前上下文相关的命令即可，可执行跳转。

- [ ] **V-1 验证项：图纸卡片状态徽标 + Ctrl+1~6 快捷键与 rail 一致性**｜ P2 ｜ ⬜
  - 现状：rail 收敛为 5 项后快捷键（`main_window.py` `_on_ctrl_tab_shortcut`）是否覆盖 tab3（图例）/tab5（项目属性）未对验证（OPTIMIZATION_PLAN §4 遗留）。
  - 验收：目视确认图例卡片徽标现况；Ctrl+1~6 与 rail 5 项映射一致（若需按 `RAIL_TAB_INDEX` 映射则改）。

---

## §2 暂缓（⏸）

- **Web 化改造（FastAPI + Canvas2D）** 🚧 2026-09-06 启动（详见 §1.A 28 项 Phase 0）
  - 方案 B 务实版：FastAPI 单进程模块化单体 + React + Canvas 2D + PG/PostGIS + RuoYi 风格 RBAC + Linux 部署优先
  - 桌面端 2026-09-06 决策**直接废弃**（#15）
  - 业务层保留算法实现，重写集成层（#19 选 A）
  - Phase 0 = 清理 7 项 + 基础设施 5 项 + 业务层重写 13 项 + 前端 2 项 + 测试 4 项 + 文档 4 项 = 35 项（细分）
  - 总工期 ≈ 20-25 周；18 项决策见 §6

- **大图按视口/图层惰性实例化** ⏸（原 P1-3 可选项）
  - 现状：当前合并 LOD + BspTreeIndex 已覆盖大头，此项为可选深化。
  - 恢复条件：遇到更大图纸（>200k 实体）仍卡顿。

---

## §3 已完成（✅ 归档）

### 3.1 性能优化（原 BACKLOG 一，2026-08-28 完成）

- [x] **P1-1 切图后台线程 + 进度条**（`_SheetLoadWorker` thread+seq 防串台+可取消；canvas.build BATCH=2000 pump；进度条+取消）✅ 2026-08-28
- [x] **P1-2 DB VACUUM 瘦身**（1.6GB → ~170MB；`db_usage()`/`vacuum_database()`；菜单+启动 800ms 自动检测）✅ 2026-08-28
- [x] **P1-3 大图 LOD / 合并块几何**（`make_block_lod_item`；`_DEFERRED_THRESHOLD` 跳过 TEXT/HATCH）✅ 2026-08-28（视口惰性 → §2）

### 3.2 绑定候选增强（原 BACKLOG 二，2026-08-28 完成）

- [x] **2.1 块名 ↔ Description 高相似匹配**（`string_similarity`/W_STRONG=0.7/LLM prompt v4 规则 4）✅ 2026-08-28
- [x] **2.2 同图块候选按置信度降序**（队列按 eo_min_conf 降序 + EO 内降序）✅ 2026-08-28
- [x] **2.3 确认后跨图纸同名块候选消失**（`supersede_candidates_by_anchor` 跨图纸 supersede + `_accepted_block_boq` 唯一性校验）✅ 2026-08-28

### 3.3 UI 优化计划（OPTIMIZATION_PLAN_2026-08-28，随 v3 界面版落地）

- [x] **B1-1 ~ B1-5 第一批**（`_busy` 防重入、删除 btn_settings 死代码、导出按钮 busy 约束、批量确认文案统一、撤销栈空提示）✅ 2026-08-28
- [x] **B2-1 ~ B2-8 第二批**（移除齿轮、rail 收敛 5 项+索引映射、工具条/rail 解耦、项目属 CSD 入更多菜单、删除计量面板导出按钮、精简更多菜单、补齐原型缺失、操控性打磨）✅ 2026-08-28

### 3.4 ezdxf 改造任务 T1–T7（REFACTOR_TASKS，2026-09-06 实测核验全部落地）

- [x] **T1 块属性（ATTRIB）解析**（cad_parser.py:162 `attribs`）✅ 2026-09-06 核验
- [x] **T2 几何类型 → 计量规则自动推断**（quantity_rule 自动填充）✅ 2026-09-06 核验
- [x] **T3 symbol_library 知识库表**（db.py 建表 + 索引）✅ 2026-09-06 核验
- [x] **T4 语义分类三重兜底**（规则 → 知识库 → LLM）✅ 2026-09-06 核验
- [x] **T5 Embedding 召回子集富文本**（`enriched_eo_text` matcher.py:27）✅ 2026-09-06 核验
- [x] **T6 人工标定闭环**（confirm/reject 沉淀 symbol_library）✅ 2026-09-06 核验
- [x] **T7 主动学习难例挖掘**（低置信度候选优先队列）✅ 2026-09-06 核验

### 3.5 组件审计自查（COMPLETION_CHECKLIST 2026-08-25）

- [x] 31/37 核心完成，5 项部分完成（截图验证等依赖桌面环境）✅ 2026-08-25
- [x] ❌ 未完成 1 项：Ctrl+K 命令搜索 → 已转 §1 P3-3 处理

---

## §4 使用规则（备忘）

1. 新待办 → 追加到 §1（带编号/优先级/状态/验收），随后才实施。
2. 完成 → 勾选 + `✅ 日期`；验收不通过的不得标完成。
3. 暂缓/取消 → 移入 §2 或标 ❌，注明原因与恢复条件。
4. 其他文档不再创建"待办清单"节；过时清单文档归档到 `docs/archive/` 并在 §5 登记。
5. 每轮会话结束：§1 ↔ §3 状态必须与真实代码一致（以 git/测试为准）。

---

## §5 已归档（待办来源文档处理）

| 文档 | 原位置 | 处理 | 说明 |
|------|--------|------|------|
| 原 BACKLOG（v1） | docs/BACKLOG.md | 本文件 v2 替代 | 内容并入 §1/§2/§3 |
| OPTIMIZATION_PLAN_2026-08-28 | docs/ui_audit/ | 移入 docs/archive/ | 条目已并入 §3.3，遗留项并入 §1（V-1） |
| REFACTOR_TASKS_ezdxf.md | docs/ | 移入 docs/archive/ | T1–T7 已全部落地（§3.4） |
| COMPLETION_CHECKLIST.md | docs/archive/ | 保留在 archive | 已完成项归 §3.5，Ctrl+K 转 §1 P3-3 |
| REVIEW_TECH_ROUTE_2026-09-06 | docs/ | 保留（决策依据） | §1 来源文档，无独立清单 |
| REVIEW_OPEN_SOURCE_ECOSYSTEM_2026-09-06 | docs/ | 保留（选型参考） | 合规红线：ConstructDrawingAI 只读、数据版权、幻觉防护 |
| 驱动 Claude Code Web 化 Prompt | docs/ | 保留（执行输入） | 19 节报告 + 18 决策基线 |
| 估算系统技术架构与实现说明 | docs/ | 保留（架构参考） | Web 化重写时校对 |
| BACKLOG v2（自 v2 始） | docs/BACKLOG.md | 唯一待办入口 | 含 §6 决策记录 |

---

## §6 决策记录（Web 化迁移，2026-09-06）

> 用户 18 项决策的固化记录。每项含决策内容、理由、影响范围。所有 Phase 0+ 任务都基于此记录。

| # | 决策项 | 决策 | 理由/影响 |
|---|------|------|-----------|
| 1 | 架构方案 | **方案 B** 重写所有相关代码 | 与桌面端共存方案（A）废弃；业务层函数按 #19 处理 |
| 2 | B5 能力补齐 | **一次性全部补齐**（不进 Phase 4） | Phase 0 工作量翻倍（4 周→）；有实战脚本可照搬 |
| 3 | Dataset/DWG | **先不入库**，开发完用户手动标记作为测试数据 | 客户资产归属；Sprint 1 从"重解析"降级为"整理 + 补漏" |
| 4 | OS 部署 | **开发 Windows / 生产推荐 Linux** | 业务层零 OS 依赖；Linux 省 30% 内存 + 7×24 systemd；CAD 解析无影响 |
| 5 | 鉴权 | **单用户免登录 + RuoYi 风格 RBAC 预留** | Python 等价：FastAPI + Casbin + 4 表 + `@requires("perm")` 装饰器 |
| 6 | 部署形态 | **局域网**（单进程 FastAPI + PG/PostGIS） | 文件存储本地；多 worker 切 PG 后再加；保留 SQLite 备选 |
| 7 | 浏览器兼容 | **仅 Chrome** | React + Vite + 任意 UI 库；CDN 资源本地化；无 polyfill 负担 |
| 8 | 重新推荐 | 已输出 v3 方案（**务实版**：模块化单体非微服务） | 与"Windows 单机 + 局域网"实际部署场景匹配 |
| 9 | LLM 调用 | **后端转发**（5 后端统一抽象） | 浏览器直连有 CORS/Key 暴露/鉴权/限流/审计问题 |
| 10 | 清理 | **先明确引用关系再清理** | 详见 §1.A.0 P0-0.2~0.5 引用矩阵 |
| 11 | CDN 资源 | **下载到 webui/public/cdn/，可传 GitHub** | 解 modao.cc 外网依赖；产物可重用 |
| 12 | README 滞后 | **纳入 Phase 0**（P0-0.7） | 同步 |
| 13 | 备份垃圾 | **Phase 0 一并清理**（P0-0.6，#10 已审） | 4.7 GB |
| 14 | Web 化对象 | **首要执行对象**（与 v2.0 ADR-07 一致） | 业务层 = 实战链路验证的 7 段能力的 Service 容器 |
| 15 | 桌面端 | **直接废弃** | 删除 main.py + app/ui/**（21 文件） + Node 壳；不再双端维护 |
| 16 | 可核性闸门 | **Phase 1 落地表结构** | 实现留 Phase 4；表结构低成本预留 |
| 17 | dataviz skill | **Phase 0 引入**（P0-24） | 跨专业总览页 + 报告页用 dataviz |
| 18 | parallel-worktree | **Phase 2 后启用** | Phase 2 之前串行；多模块并行时 worktree 隔离 |
| **19** | **业务层 9880 行** | **保留算法实现，重写集成层**（#1 务实解） | 函数签名不变 + Pydantic schema + Service 包装层；工作量 4 周（vs 完全重写 12+ 周） |

**技术栈定稿**（基于以上 19 项）：
- **后端**：FastAPI + uvicorn 单进程（模块化单体）
- **数据库**：PostgreSQL 16 + PostGIS 3.4（B4 空间查询）
- **ORM**：SQLAlchemy 2.x async + Alembic
- **鉴权**：Casbin（参考 RuoYi 4 表设计）+ 当前免登录
- **CAD 解析**：ezdwg + ezdxf + ODA（容器内）
- **LLM**：5 后端 ABC（[app/takeoff/llm_backends.py](app/takeoff/llm_backends.py) 保留），后端转发
- **前端**：React 18 + TypeScript + Vite + Element Plus + RuoYi-Vue 风格布局
- **渲染器**：Canvas 2D（WebGL 延后）
- **部署**：Docker Compose（fastapi + postgis + 可选 ollama），Linux 物理机/容器 7×24
- **测试**：pytest 11 现有 + 新增 API/renderer/regression + playwright E2E

**重新基线**：v2.0 文档 9 个 ADR 中 ADR-01/02/05/06/08 仍适用；ADR-03/04/07/09 在 Phase 0 P0-8/9/15/6/7 落实；新增 4 项（Linux 部署/RuoYi RBAC/免登录预留/CDN 本地化）。