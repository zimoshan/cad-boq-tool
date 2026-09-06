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

> 主线来源：[REVIEW_TECH_ROUTE_2026-09-06](docs/REVIEW_TECH_ROUTE_2026-09-06.md) 优化建议 + 方法论遗留项。

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

- **Web 化改造（FastAPI + Canvas2D）** ⏸ 2026-08-28
  - 方案已定稿：[CAD_BOQ_Web化_架构设计_v2.0](docs/CAD_BOQ_Web化_架构设计_v2.0.md)、[数据资产与实施 v1.0](docs/CAD_BOQ_Web化改造_数据资产与实施方案_v1.0.md)、[WEB_PLATFORM_ARCHITECTURE_2026-08-28](docs/WEB_PLATFORM_ARCHITECTURE_2026-08-28.md)。
  - 暂缓原因：桌面端优先，用户决策暂缓实施。
  - 恢复条件：桌面端稳定后（或用户重新要求）。恢复时先迁移业务层，再 Web 壳。

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