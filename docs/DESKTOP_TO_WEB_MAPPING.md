# Desktop → Web 映射表

> 2026-09-06 Web 化 Phase 0 启动版。Phase 0 完成 2026-09-06。
> 配套：[WEB_MIGRATION_PLAN.md](WEB_MIGRATION_PLAN.md) + [BACKLOG.md](BACKLOG.md)。

---

## 一、删除项（2026-09-06 已删除）

| 模块 | 处置 | git commit |
|---|---|---|
| `main.py`（PySide6 入口）| 删除 | `5056d21` |
| `app/ui/__init__.py` + 21 文件 | 删除 | `5056d21` |
| `src/index.js` + `src/boq.js`（Node 占位壳）| 删除 | `8c250ed` |
| `bin/cad-boq-tool.js`（Node bin 包装）| 删除 | `8c250ed` |
| `package.json`（Node 元数据）| 删除 | `8c250ed` |
| `verify_round3_*.png` × 3（2026-08-25 旧 GUI 截图）| 移动到 `artifacts/_legacy_ui/` | `a21ecb6` |
| `ui_audit.md`（旧 UI 审计）| 移动到 `artifacts/_legacy_ui/` | `a21ecb6` |
| 9 份 UI 归档文档 | 移动到 `docs/_removed/` | `52c2df1` |
| `~/.cad-boq-tool/projects.db.bak_*` × 5 + 备份家族（5.2 GB）| 删除 | 非 git（备份清理）|
| `.gitignore` 中 `docs/` 整目录 ignore | 解除 | `52c2df1` amend |

---

## 二、重写项（webapi/ 包装层 + alembic schema）

### 2.1 webapi Service 层（包装而非重写 #19）

| webapi 包装 | 包装原 app/ 业务函数 | 说明 |
|---|---|---|
| `webapi/services/cad.py` | `app.cad.reader.read_cad` + `app.cad.cad_parser.parse_dxf` + B4 viewport | parse + 视口查询 |
| `webapi/services/binding.py` | `app.binding.matcher.generate_candidates` + `app.binding.reviewer.confirm_binding/reject_binding` | 4 层候选 + 确认/拒绝 |
| `webapi/services/boq.py` | `app.boq.boq_parser.parse_boq` + `app.boq.writeback.write_back_quantities` | B1 4 表头 + B5 S7 |
| `webapi/services/llm.py` | `app.llm.runner.run_llm_with_retry` + `app.takeoff.llm_backends.create_backend` | 5 后端 ABC |
| `webapi/services/dataset.py` | 新增（Phase 0 JSON 存储 / Phase 1 DB）| #3 测试数据通路 |
| `webapi/services/base.py` | 新增 | ServiceError + NotFoundError + PermissionDeniedError |

### 2.2 webapi Schema 层（Pydantic v2）

| 文件 | 覆盖 |
|---|---|
| `webapi/schemas/common.py` | ApiResponse[T] / Pagination / PageResult / ErrorResponse |
| `webapi/schemas/cad.py` | Parse/Viewport + B4 字段 |
| `webapi/schemas/binding.py` | Generate/Confirm/Reject + Read |
| `webapi/schemas/boq.py` | Parse/Writeback + B2 6 新字段 |
| `webapi/schemas/dataset.py` | TestDataEntry + Registry |
| `webapi/schemas/llm.py` | 占位（Phase 1 实现）|

### 2.3 webapi Router 层（FastAPI）

| Router | 端点 |
|---|---|
| `routers/health.py` | GET /health, GET / |
| `routers/cad.py` | POST /api/cad/parse, POST /api/cad/viewport |
| `routers/binding.py` | POST /api/binding/{generate,confirm,reject} |
| `routers/boq.py` | POST /api/boq/{parse,writeback} |
| `routers/dataset.py` | GET /api/dataset, POST /api/dataset/{mark,deactivate} |

### 2.4 webapi Auth 层（RuoYi 风格 RBAC）

| 文件 | 职责 |
|---|---|
| `webapi/auth/models.py` | 5 RBAC 表 ORM（sys_user/role/user_role/menu/dict）|
| `webapi/auth/schemas.py` | Pydantic schema（User/Role/Menu/Dict/Auth）|
| `webapi/auth/service.py` | `get_user_by_username` + `get_or_create_admin` |
| `webapi/auth/decorators.py` | `@requires("perm:code")` |
| `webapi/auth/casbin_rbac.py` | Casbin 包装（keyMatch 路径 + 空策略）|
| `webapi/auth/current_user.py` | FastAPI Depends（no_login sysadmin stub）|

### 2.5 alembic schema 迁移

| 迁移 | 改动 |
|---|---|
| `0001_initial_schema` | 12 业务表 + 5 RBAC 表 + PostGIS 扩展 + B2（boq_item +6 字段）+ B4（entity +min_x..max_y +geometry GIST）|
| `0002_b5_capabilities` | entity.units / sheet.units / sheet.drawing_type / cross_sheet_dedup / writeback_audit |

### 2.6 webui 前端骨架

| 文件 | 职责 |
|---|---|
| `webui/package.json` | Vite 5.4 + React 18.3 + TS 5.5 + Tailwind 3.4 |
| `webui/vite.config.ts` | dev port 5173 + `/api` proxy → :8521 |
| `webui/index.html` + `tsconfig*.json` | 入口 + TS 配置 |
| `webui/src/main.tsx` | React 入口 |
| `webui/src/App.tsx` | v3 蓝本 1:1 占位（顶栏+三栏+rail+状态栏+Toast）|
| `webui/src/theme.ts` / `theme.css` | slate 调色板 + CSS 变量 |
| `webui/src/api/client.ts` | webapi fetch wrapper + ApiError |
| `webui/README.md` | 启动 + 组件 Phase 路线 + CDN 本地化步骤 |

### 2.7 容器化

| 文件 | 职责 |
|---|---|
| `Dockerfile` | python:3.12-slim 多阶段构建（builder 装 Rust/编译 ezdwg，runtime 拷 site-packages）|
| `docker-compose.yml` | webapi + postgis/postgis:16-3.4 + 可选 ollama（profile=with-llm）|
| `.dockerignore` | 排除 .venv/ / node_modules/ / docs/ / tests/ 等 |

### 2.8 文档

| 文件 | 职责 |
|---|---|
| `BUILD_STATUS.md` | 验证状态（venv 3.11 vs pyproject 3.12）|
| `WEB_MIGRATION_PLAN.md` | 本次重写 |
| `DESKTOP_TO_WEB_MAPPING.md` | 本次重写 |
| `CHANGELOG.md` | 本次新建（#28）|
| `DATAVIZ_INTEGRATION.md` | P0-24 dataviz 集成框架 |

---

## 三、零重写项（app/ 业务层完整保留 #19 选 A）

### 3.1 算法层（零改动）

| 模块 | 行数 | 业务职能 |
|---|---|---|
| `app/cad/reader.py` | ~500 | ezdwg/ezdxf/ODA 三层抽象 |
| `app/cad/cad_parser.py` | ~440 | 17 种实体几何 + INSERT 嵌套展开 + **B5 S3/S4 加 units/drawing_type** |
| `app/cad/geometry.py` | ~150 | 纯函数几何 |
| `app/cad/parse_cache.py` | ~150 | LRU 磁盘缓存 |
| `app/cad/block_geometry_store.py` | **新增 B3** ~80 | parquet 写读 + sha256 引用 |
| `app/cad/dwg.py` | ~150 + **B5 S1** ~50 | ODA 探测 + 跨平台 + accoreconsole |
| `app/engineering/extractor.py` | ~200 | 设备/线性/面积三类 EO |
| `app/engineering/classifier.py` | ~300 | 三重兜底分类 |
| `app/engineering/llm_classify.py` | ~150 | LLM 兜底 |
| `app/engineering/object_model.py` | ~100 | make_engineering_object |
| `app/engineering/specification.py` | ~80 | extract_spec/phrase |
| `app/engineering/cross_sheet_dedup.py` | **新增 B5 S5** ~120 | bbox 重叠 ≥0.5 贪心聚类 |
| `app/binding/matcher.py` | ~200 | 4 层候选生成 |
| `app/binding/rule_matcher.py` | ~250 | 规则匹配 |
| `app/binding/embedding_matcher.py` | ~200 | embedding 召回 |
| `app/binding/llm_matcher.py` | ~80 | LLM 精排 |
| `app/binding/candidate_aggregator.py` | ~100 | 候选聚合 |
| `app/binding/resolver.py` | ~60 | 确定性重算 |
| `app/binding/reviewer.py` | ~200 | 确认/拒绝 + 跨图 SUPERSEDED |
| `app/binding/text_norm.py` | ~80 | 文本归一化 + LCS |
| `app/takeoff/orchestrator.py` | ~150 | AI 算量编排 |
| `app/takeoff/aggregate.py` | ~300 | map-reduce 聚合 |
| `app/takeoff/stream_aggregate.py` | ~150 | 流式聚合 |
| `app/takeoff/classify.py` | ~150 | 中文大类词库 |
| `app/takeoff/block_legend.py` | ~600 | 图例建议 + 过滤 |
| `app/takeoff/context_infer.py` | ~80 | trade/floor 推断 |
| `app/takeoff/quality.py` | ~60 | 跨文件 conflict/去重 |
| `app/takeoff/folder_pipeline.py` | ~80 | 文件夹维度 |
| `app/takeoff/llm_backends.py` | ~250 | 5 后端 ABC |
| `app/takeoff/llm_classify.py` | ~300 | Ollama/OpenAI 分类 |
| `app/llm/runner.py` | ~150 | 统一入口 + 重试 + 审计 |
| `app/llm/embeddings.py` | ~100 | embedding |
| `app/llm/prompts.py` | ~300 | 提示词版本管理 |
| `app/llm/schema.py` | ~200 | JSON Schema + Pydantic |
| `app/llm/audit.py` | ~80 | llm_run 审计 |
| `app/llm/settings.py` | ~80 | LLM 配置中心 |
| `app/boq/boq_parser.py` | ~120 + **B1/B2** ~80 | 4 种表头 + 6 字段 |
| `app/boq/writeback.py` | ~60 + **B5 S7** ~50 | Takability 6 状态 + 审计 |
| `app/mapping.py` | ~50 | add_*_mapping |
| `app/measure.py` | ~150 | compute_item |
| `app/report.py` | ~250 | export_report/export_materials |
| `app/models.py` | ~170 | 9 dataclass（与 SQLite 表一一对应）|
| `app/db.py` | ~1700 | SQLite 1.6K 行 SQL + thread-local 连接 + **B3/B4 改造** ~60 行 |
| `app/config.py` | ~60 + B2 + B3 | BOQ_HEADER_CANDIDATES + BLOCK_GEOMETRY_DIR |
| `app/batch_reparse.py` | ~200 | 批量重解析 |
| `app/import_folder.py` | ~150 | 文件夹导入 |

**总业务代码 ~6800 行，零重写**（#19 选 A 落地）。

### 3.2 已存在但 Phase 0 暂未集成到 webapi（Phase 1+ 补）

- `app/takeoff/*`（orchestrator/aggregate/llm_backends/llm_classify）→ Phase 5 AI 路由
- `app/llm/embeddings.py` → Phase 5 embedding 召回
- `app/boq/boq_parser.py` 的 4 种表头识别 → 已在 P0-6 落实（boq_parser.py 重写）

---

## 四、统计

| 维度 | 数值 |
|---|---|
| 删除文件 | 33（main.py + app/ui/** 22 + Node 5 + 备份 7）|
| 移动文件 | 11（7 UI 归档 + 4 旧截图）|
| 新跟踪文件 | 14（docs/ 历史文档补 add）+ 7 _removed + 4 _legacy_ui = 25 |
| webapi 新增 | 27 文件（config + db + auth ×6 + services ×6 + schemas ×5 + routers ×5 + main）|
| webui 新增 | 11 文件（package/vite/tsconfig×2/index/main/App/theme×2/api/README）|
| 业务代码改动 | ~600 行新增（B1/B2/B3/B4/B5 6 段 + alembic 2 迁移）|
| 业务代码保留 | ~6800 行（#19 选 A：算法零重写）|
| 文档新增 | 5（WEB_MIGRATION_PLAN/DESKTOP_TO_WEB_MAPPING/CHANGELOG/DATAVIZ_INTEGRATION/BUILD_STATUS）|

**总计 git commits 16 个**（含 pre-webify tag）。
