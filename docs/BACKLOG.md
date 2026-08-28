# 待办清单（BACKLOG）

创建：2026-08-28。状态图例：⬜ 待办 / 🚧 进行中 / ✅ 完成（完成时留日期）。

---

## 一、性能优化：切图/加载慢（诊断已完成，方向已定）

> 结论（2026-08-28 实测，见问题排查记录）：数据库查询不是瓶颈。
> - `get_entities` 40k 实体：SQL 98ms + 构造 104ms；三条图层/块查询 7-17ms；blocks_json 34MB `json.loads` 654ms。
> - DB 文件 1.6GB 但实际数据仅 ~163MB（历史 DELETE 空闲页未回收，VACUUM 后 ~170MB）。
> - 日志分段计时显示：切图总耗时 0.4s~316s 波动，其中 **canvas_build 占大头（8s~186s 同图波动）**，UI 线程同步执行。

- [x] **P1-1 切图改后台线程 + 进度条**（main_window.py `_on_sheet_changed`）✅ 2026-08-28
  - `json.loads(blocks_json)` + DB 读取移出 UI 线程（_SheetLoadWorker：thread + seq 防串台 + 可取消）
  - `canvas.build` 分批（BATCH=2000）pump 事件循环；进度条 + 取消按钮；QGraphicsItem 仍 GUI 线程创建
- [x] **P1-2 DB VACUUM 瘦身**（1.6GB → ~170MB）✅ 2026-08-28
  - db.py：`db_usage()`（空闲页/碎片率）、`vacuum_database()`（独立连接，返回前后体积+节省） 
  - 工具菜单「数据库瘦身 (VACUUM)…」+ 启动 800ms 检测（freelist ≥100MB 且碎片率 ≥0.4 → 提示）
- [x] **P1-3 大图 LOD / 分层惰性渲染** ✅ 2026-08-28
  - 保留 `_DEFERRED_THRESHOLD` 跳过 TEXT/HATCH；**新增 INSERT 块定义合并 LOD**：大图且块子项 ≥3 时把块几何合并为单个 QGraphicsPathItem（避免 80k+ 实体膨胀成百万级 item 吃满主线程），拾取/图层/颜色语义不变，文本块退化叉号（canvas.py `make_block_lod_item`）
  - 按视口/图层惰性实例化留作后续可选（当前合并 LOD + BspTreeIndex 视口裁剪已覆盖大头）

---

## 二、绑定候选增强：块名 ↔ BOQ Description 匹配 + 一键定唯一绑定

> 需求（2026-08-28 用户反馈）：
> 1. 图块名与 BOQ 清单 Description **几乎一致** → 候选生成需纳入这个匹配因素（高权重）。
> 2. 一个图块只能对应一个 BOQ 子项 → 同一图块候选按匹配置信度**从高到低**排列。
> 3. 确认一个绑定后，同一图块的其他候选推荐绑定对象**应消失**（跨图纸同名的也要消失）。

### 2.1 块名 ↔ Description 高相似匹配（规则层 + LLM 提示词）

现状：规则层 [rule_matcher.py](app/binding/rule_matcher.py) `_score_boq` 分词命中，块名关键词权重仅 `W_BLOCK_WORD=0.3`（命中也难达到 `RULE_STRONG_MIN=0.6`）；LLM prompt [prompts.py](app/llm/prompts.py) 有同义词规则但无"整串几乎一致 → 强匹配"。

- [x] **2.1.1 归一化整串相似度函数**（text_norm.py）✅ 2026-08-28
  - `string_similarity(a,b)` 0~1：归一化后全等→1.0；包含→`0.7+0.3*ratio`；LCS DP 兜底→`lcs/max_len`
- [x] **2.1.2 规则层加权**（rule_matcher.py）✅ 2026-08-28
  - 短语级命中：`string_similarity` ≥0.85（STRONG_SIM_MIN）→ 强分 W_STRONG=0.7，reason「块名≈清单描述」；`desc_norm` 只对比 description（去 code/单位前缀稀释）
- [x] **2.1.3 LLM prompt 加强**（prompts.py + config.BINDING_PROMPT_VERSION 升级）✅ 2026-08-28
  - BINDING_SYSTEM_PROMPT 新增规则 4「块名↔描述整串近似→强匹配」（confidence≥0.9, needs_review=false）+ CY-08/DOME CAMERA 2MP 示例
  - config `BINDING_PROMPT_VERSION = "binding-v4"`（写明 v4 变更，llm_run 审计可追溯）

### 2.2 候选排序：同一图块按置信度从高到低

结论（2026-08-28 用户确认）：**与 T7 主动学习不冲突**。主动学习 = 根据已完成绑定持续学习（历史确认复用 [rule_matcher.py](app/binding/rule_matcher.py) `historical_confirmed` + 确认回写 symbol_knowledge [reviewer.py](app/binding/reviewer.py) `_write_symbol_knowledge`）；本需求降序 = **同一图块（EO）内部**候选排序，保证最佳绑定置顶。作用层面不同，并存不冲突。

- [x] **2.2.1 同图块候选按置信度降序** ✅ 2026-08-28
  - 同一 engineering_object（图块）的候选按 confidence 降序，最高置信度（最佳绑定一眼可见）置顶；若被 2.3 全部 supersede 则不可见（2.2.2 由 2.3 行为覆盖）
  - 跨图块「先审哪个图块」仍保留主动学习/难例优先策略原机制经确认不冲突（见上文结论）
- [x] **2.2.2 确认后置顶候选应排在最前** ✅ 2026-08-28
  - PENDING 队列按 `eo_min_conf` 降序 + EO 内部 confidence 降序排序（binding_work.py `_render_queue`）——确认后同 EO 其余候选置顶排后；跨图纸同名块候选全部 SUPERSEDED（2.3.1 覆盖，见下）

### 2.3 确认绑定 → 同图块其他候选消失（跨图纸）

现状缺口：[reviewer.py `confirm_binding`](app/binding/reviewer.py#L85) 只 `supersede_candidates(eo.id)`（**单 EO=单图块×单图纸**）；同名块跨图纸时其他图纸 EO 的 PENDING 候选仍保留。

- [x] **2.3.1 按 block_name（跨图纸）supersede**（db.py + reviewer.py）✅ 2026-08-28
  - db.py `supersede_candidates_by_anchor(project_id, block_name, layer_name, exclude_cid)`：跨图纸所有同名块/图层 PENDING → SUPERSEDED
  - `confirm_binding` 确认后调用（block/layer 双模式）
- [x] **2.3.2 图块↔BOQ 唯一性校验**（reviewer.py `_accepted_block_boq`）✅ 2026-08-28
  - 确认前检查 ACCEPTED 候选 + 正式 mapping：block/layer 已绑定另一 BOQ item → ReviewError「图块 X 已绑定到 BOQ#N…一图块只能对应一个 BOQ 子项」
- [x] **2.3.3 审核队列视图联动刷新** ✅ 2026-08-28
  - 回查确认：确认/生成候选后调用现有 load_project 刷新 PENDING 队列，已满足（test_binding_confirm_supersede 集成测试覆盖）

---

## 归档（2026-08-28 以前的已完成项）

（占位：后续把 `REFACTOR_TASKS_ezdxf.md` 等文档中的已完成任务汇入）