# cad-boq-tool 技术路线 + 工作流优化评审报告

> 评审日期：2026-09-06
> 评审方法：代码读入（extractor.py / matcher.py / classifier.py / README / BACKLOG） + 开源项目对比 + 用户痛点溯源

---

## 一、项目管线现状

### 1.1 端到端架构

```
DWG/DXF (ezdwg 直读，ODA 回退)
  ↓
[提取层] app/engineering/extractor.py
  ├─ 设备(INSERT 块)      — 匿名块(*开头) 跳过
  ├─ 线性(LINE/ARC/...)   — 按图层聚合，过滤背景图层
  └─ 面积(LWPOLYLINE闭合) — 面积 > 0 判闭合并集
  ↓
[语义层] app/engineering/classifier.py
  └─ 三重兜底: 规则(0.4) → 知识库(0.9) → LLM补充
  ↓
[绑定层] app/binding/matcher.py
  └─ 四层覆盖: 历史确认(1.0) → 规则(0.6-0.95) → 语义(embedding) → LLM精排
  ↓
[审核层] app/binding/reviewer.py
  └─ confirm_binding: 跨图纸同名块 SUPERSEDED，唯一性校验
  ↓
[回写层] app/boq/writeback.py
  └─ measured_qty → Excel BOQ
```

### 1.2 BACKLOG 进度（2026-08-28 定稿）

| 模块 | 状态 |
|---|---|
| P1 性能优化（后台线程/LOD/VACUUM） | ✅ 完成 |
| P2 绑定候选增强（块名相似度/排序/跨图消失） | ✅ 完成 |
| P0 准确率评测闭环 | ⬜ 未启动 |
| 召回拓宽（匿名块/匿名设备） | ⬜ 未启动 |
| 规格硬冲突处理 | ⬜ 未启动 |
| 后台结构化输出作战图 | ⬜ 未启动 |

### 1.3 准确率现状

定性估计约 78%，**无量化基准验证**。BACKLOG P0 未落地，无分方法（rule/embedding/LLM）的 precision/recall 统计。

---

## 二、用户痛点溯源（来自记忆 + 代码）

| # | 痛点案例 | 根因 | 当前管线位置 | 影响 |
|---|---|---|---|---|
| 1 | 图例标定页匿名块(`*`开头)误入统计 | [extractor.py L172](app/engineering/extractor.py#L172) 匿名块被 skip，但图例关联时混入 | 提取层 | 设备数量虚高 |
| 2 | 图例裸 MTEXT（无实体属性只有标注文字） | `_attribs_from_entities` 取不到 attribs → `_spec_from_attribs` 退化为空 | 提取层 × 图例层 | 规格丢失，绑定层依赖 LLM 猜 |
| 3 | SPLINE=0、欧式逗号导致导线长度归零 | 线性实体类型覆盖不完整；图层名规格提取正则不完善 | 计量层 | 导线工程量归零 |
| 4 | 平行线对/中心线 → 跨图并集重复计量 | 无连通拓扑建模（只做图层聚合，无端点连接判断） | 计量层 | 回路导线重复或遗漏 |
| 5 | 跨图块名完全相同但规格不同 | 绑定候选按 `block_name` 聚合，缺规格层级区分 | 绑定层 × 审核层 | 错绑 BOQ 项 |
| 6 | 同块候选按置信度排序混乱 | 早期版本候选生成无排序；跨图同名块候选未联动消失 | 绑定层 | 用户选择困难 |

---

## 三、技术路线差距分析

### 差距 1：提取层——缺视觉兜底（第 0 信道）

**当前状态**：
```
CAD 实体文本 → MTEXT/ATTRIB → 有则用、无则 LLM 猜
```

**缺失**：图例标注区域（MTEXT 在图例外/渲染图中）没有第二条信道，匿名块和图例裸文字完全依赖 LLM 补全。

**对照竞品**：
- OpenTakeoff：实体文本 + OCR 渲染兜底（自适应阈值、蓝图负极检测、褪色墨水桥接）
- ConstructDrawingAI：L0 Ingest → L1 Perception 符号检测，0.847 mAP@50 电气检测
- cad-ai-agent：确定性提取器分离于 LLM 编辑流程

**根本问题**：图例里的"裸 MTEXT"不在实体数据库，管线完全靠 LLM 猜规格。

### 差距 2：语义层——缺连通拓扑信息

**当前状态**：
```
图层名 + 块名 → discipline/system/object_type（三重兜底）
```

**缺失**：块的连通关系（导线端点连接哪个设备）未建模，无法按回路聚合。

**对照竞品**：
- ConstructDrawingAI P&ID 连通图提取：端点坐标 → 连接关系 → 回路拓扑图 → edge AP 0.752

**根本问题**：导线按图层长度累加，无法区分"一根导线跨两个设备"和"两根独立导线"，回路并集场景产生重复计量。

### 差距 3：标注层——缺结构化置信度溯源链

**当前状态**：
```
confidence 字段（0.4/0.7/0.85/0.9/0.95）+ entity_ids 锚点
reason 行（字符串）
```

**缺失**：无法展开"这条置信度的来源是哪个具体规则或 LLM 调用"，溯源链不透明。

**对照竞品**：
- ConstructDrawingAI CIR schema：每个值 = `{value, confidence, method, source_entity_ids, source_sheet}`
- OpenTakeoff：每个 shape 记录 `scale used, method, human_correction, original_boundary_frozen`

**根本问题**：binding_workbench 显示 reason 行，但用户无法追溯 reason 的置信度来源。

### 差距 4：反馈层——无自动化准确率闭环

**当前状态**：
```
人工确认 → symbol_knowledge 写库 → 下次同类块复用
```

**缺失**：跨项目反馈不累积为可量化指标，"78% 准确率"无基准验证。

**对照竞品**：
- OpenTakeoff：12.3% 中位绝对误差基准；"Markup is Label"数据飞轮
- ConstructDrawingAI：多 seed 均值 ± 标准差，官方数据划分，公开 baseline

**根本问题**：BACKLOG P0 准确率评测闭环未落地，无法量化改进效果。

### 差距 5：工程品质——缺 Refusal 策略

**当前状态**：
```
no_match: 计数 + 静默 skip
```

**缺失**：答不了时静默返回 0，用户不知道哪个工程对象没有绑定。

**对照竞品**：
- OpenTakeoff：拒绝时返回可操作原因（如 "That space isn't enclosed on the plan linework—the fill spilled."）

**根本问题**：静默失败比有因失败危害更大，用户无法定位问题根因。

---

## 四、工作流可用性综合评估

| 维度 | 评分 | 说明 |
|---|---|---|
| 功能完整性 | ⭐⭐⭐⭐ | DWG 直读→提取→绑定→回写全链路，竞品大多只做中间一节 |
| 准确率（定量） | ⭐⭐ | BACKLOG P0 未落地，无基准验证 |
| 工程诚实性 | ⭐⭐⭐⭐ | 规则/语义/LLM 分层、幂等写入、WAL 并发、Refusal 文化部分落地 |
| 用户可追溯性 | ⭐⭐⭐ | entity_ids 锚点 + reason 行，但缺结构化 provenance chain |
| 性能 | ⭐⭐⭐⭐ | P1 优化已落地（后台线程/BATCH LOD/VACUUM） |
| 跨项目学习 | ⭐⭐ | symbol_knowledge 库，无自动化反馈回路 |
| 中文场景适配 | ⭐⭐⭐⭐⭐ | ELV 系统规则齐全，中文 BOQ/电气积累深厚，竞品无此积累 |
| 测试覆盖 | ⭐⭐⭐ | tests/ 有 11 个集成测试，无分层量化基准 |

**整体结论**：cad-boq-tool 是同类开源项目中**功能最完整、中文适配最深、工程实践最扎实**的桌面工具。技术路线方向正确，与 OpenTakeoff 的 Refusal 文化、ConstructDrawingAI 的 CIR 思路一致。主要差距不在路线错误，而在**提取层缺视觉兜底、反馈层缺量化闭环、标注层缺结构化溯源**。

---

## 五、优化建议（按优先级）

### P0——立即可做，准确率提升最直接

#### ① 图例 OCR 兜底（PaddleOCR PP-OCRv5，本地离线）

**问题**：图例裸 MTEXT（无块属性只有标注文字）→ 规格丢失 → 绑定层 LLM 猜

**方案**：
1. 将图例区域渲染为高分辨率图像（≥300 DPI）
2. PaddleOCR PP-OCRv5 执行 OCR（中文/竖排/旋转标注支持）
3. 提取文字与 `_attribs_from_entities` 结果 RAG 合并
4. 进入 `_spec_from_attribs` 和 `infer_object_meta` 作为规格补充

**收益**：直接填补"图例裸 MTEXT"场景的规格丢失，绑定层 LLM 提示词多了真实规格文本。

**成本**：pip install paddlepaddle + ch_PP-OCRv5 模型（~200MB），完全本地，无 API 成本。

**实现位置建议**：`app/takeoff/block_legend.py` 或新增 `app/ocr/paddle_ocr.py`

---

#### ② Refusal 策略——no_match 结构化报告

**问题**：`no_match` 仅计数，用户不知道哪个工程对象没有绑定。

**方案**：
```python
# app/binding/matcher.py
def _diagnose_no_match(eo, boq_items) -> str:
    """返回结构化拒绝原因"""
    reasons = []
    if not eo.block_name and not eo.layer_name:
        reasons.append("无块名且无图层名")
    elif not boq_items:
        reasons.append("BOQ 清单为空")
    elif not boq_searchable_text(eo):
        reasons.append("EO 无可搜索文本")
    else:
        reasons.append("BOQ 无关键词交集")
    return "; ".join(reasons)

# 在 no_match 路径上增加持久化
if not base:
    reason = _diagnose_no_match(eo, boq_items)
    db.log_binding_refusal(eo.id, reason)  # 用于后续分析和 UI 提示
    stats["no_match"] += 1
```

**收益**：用户可见每个未匹配工程对象的原因，便于人工介入和规则补充。

---

### P1——中期投入，结构性改进

#### ③ CIR 统一 Schema（参照 ConstructDrawingAI）

将各层输出统一到同一个中间表示：

```python
@dataclass
class QuantityRecord:
    object_id: int
    value: float
    unit: str
    method: Literal["count", "length", "area", "hybrid"]
    confidence: float
    provenance: list[tuple[str, str, int | None]]  # [(source, detail, llm_run_id)]
    source_sheet_id: int
    source_entity_ids: list[int]
```

**收益**：审核层可展开"这条量从哪来"，回写层可附带置信度，评测层可按方法分层统计。

**实现位置建议**：新增 `app/models/quantity_record.py`，改造 `extractor.py` / `matcher.py` / `writeback.py` 的返回值结构。

---

#### ④ 连通拓扑基础版（回路级聚合）

**问题**：导线工程量按图层长度累加，无法区分"一根导线跨两个设备"和"两根独立导线"。

**方案**（简化版，不追求完整 P&ID 连通图）：
1. 设备块的包围盒（BoundingBox）+ 导线端点坐标
2. 距离阈值判断：导线端点距离设备块 ≤ threshold → 判为连接
3. 同一回路（相同图层名 + 连通端点）合并计量，不重复

**注意**：功能复杂度高，建议作为 P3 决策点，先完成 P0/P1 后再评估。

---

### P2——长期工程护城河

#### ⑤ 准确率基准闭环（BACKLOG P0）

参照 OpenTakeoff 评测框架：

```
1. 留存集：保留 20% 历史项目不参与训练/规则更新
2. 按 binding 层方法（rule/embedding/LLM）分层统计 precision/recall
3. 定期回归：每次 LLM prompt 改动后对比准确率 delta
4. 输出结构化报告：
   {"method": "rule", "precision": 0.91, "recall": 0.87, "by_discipline": {...}}
```

**收益**：准确率从"定性 78%"变为"可验证的 X%"，每次改进有量化依据。

---

### P3——可选方向（视 P0/P1 效果决策）

#### ⑥ AutoCAD MCP 交叉验证信道

使用 [U-C4N/Autocad-MCP](https://github.com/U-C4N/Autocad-MCP)（MIT，COM+ezdxf 双引擎）对 ezdwg 直读结果做对拍。

**注意**：COM 只读调用，只作校验信道，不替换现有解析层。

#### ⑦ 电气符号检测接入

在匿名块场景使用 [ConstructDrawingAI](https://github.com/A-SHOJAEI/ConstructDrawingAI) 预训练权重（SkeySpot 数据集，0.847 mAP@50）。

**注意**：需 torch 依存 + GPU，建议先建"未知块池"再决定是否引入。

---

## 六、执行路线图

```
第一周（7天）
├── P0 ① 图例 OCR 兜底
│   ├── pip install paddlepaddle + 下载 ch_PP-OCRv5 模型
│   ├── 新增 app/ocr/paddle_ocr.py（高分辨率图例渲染 + OCR）
│   ├── 改造 extractor.py _spec_from_attribs：合并 OCR 结果
│   └── 用历史失败用例回归测试
│
└── P0 ② Refusal 策略
    ├── matcher.py 新增 _diagnose_no_match
    └── db.py 新增 log_binding_refusal 表

第二周（7天）
├── P1 ③ CIR 统一 Schema
│   ├── 新增 app/models/quantity_record.py
│   ├── 改造 extractor.py / matcher.py 返回结构化 QuantityRecord
│   └── 改造 binding_workbench.py 展示 provenance 链
│
└── P1 ④ 准确率基准闭环（评测框架搭建）
    ├── 拆分 20% 历史项目作为留存集
    ├── 实现 precision/recall 分层统计
    └── 首次跑基准：rule/embedding/LLM 各层准确率

第三~四周（14天）
├── 视 P0 效果决策 P3 ⑥ AutoCAD MCP 交叉验证
└── 视 P0 效果决策 P3 ⑦ 电气符号检测接入
```

---

## 七、参考来源

- 本项目代码：[extractor.py](app/engineering/extractor.py)、[matcher.py](app/binding/matcher.py)、[classifier.py](app/engineering/classifier.py)
- BACKLOG：[docs/BACKLOG.md](docs/BACKLOG.md)
- ConstructDrawingAI：[README](https://github.com/A-SHOJAEI/ConstructDrawingAI) — CIR schema、L0-L4 五层、mAP 基准
- opentakeoff：[README](https://github.com/Kentucky-ai/opentakeoff) — Refusal 文化、12.3% 误差基准、"Markup is Label"
- cad-ai-agent：[README](https://github.com/jeremylongshore/cad-ai-agent) — LLM 出计划不出实体、分层测试
- U-C4N/Autocad-MCP：[README](https://github.com/U-C4N/Autocad-MCP) — COM+ezdxf 双引擎、ISO GD&T 校验
- PaddleOCR：[GitHub](https://github.com/PaddlePaddle/PaddleOCR) — PP-OCRv5 中文 OCR
