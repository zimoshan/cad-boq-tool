# CAD·BOQ Web 化架构设计 v2.0

| 项 | 内容 |
|---|---|
| 版本 | v2.0（取代 v1.0；v1.0 引用了本任务范围外的其他文档，已全部剔除并重推结论） |
| 日期 | 2026-08-29 |
| 设计输入 | ① `docs/CAD_BOQ_Web化改造_数据资产与实施方案_v1.0.md`（下称「实施方案」）<br>② `cad-boq-tool` 代码与运行时数据库**实测**<br>③ LBH 项目实战工作链 `https://workbuddy.link/p/mOPmZmsOPf2kBCEBcKtafA`（下称「实战链路」）+ 本机 `D:\ifc_2026-08-24_0536` 复核 |
| 设计原则 | **演进而非重写**——`app/cad`、`app/binding`、`app/takeoff` 等核心算法零重写，只抽 Service 边界 + 替换展示层；但**能力缺口必须补齐**（见 ADR-07） |
| 状态 | 待确认（第 10 节列出 13 项；其中 4 项阻塞定稿） |

> **v2.0 相对 v1.0 的三处实质性推翻**
> 1. v1.0 称「仓库内 0 个 JSON，Sprint 1 必须从 DWG 重解析」——**错**。37 张电气图的转储缓存、34 份坐标文件、去重并集、机械 6 份系统缓存**全在 `D:\ifc_2026-08-24_0536` 下**，可直接整理为 Dataset（详见 1.3、ADR-06）。
> 2. v1.0 称 B1「需用户提供表头结构才能修」——**信息已足够**。被解析的文件是 `Rev——1`（表头在 row 1），根因是**表头探测部分成功即被接受**，而非完全失败（详见 2.1）。
> 3. v1.0 把 `cad-boq-tool` 当作 Web 化的完整对象——**不成立**。LBH 四份清单的实际交付物是由 `D:\ifc_2026-08-24_0536` 下的临时脚本链产出的，`cad-boq-tool` 从未端到端跑通过（1 条 ACCEPTED、480 条 BOQ 全错）。架构对象需重新定义（ADR-07）。

---

## 1. 设计输入基线（实测）

### 1.1 代码资产（`cad-boq-tool`）

| 项 | 实测 |
|---|---|
| 业务层规模 | `app/**` **9,879 行**（不含 `app/ui/*`）；`app/db.py` 1,687 行为最大模块 |
| Qt 依赖 | **业务层零依赖**——`app/cad`、`app/binding`、`app/takeoff`、`app/engineering`、`app/boq`、`app/llm`、`app/measure.py`、`app/mapping.py` 均可被 FastAPI 直接 import |
| 模块清单 | `cad/`（reader, cad_parser, dwg, geometry, parse_cache）、`takeoff/`（orchestrator, aggregate, stream_aggregate, quality, classify, folder_pipeline, llm_*）、`binding/`、`engineering/`、`boq/`（boq_parser, writeback）、`llm/` |
| **缺失能力（grep 实测）** | `app/**` 全文**无** `accoreconsole` / `DXFOUT` / `INSUNITS` / `EXTMAX` —— 即「DWG 无头转换」与「单位自动标定」两项在代码里完全不存在 |
| 回写能力 | `app/boq/writeback.py` 仅 2 个函数（`write_back_quantities` / `reset_measured_qty`），**写的是自身 SQLite**，无 openpyxl、无公式保留 —— 实战要求的「原 Excel 保真回写」能力不存在 |
| 单位处理 | 仅 `app/measure.py:12` 的 `project_scale * sheet_scale * item.scale_factor` 手工比例，**无自动标定** |

### 1.2 运行时数据库

`~/.cad-boq-tool/projects.db`，**171.5 MB**（WAL，thread-local 连接池）。

| 表 | 实测 | 病灶 |
|---|---|---|
| project | 1 个：`Bengasi-hospital`（id=25） | 即 LBH 项目 |
| sheet | **4 张**（仅电气），最大 79,424 实体 | 占 LBH 电气图纸的 4/37 |
| entity | 184,325 | `bbox` 为 **TEXT(JSON)**，无法空间查询 |
| **boq_item** | **480 条，全部错误** | `code` 100% 为占位 `item-N`；`description` 40 条为字面 `"None"`；`original_qty` **100% 为 0.0**。详见 2.1 |
| engineering_object | 64 | |
| binding_candidate | 392（ACCEPTED **1** / PENDING 32 / SUPERSEDED 359） | 仅 1 条走完全流程 |
| llm_run | 996（binding 852 / classify 144） | 审计数据完整 |
| mapping | 95 | |
| symbol_library / block_legend | 5 / **0** | `block_legend` 空表 |

存储异常：`sheet` 表 **99.8 MB**（`blocks_json` 单图 **34 MB** 直接存 TEXT 列）；`entity` 59.6 MB。另有备份垃圾 **~4.7 GB**（2 份 1.6 GB + 3 份 440 MB）。

### 1.3 LBH 真实数据资产（本机核复）

**5 个专业图纸目录**（`D:\ifc_2026-08-24_0536\`）

| 目录 | 内容与规模 | 状态 |
|---|---|---|
| `latest drawing-electrical` | 53 个子目录，**37 DXF + 42 DWG** | 37 张已完成转储；49 号室外安防图已补转 |
| `latest drawing-Mechanical` | **5 个 DWG**（Domestic Water / Fire / HVAC Piping / Ventilation / Waste Water） | 已用 accoreconsole 转 DXF 至 `D:\mech_dxf\`，**1.53 GB**（vent 单图 485 MB） |
| `latest drawing-Medical` | 1 个 DWG：`MEDICAL-GAS-R4`（2026-01-28 修订版） | 已转 DXF（417 MB）并解析 |
| `latest drawing- Architecture & Interior` | `01_ARCHITECTURAL PROJECTS`、`02_INTERIOR DETAIL PROJECTS`、**`03_BOQ` 26 份设计院自算分项统计表**（门/洁具/墙面积/天花/地坪/幕墙/景观…） | **非 CAD 校核路线**：建筑核量用的是这 26 份 Excel，与清单口径天然对齐 → 核对率 83.5% |
| `latest drawing-Structure` | **153 个 DWG**，全部混凝土（基础/柱墙/挡土墙/模板/梁详图），**无钢结构详图** | 仅 5 条清单项，2 条可核 |

**4 份清单 + 4 份回填版**（结构已逐份实测）

| 清单 | 结构 | 关键锚点 |
|---|---|---|
| BOQ-001 电气 | 493 行 × 12 列（A–L），冻结 `A12`，**表头 row 11**，数据 12–486，49 合并格 | 列：Item / Section / Description / Brand / Unit / Bill qty(F) / Installed(G) / Qty remaining(H) / Material status(I) / Rate(J) / Amount(K=IF(J="","",H*J)) / Note(L)；`SUBTOTAL K488=SUM(K12:K486)`，`TOTAL K491=SUM(K488,K489,K490)`；Item 格式 `rNNN`；8 个 `ADD` 行（478–486）无 rNNN |
| BOQ-001 Rev1 | 483 行 × 12 列，冻结 `A2`，**表头 row 1** | **← `cad-boq-tool` 实际解析的是这一份**（删掉 9 行前言） |
| BOQ-002 机械 | 926 行 × 13 列（A–M），冻结 `A13`，752 数据行，160 分部标题，170 合并格 | Item 格式 `M-rNN`；**755 个 Amount 公式在 L 列**；SUBTOTAL r921 / TOTAL r924 |
| BOQ-003 建筑 | 716 项 / **692 计量条目**，24 分部，695 公式，39 合并格，冻结 `A13`，max_col 12 | 回填从 **M 列**起 |
| BOQ-004 结构 | **5 项**（S-r1~S-r5），max_col 9，19 合并格，冻结 `A10`，8 公式 | 回填从 **J 列**起 |

**已产出的解析缓存（可直接作为 Dataset 原料）**

| 位置 | 内容 |
|---|---|
| `latest drawing-electrical/01-LBH lighting system/_takeoff/` | **94 个 JSON，37 MB**：`dump_*.json` 37 份（按系统的图元/图层/块统计）、`pos_*.json` 34 份（块插入坐标）、`_dedup.json`（跨图去重并集）、`_tray_pts.json`（15 MB，桥架采样点） |
| `latest drawing-Mechanical/` | `mech3_{domestic,fire,hvac,vent,ww,medgas}.json` 6 份（2.3 MB，递归块展开后的图层/块清单）+ `boq2_items.json`（203 KB，752 条清单全量） |
| `latest drawing- Architecture & Interior/` | `_arch_backfill.json`、`_arch_probe.json`、`03_BOQ_json/`（26 份统计表抽取结果） |
| 脚本资产 | 电气 `_takeoff/` 30+ 个 py；机械 20+ 个 py；建筑 7 个 py；项目根 2 个（跨专业汇总） |
| 已沉淀技能 | `cad-electrical-takeoff`（SKILL.md 19.9 KB + 19 个脚本）、`cad-mep-boq-backfill`（SKILL.md 13.9 KB，**无 scripts 目录**） |

**实战核量成果**（四专业总览）

| 专业 | 计量条目 | 量化核对 | 核对率 | 吻合/基本吻合/偏差较大/需澄清/不可核 |
|---|---:|---:|---:|---|
| 001 电气 | 348 | 231 | **66.4%** | 140 / 0 / 91 / 9 / 107 |
| 002 机械 | 752 | 13 | **1.7%** | 5 / 5 / 3 / 1 / 738 |
| 003 建筑与室内 | 692 | 578 | **83.5%** | 560 / 7 / 11 / 0 / 114 |
| 004 结构 | 5 | 2 | **40.0%** | 2 / 0 / 0 / 0 / 3 |
| **合计** | **1,797** | **824** | **45.9%** | 707 / 12 / 105 / 10 / 962 |

### 1.4 核心发现：双轨现状

```
轨道 A（产品壳）  cad-boq-tool
  9,879 行业务层 · 零 Qt 依赖 · 完整的绑定/EO/LLM 框架
  但：4 张图 · 480 条 BOQ 全错 · 1 条 ACCEPTED · 无任何 LBH 交付产出
         │
         │  ← 缺口：DWG 无头转换 · 单位标定 · 跨图去重
         │     型号归一化 · 可核性判定 · Excel 保真回写
         │
轨道 B（实战链）  D:\ifc_2026-08-24_0536 下的临时脚本
  37 张电气图 + 6 个机械系统 + 26 份建筑统计表 + 医疗气体
  产出：4 份回填清单 + 4 份核量报告 + 跨专业总览
  代价：一次性脚本 · 硬编码路径 · 无回归 · 换项目要改三处正则
```

**这是本次架构设计要解决的真问题**：不是"给 cad-boq-tool 加个 Web 界面"，而是**把轨道 B 验证过的 7 段能力，工程化地装进轨道 A 的 Service 容器，再套 Web 外壳**。

### 1.5 对实施方案前提的修正

| 实施方案表述 | 实测 | 影响 |
|---|---|---|
| §7「当前已经产生的真实 LBH 图纸 JSON 不要废弃」 | **前提成立，但位置不在仓库**——在 `D:\ifc_2026-08-24_0536` 下，共 100+ 份缓存（约 40 MB） | Sprint 1 从「重解析」降级为「**整理 + 补漏**」，工作量大幅下降（ADR-06） |
| §7「整理为 `datasets/lbh/`」 | 目录结构照搬即可；**但 `source/dwg/` 需决策**（42 份电气 DWG + 153 份结构 DWG + 医疗 DWG 属客户资产） | 见待确认 D1 |
| §3「第一阶段保持 Python 核心算法不变」 | 成立：业务层零 Qt 依赖 | 但「算法不变」不等于「能力够用」，见 ADR-07 |
| §21「可核性必须是 Web 一级功能」 | **实战已充分验证**：机械 738 项不可核若强行给数 = 10 倍级误导 | 提升为 Phase 1 内容，不推迟（ADR-08） |

---

## 2. 阻塞项（Phase 0 必须先修）

### 2.1 B1 · BOQ 解析产生 480 条垃圾数据（根因已完全定位，可直接修）

**证据**：`boq_item` 480 条，`code` 100% = `item-N`，`original_qty` 100% = `0.0`，`description` 40 条 = `"None"`。

**被解析的文件是 `Rev——1.xlsx`**（表头在 **row 1**，冻结 `A2`）——不是 Rev0（表头在 row 11）。

**根因链（`app/boq/boq_parser.py:54-66` + `app/config.py:32-37`）**：

```python
for i, row in enumerate(rows[:5]):
    m = _detect_headers(row)
    if len(m) >= 2:            # ← 门槛过低：命中 2 列就接受
        header_idx, mapping = i, m; break
```

第 0 行（`Item / Section / Description / Brand / Unit / Bill qty / Installed …`）的逐列匹配结果：

| 列 | 表头 | 候选词表 | 结果 |
|---|---|---|---|
| A | `Item` | code 候选 = `编号/序号/item no/item no./code/no/no./item code` | **未命中**（裸 `item` 不在表内） |
| B | `Section` | — | 未命中 |
| C | `Description` | description 候选含 `description` | ✅ 命中 → `description=2` |
| D | `Brand` | — | 未命中 |
| E | `Unit` | unit 候选含 `unit` | ✅ 命中 → `unit=4` |
| F | `Bill qty` | original_qty 候选 = `数量/工程量/qty/quantity/original qty` | **未命中**（`billqty` 不在表内） |
| G | `Installed` | — | 未命中 |
| H | `Qty remaining` | `qtyremaining` ≠ `qty` | 未命中 |

`len(m)==2 ≥ 2` → **残缺映射被接受**，于是：

- `mapping` 无 `code` → `code=""` → 全部走 `f"item-{n}"` 占位分支（480/480 ✓）
- `mapping` 无 `original_qty` → `qty=0.0`（480/480 ✓）
- `desc = row[2]` → 分部标题行取到 `None` → `str(None)="None"`（40 条 ✓），数据行取到真实描述（440 条，如 `ADP` ✓）
- `unit = row[4]` → `set` 等真实单位 ✓
- `if not code and not desc: continue` 因 `desc="None"` 为真值而**失效**，分部标题行全部入库

**修复方案（信息已足够，无需再问）**：

1. `BOQ_HEADER_CANDIDATES["code"]` 补 `item`、`item #`、`ref`、`item ref`；
2. `BOQ_HEADER_CANDIDATES["original_qty"]` 补 `bill qty`、`bill quantity`、`contract qty`；
3. **提高接受门槛**：必须命中 `code` + `description` + `unit` + `original_qty` 四列中的**至少 3 列且含 `code`**，否则不静默兜底，返回错误交前端让用户手动指定表头行与列映射；
4. 表头扫描窗口 `rows[:5]` → `rows[:20]`（Rev0 表头在 row 11，将来导入 Rev0 会直接踩坑）；
5. `str(None)` 必须在 `str()` 前拦截，`None` → `""`；
6. **映射失败即报错，不再生成 `item-N` 占位码**。

### 2.2 B2 · BoqItem 模型缺字段（新增，B1 的连带）

实测 `BoqItem`（`app/models.py:48-59`）与 `boq_item` 表均无以下字段，而 LBH 四份清单**全部**依赖它们：

| 缺字段 | 为什么必须有 |
|---|---|
| `section`（分部名） | 实施方案 §21 可核性按分部组织；实战中 24/32/160 个分部是主要导航维度 |
| `brand` | 清单 D 列；实战中 `-kitli` 后缀 ↔ `+ BATTERY` 版本的区分依据 |
| `bill_qty` / `installed` / `qty_remaining` 三列分离 | 现只有 `original_qty` 一个。实战确认 **Amount = Qty remaining × Rate**，回填比的是 **Bill qty**（原合同量），二者混用直接算错偏差 |
| `row_index` 语义 | 现为 Excel 行号，但 `Item` 编号（`rNNN` / `M-rNN`）才是稳定主键——实战明确踩过「item 编号 ≠ 行号」的坑 |

### 2.3 B3 · 块几何 34 MB 存 SQLite TEXT

`sheet.blocks_json` 单图 34 MB，`sheet` 表 99.8 MB。单次 `get_sheets` 即可拖垮进程，Web 端 34 MB 响应不可接受。→ ADR-03。

### 2.4 B4 · `entity.bbox` 为 TEXT，无法空间查询

与实施方案 §13「根据 viewport 请求局部数据」直接冲突——无空间列则只能全量下发 79,424 实体。→ ADR-04。

### 2.5 B5 · 能力缺口：实战链路的 7 段能力有 6 段在 `app/` 中不存在

| 实战能力 | `app/` 现状 | 缺口 |
|---|---|---|
| S1 DWG→DXF 无头转换 | **无**（grep 无 `accoreconsole`/`DXFOUT`） | 全缺。ODA 本机装的是 GUI 版不能 headless；实战已验证 `accoreconsole.exe /i <dwg> /s <scr>` + `_.DXFOUT\n<path>\n16` 可行 |
| S2 大图转储缓存 | `cad/parse_cache.py` 有 | 基本可用，需按 ADR-06 对齐 Dataset 目录 |
| S3 单位自动标定 + 图纸类型判定 | **无**（grep 无 `INSUNITS`/`EXTMAX`）；只有手工 `scale_factor` | 全缺。实战教训：`$EXTMAX` 可能是**过期缓存值**（机械图头部显示 222 m，实际 1,705 m × 9,132 m），必须用实体实际范围复核 |
| S4 归集 + 型号归一化 + 图层黑名单 | `takeoff/orchestrator`、`aggregate` 有归集 | 缺归一化与黑名单。实战：欧式逗号 `3x2,5` vs 图层 `3x2.5` 未归一化 → 归集率 29%；归一化后 **95.9%**；`DETAIL/SECTION/LEGEND` 图层必须排除 |
| S5 跨图去重（并集，非相加） | **无** | 全缺。实战核心：同一批设备在 4–5 张图重复出现，必须按空间网格求并集 |
| S6 Item 编号映射（含组合降级） | `binding/matcher` 走 AI 路线 | 口径不同，需并存。实战：图纸未按规格分级时按组合计，组内其余行标「已并入第 N 行」 |
| S7 可核性判定 + Excel 保真回写 | **无**；`boq/writeback.py` 只写自身 SQLite | 全缺。实战：openpyxl 必须 `data_only=False` 保公式、只写新增列、不可克隆 `StyleProxy` |

### 2.6 B6 · 备份垃圾 ~4.7 GB

2 份 1.6 GB + 3 份 440 MB 备份。数据资产化前清理，后续由 Dataset 版本化承担可回溯职责。

---

## 3. 架构总览

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ Browser  (React 18 + TypeScript + Vite)                                   │
│  ┌────────────┬──────────────────────────────────┬─────────────────────┐  │
│  │ 左栏        │  中栏：CAD Viewport              │ 右栏：任务面板       │  │
│  │ 图纸/图层   │  Canvas 2D + 空间网格索引 + LOD   │ BOQ / 绑定 / 属性    │  │
│  │ 块树/搜索   │  拾取·框选·平移·缩放·高亮        │ 证据 / 可核性 / 历史 │  │
│  └────────────┴──────────────────────────────────┴─────────────────────┘  │
│  状态：TanStack Query（服务端态） + Zustand（视图态/选择集）                │
└────────────────────────────┬──────────────────────────────────────────────┘
                             │ REST / JSON (gzip)          ▲ SSE（job 进度）
┌────────────────────────────▼──────────────────────────────────────────────┐
│ FastAPI  (web/server.py, uvicorn, --workers 1)                            │
│  routers/    薄层：参数校验 · 序列化，不含业务规则                         │
│  services/   厚层：业务编排（从 app/ 提取 + 补齐 B5 六段能力）              │
│  jobs/       JobManager：后台任务 + 进度事件 + SSE 广播                     │
│  schemas/    Pydantic v2 模型 = 前后端唯一类型契约（TS 由 OpenAPI 生成）    │
└────────────────────────────┬──────────────────────────────────────────────┘
                             │ 直接 import（算法不改）
┌────────────────────────────▼──────────────────────────────────────────────┐
│ app/  （现有业务层，抽边界不改算法）                                       │
│   cad/  engineering/  binding/  takeoff/  boq/  llm/                       │
│   db.py  measure.py  mapping.py  report.py  config.py  models.py          │
└────────────────────────────┬──────────────────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────────────────────┐
│ Data Layer                                                                │
│   SQLite      业务真相源：project/drawing/BOQ/EO/Binding/Job               │
│   Artifacts   大二进制：块几何(.json.gz) · render cache · 上传原件          │
│   Dataset     只读回归资产：现有缓存整理 + Parquet + manifest + labels      │
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
| R6 | **任何写回原清单的操作，不得触碰原表已有列**（实战铁律，见 6.4） |

---

## 4. 架构决策记录（ADR）

全部裁决依据 = 实施方案 + 代码/数据实测 + 实战链路，不引用其他文档。

### ADR-01 · 前端 React + TypeScript；渲染 Canvas 2D，WebGL 延后

实施方案 §3 明确 `React + TypeScript` + `Canvas/WebGL`；§12 要求 Entity Schema 前后端统一定义。

**裁决**：采纳 React 18 + TS + Vite；**渲染引擎选 Canvas 2D**，WebGL 作为可插拔后置实现。

理由：
1. TS 类型契约 + OpenAPI 代码生成是把「Entity Schema 统一」工程化的唯一可行手段；
2. 实测单图最大 **79,424 实体**，未达需 WebGL 的量级；实施方案 §13 的「viewport 局部请求」用 Canvas 2D + 空间索引即可达成；
3. 预留 `RenderBackend` 接口，Canvas2D 为默认实现，避免过早优化。

### ADR-02 · 运行时存储 SQLite 唯一；Parquet 仅作 Dataset 归档

实施方案 §6 把 Parquet 列为「大量 CAD Entity」存储。实测：全项目实体量约 18 万（已导入）+ 百万级（全量），SQLite 单表在恰当索引下完全胜任。

**裁决**：
- **运行时**：SQLite（B4 修复后支持空间查询）。不引入 Parquet 作为在线存储——会多出一套读写路径与一致性问题，收益不成立。
- **Dataset**：Parquet 作**只读归档与离线分析**（实施方案 §6 的 Offline Analysis 用途），由导出脚本从缓存生成。
- **交换/调试**：JSON，按实施方案 §11 拆 `metadata / layers / blocks / entities`。

### ADR-03 · 块几何外置（修 B3）

`sheet.blocks_json` → `artifacts/blocks/<project_id>/<sheet_id>__blocks__v<n>.json.gz`；DB 仅留 `blocks_path` + `blocks_sha256` + `blocks_count`。

预期：`sheet` 表 99.8 MB → < 100 KB，DB 总量降至约 70 MB。API 侧 `GET /api/sheets/{sid}/blocks` 流式返回 gzip，前端按块名惰性索引。

### ADR-04 · 空间列 + 视口查询（修 B4，支撑实施方案 §13）

`entity` 表新增 `min_x/min_y/max_x/max_y` REAL 四列 + 复合索引 `(sheet_id, min_x, max_x, min_y, max_y)`；`db.replace_entities` 写入时同步填充。

```sql
SELECT id, handle, dxf_type, layer, block_name, bbox, length, area, color, geom_json
FROM entity
WHERE sheet_id = ?
  AND max_x >= ? AND min_x <= ?
  AND max_y >= ? AND min_y <= ?
  AND layer IN (...)
LIMIT ?;
```

两级加载：

| 图纸规模 | 策略 |
|---|---|
| ≤ 20,000 实体 | 整图一次下发（gzip 后约 3–8 MB），前端建网格索引做裁剪与拾取 |
| > 20,000 实体 | 按视口 `?bbox=` 拉取（前端节流 250 ms）；`TEXT/HATCH/标注` 默认延迟加载 |

### ADR-05 · 异步任务：进程内 JobManager + SSE

实施方案 §30 允许「第一阶段继续使用 ProcessPool，不必立即引入 Redis/Celery」。

**裁决**：SSE 而非 WebSocket。进度推送是**单向**的，SSE 语义匹配、断线重连由浏览器原生处理、零额外依赖。

```text
POST /api/jobs                    → {job_id}  （202 Accepted）
GET  /api/jobs/{id}/stream        → text/event-stream: progress / done / error
GET  /api/jobs/{id}               → 状态查询（补偿断连）
```

Job 类型：`convert_dwg` / `parse_drawing` / `import_folder` / `generate_candidates` / `embedding_build` / `cross_sheet_dedup` / `batch_takeoff` / `recompute_quantity` / `writeback_boq` / `dataset_export`。

并发：同步路由用 `def`（FastAPI 自动放线程池）；CPU 密集解析走 `anyio.to_thread` / ProcessPool；SQLite WAL + `busy_timeout` + 单 worker。

### ADR-06 · Dataset 直接整理现有产物，不从 DWG 重解析（新）

实测已有可直接使用的缓存：电气 94 份 JSON（37 MB）+ 机械 6 份（2.3 MB）+ 建筑 `03_BOQ_json/`。

**裁决**：Sprint 1 的工作是「**整理 + 补漏 + 结构化**」而非「重解析」：

| 工作 | 量级 | 说明 |
|---|---|---|
| 整理现有缓存 → `datasets/lbh/parsed/json/` | 100+ 份，约 40 MB | 路径规范化 + 重命名 + manifest 登记 |
| 补漏：尚未转储的图纸 | 电气 42−37 = 5 份 DWG 待转；结构 153 份（仅 5 条清单项，可暂缓） | 需先跑 S1 转换 |
| 生成 Parquet 归档 | 由 JSON 导出，不重新读 DXF | 秒级 |
| **labels/** 从 4 份回填清单反向抽取 | 824 条量化核对 + 14 项澄清 + 105 项重大偏差 | **这是最有价值的资产**：直接成为 L3/L4 回归的正负样本 |

收益：Sprint 1 从「数小时 + 数 GB」降为「约半小时 + 40 MB」，且**基线是实战已验证过的**（824 条核对结论），而非新解析的未验证数据。

### ADR-07 · Web 化的首要对象 = 实战链路，cad-boq-tool 作容器（新，核心）

**问题**：实施方案 §3 说「保持 Python 核心算法不变，仅增加 API 层和前端」。但实测显示：LBH 四份清单的交付物**不是** cad-boq-tool 产出的，而是临时脚本链产出的；cad-boq-tool 的绑定/EO/LLM 框架从未在真实数据上端到端跑通（1 条 ACCEPTED、BOQ 全错）。

**裁决**：

1. **Service 容器**沿用 `app/` 的划分（不重写算法）；
2. **但每个 Service 必须补齐 B5 的能力缺口**，补齐来源是实战链路已验证的 7 段能力（S1–S7）与其踩坑记录；
3. **验收口径以实战成果为准**：Phase 4 的出口标准不是「跑通流程」，而是「**在 LBH 电气专业上重现 66.4% 核对率与 140 条吻合结论**」，机械/建筑/结构同理。

这条 ADR 把「演进而非重写」从**代码层面**升级到**能力层面**——代码不重写，但能力必须对齐。

### ADR-08 · 可核性闸门进入 Phase 1（不推迟）

实施方案 §21 已把可核性定为「Web 一级功能」。实战提供了决定性证据：

- 机械专业 **738 项不可核**：末端支管全画在图块内部，模型空间线长只有干管，给水实测 2,301 m vs 清单 23,412 m，**覆盖率不足 10%**；
- 若强行回填数字 = 10 倍级误导；实战选择标注「不可核 + 具体原因」（无对应图块 471 / 长度面积不可量取 158 / 无图纸 66 / 并入分组 31 / 按套计 13）。

**裁决**：可核性判定的**表结构在 Phase 1（数据资产）就建立**，实现在 Phase 4 业务闭环完成。理由：可核性本身就是 Business Data 的一张表，地基阶段预留结构成本最低；推迟实现则 Phase 4 会重新产出误导性数字。

### ADR-09 · BOQ 模型扩展：section + 三数量列 + Item 主键（修 B2）

`BoqItem` / `boq_item` 表新增：`section`、`brand`、`bill_qty`、`installed`、`qty_remaining`、`item_key`。

- `item_key` = 清单 `Item` 列原值（`rNNN` / `M-rNN` / `ADD#<row>`），**作为映射主键**，`row_index` 降为辅助；
- 计价口径：**Amount = Qty remaining × Rate**，回填比对基准 = **Bill qty**（原合同量）。二者在 LBH 三份清单里是不同列，混用直接算错偏差；
- 分部（`section`）为可核性分组与报告导航维度。

---

## 5. 数据架构（实施方案 §5 三层模型落地）

### 5.1 Canonical Data — 精确层

| 实体 | 存储 | 说明 |
|---|---|---|
| `drawing` | SQLite | sha256、**discipline**、**drawing_type**（plan/schematic/detail/legend/schedule）、level、zone、revision、scale、parser_version、**units**（ADR-07 S3） |
| `layer` | SQLite | name + color + entity_count + **is_excluded**（DETAIL/LEGEND 黑名单，ADR-07 S4） |
| `block_ref` | SQLite | block_name + `blocks_path`（ADR-03）+ insert_count + **resolved_kind**（匿名动态块反推的语义类别，如"阀门符号"/"器具接点"） |
| `entity` | SQLite | 见下方 Schema |
| `measurement` | SQLite (`entity.length/area`) | 解析期预计算；**长度单位由 `drawing.units` 决定**（电气 cm / 机械 mm），换算在读取层统一 |

**Entity Schema（对照实施方案 §12）**

```jsonc
{
  "schema_version": "cad-1.0",
  "entity_id": 2014789,
  "handle": "55",                  // DWG handle，跨解析稳定，溯源主键
  "type": "LWPOLYLINE",
  "sheet_id": 75,
  "layer_name": "00 aten line NHXMH 4x1.5",
  "layer_id": null,                // 【Phase 1 回填】ADR-04 之后建立 layer 表
  "block_id": null,
  "bbox": [28520.0, -2323.43, 41520.0, 5986.57],
  "geometry": { "type": "lwpolyline", "points": [[...]], "closed": true },
  "measurement": { "length": 34310.0, "area": 0.0, "unit": "cm" },   // 单位显式携带
  "attributes": {},                // INSERT 的 ATTRIB（实施方案 §24）
  "source": { "drawing_id": 75, "parser": "ezdxf", "parser_version": "1.4" }
}
```

演进说明：实施方案 §12 要求 `layer_id` 引用而非重复 `layer_name`。18 万实体直接改名风险过高，采取两步走——Phase 1 建 `layer` 表并回填 `layer_id`，Phase 4 后将 `layer_name` 降级为冗余。

### 5.2 Render Data — 高性能层（Artifacts，可删除重建）

```text
artifacts/render/<project_id>/<sheet_id>/
├── overview.json          # 全图 bbox、按类型计数、图层摘要
├── grid_index.json        # 服务端预建均匀网格索引（>5 万实体时生成）
└── tiles/                 # 【延后】仅当单图 > 10 万实体启用
```

原则：**原始 CAD 数据为「精确」，Render Data 为「高性能」**（实施方案 §14）。MVP 不预生成 tiles。

### 5.3 Business Data — 业务层

现有：`project / sheet / entity / boq_item / mapping / engineering_object / binding_candidate / llm_run / project_config / llm_settings / symbol_library`

新增（Phase 1 建表，Phase 4 实现）：

| 表 | 用途 | 依据 |
|---|---|---|
| `drawing_type` | plan / schematic / detail / legend / schedule | ADR-07 S3 |
| `takability` | MEASURABLE / GROUP_ONLY / NOT_MEASURABLE / NO_DRAWING / VERSION_CONFLICT / PROVISIONAL | ADR-08、实施方案 §21 |
| `coverage_check` | 图纸总量 vs 清单量对账 | 实施方案 §21 |
| `cross_sheet_dedup` | 跨图去重并集结果与判定方法 | ADR-07 S5 |
| `spec_match` | EXACT / NORMALIZED_EQUAL / COMPATIBLE / UNKNOWN / CONFLICT | 实施方案 §19 |
| `confidence_calibration` | 置信度校准样本与参数 | 实施方案 §20 |
| `job` | 异步任务状态与进度 | ADR-05 |
| `writeback_audit` | 保真回写审计：原文件 sha256、改动列范围、公式/合并格校验结果 | ADR-07 S7 |

### 5.4 存储分工

| 介质 | 定位 | 可变性 | 内容 |
|---|---|---|---|
| DWG | Original Source | 只读 | 42 电气 + 153 结构 + 1 医疗 + 5 机械（待确认是否入库，D1） |
| DXF | Derived Conversion Artifact | 可重建 | 37 电气（已有）+ 5 机械（`D:\mech_dxf`，1.53 GB） |
| SQLite | **业务唯一可写真相源** | 读写 | 上表全部 |
| JSON | 交换 / Dataset / API | Dataset 只读 | metadata/layers/blocks/entities |
| Parquet | Dataset 归档 / 离线分析 | 只读 | entity 快照 |
| Artifacts | 大二进制 + Render Cache | 可删除重建 | 块几何 / tiles / 上传原件 |
| Dataset | **回归测试资产，运行时禁止覆盖** | 只读（版本递增） | `datasets/lbh/` |

---

## 6. 后端架构

### 6.1 Service 划分（容器沿用 `app/`，能力按 ADR-07 补齐）

| Service | 复用现有模块 | 需补齐的实战能力 |
|---|---|---|
| `ConversionService` | — | **S1**：`accoreconsole` 无头 DWG→DXF（`_.DXFOUT\n<path>\n16`）；ODA GUI 版不可 headless 已是实测结论 |
| `DrawingService` | `cad/reader`、`cad/cad_parser`、`cad/dwg`、`cad/parse_cache`、`import_folder` | **S3**：`$INSUNITS` 单位标定 + 实体实际范围复核（头部 `$EXTMAX` 可能过期）；图纸类型判定；块几何外置 |
| `GeometryService` | `db.get_entities` + ADR-04 | 视口查询、图层/块统计、LOD |
| `EoService` | `engineering/extractor`、`classifier`、`specification`、`llm_classify` | 匿名动态块（`*U3`/`*U5`）内容探测反推语义类别 |
| `BoqService` | `boq/boq_parser` | **B1/B2 修复**、ADR-09 模型扩展、分部解析 |
| `BindingService` | `binding/matcher`、`candidate_aggregator`、`rule_matcher`、`embedding_matcher`、`llm_matcher` | 型号归一化（欧式逗号 `3x2,5` ↔ `3x2.5`）、图层黑名单 |
| `ReviewService` | `binding/reviewer` | **唯一生效通道**；正负样本沉淀 |
| `QuantityService` | `measure.compute_item`、`mapping`、`takeoff/aggregate`、`takeoff/quality` | **S5 跨图去重**（网格并集；禁止「占格归属法」，该方法有 `STEP/CELL` 系统性低估缺陷）；双边线线状设备中心线重建 |
| `TakabilityService` | 新增 | 图纸类型 + 可核性闸门 + 覆盖率 + 粒度对齐 |
| `AiService` | `llm/runner`、`llm/embeddings`、`llm/audit`、`takeoff/llm_backends` | `llm_run` 全量审计；超时重试与 fallback |
| `CalibrationService` | 新增 | 综合置信度（实施方案 §20） |
| `StandardProfileService` | 新增 | `cad_standard/layer_rules.json` 等 5 份规则集（实施方案 §26） |
| `ReportService` | `report.export_*`、`boq/writeback` | **S7 Excel 保真回写**（`data_only=False` 保公式、只写新增列、不克隆 `StyleProxy`、失败回退） |
| `DatasetService` | 新增 | 现有缓存整理（ADR-06）、manifest、完整性校验 |

### 6.2 实战链路 → Service 映射（ADR-07 落地视图）

```text
S1 DWG→DXF           ConversionService        ← 全新建
S2 转储缓存          DrawingService            ← 复用 parse_cache
S3 单位/类型标定     DrawingService            ← 全新建（INSUNITS + 实体范围复核）
S4 归集+归一化+黑名单 QuantityService/Standard ← 部分新建
S5 跨图去重（并集）  QuantityService           ← 全新建（核心）
S6 Item 编号映射     BindingService/BoqService ← 口径并存
S7 可核性+保真回写   TakabilityService/Report  ← 全新建
```

### 6.3 候选生成管线（实施方案 §18）

现状：`embedding TOP-15` + `rule MAX-5`，LLM 只在子集内精排，召回被过早截断。

```text
Historical（历史确认）∪ Rule ∪ Embedding ∪ Lexical
   ↓ 去重 + 负样本抑制
   ↓ Top 20（从 15 放宽）
   ↓ LLM 精排 → Top 5
   ↓ PENDING 写入 binding_candidate
   ↓ 人工确认 → mapping + knowledge
```

硬约束（实施方案 §36）：AI 只生成 `PENDING`；人工确认后才写正式 `mapping`；Reject 必须形成负样本回灌抑制；规格 CONFLICT 强制 `needs_review`，**LLM 的文字理由不得覆盖硬冲突**。

### 6.4 Excel 保真回写契约（实战铁律，写入 R6）

| 规则 | 内容 |
|---|---|
| W1 | `openpyxl.load_workbook(data_only=False)`——`data_only=True` 会丢掉全部公式 |
| W2 | 只写**新增列**，绝不触碰原表任何已有列（回填起始列 = 原 `max_col + 1`） |
| W3 | 新增表头**不可克隆** `StyleProxy`（会抛异常），直接给新样式 |
| W4 | 保存前校验：公式数、合并格数、冻结窗格与原始一致；写入后 diff 原列 = 0 |
| W5 | 文件被 Excel 占用导致保存失败时，回退到 `<原目录>/_takeoff/` 并显式告知 |
| W6 | 写入 `writeback_audit`：原文件 sha256、新增列范围、校验结果 |

各清单回填起始列（实测）：BOQ-003 → **M**；BOQ-004 → **J**；BOQ-002 → **N**（原 13 列）；BOQ-001 → **M**（原 12 列）。

### 6.5 目录结构

```text
web/
├── server.py            # FastAPI 入口：GZip、CORS、静态、路由、lifespan
├── deps.py              # 依赖注入
├── jobs/{manager,tasks}.py
├── routers/             # projects drawings geometry boq bindings review
│                        # quantity takability takeoff report datasets jobs
├── services/            # 见 6.1，每个 Service 一个文件
├── schemas/             # Pydantic v2（TS 类型由 OpenAPI 生成）
├── static/              # Vite build 产物（gitignored）
└── start_web.bat

web-frontend/
└── src/
    ├── api/             # generated client + hooks
    ├── cad/             # RenderBackend / Canvas2DBackend / SpatialGrid / Viewport / drawEntity
    ├── panels/          # 图纸 预检 标定 映射 AI绑定 计量 可核性 报告
    ├── store/           # Zustand
    └── App.tsx
```

### 6.6 API 契约

| 方法 | 路径 | Service |
|---|---|---|
| GET/POST | `/api/projects`、`/api/projects/{pid}` | DrawingService |
| POST | `/api/projects/{pid}/drawings/convert`（DWG→DXF）→ Job | ConversionService |
| POST | `/api/projects/{pid}/drawings/upload` → Job | DrawingService |
| GET | `/api/drawings/{sid}`、`/metadata`、`/layers`、`/blocks`、`/overview` | GeometryService |
| GET | `/api/drawings/{sid}/viewport?bbox=&layers=&types=&limit=` | GeometryService |
| POST/GET/PATCH | `/api/projects/{pid}/boq` | BoqService |
| GET | `/api/boq/{iid}/measure?sheet=` | QuantityService |
| POST | `/api/projects/{pid}/dedup/cross-sheet` → Job | QuantityService |
| POST | `/api/projects/{pid}/binding/candidates` → Job | BindingService |
| POST | `/api/candidates/{cid}/confirm` \| `/reject` | ReviewService |
| GET/POST | `/api/projects/{pid}/takability` | TakabilityService |
| POST | `/api/projects/{pid}/takeoff` → Job | QuantityService |
| POST | `/api/projects/{pid}/writeback` → Job | ReportService（W1–W6） |
| GET | `/api/projects/{pid}/report.xlsx` | ReportService |
| GET/POST | `/api/datasets/{dsid}/export` \| `/validate` | DatasetService |
| POST/GET | `/api/jobs`、`/api/jobs/{id}`、`/api/jobs/{id}/stream` | JobManager |

统一约定：JSON `ensure_ascii=False`；大响应 GZip；错误 `{detail, code, trace_id}`。

---

## 7. 前端架构

### 7.1 布局（实施方案 §27）

```text
┌────────────────────────────────────────────────────────────┐
│ 项目 ▾ | 打开 | 保存 | 更多                                 │
├────────────────────────────────────────────────────────────┤
│ 图纸 | 预检 | 标定 | 映射 | AI绑定 | 计量 | 可核性 | 报告    │
├──────────┬──────────────────────────────┬──────────────────┤
│ 图纸/图层 │        CAD Canvas            │ 当前任务面板      │
│ 块树/搜索 │                              │ BOQ / 绑定 / 属性 │
├──────────┴──────────────────────────────┴──────────────────┤
│ 当前图纸 | 模式 | 实体数 | 单位 | 可核率 | 状态              │
└────────────────────────────────────────────────────────────┘
```

相对实施方案 §27 增加两点：**「可核性」提为一级页签**（ADR-08）；**状态栏显示当前图纸单位**（电气 cm / 机械 mm 混用是实战踩过的坑）。

### 7.2 渲染管线（对照 `app/ui/canvas.py` 逐函数翻译）

| 桌面函数 | Web 实现 |
|---|---|
| `to_scene()`（Y 翻转） | `world→screen` 变换矩阵 |
| `build_geom_item()` | `drawEntity()`：line / polyline / lwpolyline / spline / circle / arc(2° 采样) / ellipse / hatch / text / insert / point |
| `_collect_block` + `make_block_group()` | `drawInsert()`：读 `blocks_path` → 旋转/缩放/平移 → 派发 |
| `zoom_fit / zoom_step / 锚点平移` | `setTransform` + 光标中心缩放 |
| `entities_from_rect()` / `entity_at()` | `SpatialGrid` 裁剪与命中 |
| `_update_lod` | PPU 阈值切换抗锯齿与简化绘制 |
| `highlight / flash / show_tag` | 高亮 + 其余 opacity 0.22 + 绝对定位 DOM 浮标签 |

### 7.3 状态模型

| 类别 | 方案 | 内容 |
|---|---|---|
| 服务端态 | TanStack Query | 项目/图纸/图层/BOQ/候选/计量；缓存失效与 Job 完成事件联动 |
| 视图态 | Zustand | 视口变换、选择集、可见图层/类型、当前模式 |
| 实时 | SSE | Job 进度；绑定候选数变化 |

### 7.4 性能预算（对照实施方案 §36）

| 指标 | 目标 |
|---|---|
| 首屏 overview | < 800 ms |
| 小图（≤2 万实体）整图可交互 | < 2 s |
| 大图（7.9 万实体）视口拉取→渲染 | < 500 ms（节流 250 ms） |
| 平移/缩放帧率 | ≥ 30 fps |
| 分辨率 | 1280×720 / 1920×1080 / 2560×1440 均可用 |

---

## 8. 数据集与回归（实施方案 §7–§9，按 ADR-06 调整）

### 8.1 目录

```text
datasets/
└── lbh/
    ├── README.md
    ├── manifest.json
    ├── source/
    │   ├── dwg/                      # 【待确认 D1】是否入库（客户资产）
    │   └── boq/                      # 4 份原始清单（建议入库：45+75+67+7 KB）
    ├── converted/dxf/<version>/      # 37 电气 + 5 机械（1.53 GB，建议软链接，D2）
    ├── parsed/
    │   ├── json/<parser_version>/    # 现有 100+ 份缓存整理而来（ADR-06）
    │   └── parquet/<parser_version>/
    ├── render/<drawing_id>/
    ├── labels/
    │   ├── bindings/  rejected_bindings/
    │   ├── takability/               # ★ 824 条量化核对结论（从 4 份回填清单反向抽取）
    │   ├── drawing_types/
    │   └── specifications/
    ├── expected/quantities/          # ★ 824 条图纸实测值 = 天然基线（D3 确认口径）
    ├── clarifications/               # 14 项需发函澄清 + 105 项重大偏差
    └── snapshots/
```

### 8.2 Manifest（在实施方案 §8 基础上补解析环境字段）

```jsonc
{
  "dataset_id": "LBH-2026-08",
  "project": "Euesperides Medical Hospital",
  "schema_version": "cad-1.0",
  "parser_backend": "ezdxf",           // 实战链路实际用的是 ezdxf
  "backend_version": "x.y.z",
  "source_revision": "R4",
  "disciplines": ["Electrical", "Mechanical", "Architectural", "Structural", "Medical"],
  "drawings": [{
    "drawing_id": "LBH-E-01-LIGHTING-MAIN",
    "filename": "01-LBH lighting system/main.dxf",
    "sha256": "...",
    "discipline": "Electrical",
    "drawing_type": "plan",
    "units": "cm",                     // ★ 电气 cm / 机械 mm，混用是实战踩过的坑
    "revision": "R4",
    "entity_count": 41511,
    "cache_origin": "_takeoff/dump_main.json",   // ★ 来源可追溯
    "json_path": "parsed/json/v1/LBH-E-01-LIGHTING-MAIN/"
  }]
}
```

### 8.3 命名与不可变原则

- 命名：`<project_id>__<drawing_id>__<artifact>__v<version>.<ext>`；禁止 `final/new/latest/test.*`；
- Parser 版本分目录（`parsed/v1/`、`parsed/v2/`），禁止覆盖；
- 人工标定属新增 Label 版本，可追加不可覆盖；
- `DatasetService.validate()`：manifest ↔ 文件 sha256 ↔ entity_count 三方一致。

### 8.4 回归测试分层

| 层 | 内容 | 触发 |
|---|---|---|
| L1 Schema | JSON/Parquet 结构校验、manifest 完整性 | 每次导出 |
| L2 Parser | 同图跨 parser 版本对比：实体数、图层数、总长/总面积偏差阈值 | Parser 升级 |
| L3 Binding | 用 `labels/` 正负样本跑候选生成，断言 Top1 命中率与负样本抑制率 | 算法变更 |
| L4 Quantity | 与 `expected/quantities/`（824 条实战值）对比 | 计量引擎变更 |
| **L5 Writeback** | **保真回写校验：公式数/合并格/冻结窗格与原文件一致，原列 diff = 0** | 每次回写 |

L5 为新增——实战中这是最容易出事且后果最严重的一环（交付物业主直接打开原文件）。

---

## 9. 演进路线

Phase 0 为本次新增（B1–B6 阻塞项），其余在实施方案 Sprint 1–6 基础上按 ADR-06/07/08 重排。

| 阶段 | 内容 | 出口标准 |
|---|---|---|
| **Phase 0 · 地基修复** | B1 BOQ 解析（信息已足）；B2 模型扩展；B3 块几何外置；B4 空间列；B6 备份清理 | DB < 80 MB；BOQ 480 条 `item_key/description/unit/bill_qty` 全部正确；`?bbox=` 查询 P95 < 50 ms |
| **Phase 1 · 数据资产** | `datasets/lbh/`；**整理现有 100+ 份缓存**（非重解析）；manifest；JSON Schema；Validator；**可核性/takability 表结构**；L1/L2 回归 | `validate()` 通过；两次导出 sha256 一致；824 条 labels 入库 |
| **Phase 2 · Web 数据层** | FastAPI 骨架；Job + SSE；Drawing/Layer/Block/Entity/Viewport API；OpenAPI → TS 类型 | 浏览器可取到 7.9 万实体图纸的视口数据；Job 进度可见 |
| **Phase 3 · CAD Viewer** | React 三栏壳；Canvas 2D 渲染器；LOD/网格索引；拾取/框选/图层过滤 | 大图不全量加载；平移 ≥30 fps；实施方案 §36 Web 验收项全过 |
| **Phase 4 · 业务闭环 + 能力补齐** | **补齐 B5 六段能力**（S1 转换 / S3 标定 / S4 归一化+黑名单 / S5 跨图去重 / S6 Item 映射 / S7 可核性+保真回写）；确定性计量与溯源 | **在 LBH 电气专业重现 66.4% 核对率与 140 条吻合结论**（ADR-07 验收口径）；不可核条目不输出伪精确数字；L5 回写校验全绿 |
| **Phase 5 · AI** | Candidate Union（Top20→LLM Top5）；Embedding；审核工作台；正负样本；置信度校准 | AI 只出 PENDING；Reject 成负样本；规格冲突强制 review |
| **Phase 6 · 工程化** | 版本冲突检测；跨专业索引与重复计价；组级降级计量；StandardProfile | 覆盖率/冲突/版本三类闸门上线；L3/L4 回归全绿 |

**Phase 0+1+2 完成即价值显现**。Phase 3 渲染器是最大风险项，建议先用小图（sheet 73，1.2 万实体）验证，再上 7.9 万实体。**Phase 4 是能力补齐的主战场**，工作量最大但全部有实战脚本可照搬。

---

## 10. 待确认清单

### A 类 · 阻塞定稿（4 项）

| # | 决策点 | 选项 | 我的建议 |
|---|---|---|---|
| **A1** | **桌面版去留** | (a) 双端共存共享 SQLite<br>(b) 桌面版冻结，只修 bug<br>(c) 桌面版废弃 | **(b)**。两套 UI 长期维护成本高；`app/ui/*` 暂不删，作为渲染器翻译参照。需确认是否有存量用户 |
| **A2** | **Dataset 规模** | (a) 仅整理现有 100+ 份缓存（约 40 MB）<br>(b) 补转剩余 5 份电气 DWG 后再整理<br>(c) 全量含结构 153 份 DWG | **(b)**。结构仅对应 5 条清单项，投入产出比极低；电气剩余 5 份能补齐专业覆盖 |
| **A3** | **部署形态** | 单机 localhost / 局域网多人 / 服务器 | 需明确。决定要不要认证、多租户、PostgreSQL 替代 SQLite |
| **A4** | **是否需要用户认证与多人协作** | 需要 / 不需要 | 现状无认证概念；多人同时确认绑定会产生写冲突。若需要，补：同时在线人数、角色划分 |

### B 类 · 需补充信息（5 项）

| # | 缺失项 | 为什么需要 | 补充形式 |
|---|---|---|---|
| **B1** | **`source/dwg/` 是否入库** | 42 电气 + 153 结构 + 1 医疗 + 5 机械 DWG 属客户资产，实施方案 §7 要求 `source/dwg/` | 明确：可复制入库 / 仅软链接引用 / 禁止入库 |
| **B2** | **1.53 GB 机械 DXF 的存放策略** | `D:\mech_dxf\` 现占 1.5 GB，属 derived 可重建；但重建需 accoreconsole 授权与 15–20 min | 保留 / 转完即删（需时重转） |
| **B3** | **824 条实战核对值能否作为 Golden Answer** | 实施方案 §7 的 `expected/quantities/` 与 L4 回归都需要。这 824 条是目前唯一「已验证」的基线，但**未经业主书面认可** | 确认：可作为内部回归基线 / 需业主确认后才能作为验收基线 |
| **B4** | **LLM 后端实际可用性** | `llm_settings` 配了 5 个后端 + fallback；实施方案 §3 提到 Ollama | 当前可用的是本地 Ollama 还是云端 API？模型名？有无 Token 预算约束？ |
| **B5** | **`docs/` 被 `.gitignore:11` 忽略** | 早期文档已 tracked，此后新建文档一律不进版本控制（`git check-ignore` 已确认） | 确认是否移除 `docs/` 忽略规则（保留 `docs/archive/` 的忽略即可） |

### C 类 · 建议确认（4 项，不阻塞）

| # | 事项 | 说明 |
|---|---|---|
| C1 | 界面语言 | LBH 为海外项目（土耳其图纸、英文清单），是否需英文界面 / 中英切换 |
| C2 | 分辨率上限 | 实施方案 §36 只到 2560×1440，是否需支持 4K |
| C3 | 移动端/平板 | 工地现场是否有移动端查看需求 |
| C4 | 现有 392 条候选的处理 | 359 条 SUPERSEDED 是否保留作为负样本训练集，还是清理 |

---

## 11. 风险登记

| 风险 | 等级 | 对策 |
|---|---|---|
| **Phase 4 能力补齐工作量被低估** | **高** | B5 六段能力中 4 段全缺。但有实战脚本可照搬（`_takeoff/` 30+ py、机械 20+ py、2 个技能），建议按技能 → Service 逐段翻译，每段用 LBH 电气数据做回归 |
| 渲染器重写（约 40% 前端工作量） | 高 | 逐函数对照 `app/ui/canvas.py` 翻译；先用 1.2 万实体小图验证；几何 schema 不改 |
| 单位混用导致量级错误 | **高** | 实战已踩：电气图 `len` 单位是 **cm**，机械 `$INSUNITS=4` 是 **mm**，差 10 倍。ADR-07 S3 强制标定 + Entity Schema 携带 `unit` 字段 + 状态栏常显 |
| 跨图重复计量 | 高 | 实战已踩：同一批设备在 4–5 张图重复出现、开关在两张图重复表达、桥架四条平行敷设。S5 强制并集，禁止「占格归属法」 |
| 大图性能不达标 | 中 | ADR-04 空间列 + 视口加载 + 延迟类型；>10 万实体再上 tiles/WebGL |
| 保真回写破坏原清单 | **高** | W1–W6 契约 + L5 回归层，每次回写强制校验并写审计 |
| 清单结构陷阱导致解析错位 | 中 | 实战已踩 5 类：item 编号 ≠ 行号、逗号小数点、交叉引用注记混入数量列、多版修订列、分部名需子串匹配。B1 修复 + 解析结果强制人工抽检 20 条 |
| LLM 调用不稳定 | 中 | 全部走 Job + SSE；沿用重试（≤2）与多后端 fallback；`llm_run` 全量审计 |
| 置信度校准样本不足 | 低 | 现状仅 1 ACCEPTED / 32 PENDING；Phase 5 前需积累，先用规则加权兜底 |
| Dataset 与运行时数据不一致 | 中 | `DatasetService.validate()` 三方校验，纳入 CI |
