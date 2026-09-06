# CAD·BOQ Web 化架构设计 v1.0

| 项 | 内容 |
|---|---|
| 版本 | v1.0 |
| 日期 | 2026-08-29 |
| 上游输入 | `docs/CAD_BOQ_Web化改造_数据资产与实施方案_v1.0.md`（下称「实施方案」） |
| 相关文档 | `docs/WEB_PLATFORM_ARCHITECTURE_2026-08-28.md`（下称「8-28 Web 方案」）、`docs/估算系统技术架构与实现说明.md`（下称「架构审计 v1.1」）、`docs/BACKLOG.md` |
| 设计原则 | **演进而非重写**——`app/cad`、`app/binding`、`app/takeoff`、`app/measure` 等核心算法零重写，只抽取 Service 边界 + 替换展示层 |
| 状态 | 待确认（第 10 节列出 15 项待补充/决策事项，其中 5 项阻塞定稿） |

---

## 1. 设计输入基线（实测，非推测）

所有数字于 2026-08-29 19:00 从本机实测获得，作为架构判断的事实依据。

### 1.1 运行时数据现状

| 项 | 实测值 | 说明 |
|---|---|---|
| 数据库 | `~/.cad-boq-tool/projects.db`，**171.5 MB** | WAL 模式，thread-local 连接池 |
| 项目 | 1 个：`Bengasi-hospital`（id=25） | 即 LBH 项目 |
| 图纸 | 4 张（仅电气专业已导入） | 73/74/75/76 |
| 实体总数 | **184,325** | 单图最大 79,424（sheet 75） |
| BOQ 条目 | 480 | **解析结果全部错误，见 2.1** |
| EngineeringObject | 64 | |
| BindingCandidate | 392（ACCEPTED 1 / PENDING 32 / SUPERSEDED 359） | 仅 1 条走完全流程 |
| llm_run | 996（binding 852 / classify 144） | 审计数据完整，可做置信度校准样本 |
| symbol_library | 5 | |
| block_legend | 0 | 与 symbol_library 冗余（架构审计 C-08） |
| mapping | 95 | |

### 1.2 存储占用异常（架构债）

| 表 | 占用 | 病灶 |
|---|---|---|
| `sheet` | **99.8 MB** | `blocks_json` 单张图 **34 MB** 直接存 SQLite TEXT 列（4 张图共约 138 MB 原始 JSON） |
| `entity` | 59.6 MB | `bbox` 为 **TEXT (JSON string)**，无法做 SQL 空间窗口查询 |
| `llm_run` | 3.9 MB | `input_text`/`output_text` 全文入库，可接受 |

### 1.3 源文件与代码资产

| 项 | 实测 |
|---|---|
| DWG 源 | `D:\ifc_2026-08-24_0536\`，**238 份 / 25 MB**，分 5 个专业目录（electrical / Architecture & Interior / …） |
| BOQ 源 | 同上目录 `2、电气、机械、建筑和室内、结构清单表/MD-LBH-BOQ-001_Electrical_Remaining_Works_UNPRICED_Rev——1.xlsx` |
| 代码规模 | `app/**` 业务层 **9,879 行**（不含 `app/ui/*`）；`app/db.py` 1,687 行为最大模块 |
| 业务层 Qt 依赖 | **无**——`app/cad`、`app/binding`、`app/takeoff`、`app/engineering`、`app/boq`、`app/llm`、`app/measure.py`、`app/mapping.py` 均可被 FastAPI 直接 import |
| 仓库内数据资产 | **0**——无 DWG/DXF，无解析 JSON，数据全在用户目录的 SQLite 里 |
| 版本控制 | `.gitignore:11` 含 `docs/`——早期文档已 tracked，但新建文档一律不被跟踪（隐患，见 10-B5） |

### 1.4 结论：实施方案的前提需要修正

实施方案第 7 节假定「当前已经产生的真实 LBH 图纸 JSON」可直接整理为 Dataset。实测否：

- 仓库内**不存在**解析产出的 JSON 文件，只有 SQLite；
- 已导入的**只有 4 张电气图**（占 238 份源图的 1.7%），机械/建筑/结构尚未导入；
- 现有 BOQ 解析结果 480 条全错，不能直接作为 `expected/quantities` 基线。

因此 Sprint 1 的真实工作量是「**从 SQLite 反向导出 + 从 DWG 源重新解析**」，而非「整理现有 JSON」。这一点直接影响工期估算，见第 9 节与待确认项 A3。

---

## 2. 阻塞项（Phase 0 必须先修，否则 Web 化地基不稳）

| ID | 阻塞项 | 证据 | 影响 | 修复方案 |
|---|---|---|---|---|
| **B1** | **BOQ 表头探测失败 → fallback 生成全量占位数据，480 条全错** | 入库值 `code='item-1'`、`description='None'`、`unit='None'`、`original_qty=0.0` | BOQ 是绑定的目标侧，全错则 Sprint 4/5 全部作废；实施方案 §17 的正负样本也无法建立 | 根因已定位，见下方分析。需用户提供该 Excel 的正确表头行号/列名（待确认 B2） |

**B1 根因（`app/boq/boq_parser.py:60-70`）**：

```python
for i, row in enumerate(rows[:5]):
    m = _detect_headers(row)
    if len(m) >= 2: header_idx, mapping = i, m; break
if header_idx is None:
    header_idx = 0                                    # ← 未命中：把第 1 行当表头丢掉
    mapping = {"code": 0, "description": 1, "unit": 2}  # ← 硬编码兜底列位
```

三重失效叠加：
1. 该 Excel 前 5 行是合同声明/标题（代码里已有 `_is_skippable_contract_text` 处理这类文本，但它在兜底之后才生效），`_detect_headers` 未命中；
2. 兜底路径把第 1 行当表头丢弃，且硬编码取第 0/1/2 列——与真实列位不符，取到的全是 `None`；
3. `str(None).strip()` 得到字符串 `"None"`，导致 `if not code and not desc: continue` 的过滤失效（`"None"` 非空），最终 480 条全量入库为垃圾数据，`code` 则走 `f"item-{n}"` 占位分支。

修复方向：表头探测窗口从「前 5 行」放宽（或改为全表扫描 + 置信度打分）；探测失败时**不静默兜底**，而是返回错误交由 UI/API 让用户手动指定表头行与列映射；`None` 须在 `str()` 前拦截。
| **B2** | **块几何 34 MB 存 SQLite TEXT** | `sheet.blocks_json` 单图 34 MB，sheet 表 99.8 MB | 单次 `get_sheets` 即可拖垮进程；DB 文件不可控膨胀；Web 端 `/api/sheets/{id}/blocks` 响应 34 MB 不可接受 | 块几何外置到文件系统（`artifacts/blocks/<sheet_id>/v<n>.json.gz`），DB 只存 `blocks_path` + `blocks_sha256`。见 ADR-03 |
| **B3** | **`entity.bbox` 为 TEXT，无法空间查询** | `bbox TEXT` 存 JSON string | Web viewport 按需加载（实施方案 §13）依赖窗口查询，无空间列则只能全量拉取 79,424 实体，与「大图不全量加载」验收标准直接冲突 | 迁移脚本新增 `min_x/min_y/max_x/max_y` REAL 四列 + 复合索引 `(sheet_id, min_x, max_x, min_y, max_y)`，`replace_entities` 写入时同步填充。见 ADR-04 |
| **B4** | **磁盘垃圾 ~4.7 GB** | `projects.db.bak_20260826_*.db` 各 1.6 GB ×2，`projects.db.fresh/rebuilt/before-rebuild.bak` 各 440 MB ×3 | 无直接功能影响，但须在数据资产化前清理并制定备份策略 | 归档到 `~/.cad-boq-tool/archive/` 或直接删除；后续改由「Dataset 版本化」承担可回溯职责（实施方案 §9） |

---

## 3. 架构总览

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ Browser  (React 18 + TypeScript + Vite)                                   │
│                                                                           │
│  ┌────────────┬──────────────────────────────────┬─────────────────────┐  │
│  │ 左栏        │  中栏：CAD Viewport              │ 右栏：任务面板       │  │
│  │ 图纸/图层   │  Canvas 2D + 空间网格索引 + LOD   │ BOQ / 绑定 / 属性    │  │
│  │ 块树 / 搜索 │  拾取·框选·平移·缩放·高亮        │ 证据 / 冲突 / 历史   │  │
│  └────────────┴──────────────────────────────────┴─────────────────────┘  │
│  状态：TanStack Query（服务端态） + Zustand（视图态/选择集）                │
└────────────────────────────┬──────────────────────────────────────────────┘
                             │ REST / JSON (gzip)          ▲ SSE（job 进度）
┌────────────────────────────▼──────────────────────────────────────────────┐
│ FastAPI  (web/server.py, uvicorn, --workers 1)                            │
│                                                                           │
│  routers/    薄层：参数校验 · 鉴权 · 序列化，不含业务规则                  │
│  services/   厚层：业务编排（从 app/ 提取，算法零重写）                    │
│  jobs/       JobManager：后台任务 + 进度事件 + SSE 广播                     │
│  schemas/    Pydantic v2 模型 = 前后端唯一类型契约（TS 类型由 OpenAPI 生成）│
└────────────────────────────┬──────────────────────────────────────────────┘
                             │ 直接 import（不改算法）
┌────────────────────────────▼──────────────────────────────────────────────┐
│ app/  （现有业务层，仅抽取边界，不改算法）                                 │
│   cad/  engineering/  binding/  takeoff/  boq/  llm/                       │
│   db.py  measure.py  mapping.py  report.py  config.py  models.py          │
└────────────────────────────┬──────────────────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────────────────────┐
│ Data Layer                                                                │
│   SQLite     业务真相源：project/drawing/EO/BOQ/Binding/Review/Job        │
│   Artifacts  大二进制：块几何(.json.gz) · render tiles · 上传原件          │
│   Dataset    只读回归资产：parsed JSON + Parquet + manifest + labels      │
└───────────────────────────────────────────────────────────────────────────┘
```

分层契约（**禁止跨层**）：

| 规则 | 内容 |
|---|---|
| R1 | `routers/` 不得 import `app.db`，必须经 `services/` |
| R2 | `services/` 不得感知 HTTP（`Request`/`Response`），只收发 dataclass / Pydantic 模型 |
| R3 | `app/**` 现有模块**不得** import `web/**`（依赖方向单向） |
| R4 | 浏览器**不得**直接读取 Dataset 目录，一律经 API |
| R5 | 长任务（>2s）一律走 Job + SSE，禁止同步 HTTP 阻塞 |

---

## 4. 架构决策记录（ADR）

两份上游文档在 4 个关键点上直接冲突，此处给出裁决与理由。

### ADR-01 · 前端技术栈：React + TypeScript（采纳实施方案），渲染层 Canvas 2D（采纳 8-28）

| 来源 | 主张 |
|---|---|
| 实施方案 §3 | React + TypeScript + Canvas/WebGL |
| 8-28 §6.2 | 原生 JS ES Modules，零构建，**「不建议直接借贷 React 生态」** |

**裁决**：语言/框架采纳实施方案（React 18 + TS + Vite），**渲染引擎采纳 8-28（Canvas 2D）**，WebGL 延后。

理由：
1. 实施方案 §12 要求 Entity Schema 前后端统一定义，TS 的类型契约 + OpenAPI 代码生成能把这个约束工程化，原生 JS 做不到；
2. 实测单图最大 **79,424 实体**，落在 8-28 §5.3 论证的 Canvas 2D 舒适区（其阈值是 10 万+ 才考虑 WebGL）。过早引入 WebGL 是过度设计；
3. 8-28 反对 React 的核心理由是「零构建、离线可用」，该约束已可通过 Vite build + 静态产物缓解。

**渲染引擎预留抽象**：`RenderBackend` 接口先定义，Canvas2D 为默认实现，WebGL 实例绘制作为可插拔后置实现。

### ADR-02 · 运行时存储：SQLite 唯一可写真相源；Parquet 仅作 Dataset 归档

实施方案 §6 把 Parquet 列为「大量 CAD Entity」的存储。实测实体量 18 万（全量 238 图约 500 万级），SQLite 单表在恰当索引下完全胜任（现 59.6 MB）。

**裁决**：
- **运行时**：SQLite（B3 修复后支持空间查询）。不引入 Parquet 作为在线存储——它会引入另一套读写路径与一致性问题，收益不成立。
- **Dataset**：Parquet 作为**只读归档与离线分析**格式（实施方案 §6 的「Offline Analysis」用途），由导出脚本从 SQLite 生成。
- **交换/调试**：JSON，按实施方案 §11 拆分为 `metadata / layers / blocks / entities` 四个文件。

### ADR-03 · 块几何外置（修复 B2）

`sheet.blocks_json` → `artifacts/blocks/<project_id>/<sheet_id>__blocks__v<n>.json.gz`。

- DB 仅保留 `blocks_path` TEXT + `blocks_sha256` TEXT + `blocks_count` INT；
- 预期效果：`sheet` 表 99.8 MB → <100 KB，DB 总量降至约 70 MB；
- API 侧 `GET /api/sheets/{sid}/blocks` 改为流式返回 gzip 文件，前端按块名惰性索引（不必全量 parse 34 MB）。

### ADR-04 · 空间列 + 视口查询（修复 B3，支撑实施方案 §13）

`entity` 表迁移新增 4 个 REAL 列 + 复合索引；`db.replace_entities` 解析 bbox 字符串后同步写入。

窗口查询 SQL 形态：

```sql
SELECT id, handle, dxf_type, layer, block_name, bbox, length, area, color, geom_json
FROM entity
WHERE sheet_id = ?
  AND max_x >= ? AND min_x <= ?     -- 视口 left / right
  AND max_y >= ? AND min_y <= ?     -- 视口 bottom / top
  AND layer IN (...)                -- 图层过滤
LIMIT ?;
```

两级加载策略（沿用 8-28 §4.3，已验证）：

| 图纸规模 | 策略 |
|---|---|
| ≤ 20,000 实体 | 整图一次下发（gzip 后约 3–8 MB），前端建网格索引做裁剪与拾取，交互零延迟 |
| > 20,000 实体 | 按视口 `?bbox=` 拉取（前端节流 250 ms）；`TEXT/HATCH/标注` 默认延迟加载 |

### ADR-05 · 异步任务：进程内 JobManager + SSE（不引入 Celery/Redis）

实施方案 §30 明确「第一版可继续使用 ProcessPool，不必立即引入 Redis/Celery」。

**裁决**：SSE（而非 8-28 的 WebSocket）。进度推送是**单向**的，SSE 语义更匹配、断线重连由浏览器原生处理、无需额外依赖。

```text
POST /api/jobs  →  {job_id}  （202 Accepted）
GET  /api/jobs/{id}/stream (text/event-stream)  →  progress / done / error
GET  /api/jobs/{id}  →  状态查询（补偿断连）
```

Job 类型：`parse_drawing` / `import_folder` / `generate_candidates` / `embedding_build` / `batch_takeoff` / `recompute_quantity` / `export_report` / `dataset_export`。

并发模型：同步路由用 `def`（FastAPI 自动放线程池，避免阻塞事件循环）；CPU 密集解析走 `anyio.to_thread` 或 ProcessPool；SQLite WAL + `busy_timeout` + 单 worker，沿用现有 thread-local 连接池。

### ADR-06 · 知识口径统一（架构审计 C-08）

`block_legend` 与 `symbol_library` 合并为单一 `knowledge_symbol` 表。takeoff 图例标定与 binding 人工确认**双写同一张表**（架构审计 S-9）。当前 `block_legend` 为 0 行，迁移成本极低。

### ADR-07 · 优先级裁决：数据地基与可核性闸门不是二选一

实施方案 Sprint 顺序把「数据资产」排第一；架构审计 v1.1 第 12 节把「可核性闸门 + 原文件保真回写」重排为 P0（LBH 实战证明：没有可核性判定，739 条不可核条目跑完全流程输出误导性数字；没有原文件保真回写，交付物业主不收）。

**裁决**：二者是**容器与内容**的关系，不是竞争关系：

- Phase 1（数据地基）只做**容器**：目录规范、manifest、schema、导出/校验脚本、回归框架；
- 可核性（S-12/S-13/S-15）与保真回写（S-16）作为**第一批内容**进入 Phase 3，不推迟到 Phase 5；
- 理由：可核性模型本身就是 Business Data 的一张表，地基阶段把表结构预留出来即可，实现排在业务闭环阶段代价最低。

---

## 5. 数据架构（实施方案 §5 三层模型落地）

### 5.1 Canonical Data — 精确层（SQLite + Dataset JSON）

| 实体 | 存储 | 说明 |
|---|---|---|
| `drawing` | SQLite | 图纸元数据：sha256、discipline、**drawing_type**（S-12）、level、zone、revision、scale、parser_version |
| `layer` | SQLite | 图层：`layer_id` + name + color + entity_count + **discipline/system/object 解析结果**（实施方案 §23） |
| `block_ref` | SQLite | 块定义引用：block_name + `blocks_path`（ADR-03）+ insert_count |
| `entity` | SQLite | 见下方 Schema |
| `geometry` | SQLite (`entity.geom_json`) | 类型固定：`line / polyline / lwpolyline / spline / circle / arc / ellipse / hatch / text / insert / point` |
| `measurement` | SQLite (`entity.length/area`) | 解析期预计算，计量期直接取用 |

**Entity Schema 演进**（对照实施方案 §12）：

```jsonc
{
  "schema_version": "cad-1.0",
  "entity_id": 2014789,        // SQLite rowid，运行时稳定
  "handle": "55",              // DWG handle，跨解析稳定，溯源主键
  "type": "LWPOLYLINE",
  "sheet_id": 75,
  "layer_name": "0",           // 现状：字符串。下阶段迁移为 layer_id 引用
  "layer_id": null,            // 【预留】ADR-04 之后建立 layer 表再回填
  "block_id": null,
  "bbox": [28520.0, -2323.43, 41520.0, 5986.57],
  "geometry": { "type": "lwpolyline", "points": [[...]], "closed": true },
  "measurement": { "length": 34310.0, "area": 108030000.0 },
  "attributes": {},            // INSERT 的 ATTRIB（实施方案 §24 标准属性位）
  "source": { "drawing_id": 75, "parser": "ezdwg", "parser_version": "2.x" }
}
```

演进说明：实施方案 §12 要求用 `layer_id` 引用而非重复 `layer_name`。现状 18 万实体直接改名风险过高，采取**两步走**——Phase 1 先建 `layer` 表并回填 `layer_id`，Phase 3 之后再将 `layer_name` 降级为冗余字段。

### 5.2 Render Data — 高性能层（Artifacts 文件系统，可删除可重建）

```text
artifacts/render/<project_id>/<sheet_id>/
├── overview.json          # 全图 bbox、按类型计数、图层摘要（首屏即取）
├── grid_index.json        # 服务端预建的均匀网格索引（可选，>5 万实体时生成）
└── tiles/                 # 【延后】仅当单图 > 10 万实体时启用
    └── <z>/<x>_<y>.bin
```

原则：**原始 CAD 数据为「精确」，Render Data 为「高性能」**（实施方案 §14）。Render 层全部可由 Canonical 重建，标记 `derived` + `cache`，允许任意删除。

MVP 阶段 **不预生成 tiles**——用 ADR-04 的视口查询 + 前端网格索引即可满足 79,424 实体的性能目标（8-28 §5.3 已论证）。

### 5.3 Business Data — 业务层（SQLite）

现有：`project / sheet / entity / boq_item / mapping / engineering_object / binding_candidate / llm_run / project_config / llm_settings / symbol_library`

Phase 3 新增（承接架构审计 S-12~S-20 与实施方案 §21/§36）：

| 表 | 用途 | 来源 |
|---|---|---|
| `drawing_type` | 图纸类型：plan / schematic / detail / legend / schedule | S-12 |
| `takability` | 可核性判定：MEASURABLE / GROUP_ONLY / NOT_MEASURABLE / NO_DRAWING / VERSION_CONFLICT / PROVISIONAL | S-13 |
| `coverage_check` | 覆盖率校验（图纸总量 vs 清单量对账） | S-15 |
| `spec_match` | 规格匹配分级：EXACT / NORMALIZED_EQUAL / COMPATIBLE / UNKNOWN / CONFLICT | 实施方案 §19 |
| `confidence_calibration` | 置信度校准样本与模型参数 | 实施方案 §20 |
| `job` | 异步任务状态与进度 | ADR-05 |
| `knowledge_symbol` | 合并后的统一知识表 | ADR-06 |

### 5.4 存储分工总表

| 介质 | 定位 | 可变性 | 典型内容 |
|---|---|---|---|
| DWG | Original Source | 只读 | 238 份源图 |
| DXF | Derived Conversion Artifact | 可重建 | ODA 转换产物 |
| SQLite | **业务唯一可写真相源** | 读写 | 上表全部 |
| JSON | 交换 / 配置 / Dataset / API | Dataset 只读 | metadata/layers/blocks/entities |
| Parquet | Dataset 归档 / 离线分析 | 只读 | 大量 entity 快照 |
| Artifacts | 大二进制 + Render Cache | 可删除重建 | 块几何 / tiles / 上传原件 |
| Dataset | **回归测试资产，算法运行时禁止覆盖** | 只读（版本递增） | `datasets/lbh/` |

---

## 6. 后端架构

### 6.1 Service 层划分（从现有 `app/` 提取，算法零重写）

| Service | 复用的现有模块 | 职责 |
|---|---|---|
| `DrawingService` | `cad/reader.read_cad_smart`、`cad/cad_parser`、`cad/dwg`、`cad/parse_cache`、`import_folder` | 导入、解析、重解析、图纸 CRUD、块几何外置 |
| `GeometryService` | `db.get_entities` + ADR-04 空间查询 | 视口查询、实体详情、图层/块统计、LOD 分级 |
| `EoService` | `engineering/extractor`、`engineering/classifier`、`engineering/specification`、`engineering/llm_classify` | 工程对象提取与规格推断 |
| `BoqService` | `boq/boq_parser` | BOQ 导入（含 B1 修复）、CRUD、重解析 |
| `BindingService` | `binding/matcher.generate_candidates`、`candidate_aggregator`、`rule_matcher`、`embedding_matcher`、`llm_matcher` | 候选生成（见 6.2） |
| `ReviewService` | `binding/reviewer.confirm_binding / reject_binding / auto_confirm_rule_candidates` | **唯一生效通道**；正负样本沉淀 |
| `QuantityService` | `measure.compute_item`、`mapping`、`takeoff/aggregate`、`takeoff/quality` | 确定性计量 + 覆盖率 |
| `TakabilityService` | 新增 | 图纸类型 + 可核性闸门 + 覆盖率 + 粒度对齐（S-12~S-15） |
| `AiService` | `llm/runner`、`llm/embeddings`、`llm/audit`、`takeoff/llm_backends` | LLM/Embedding 统一出口；`llm_run` 全量审计；超时重试与 fallback |
| `CalibrationService` | 新增 | 综合置信度（实施方案 §20）；先用规则加权，样本足够后上 Isotonic Regression |
| `StandardProfileService` | 新增 | `cad_standard/layer_rules.json` 等 5 份规则集（实施方案 §26） |
| `ReportService` | `report.export_*`、`boq/writeback` | 导出 + **原文件保真回写**（S-16，openpyxl 保留公式/合并格） |
| `DatasetService` | 新增 | Dataset 导出、manifest 生成、完整性校验（实施方案 §8/§36） |

### 6.2 候选生成管线（实施方案 §18，修复架构审计 C-01 硬截断）

现状：`embedding TOP-15` + `rule MAX-5`，LLM 只在子集内精排，召回被过早截断。

目标形态：

```text
Historical（_accepted_block_boq 历史确认）
  ∪ Rule
  ∪ Embedding
  ∪ Lexical
      ↓ 去重 + 负样本抑制（_rejected_pairs）
      ↓ Top 20（从 15 放宽）
      ↓ LLM 精排 → Top 5
      ↓ PENDING 候选写 binding_candidate
      ↓ 人工确认（ReviewService）→ mapping + knowledge_symbol
```

硬约束（实施方案 §36）：
- AI 只能生成 `PENDING`；
- 人工确认后才写正式 `mapping`；
- Reject 必须形成负样本并回灌抑制；
- 规格 CONFLICT 强制 `needs_review = true`，**LLM 的文字理由不得覆盖硬冲突**。

### 6.3 目录结构

```text
web/
├── server.py                 # FastAPI 入口：GZip、CORS、静态、路由挂载、lifespan
├── deps.py                   # 依赖注入（get_db / get_current_project）
├── jobs/
│   ├── manager.py            # JobManager：提交/取消/进度/事件队列
│   └── tasks.py              # 各 Job 类型实现（调 Service）
├── routers/
│   ├── projects.py  drawings.py  geometry.py  boq.py
│   ├── bindings.py  review.py  quantity.py  takability.py
│   ├── legend.py    takeoff.py report.py    llm_settings.py
│   ├── datasets.py  jobs.py
├── services/                 # 见 6.1，每个 Service 一个文件
├── schemas/                  # Pydantic v2 模型（TS 类型由 OpenAPI 生成）
├── static/                   # Vite build 产物（gitignored）
└── start_web.bat

web-frontend/                 # React + TS 源码
├── src/
│   ├── api/                  # generated client（openapi-typescript）+ hooks
│   ├── cad/
│   │   ├── RenderBackend.ts  # 抽象（ADR-01）
│   │   ├── Canvas2DBackend.ts
│   │   ├── SpatialGrid.ts    # 前端网格索引（裁剪 + 拾取）
│   │   ├── Viewport.ts       # 变换矩阵、缩放/平移、LOD 阈值
│   │   └── drawEntity.ts     # 逐类型绘制（对照 app/ui/canvas.py build_geom_item）
│   ├── panels/               # 图纸/预检/标定/映射/AI绑定/计量/报告
│   ├── store/                # Zustand：选择集、可见图层、视图态
│   └── App.tsx
└── vite.config.ts            # proxy /api → localhost:8521
```

### 6.4 API 契约（合并实施方案 §13 与 8-28 §4.2）

| 方法 | 路径 | Service |
|---|---|---|
| GET/POST | `/api/projects`、`/api/projects/{pid}` | DrawingService |
| GET | `/api/projects/{pid}/drawings` | DrawingService |
| POST | `/api/projects/{pid}/drawings/upload`（多文件）→ Job | DrawingService |
| GET | `/api/drawings/{sid}`、`/metadata`、`/layers`、`/blocks`、`/overview` | GeometryService |
| GET | `/api/drawings/{sid}/viewport?bbox=&layers=&types=&limit=` | GeometryService |
| GET | `/api/entities/{eid}` | GeometryService |
| POST/GET/PATCH | `/api/projects/{pid}/boq` | BoqService |
| GET/POST/DELETE | `/api/projects/{pid}/mappings` | QuantityService |
| GET | `/api/boq/{iid}/measure?sheet=` | QuantityService |
| POST | `/api/projects/{pid}/binding/candidates` → Job | BindingService |
| GET | `/api/projects/{pid}/binding/candidates?status=` | BindingService |
| POST | `/api/candidates/{cid}/confirm` \| `/reject` | ReviewService |
| POST | `/api/projects/{pid}/review/batch-confirm` | ReviewService |
| GET/POST | `/api/projects/{pid}/takability` | TakabilityService |
| GET/POST | `/api/projects/{pid}/knowledge` | ReviewService + ADR-06 |
| POST | `/api/projects/{pid}/takeoff` → Job | QuantityService |
| GET | `/api/projects/{pid}/report.xlsx`、`/writeback.xlsx` | ReportService |
| GET/POST | `/api/datasets/{dsid}/export` \| `/validate` | DatasetService |
| GET/PUT | `/api/llm-settings` | AiService |
| POST/GET | `/api/jobs`、`/api/jobs/{id}`、`/api/jobs/{id}/stream` | JobManager |

统一约定：JSON `ensure_ascii=False`；大响应启用 GZip；错误统一 `{detail, code, trace_id}`。

---

## 7. 前端架构

### 7.1 布局（实施方案 §27）

```text
┌────────────────────────────────────────────────────────────┐
│ 项目 ▾ | 打开 | 保存 | 更多                                 │
├────────────────────────────────────────────────────────────┤
│ 图纸 | 预检 | 标定 | 映射 | AI绑定 | 计量 | 报告 | 更多      │
├──────────┬──────────────────────────────┬──────────────────┤
│ 图纸/图层 │        CAD Canvas            │ 当前任务面板      │
│ 块树/搜索 │                              │ BOQ / 绑定 / 属性 │
├──────────┴──────────────────────────────┴──────────────────┤
│ 当前图纸 | 当前模式 | 实体数 | 可核率 | BOQ | 状态            │
└────────────────────────────────────────────────────────────┘
```

约束：CAD Canvas 始终保持主体空间；一级导航固定不折叠；低频功能进「更多」。

### 7.2 渲染管线（对照 `app/ui/canvas.py` 逐函数翻译）

| 桌面函数 | Web 实现 |
|---|---|
| `to_scene()`（Y 翻转） | `world→screen` 变换矩阵 |
| `build_geom_item()` | `drawEntity()`：`line / polyline / lwpolyline / spline / circle / arc(2° 采样) / ellipse / hatch / text / insert / point` |
| `_collect_block` + `make_block_group()` | `drawInsert()`：读 `blocks_path` 几何 → 旋转/缩放/平移 → 派发绘制 |
| `zoom_fit / zoom_step / 锚点平移` | `setTransform` + 光标中心缩放 |
| `entities_from_rect()` / `entity_at()` | `SpatialGrid` 网格索引裁剪与命中 |
| `_update_lod` | PPU 阈值切换抗锯齿与简化绘制 |
| `highlight / flash / show_tag` | 目标高亮 + 其余 opacity 0.22 + 绝对定位 DOM 浮标签 |

### 7.3 状态模型

| 类别 | 方案 | 内容 |
|---|---|---|
| 服务端态 | TanStack Query | 项目/图纸/图层/BOQ/候选/计量结果；缓存失效与 Job 完成事件联动 |
| 视图态 | Zustand | 视口变换、选择集、可见图层/类型、当前模式 |
| 实时 | SSE | Job 进度；绑定候选数变化 |

### 7.4 性能预算（对照实施方案 §36 验收）

| 指标 | 目标 |
|---|---|
| 首屏 overview | < 800 ms |
| 小图（≤2 万实体）整图可交互 | < 2 s |
| 大图（7.9 万实体）视口拉取→渲染 | < 500 ms（节流 250 ms） |
| 平移/缩放帧率 | ≥ 30 fps |
| 分辨率 | 1280×720 / 1920×1080 / 2560×1440 均可用 |

---

## 8. 数据集与回归测试架构（实施方案 §7–§9）

### 8.1 目录

```text
datasets/
└── lbh/
    ├── README.md
    ├── manifest.json
    ├── source/dwg/                      # 原始 DWG（软链接或受控副本，见待确认 B1）
    ├── converted/dxf/<version>/         # ODA 转换产物（derived）
    ├── parsed/
    │   ├── json/<parser_version>/<drawing_id>/
    │   │   ├── metadata.json
    │   │   ├── layers.json
    │   │   ├── blocks.json
    │   │   └── entities.json
    │   └── parquet/<parser_version>/<drawing_id>.parquet
    ├── render/<drawing_id>/
    ├── boq/
    ├── labels/
    │   ├── engineering_objects/  bindings/  rejected_bindings/
    │   └── takability/  drawing_types/  specifications/
    ├── expected/quantities/             # 【阻塞】需业主认可基线，见待确认 B7
    └── snapshots/
```

### 8.2 Manifest（在实施方案 §8 基础上补充解析环境字段）

```jsonc
{
  "dataset_id": "LBH-2026-08",
  "project": "Euesperides Medical Hospital",
  "schema_version": "cad-1.0",
  "parser_version": "2.x",
  "source_revision": "R4",
  "generated_at": "2026-08-29T19:00:00+02:00",
  // ↓ 新增：解析结果强依赖后端与库版本，缺失则回归不可复现
  "parser_backend": "ezdwg",          // ezdwg | ezdxf | oda
  "backend_version": "x.y.z",
  "drawings": [{
    "drawing_id": "LBH-E-101",
    "filename": "E-101.dwg",
    "sha256": "...",
    "discipline": "Electrical",
    "drawing_type": "plan",
    "floor": "L01",
    "revision": "R4",
    "entity_count": 41511,
    "json_path": "parsed/json/v2/LBH-E-101/",
    "parquet_path": "parsed/parquet/v2/LBH-E-101.parquet"
  }]
}
```

### 8.3 命名与不可变原则

- 命名：`<project_id>__<drawing_id>__<artifact>__v<version>.<ext>`（`LBH__E-101__entities__v2.json`）；禁止 `final/new/latest/test.*`；
- **Parser 版本分目录**（`parsed/v2/`、`parsed/v3/`），禁止覆盖；
- 人工标定属新增 Label 版本，可追加不可覆盖；
- Dataset 目录挂只读校验：`DatasetService.validate()` 校验 manifest ↔ 文件 sha256 ↔ entity_count 三者一致。

### 8.4 回归测试分层

| 层 | 内容 | 触发 |
|---|---|---|
| L1 Schema | JSON/Parquet 结构校验、manifest 完整性 | 每次导出 |
| L2 Parser | 同一 DWG 跨 parser 版本对比：实体数、图层数、总长/总面积偏差阈值 | Parser 升级 |
| L3 Binding | 用 `labels/` 正负样本跑候选生成，断言 Top1 命中率与负样本抑制率 | 算法变更 |
| L4 Quantity | Count/Length/Area 确定性引擎结果与 `expected/quantities/` 对比 | 计量引擎变更 |

---

## 9. 演进路线

Phase 0 为本次新增（B1–B4 阻塞项），其余在实施方案 Sprint 1–6 基础上按 ADR-07 重排优先级。

| 阶段 | 内容 | 出口标准 |
|---|---|---|
| **Phase 0 · 地基修复** | B1 BOQ 解析修正；B2 块几何外置；B3 空间列迁移；B4 备份清理 + 备份策略 | DB < 80 MB；BOQ 480 条 description/unit/qty 正确；`?bbox=` 查询 P95 < 50 ms |
| **Phase 1 · 数据资产**（Sprint 1） | `datasets/lbh/` 目录；从 SQLite 反向导出 + 从 DWG 重解析；manifest；JSON Schema；Dataset Validator；L1/L2 回归 | `validate()` 通过；同一图纸两次导出 sha256 一致；Dataset 不被运行时覆盖 |
| **Phase 2 · Web 数据层**（Sprint 2） | FastAPI 骨架；Job + SSE；Drawing/Layer/Block/Entity/Viewport API；OpenAPI → TS 类型 | 浏览器可取到 7.9 万实体图纸的视口数据；Job 进度可见 |
| **Phase 3 · CAD Viewer**（Sprint 3） | React 三栏壳；Canvas 2D 渲染器；LOD/网格索引；拾取/框选/图层过滤/属性面板 | 大图不全量加载；7.9 万实体平移 ≥30 fps；实施方案 §36 Web 验收项全过 |
| **Phase 4 · 业务闭环**（Sprint 4 + S-12/13/15/16） | BOQ 映射（点/框/整层/整块）；确定性计量与溯源；**图纸类型 + 可核性闸门 + 覆盖率**；**原文件保真回写** | 完成一次「拾取→分配→出量→写回原清单」闭环；不可核条目不输出伪精确数字 |
| **Phase 5 · AI**（Sprint 5） | Candidate Union（Top20→LLM Top5）；Embedding；人工审核工作台；正负样本；置信度校准 | AI 只出 PENDING；Reject 成负样本；规格冲突强制 review |
| **Phase 6 · 工程化**（Sprint 6） | 版本冲突检测；跨专业索引与重复计价；跨图去重；组级降级计量；StandardProfile | 覆盖率/冲突/版本三类闸门上线；L3/L4 回归全绿 |

**Phase 0 + 1 + 2 完成即价值显现**（数据地基可复现 + 浏览器可取数）。Phase 3 渲染器是最大风险项，建议先用小图（sheet 73，1.2 万实体）验证，再上 7.9 万实体。

---

## 10. 待确认清单（条件不足，需补充）

### A 类 · 必须决策（阻塞架构定稿）

| # | 决策点 | 选项 | 我的建议 |
|---|---|---|---|
| **A1** | **前端技术栈**：实施方案要 React+TS，8-28 文档要原生 JS 零构建 | (a) React + TS + Vite（实施方案）<br>(b) 原生 JS ES Modules（8-28）<br>(c) Vue 3 无构建 | **(a)**。需 TypeScript 承接 Entity Schema 契约；8-28 反对 React 的理由（零构建）可用 build 产物缓解。已按此假设完成 ADR-01 |
| **A2** | **桌面版去留**：8-28 主张双端共存，实施方案说「逐步迁移」 | (a) 双端共存，共享 SQLite<br>(b) 桌面版冻结，只修 bug<br>(c) 桌面版废弃 | **(b)**。两套 UI 长期维护成本高；但 `app/ui/*` 暂不删除，作为渲染器翻译参照。需确认桌面版是否有存量用户 |
| **A3** | **Dataset 规模**：现有仅 4 张电气图已解析 | (a) 仅现有 4 图（18 万实体，约 30 min）<br>(b) 全量 238 份解析（约 500 万+ 实体，数小时 + 数 GB）<br>(c) 抽样：每专业取 5–10 张代表图 | **(c)**。回归数据集要的是「覆盖各类图纸形态」而非「全量」；全量解析更适合作为 Phase 6 的性能测试集另行处理 |
| **A4** | **Parquet 定位** | (a) 运行时存储（实施方案 §6 字面）<br>(b) 仅 Dataset 归档/离线分析 | **(b)**。18 万实体规模 SQLite 足够（现 59.6 MB），引入 Parquet 作为在线存储会多出一套一致性问题，收益不成立 |
| **A5** | **优先级**：数据地基（实施方案 Sprint 1）vs 可核闸门（架构审计 P0） | (a) 地基优先，可核性排 Phase 5<br>(b) 地基做容器、可核性排 Phase 3（ADR-07） | **(b)**。LBH 实战已证明无可核性判定会输出误导性数字，拖到 Phase 5 风险太大 |

### B 类 · 缺信息（需提供）

| # | 缺失项 | 为什么需要 | 补充形式 |
|---|---|---|---|
| **B1** | **DWG 源文件能否纳入 `datasets/`** | 238 份 / 25 MB 属客户资产，可能涉保密；实施方案 §7 要求 `source/dwg/` | 明确：可复制 / 仅软链接引用 / 禁止入库 |
| **B2** | **BOQ Excel 的正确表头结构** | B1 阻塞项修复的直接依据（现 `description='None'` 全错） | 表头所在行号 + 各列含义，或一份人工确认的正确解析样例（20–30 条即可） |
| **B3** | **部署形态** | 决定要不要认证、多租户、PostgreSQL 替代 SQLite | 单机 localhost / 局域网多人 / 服务器部署 |
| **B4** | **是否需要用户认证与多用户协作** | 现状无认证概念；多人同时确认绑定会产生写冲突 | 需要 / 不需要（若需要，补：同时在线人数、角色划分） |
| **B5** | **`docs/` 被 `.gitignore:11` 忽略，新旧文档待遇不一致** | 实测：早期文档（`BACKLOG.md`、`WEB_PLATFORM_ARCHITECTURE_2026-08-28.md` 等）已被 git 跟踪；但**此后新建的文档一律不进版本控制**（`git check-ignore` 已确认本文件被忽略）。架构决策文档丢失无法恢复 | 确认是否从 `.gitignore` 移除 `docs/`（或对 `docs/` 保留 `docs/archive/` 的忽略规则） |
| **B6** | **LLM 后端实际可用性** | 现有 `llm_settings` 配了 5 个后端 + fallback；实施方案 §3 提到 Ollama | 当前可用的是本地 Ollama 还是云端 API？模型名？有无 Token 预算约束？ |
| **B7** | **期望工程量基线（Golden Answer）** | 实施方案 §7 的 `expected/quantities/` 与 L4 回归都需要；无基线则回归只能做「自身一致性」而非「正确性」 | 业主认可的核对结果 / 手工算量样本 / 历史结算量（任一种，条目数不限） |
| **B8** | **图纸类型与可核性的判定规则来源** | S-12/S-13 的实现需要规则；架构审计 §16.1 有 LBH 经验阈值，但是否可直接作为通用规则 | 确认可沿用 LBH 经验阈值，或提供设计院通用的判定标准 |

### C 类 · 建议确认（不阻塞定稿，影响细节设计）

| # | 事项 | 说明 |
|---|---|---|
| C1 | 界面语言 | LBH 为海外项目，是否需英文界面 / 中英切换 |
| C2 | 分辨率上限 | 实施方案 §36 只到 2560×1440，是否需支持 4K |
| C3 | 移动端/平板支持 | 工地现场是否有移动端查看需求（影响 Canvas 交互设计与布局响应式策略） |
| C4 | 主题 | 沿用 8-28 的 light/dark 双主题，还是只做单主题 |
| C5 | 现有 392 条候选的处理 | 359 条 SUPERSEDED 是否保留作为负样本训练集，还是清理 |

---

## 11. 风险登记

| 风险 | 等级 | 对策 |
|---|---|---|
| 渲染器重写（约 40% 前端工作量） | 高 | 逐函数对照 `app/ui/canvas.py` 翻译；先用 1.2 万实体小图验证，再上大图；几何 schema 不改 |
| BOQ 解析修复后需重新生成全部绑定 | 高 | Phase 0 完成前不启动 Phase 5；B2 信息到位后一次性重解析 |
| 大图性能不达标 | 中 | ADR-04 空间列 + 视口加载 + 延迟类型；`scripts/bench_perf.py` 已有基准可回放；>10 万实体再上 tiles/WebGL |
| 桌面版与 Web 版数据争用 | 中 | 单进程单 worker + WAL + `busy_timeout`；A2 建议桌面版冻结以降低并发写 |
| LLM 调用不稳定 | 中 | 全部走 Job + SSE；沿用现有重试（≤2）与多后端 fallback；`llm_run` 全量审计可回溯 |
| 置信度校准样本不足 | 低 | 现状仅 1 ACCEPTED / 32 PENDING，样本过少；Phase 5 前需积累，先用规则加权兜底 |
| Dataset 与运行时数据不一致 | 中 | `DatasetService.validate()` 做 manifest ↔ sha256 ↔ count 三方校验，纳入 CI |
