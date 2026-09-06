# 调研报告：图层/块字母序排序 + BOQ 下钻设备导线明细（长度/规格/型号）

> 调研日期：2026-08-25 ｜ 范围：cad-boq-tool 全链路（UI → db → 提取 → 计量）
> 结论基于真实图纸实证：`latest drawing-electrical/01-LBH lighting system/01-LBH lighting system.dxf`（30,696 实体，含 9,743 条文字标注）

---

## 一、需求 A：图层/块按名称字母序排序

### 1.1 现状（排序问题全景）

| # | 位置 | 当前排序 | 问题 |
|---|------|---------|------|
| 1 | `app/db.py:distinct_layers()` | `ORDER BY c DESC`（实体数降序） | **核心问题**：主窗口切换图纸时图层树按数量排 |
| 2 | `app/db.py:distinct_blocks()` | `ORDER BY c DESC`（实体数降序） | **核心问题**：块树按数量排 |
| 3 | `app/db.py:collect_blocks()` | `sorted(out, key=lambda x: -x[1])`（数量降序） | 图例面板（LegendPanel）块列表按数量排 |
| 4 | `app/db.py:get_engineering_objects()` | `ORDER BY id`（插入序） | 绑定工作台对象列表按提取顺序排 |
| 5 | `main_window.py:open_drawing()` | `drawing.layers.items()`（dict 插入序=解析顺序） | 打开图纸时图层/块树按解析顺序排 |

**所有"按实体数量排序"的根因都在 #1/#2/#3**——用户"实体数量我不关心"即指此。

### 1.2 方案（改动点明确，风险低）

| 位置 | 改动 |
|------|------|
| `db.py:distinct_layers` | `ORDER BY c DESC` → `ORDER BY layer COLLATE NOCASE ASC` |
| `db.py:distinct_blocks` | `ORDER BY c DESC` → `ORDER BY block_name COLLATE NOCASE ASC` |
| `db.py:collect_blocks` | `key=lambda x: -x[1]` → `key=lambda x: (x[0].lower(), x[0])` |
| `db.py:get_engineering_objects` | `ORDER BY id` → `ORDER BY COALESCE(block_name, layer_name) COLLATE NOCASE ASC` |
| `main_window.py:open_drawing`（2 处 rebuild） | `drawing.layers.items()` → `sorted(..., key=lambda kv: kv[0].lower())`；`drawing.block_refs.items()` 同理 |

- 图层树中 `(entity_count)` 计数**保留显示**（信息有用），仅排序依据改为名称。
- `COLLATE NOCASE` 保证英文图层名大小写不敏感排序（`A-Z` 先于小写，避免 `a` 排到 `B` 前）。
- `get_sheets()`（图纸列表，`ORDER BY id`）不动——用户需求限定"图层、块"。

### 1.3 验收标准

- 打开任意图纸：图层树、块树均按名称 A→Z 升序，与实体数量无关。
- 切换图纸（`_select_sheet`）、图例面板、绑定工作台对象表同规则。
- 显隐、右键关联、Isolate/锁定、定位等交互不受影响。
- 既有测试（test_core/test_legend/test_binding/test_e2e/gui_smoke）全过。

---

## 二、需求 B：BOQ 清单项下钻——设备与导线的长度/规格/型号

### 2.1 调研结论：链路已经打通 80%，缺口在"导线规格"

**已有数据基础（全部实证可用）：**

| 环节 | 现状 | 证据 |
|------|------|------|
| BOQ 条目 ↔ 实体 | `mapping.mapped_entity_ids(item_id, sheet_id)` 已能展开 layer/block/entity 三种模式到实体 id 列表 | `app/mapping.py:42-59` |
| 实体类型 | `entity` 表含 `dxf_type`（INSERT/LINE/LWPOLYLINE/TEXT/...）、`layer`、`block_name`、`length`、`area` | `app/db.py:32-44` |
| 设备区分 | INSERT 实体 = 设备（`block_name` 非空） | `extractor.py:77-118` |
| 导线区分 | `LINEAR_TYPES = (LINE, LWPOLYLINE, POLYLINE, ARC, SPLINE)`，长度已预计算入 `entity.length` | `classifier.py:123` |
| 设备规格 | `block_legend.spec`（人工/LLM 标定）或 `infer_spec_from_block()`（块名正则） | `specification.py:18` |
| 导线长度 | `measure.compute_item()` 已按 `Σ entity.length × factor` 出总长，且返回实体级 `detail` | `measure.py:38-66` |
| 文字标注 | TEXT/MTEXT 的文本+插入点已入库（`geom_json.text` / `geom_json.pos`） | `cad_parser.py:190-197` |
| 规格抽取 | `extract_specifications(texts)` 已存在（DN100/Φ50/SC20/mm²...） | `specification.py:7` + `aggregate.py:72-80` |

**真实图纸实证（01-LBH lighting system.dxf）：**

```
线缆图层（图层名 = 电缆型号标注）：
  00 aten line NHXMH 4x1.5   → 1631 条线实体
  00 aten line NHXMH 4x2.5   → 385 条
  00 aten line NHXMH 3x2.5   → 85 条
  00 aten line NHXMH 2x1.5   → 66 条

导线图层上的 TEXT/MTEXT（回路标识，非规格）：
  00 aten sistem pano kuvvet | '{\fArial|b0|i0|c162|p34;LB.N.FOF-1.DP}'
  → 富文本前缀 {\f...;} + 纯文本 'LB.N.FOF-1.DP'（配电回路号）
```

**三个关键缺口：**

| 缺口 | 说明 | 影响 |
|------|------|------|
| ① 电缆型号正则缺失 | `extract_typical_sizes(["00 aten line NHXMH 4x1.5"])` → **`[]`**。`NxS` 格式（4×1.5：芯数×截面积）不在 `SIZE_PATTERNS` | 图层名里的型号抽不出 |
| ② 导线规格未入库 | `extractor.py` 线性对象段 `specification=""`，且不收集图层 TEXT | 工作台"规格"列导线恒为 "-" |
| ③ MTEXT 富文本未剥离 | 文本存的是 `{\fArial\|b0\|i0\|c162\|p34;LB.N.FOF-1.DP}`，需去格式化前缀 | 标注样本不可读 |

### 2.2 方案总览（三层：数据 → 服务 → UI/导出）

```
┌─ 数据层 ─────────────────────────────────────────────┐
│ ① aggregate.SIZE_PATTERNS 新增电缆型号正则            │
│    - NxS:   (\d{1,2})\s*[xX×]\s*\d{1,2}(?:\.\d+)?    │
│    - 型号前缀: (NHXMH|NH-YJV|WDZ-YJY|ZR-YJV|YJV|BVR|BYJ|RVVP|...)\s*NxS │
│ ② specification 新增 normalize_annotation()：剥离      │
│    MTEXT 富文本 {\f...;} 前缀                          │
│ ③ extractor 线性段：收集 图层名 + 图层 TEXT/MTEXT 文本  │
│    → extract_specifications → 填 specification       │
├─ 服务层 ─────────────────────────────────────────────┤
│ ④ app/takeoff/boq_detail.py（新）                     │
│    boq_item_detail(item_id, sheet_id) → {            │
│      devices: [{block_name, spec, count}],           │
│      cables:  [{layer, spec, length_m, text_samples}],│
│      labels:  [text...]  // 未匹配规格的标注样本       │
│    }                                                 │
├─ UI/导出层 ──────────────────────────────────────────┤
│ ⑤ BoqTable 增加「明细」入口（双击行 / 右键 / 列按钮）    │
│ ⑥ BoqDetailDialog（复用 BaseDialog）                 │
│    上表：设备明细（块名/规格/数量）                     │
│    下表：导线明细（图层/规格型号/总长度/标注样本）        │
│ ⑦ report.py 导出第二 sheet「条目明细」                 │
└──────────────────────────────────────────────────────┘
```

### 2.3 数据层细节

**① 电缆型号正则（新增到 `aggregate.SIZE_PATTERNS`）：**

```python
re.compile(r"(?:NHXMH|NH-YJV|NH-YJY|WDZ-YJY|WDZ-YJE|ZR-YJV|ZR-YJY|YJV|YJY|BVR|BV|BYJ|RVVP|RVV|RVS|KYJV|KVV|DJYPVP)\s*\d{1,2}\s*[xX×]\s*\d{1,2}(?:\.\d+)?", re.IGNORECASE),
re.compile(r"\d{1,2}\s*[xX×]\s*\d{1,2}(?:\.\d+)?", re.IGNORECASE),   # 通用 NxS（配合上一条兜底）
```
效果预期：`00 aten line NHXMH 4x1.5` → `NHXMH 4x1.5`（或 `4X1.5`）。

**② 标注文本规范化（`specification.py` 新增）：**

```python
MTEXT_PREFIX = re.compile(r"^\{\\f[^;]*;")          # {\fArial|b0|i0|c162|p34;
def clean_annotation(text: str) -> str:
    t = MTEXT_PREFIX.sub("", text or "")
    t = t.replace("\\P", " ").replace("^J", " ")     # 段落符
    return t.strip()
```

**③ 导线规格提取（`extractor.py` 线性段改造）：**

```python
# 线性段收集文本源：图层名（最强信号，本图纸实证）+ 图层内文字标注
text_src = [lname]                                   # 图层名本身携带型号
text_src += [clean_annotation(json.loads(e.geom_json).get("text", ""))
             for e in ents if e.dxf_type in ("TEXT", "MTEXT")]
specs = extract_specifications(text_src)
specification = " ".join(specs)                      # 或 " / ".join
```

**④ 服务层 `boq_item_detail()` 返回结构：**

```python
{
  "item_id": 12, "code": "C12", "description": "照明配线",
  "unit": "m", "rule_type": "length",
  "devices": [   # 设备：INSERT 块聚合
    {"block_name": "CAM_4MP_DOME", "spec": "4MP", "count": 23, "legend_confirmed": True},
  ],
  "cables": [    # 导线：按 图层+规格 分组
    {"layer": "00 aten line NHXMH 4x1.5", "spec": "NHXMH 4x1.5",
     "length_m": 482.3, "entity_count": 1631, "text_samples": ["LB.N.FOF-1.DP", ...]},
  ],
  "labels": ["未匹配规格的标注样本…"],   # 供人工补全
  "total_qty": 0.0, "count": 0,        # 复用 measure.compute_item
}
```

### 2.4 UI 层细节

| 组件 | 设计 |
|------|------|
| BoqTable | 表头加第 9 列「明细」；双击行或点「明细」按钮 → 打开 BoqDetailDialog。保持 WCAG（图标+文字） |
| BoqDetailDialog | 复用 `BaseDialog`（Header 固定 + QScrollArea 内容区 + Footer 固定）。上表设备、下表导线，均 `setAlternatingRowColors`；导线表列：图层 / 规格型号 / 长度(m) / 实体数 / 标注样本（换行+tooltip） |
| mapping_panel | `set_result()` 摘要区追加「设备 n 类 · 导线 n 类（总长 X m）」 |
| 空态 | 无映射：明细对话框提示"该条目尚未映射实体" |

### 2.5 导出层细节

`report.export_report` 增加第二 sheet「条目明细」：
- 列：编号 / 描述 / 类别(设备|导线) / 块名或图层 / 规格型号 / 数量或长度(m) / 标注样本
- 与主 sheet 逐条对应（按 item.code 分组）

### 2.6 验收标准

- 打开 01-LBH lighting system.dxf 导入对应 BOQ：照明配线条目下钻可见 `NHXMH 4x1.5`（长度 = 1631 条线总长）、`NHXMH 4x2.5` 等分组，规格与图层名一致。
- 设备条目下钻：块名 + 规格（图例确认优先）+ 数量。
- 导线标注样本显示为纯文本（无 `{\f...}` 前缀）。
- 无文字标注的图层：spec 留空、标注样本列为空，不报错。
- 全部既有测试通过 + 新增 boq_detail 单测。

---

## 三、改动文件清单（估算）

| 文件 | 改动 | 复杂度 |
|------|------|--------|
| `app/db.py` | 4 处排序（distinct_layers/distinct_blocks/collect_blocks/get_engineering_objects） | 低 |
| `app/ui/main_window.py` | open_drawing 2 处 rebuild 排序 | 低 |
| `app/takeoff/aggregate.py` | SIZE_PATTERNS 新增电缆正则 | 低 |
| `app/engineering/specification.py` | `clean_annotation()` + 复用 | 低 |
| `app/engineering/extractor.py` | 线性段规格提取 | 中 |
| `app/takeoff/boq_detail.py`（新） | 明细聚合服务 | 中 |
| `app/ui/boq_table.py` | 明细列 + 双击 | 低 |
| `app/ui/boq_detail_dialog.py`（新） | 明细对话框 | 中 |
| `app/report.py` | 第二 sheet | 低 |
| 测试 | `test_boq_detail.py`（新）+ 回归 | 中 |

**预估：需求 A 半小时级；需求 B 主体 1 天级（含验证）。**

---

## 四、待确认项（实施前）

1. **导线规格优先取图层名还是 TEXT 标注？**（实证：本图纸图层名携带型号、TEXT 是回路号）建议优先级：**图层名 → TEXT/MTEXT 标注 → 空**。是否需把"回路号"单独成列（而非混入标注样本）？
2. **设备明细的规格列**：沿用现有 `block_legend.spec`（人工/LLM 标定优先）+ 块名推断兜底，是否满足？还是需要 LLM 从块属性提取？
3. **导出**：明细 sheet 是否需要（默认加，成本低）。
4. **排序范围**：确认仅图层/块（图纸列表 `get_sheets` 保持按导入顺序）。
