# cad-boq-tool 性能优化方案

> 日期：2026-08-26 ｜ 基于实测数据（40 图 / 1731 EO / 480 BOQ / 1.5GB 库）与代码勘察
> 覆盖：多线程、缓存、批量 SQL、渲染、embedding 成本控制

---

## 0. 现状盘点（已具备的优化）

代码库**已有**以下机制（勿重复设计）：

| 环节 | 现状 | 位置 |
|---|---|---|
| CAD 解析缓存 | sha256(path+mtime+size+version) → parquet/json，二次打开 47s→<1s | `app/cad/parse_cache.py` |
| 批量解析 | `ProcessPoolExecutor` 进程池（CPU 密集不受 GIL 限制）+ 后台 QThread | `app/batch_reparse.py`、`app/import_folder.py` |
| ODA DWG 转换 | `ThreadPoolExecutor` 分组并行 + 独立工作目录 | `app/cad/dwg.py:149` |
| SQLite | WAL + busy_timeout + 256MB 页缓存 + 256MB mmap | `app/db.py:_open_db` |
| UI 长任务 | 解析/导入/绑定候选生成均已 QThread 后台化 | `app/ui/*` |

**结论：基础设施层（解析/转换/入库）已基本到位。真实瓶颈在下游计算与查询模式。**

---

## 1. 瓶颈实测与定位

### 1.1 最大瓶颈：Embedding 召回每 EO 重算全部 BOQ 向量

`app/binding/embedding_matcher.py:70-72`：

```python
vectors = provider.embed([eo_text] + boq_texts)   # 每个 EO 都重算全部 BOQ！
```

- BOQ 文本只取决于 `project_id`，**跨 EO 完全不变**，却随每个 EO 重算一次。
- 量级：1731 EO × 480 BOQ = **83 万条向量嵌入请求**（本地 Ollama 也需 ~每批几十 ms）。
- 同理 `matcher._boq_top_n_for_llm` 每个 EO 调 `db.get_boq_items(project_id)` 全量查 480 条。

**修复：BOQ 向量一次计算 → 进程内缓存复用（LRU）**，或按 project_id 惰性缓存到内存 dict。

### 1.2 第二瓶颈：DB 连接无复用 + N+1 查询

- `get_conn()` 每次调用都 `sqlite3.connect()`（打开文件、设置 PRAGMA），无连接池 → `binding_workbench` 对每个 group 调 `_obj_state` × `get_candidates`（ACCEPTED/PENDING/REJECTED 各查一次）= **每行 3 次 connect + 查询**。
- `binding_workbench.py:251-258` 对 1731 个 EO 触发 ~5000 次独立查询。
- `rule_matcher.py:109` 每个 EO 全量 `get_boq_items`。

**建议**：① `get_conn` 加 `threading.local()` 每线程复用单连接；② 工作台批量预取 —— 按 project_id 一次查全部候选，内存中做状态计数（`defaultdict`）。

### 1.3 第三瓶颈：LLM 路由层重复 I/O

- `llm_classify_uncertain` 逐对象跑 LLM（每次 prompt 构造 + 网络往返）。
- 批量候选生成时 `llm_rerank` 逐个 EO 调用一次 Qwen → 1731 EO 即便命中 20% 也是 ~350 次串行调用。

**建议**：LLM 批处理（一次 prompt 携带 N 个 EO），或后台任务队列 + 并发上限，避免阻塞 UI 线程。

### 1.4 UI 渲染

- 1731 行 QTableWidget 用 `setRowCount` + 逐格 `setItem`（`_render_objects`），大项目卡顿。
- 画布对 6k+ 实体整绘 `QPainterPath`（canvas.py 200/220）。

**建议**：表格虚拟化（QTableView + QAbstractTableModel）+ 批量 setItem；画布按 viewport 可见区域裁剪（LOD）。

---

## 二、优化方案（按优先级）

### P0 — 必做（✅ 全部落地，2026-08-26）

#### P0-1：Embedding BOQ 向量进程内缓存 ✅（+P2-3 落盘）
- 文件：`app/binding/embedding_matcher.py` —— L1 进程内 `_BOQ_VECTOR_CACHE` + L2 磁盘 `~/.cad-boq-tool/embedding_cache/`；`invalidate_embedding_cache` 同时清内存+盘文件。
- **实测验收**：`scripts/bench_perf.py --embed-calls` → embedding 请求 201（BOQ 1 + EO 200），非 EO×BOQ（原估 83 万）。

#### P1-2 DB 连接线程本地复用 ✅（+ 状态批量预取）
- **文件**：`app/db.py`
- **改动**：`_open_db` 结果存 `threading.local()`；每次 `get_conn` 若同线程已有连接直接返回（DIFFERENT：事务内用上下文差异 —— 用 `get_conn()` 已是 `with` 控制）。注意 WAL 模式下多线程各自连接安全。
- **附**：`binding_workbench` 状态查询改批量：
  ```python
  cand_status = db.candidate_status_summary(project_id)  # SELECT status, engineering_object_id, count(*) GROUP BY
  # 内存 O(1) 查每组状态
  ```
- **验收**：`_render_objects` 从 ~5000 次 connect 降到 1-2 次。实测 `candidate_status_summary` 单次 0.2ms。

#### P1-3：BOQ 全量加载一次复用 ✅
- **文件**：`app/binding/matcher.py`、`rule_matcher.py`
- **改动**：`generate_candidates` 外层先 `items = db.get_boq_items(project_id)`，传给内层；删循环内 `_boq_top_n_for_llm`/`match_rule` 的重复 get_boq_items。
- **验收**：非 LLM 模式候选生成从 1731 次全表 BOQ 查询 → 1 次。

#### P1-4：画布 LOD（可见区裁剪）✅
- **文件**：`app/ui/canvas.py`
- **改动**：`_update_lod()` 按 `mapToScene(viewport().rect())` 可见区裁剪 + 缩放阈值（`_LOD_OVERVIEW_PPU`）切换细节绘制；大幅图延迟重绘（`_DEFERRED_THRESHOLD`）防卡顿。
- **验收**：3000+ 实体图缩放/平移不掉帧（FPS>30）。

### P2 优化（可选，长期）

| # | 项 | 说明 | 文件 |
|---|---|---|---|
| P2-1 | 表格模型虚拟化 | QTableWidget→QAbstractTableModel + 按需取数 | `binding_workbench.py` ✅ |
| P2-2 | LLM 批量并发 | 候选生成 LLM 调用加入 `ThreadPoolExecutor(max_workers=2)`，提示词拼接多条；仍写 llm_run 审计 | `matcher.py`/`llm_matcher.py` ✅ |
| P2-3 | embedding 低维缓存落盘 | BOQ 向量存 `~/.cad-boq-tool/embedding_cache/`，跨会话复用（BOQ 指纹/模型/条数校验，任一变化即重建） | `embedding_matcher.py` ✅ |
| P2-4 | 索引补齐 | `binding_candidate(project_id, engineering_object_id)` + `(project_id,eo,status)` 复合索引（新库 schema + `_migrate` 旧库增量） | `db.py` ✅ |
| P2-5 | 持久化 memo(缓存) 清理 | 缓存上限 100 → `config.PARSE_CACHE_MAX_ENTRIES`（环境变量 `CAD_BOQ_PARSE_CACHE_MAX` 覆盖） | `parse_cache.py` ✅ |
| P2-6 | takeoff 统计 map-reduce | `aggregate()` 分块 `_map_chunk/_merge_accumulators`，单遍 O(N)；区域 bbox 消除「区域×全实体」二次扫描；`chunk_size` 可调 | `app/takeoff/aggregate.py` ✅ |

### P3-1 建档（测量基准）

- **`scripts/bench_perf.py`**（实测通过）：`--drawing` 测冷/热解析 + 分块聚合；`--project` 测 BOQ 装载/candidate_status_summary；`--embed-calls` 用伪 provider 验收 P0-1。
- 实测（Benghazi 电气项目 1 号 + 40 张 DWG）：embedding 请求 **201 = BOQ 1 次 + 200 EO**（优化前预估 83 万）；解析 12.3k 实体 冷 9450ms → 缓存热 985ms；聚合 15.5ms。
- 覆盖测试：`tests/test_aggregate_chunked.py` 固化「分块 == 单块」等价契约。

---

## 三、多线程设计原则

1. **边界**：只有 CPU 密集（ezdxf 解析、几何计算）用进程池；I/O 密集（SQLite、Ollama 调用）用线程池；Ollama/Qwen 用请求级超时（已有 retry）。
2. **UI 不阻塞**：任何 >300ms 任务必须走 `QThread`/`QRunnable` + 信号回 UI（现有模式已验证，扩展即可）。
3. **线程安全**：SQLite WAL 允许跨线程读，但写入串行——`get_conn` 持 `threading.local` 连接池后，**写入保持单线程主链**；候选生成（只读+批量 INSERT）可在线程池。
4. **不变缓存先行**：所有"跨调用不变"的数据（BOQ 向量、symbol_library 全表、图层颜色表）优先进程内缓存，再考虑落盘。

---

## 四、预期收益估算

| 优化项 | 优化前（估算） | 优化后 |
|---|---|---|
| LLM 模式候选生成（embedding） | ~83 万个向量请求 | ~2200 个 → **实测 201**（BOQ 1 + EO 200）|
| DB 扫描 candidate 状态 | ~5000 次 connect+SQL | 批量预取 → **实测 1 次 0.2ms** |
| 非 LLM 候选生成 | 1731 × 全量 BOQ 查询/检测 | 1 × BOQ + EO 内存匹配 |
| 大图渲染 | 全量绘制 → 卡顿 | LOD 可见区裁剪 → 顺滑 |
| 解析 + 聚合 | 47s 冷解析 | 冷 9450ms / 热 **985ms**（12.3k 实体），聚合 15.5ms |

> 注：P0-1、P1-2/3/4、P2-1~6 **全部 8 项已落地**（2026-08-26 实测验收）；新增 P3-1 基准脚本 `scripts/bench_perf.py` 便于后续回归。

---

## 五、与现有任务的关系

- **与 REFACTOR_TASKS T1-T7**：性能项独立于功能改造，可并行执行；T5（Embedding 增强）落地后 P0-1 缓存价值更大。
- **与 LLM 精度调研**：P0-3 混合召回要求 embedding 候选集质量，缓存让迭代更快。
- **与分层候选改造（BINDING_WORKFLOW）**：分层候选必然频繁循环调用 semantic_candidates → 必须先做 P1-1 缓存再做分层，否则分层 4 层全跑 = 4× 全量成本。