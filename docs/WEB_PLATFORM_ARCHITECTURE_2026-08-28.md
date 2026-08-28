# cad-boq-tool Web 化（浏览器前端 + 独立后端服务）可行方案

| 项目 | 内容 |
|---|---|
| 日期 | 2026-08-28 |
| 性质 | 交互层 Web 化：桌面 PySide6 → 浏览器；后端 Uvicorn/FastAPI 独立运行 |
| 核心原则 | **业务逻辑 100% 复用，只重写展示层与渲染层**；桌面版保留，双端共存 |
| 界面蓝本 | `design/main.html`（v3 原型：深色顶栏 / 左资源树 / 中画布 / 右 rail 面板）已定稿 |

---

## 1. 现状盘点（哪些能直接复用）

代码分层清晰，业务层完全不依赖 Qt，这是 Web 化可行的前提：

| 层 | 现有模块 | Web 化处理 |
|---|---|---|
| 业务逻辑（**零重写**） | `app/db.py`、`app/cad/*`、`app/engineering/*`、`app/binding/*`、`app/takeoff/*`、`app/boq/*`、`app/measure.py`、`app/mapping.py`、`app/report.py`、`app/llm/*`、`app/import_folder.py` | FastAPI 路由直接 import 调用 |
| 数据层 | SQLite `~/.cad-boq-tool/projects.db`（WAL，thread-local 连接池） | 原样保留；FastAPI 线程模型天然兼容 |
| DWG 处理 | `app/cad/reader.py`（ezdwg 直读/ezdxf）+ `app/cad/dwg.py`（ODA 回退） | 后端服务同一台机运行，原封不动 |
| 展示层 | `app/ui/*`（PySide6 控件） | 重写为 Web 前端（工作量中等） |
| 渲染层 | `app/ui/canvas.py`（QGraphicsView） | 重写为 HTML5 Canvas 2D 渲染器（工作量最大） |
| 界面视觉 | `design/main.html`（Tailwind + Iconify 原型） | **直接作为 Web 界面布局/风格蓝本** |

关键利好：

1. **几何契约已固定**。CAD 解析产出 `entity.geom_json`（JSON dict），类型为 `line / polyline / lwpolyline / spline / circle / arc / ellipse / hatch / text / insert / point`，`length / area / bbox / color` 已入库。Web 端渲染器消费**相同 schema**，只需把 `canvas.py` 的 `build_geom_item()` 逐类型"翻译"成 Canvas 2D 绘制即可。
2. **块渲染免展开**：块定义几何已缓存于 `sheet.blocks_json`（块名 → `[geom...]`），INSERT 渲染直接下发块几何，无需在浏览器做块展开。
3. **AI 管线行为完全可复用**：绑定候选（规则→语义→LLM 分层）、图例标定、AI 算量、`llm_run` 审计、人工确认写 `mapping` / 写回调 `symbol_library` 知识库——这些都在 `app/binding/reviewer.py`、`app/takeoff/orchestrator.py` 里，后端 API 一调即得，Web 端只负责"点确认/点拒绝"。

---

## 2. 目标架构

```text
浏览器 (http://localhost:8520)
 ┌──────────────────────┬─────────────────────────┬──────────────────────┐
 │ 左：项目/图纸/图层树   │  中：CAD 画布(Canvas 2D) │  右：rail + 面板     │
 │  图纸卡片行           │   网格底纹/缩放/平移       │ 绑定工作台/BOQ清单/  │
 │  图层 checkbox 显隐   │   拾取/框选/定位高亮       │ 实体属性/操作记录    │
 │  块树 高亮            │   INSERT 块渲染           │ 图例标定/AI结果       │
 │  (main.html 1:1)     │   floating tag           │  (main.html 1:1)     │
 └──────────────────────┴─────────────────────────┴──────────────────────┘
        │  REST (fetch)            ▲  WebSocket（解析/AI 进度、job 状态）
        ▼                          │
 ┌──────────────────────────────────────────────────────────────────────┐
 │  FastAPI 后端 (uvicorn, localhost:8521) — server.py + routers        │
 │                                                                      │
 │  项目/图纸  │  几何(分块) │  BOQ  │  Mapping/计量 │  图例 │  绑定工作台  │
 │  /projects  │  /sheets/…  │ /boq  │  /mappings    │ /legend│ /bindings  │
 │  /upload    │  /geometry  │ /upload │ /measure   │       │ /candidates │
 │  (多部件)   │  ?bbox=…    │       │              │       │ /takeoff    │
 │                                                                      │
 │  [Job Manager] 解析/转换/批量算量 后台线程 + 广播进度 → /ws/jobs       │
 │                                                                      │
 │  复用（零重写）：db / cad(ezdwg·ezdxf·ODA) / boq_parser / mapping /   │
 │  measure / report / binding(reviewer) / takeoff(orchestrator) / llm  │
 └──────────────────────────────────────────────────────────────────────┘
```

后端与前端打包进一个 `web/` 目录，桌面版（`main.py`）保持不动。新增 `start_web.bat` 双击启动。

---

## 3. 工作流程（桌面版 → Web 版一一对应）

### 3.1 全流程总览（用户视角）

```
新建项目 → 打开图纸(DWG/DXF/文件夹) → 导入 BOQ Excel
  → [可选] AI 算量（单图/批量，后台 job + 进度条）
  → 绑定工作台：审核 AI 候选 / 确认 / 拒绝 / 批量确认
  → 画布拾取映射：点选/框选/图层整层/块整块 四种模式
  → 图例标定（块语义 + LLM 辅助）
  → 导出 Excel 算量报告（下载）
```

### 3.2 桌面交互 → Web 交互映射

| 桌面版 | Web 版 | 后端接口 |
|---|---|---|
| 新建项目对话框 | 顶栏项目下拉 + 新建 | `POST /api/projects` |
| 打开图纸（DWG/DXF/文件夹） | 文件上传（多选）→ 上传即后台解析 | `POST /api/projects/{id}/sheets/upload` + `GET /api/jobs/{id}` |
| 导入 BOQ Excel | 上传 Excel → 后端 `boq_parser` 解析入库 | `POST /api/projects/{id}/boq/upload` |
| BOQ 表格（改规则/比例） | 右侧 BOQ 面板表格（可编辑） | `GET/PATCH /apids.api/boq/{id}` |
| 画布缩放 Ctrl+滚轮/平移中键 | 滚轮缩放（光标锚点）/中键或空格平移 | 纯前端（渲染器） |
| 双击点选实体 | 双击拾取 | 前端拾取 → `POST /api/mappings` |
| Shift+左键拖拽框选 | Shift+拖拽矩形选择 | 同上 |
| 右键图层树批量关联 | 左树图层 checkbox / 右键菜单"整层关联" | `POST /api/mappings` (mode=layer) |
| 右键块树批量关联 | 左树图层树 checkbox 用 | `POST /api/mappings` (mode=block) |
| 图层显隐 / 类型显隐 | 左树 checkbox / 画布工具条类型开关 | 纯前端（本地过滤） |
| 定位高亮（含房址浮标签） | 同（目标高亮+其余变暗+虚线框+浮标签） | `GET /api/entities/{ids}` → 渲染器 |
| 绑定工作台（候选/确认/拒绝/批量） | 右侧工作台（rail 第 1 图标） | `GET /api/candidates` `POST /api/candidates/{id}/confirm・reject` |
| 图例标定表格（LLM 辅助） | 右侧图例面板 | `GET/POST /api/legend` + `POST /api/projects/{id}/legend/llm` |
| AI 算量对话框（进度/结果） | 右上 AI 算量下拉 + WebSocket 进度 + 结果弹层 | `POST /api/projects/{id}/takeoff` + `WS /ws/jobs` |
| 导出 Excel | 「导出」 → 浏览器下载 | `GET /api/projects/{id}/report.xlsx` |
| LLN 设置弹窗（5 后端） | 右键设置弹层 | `GET/PUT /api/llm-settings` |

### 3.3 长任务（解析、LLM、批量）的 Web 化处理

桌面是"同步调用 + 进度回调"；Web 必须变异步 job：

- 统一 **Job Manager**：`POST` 创建 job → 返回 `job_id` → 后端 `asyncio.to_thread` 跑真实工作（CPU 密集，GIL 线程池即可，与桌面同构）→ 进度经 `WebSocket /ws/jobs` 推给前端（`parse_dxf` 的 `progress_callback`、`orchestrator` 的 6 阶段 `PHASE_*`、文件夹批量的 N 张）→ `GET /api/jobs/{id}` 可轮询兜底。
- 文件上传：DWG/DXF 可达几十 MB，前端 `fetch` 孟 multipart；解析入口与桌面版共用 `parse_cache`（`~/.cad-boq-toool` 下），重复打开同一张图不重解析。

---

## 4. 数据传输方案（重点）

### 4.1 传输协议与总体原则

- **REST（fetch）**：所有查询/增删改；JSON，中文 `ensure_ascii=False`。
- **WebSocket**：仅 job 进度 + 事件（计算重新同步候选数）。
- **文件下载**：报告/导出 → GET 流式返回 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`。
- **压缩**：几何大响应启用 gzip（FastAPI `GZipMiddleware`，大图尤其见效）。

### 4.2 API 设计（对照现有 db 函数，几乎一一映射）

| 方法 | 路径 | 后端调用的现有模块 |
|---|---|---|
| GET | `/api/projects` | `db.list_projects` |
| POST | `/api/projects {name}` | `db.create_project` |
| GET/PATCH/DELETE | `/api/projects/{id}` | `db.get_project/rename/delete_project` |
| POST | `/api/projects/{id}/sheets/upload`（多个 DWG/DXF,<多选择器>） | `app.cad.reader.read_cad` → `cad_parser.parse_dxf` → `db.add_sheet` + `replace_entities`（后台 job） |
| GET | `/api/projects/{id}/sheets` | `db.get_sheets` |
| DELETE | `/api/sheets/{sid}` | `db.delete_sheet` |
| GET | `/api/sheets/{sid}/meta`（图层/块/计数） | `db.distinct_layers` + `layer_color_map` + `distinct_blocks` |
| GET | `/api/sheets/{sid}/geometry?bbox=x0,y0,x1,y1&layers=&types=&limit=` | `db.get_entities` + **新增 R*Tree 窗口查询**（见 4.3） |
| GET | `/api/sheets/{sid}/blocks` | `sheet.blocks_json` 一次返回 |
| POST | `/api/projects/{id}/boq/upload`（Excel） | `boq.boq_parser` → `db.replace_boq_items` / `append_boq_items` |
| GET | `/api/projects/{id}/boq` | `db.get_boq_items` |
| PATCH | `/api/boq/{id} {rule_type,scale_factor,unit,…}` | `db.update_boq_item` |
| POST | `/api/projects/{id}/mappings {mode,sheet_id,entity_ids\|layer\|block}` | `mapping.add_*mapping`（layer/block/entity 三模式与桌面同函数） |
| GET | `/api/boq/{id}/measure?sheet=` | `measure.compute_item` |
| GET/PATCH/POST/DELETE | `/api/projects/{id}/legend` | `db.get_block_legend / save_block_legend / set_block_confirmed` |
| POST | `/api/projects/{id}/legend/llm` | 工作台 `block_legend` LLM 标定（job） |
| GET | `/api/projects/{id}/binding/candidates?status=` | `db.get_pending_candidates / get_candidates` |
| POST | `/api/candidates/{cid}/confirm` | `reviewer.confirm_binding`（→ mapping + 知识库 + 重算） |
| POST | `/api/candidates/{cid}/reject` | `reviewer.reject_binding` |
| POST | `/api/projects/{id}/binding/batch-confirm` | `reviewer.auto_confirm_rule_candidates` |
| POST | `/api/projects/{id}/takeoff {single\|folder}` | `takeoff.orchestrator.takeoff_pipeline` / `folder_pipeline`（job） |
| GET | `/api/projects/{id}/report.xlsx` | `report.export_report` |
| GET/PUT | `/api/ui/llm-settings` | `db.get_llm_settings / set_llm_settings`（5 后端 + fallback） |

### 4.3 几何下发策略（大图性能关键）

桌面版在 `canvas.py` 已处理大数据：
- `entity` 表每行存 `bbox`（JSON string），**不便于 SQL 贪心查询**。
- 桌面端整图 `get_entities` 载入后靠 Qt `QGraphicsScene` 的 BspTree 索引裁剪。

**Web 端方案（确定性、可增量实现）：**
1. **数据库加空间列**：解析入库时（`db.replace_entities`）写 `min_x/min_y/max_x/max_y` 四列 + 复合索引 `(sheet_id, min_x, max_x, min_r, max_y)`。窗口查询：`WHERE sheet_id=? AND max_x>=left AND min_x<=right AND …`。数值列查询远比 JSON 解析快。**迁移成本极低**：`_migrate` 模式同 `blocks_json`（部分旧行重建时补）。
2. **两级加载策略**（把桌面 `_DEFERRED_THRESHOLD=15000` 与 Qt 裁剪对齐）：
   - **小图（≤ 20k 实体）**：整图一次性下发（gzip 后约 3-8MB JSON），渲染器全部绘制 + 浏览器本地统一网格索引做裁剪与拾取。交互零延迟。
   - **大图（> 20k）**：前端按视口窗口 `?bbox=` 分块拉取（节流 250ms），渲染器用**空间网格索引**只画视口内实体；`TEXT/HATCH/标注` 沿用桌面**延迟加载**策略（默认不做，勾选类型开关时按需拉取）。
3. 几何 JSON schema 与桌面**完全一致**（`line/polyline/…/insert`），渲染器直接映射。

---

## 5. CAD 渲染方案（核心工程）

### 5.1 渲染器设计（renderer.js）

将 `app/ui/canvas.py` 逐函数翻译为浏览器 Canvas 2D：

| 桌面函数 | Web 对应 |
|---|---|
| `to_scene()`（Y 翻转） | `world→screen` 变换矩阵（同样 Y 轴取反） |
| `build_geom_item()` | `drawEntity(ctx, entity)` 按 `geom.type` 分支：line / polyline / spline / circle(整圆) / / arc(2°采样折线) / ellipse(参数化采样) / hatch(闭合边界填充) / text(fillText) |
| `_collect_block`+`make_block_group()` | `drawInsert()`：用返回的 `blocks_json` 几何 做旋转+缩放+平移变换，再派发到各绘制函数 |
| `zoom_step/zoom_fit/zoom_actual` + 锚点平移 | `setTransform + translate/scale`；滚轮以光标为中心 |
| `entities_from_rect()` | 网格索引 + `跨矩形`判断（只有主网格内的实体数） |
| `entity_at()` | 网格索引 + 逐一近邻命中判定 |
| `set_layer_visible/set_type_visible` | 前端维护 层/类型 → 可见集（重绘前过滤） |
| `isolate_layer/restore_layers` | 透明度滤镜（同质 64→255） |
| `highlight_entities/flash/show_tag` | 目标高亮 + 其余 opacity 0.22 + 虚线框；闪烁动画；`position:absolute` DOM 浮标签（不受画布缩放影响，等价 `ItemIgnoresTransformations`） |
| LOD（`_update_lod`：概览关 AA） | 视域 PPU 阈值切换 `antialias` / 简化绘制 |
| 主题切换 light/dark | CSS 变量动态切换（配 `theme.py` 已定义的色板常量） |

### 5.2 交互状态机（与桌面宝典一致）

- **模式**：拾取 / 框选（Shift+拖拽）/ 平移（中键/空格+拖拽）；缩放历史（前进/后退）；「整图」「实际大小」。
- **状态着色**：默认色 → 悬停（同 `hover`）→ 选中/待分配（`pending`）→ **已映射（`mapped` 青）**。但不同于桌面：
  - 桌面对"已映射实体着色"需要项数据，Web 端直接从 `GET /api/mappings` 得到映射集合（`{sheet_id, entity_ids}`），前端把已映射实体 id 列表并入渲染状态——与 `main.html` 的"已映射设备"图例配色呼应。

### 5.3 大图性能模型

| 场景 | 机制 | 与桌面对比 |
|---|---|---|
| 6 万实体平移 | 视口窗口拉取 + 网格索引裁剪 | 略优于桌面（增量加载） |
| 缩→fit 全图 | `bbox` 全图一次性拉取（30k+）后按 LOD 简化 | 桌面全量建模 BMP 索引相差不大 |
| 文字/填充 | 默认不渲染（延迟类型） | 与桌面 `_DEFERRED_TYPES` 一致 |
| 高亮/闪烁 | 只对目标实体做状态重绘 | 同上 |
| 极端（超大图，百万实体） | 阶段后满可选：服务端预切片 → WebGL(regl) 实例化导线绘制 | 仅当 10 万+ 再考虑 |

**结论：Canvas 2D + 空间网格是标定。** 不需要 WebGL 起步，MVP 阶段 60k 图纸能回归测试（`scripts/bench_perf.py` 有基准）。

---

## 6. 界面方案（直接落地 `design/main.html`）

### 6.1 布局（与 v3 原型 1:1）

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ 顶栏(深色 slate-900, 52px): 品牌・项目下拉・新建・打开图纸・AI 算量・导出    │
├────────────┬──────────────────────────────────────────────┬──────────────┤
│ 左 260px   │  画布区 (深色 surround slate-700)              │ 右 400px      │
│ 图纸列表    │  深色工具条:工具/拾取/整图/缩放% /类型开关      │ rail 45px     │
│ 搜索+树形   │  Canvas 2D 网格底纹                            │ │              │
│ 图层 checkbox│  选中浮层Bar(数量/分配/清空)                   │ │ 绑定工作台    │
│ 块树        │  · 右下 hint · 地图线图例                       │ │ BOQ 清单     │
│ 收起按钮    │  浮标签                                        │ 实体属性       │
└────────────┴──────────────────────────────────────────────┴──────┴───────┘
│ 状态栏(白底): 实体数 · 图层数 · BOQ条数 · 模式 · LLM后端 · 记录                    │
└─────────────────────────────────────────────────────────────────────────┘
```

完全引用 `design/main.html` 的已知要素：
- 顶栏：图标（Segoe Fluent 或 SVG/iconify 图标对应的本地化）、强调色 cyan-500/600。
- 图纸列表卡片行（状态圆点、尺寸/比例/徽标/已识别）。
- 图层树/块树、筛选框；画布工具条（清单/计量/图例/AI/属性 五模式 + 拾取下拉整图 缩放%）。
- 右下 rail：绑定工作台 / BOQ 清单 / 实体属性 / 操作记录 + 帮助；面板头 标题+副标题+图标按钮。
- Toast 浮层、`选择条`（X 个已选择+分配+清空）、浮标签、右下 hint。
- **配色即以 `app/ui/theme.py` 的恒定色板为准（slate/cyan 系）**；Web 端用 CSS 变量同值即可，保证两端视觉一致。

### 6.2 技术栈建议（零构建、离线可用）

| 项 | 方案 | 理由 |
|---|---|---|
| 后端 | FastAPI + uvicorn | 复用现有 Python、异步 job 适配 |
| 前端 | **原生 JS(ES Modules) + HTML/CSS 手写**；不用框架 | 与原型 stay 零构建、离线、无 node 依赖；js 只在面板交互，渲染器 + DOM 模板便足够 |
| 样式 | 手写 CSS 变量（对齐 theme.py），可选将 `tailwind` 保留为设计工具 | 离线可用 |
| 图标 | 本地 SVG 图标 sprites（或生成字体）；不强依赖 iconify CDN | 离线启动不白屏 |
| 渲染 | HTML5 Canvas 2D + 监听 | 无外部依赖 |
| 实时 | WebSocket（自带 `ws` 即可，浏览器原生） | 进度推送 |
| 部署 | `start_web.bat`：`uvicorn web.server:app --port 8520` + `webbrowser.open` | 一键启动习惯延续 |

> 若后期面板变繁琐，可升级为 Vue 3（普通引入，仍无构建）；不建议直接借贷 React 生态（本项目所需交互有限，渲染核心也不依赖框架）。

### 6.3 与桌面版对照的核心组件

| 桌面 PySide6 | Web 组件文件 |
|---|---|
| MainWindow | `layout.js`（顶栏/左栏/rail/面板容器） |
| BoqTable | `boq_table.js` |
| MappingPanel | `mapping_panel.js` |
| CanvasToolbar | `canvas_toolbar.js` |
| LayerTree | `layer_tree.js` |
| LegendPanel | `legend_panel.js` |
| BindingWorkbench | `binding_workbench.js` |
| AiResultsDialog | `ai_results_dialog.js` + `job_progress.js` |
| HistoryPanel | `history_panel.js`（可对接 `llm_run` 表事件） |

---

## 7. 后端服务工程（FastAPI）

### 7.1 目录结构

```text
web/
├── server.py              # FastAPI 入口：挂载静态 + 全部路由 + WS
├── routers/
│   ├── projects.py        # 项目/图纸/上传/解析(job)/geometry/blocks/layers
│   ├── boq.py             # Excel 上传/查询/更新
│   ├── mappings.py        # 映射(点选/框选/整层/整块) + measure
│   ├── binding.py         # 工作台候选/确认/拒绝/批量确认
│   ├── legend.py          # 图例 CRUD + LLM 标定
│   ├── takeoff.py         # AI 算量(单图/文件夹) + 进度
│   ├── report.py          # Excel 下载
│   └── llm_settings.py    # LLM 配置
├── jobs.py                # JobManager（后台任务 + 进度广播 + 查询）
├── static/
│   ├── index.html / style.css / app.js
│   └── core/renderer.js viewport.js picking.js grid.js
│   └── panels/*.js
├── start_web.bat
└── README.md
```

### 7.2 并发与线程

- FastAPI 运行在 `uvicorn --workers 1`（本地单用户）；后台 CPU 任务用 `run_in_threadpool` / `anyio.to_thread`（GIL 下的 ezdxf 解析在纯 Python 下并行无明显加速，但 I/O（ODA 转换、磁盘读）直接受益）。
- **DB 连接**：现有 thread-local 连接池恰好适配 FastAPI 线程池；SQLite + WAL + `busy_timeout` 在单进程内多请求下足够。需注意 FastAPI 同步路由尽量在 `def`（自动跑线程池）而非 `async def`，避免阻塞事件循环。

### 7.3 存储

- 上传的 DWG/DXF 存到 `~/.cad-boq-tool/imports/{project_id}/{filename}`，DXF 转换/解析缓存沿用 `parse_cache`。
- 解析结果写入同一 `projects.db`——**桌面版能看到 web 版产生的数据**（双端共存的基础）。

---

## 8. 实施路线（每阶段可独立交付验证）

| 阶段 | 内容 | 验证标准 |
|---|---|---|
| **W1** | `server.py` API 骨架 + 项目/图纸上传解析 job + `index.html` 三栏壳 + 项目/图纸列表 | 浏览器能看到项目与图纸，上传 DWG 后台解析进度条走完 |
| **W2** | `geometry` 窗口 API + `renderer.js`（渲染/缩放/平移/拾取/框选/图层显隐/LOD/高亮） | 浏览器开真实图纸可缩放平移点选，高亮定位正常 |
| **W3** | BOQ 表格 + 4 种映射（点/框/整层/整块）+ 计量实时 + 关联着色 | 浏览器完成一次完整"拾取→分配→出数量"闭环 |
| **W4** | 图例标定 + 绑定工作台（候选/确认/拒绝/批量）+ AI 算量（单图/文件夹）+ 进度 WS | 浏览器完成绑定闭环，AI 算量进度可见 |
| **W5** | 导出 Excel 下载 + LLM 设置 + 历史面板 + 打磨（空态/错误/大图性能测试） | 桌面与 Web 全流程等价，数据互通 |

**W1+W2 完成即价值显现**（浏览器看到真实图纸、可缩放点选）。W2 的渲染器是最大风险，先做 W2 验证渲染器，再铺后续。

---

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 渲染器重写（约 40% 工作量） | `build_geom_item` 逐函数对照翻译，先用小图 demo 验证；`geometry` 数据 schema 与后端契约不改变 |
| 大图性能 | 空间列 + 窗口加载 + 延迟类型；沿用并重放 `bench` 基准；必要时 WebGL 后置 |
| 重绘抖动 / 拾取不一致 | 前端统一空间网格（与 Qt BspTree 等价）；增加双端冒烟对照用例 |
| 桌面版回归 | 桌面不动，Web 独立目录；业务层逻辑共用测试（tests/ 已有） |
| LLM 调用超时/失败 | 全部走 job + WS；沿用 quality_threshold 与 fallback |
| SQLite 并发写 | 单进程单 worker+WAL；写入模型沿用现有模式 |

## 10. 结论

业务逻辑 100% 复用 + FastAPI 后端壳（薄）+ 自研 Canvas 2D 渲染器（翻译 `canvas.py`）+ 直接落地 `main.html` 原型，是投入/收益最优路径。**渲染器是唯一大项**；几何 schema 已由 `cad_parser` 固化为 JSON，后端仅需新增一个空间列做窗口查询。

预计总新增代码：后端 ~1200 行（接口壳+job），前端 ~1500 行（渲染器 JS）+ ~1200 行（页面/面板）。W1-W5 大约 2-3 周单人可完成。