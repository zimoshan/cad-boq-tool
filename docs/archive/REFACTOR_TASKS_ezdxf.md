# 改造任务清单（待审核）

> 依据 `docs/TECH_SOLUTION_COMPARISON_ezdxf.md` 的改造方案，拆分为可独立审核/执行的任务。
> 每个任务含：目标、涉及文件、改动要点、验收标准、依赖关系。
> **请逐条审核，确认后再执行。**

---

## 任务总览

| # | 任务 | 优先级 | 依赖 | 状态 |
|---|------|--------|------|------|
| T1 | 块属性（ATTRIB）解析 | P0 | 无 | ⏳ 待审核 |
| T2 | 几何类型 → 计量规则自动推断 | P0 | 无 | ⏳ 待审核 |
| T3 | 知识库表（symbol_library）设计 | P1 | 无 | ⏳ 待审核 |
| T4 | 语义分类三重兜底（规则→知识库→LLM） | P1 | T3 | ⏳ 待审核 |
| T5 | Embedding 召回子集增强 | P1 | T1 | ⏳ 待审核 |
| T6 | 人工标定闭环（确认/拒绝沉淀知识库） | P2 | T3 | ⏳ 待审核 |
| T7 | 主动学习难例挖掘 | P2 | T6 | ⏳ 待审核 |

---

## T1：块属性（ATTRIB）解析

**目标**：解析 INSERT 块内 ATTRIB，把 `tag=value`（型号/规格/材质）入库，提升规格识别率。

**涉及文件**：
- `app/cad/reader.py`（`_EntityWrapper` 增加 `attribs` 属性，兼容 ezdxf + ezdwg）
- `app/cad/cad_parser.py`（INSERT 分支读取 attribs 存入 geom）
- `app/models.py`（`Entity` 或 `EngineeringObject` 增加规格字段，或复用 `specification`）
- `app/engineering/specification.py`（`infer_spec_from_block` 优先用块属性）

**改动要点**：
1. `_EntityWrapper` 增加 `attribs` 属性：ezdxf 用 `entity.attribs`，ezdwg 从附加实体读取。
2. `cad_parser.py` INSERT 分支把 `attribs` 写入 `geom_json`。
3. `extractor.py` 生成 `EngineeringObject` 时，规格优先取块属性，其次 `infer_spec_from_block`。

**验收**：设备规格识别准确率提升；无 ATTRIB 的块仍走正则兜底，不报错。

---

## T2：计量规则自动推断

**目标**：从实体几何类型自动推断默认计量规则（count/length/area），减少人工设置。

**涉及文件**：
- `app/engineering/extractor.py`（生成 EO 时按几何类型填 `quantity_rule`）
- `app/measure.py`（`compute_entity_qty` 保持确定性，仅默认值来源变化）

**改动要点**：
1. 聚合实体时统计几何类型：INSERT→count、LINE/ARC/SPLINE/开 LWPOLYLINE→length、CIRCLE/闭合 LWPOLYLINE/HATCH→area。
2. 生成 `EngineeringObject` 时自动填 `quantity_rule`，人工在绑定工作台复核。

**验收**：设备/线性/面积三类对象默认计量规则正确，无需人工逐条设置。

---

## T3：知识库表（symbol_library）设计

**目标**：新增可学习的图例符号库，沉淀人工标定结果。

**涉及文件**：
- `app/db.py`（新增 `symbol_library` 表 + CRUD）
- `app/models.py`（新增 `SymbolLibrary` 模型）

**改动要点**：
1. 建表：`{block_name/layer_name, discipline, system, spec, unit, quantity_rule, confirmed_by, confirmed_at}`。
2. 提供 `get_symbol_library` / `upsert_symbol` / `delete_symbol` 接口。

**验收**：表结构可建、CRUD 可用。

---

## T4：语义分类三重兜底（规则 → 知识库 → LLM）

**目标**：分类判定从"仅关键词规则"升级为"规则 → 知识库 → LLM"三重兜底。

**涉及文件**：
- `app/engineering/classifier.py`（新增知识库查询 + LLM 兜底）
- `app/llm/prompts.py`（新增分类 prompt）
- `app/llm/schema.py`（新增分类输出 schema）

**依赖**：T3（知识库表）

**改动要点**：
1. 分类顺序：规则层命中即用 → 知识库命中即用 → LLM 分类。
2. LLM 结果回写知识库（供下次复用）。

**验收**：未命中规则的图层/块能通过知识库或 LLM 正确分类。

---

## T5：Embedding 召回子集文本增强

**目标**：把 `eo_text` 扩展为含块属性与知识库规格的富文本，提升召回命中率。

**涉及文件**：
- `app/binding/matcher.py`（`_boq_top_n_for_llm` 的 `eo_text` 拼接）
- `app/binding/embedding_matcher.py`（`eo_text` 拼接）

**依赖**：T1（块属性）

**改动要点**：`eo_text` 加入 `attribs` 与知识库规格。

**验收**：召回子集命中真实 BOQ 的概率提升。

---

## T6：人工标定闭环（确认/拒绝沉淀知识库）

**目标**：人工确认/拒绝候选时，自动写入/更新 `symbol_library`。

**涉及文件**：
- `app/binding/reviewer.py`（`confirm_binding` / `reject_binding` 增加知识库写入）

**依赖**：T3（知识库表）

**改动要点**：确认时 upsert 知识库；拒绝时记录负样本（可选）。

**验收**：确认后知识库自动更新，新项目可复用。

---

## T7：主动学习难例挖掘

**目标**：低置信度候选自动排队，提示人工优先复核。

**涉及文件**：
- `app/ui/binding_workbench.py`（按置信度排序 + 难例标记）

**依赖**：T6

**改动要点**：低置信度候选置顶/高亮，提示优先复核。

**验收**：难例优先进入人工复核队列。

---

## 执行顺序建议

```
T1 ──→ T5
T2 ──→ (独立)
T3 ──→ T4 ──→ T6 ──→ T7
```

**建议先做 T1 + T2（P0，无依赖，见效快），再做 T3→T4→T6→T7（知识库闭环）。**

---

## 请审核

请逐条确认：
1. 任务范围是否合理？
2. 优先级/依赖关系是否调整？
3. 是否有需要补充或删除的任务？

确认后我将按顺序执行。