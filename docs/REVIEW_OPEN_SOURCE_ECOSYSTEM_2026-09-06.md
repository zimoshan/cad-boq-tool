# cad-boq-tool 开源生态评审报告

> 评审日期：2026-09-06
> 评审方法：网络检索 + GitHub API 逐仓核验（星标/许可证/更新时间）+ README 深度读入

---

## 一、方法说明

通过网络检索 + GitHub API 逐仓核验（星标、许可证、最近更新时间），核验了 30+ 仓库，筛掉了若干疑似假结果（如 `jwplayer/takeoff`、`open-cost/cost-estimation` 等未经验证的名称，均未采用）。

**关键发现**：本项目"直读实体 → 规则/语义/LLM 分层匹配 → 人工确认闭环"的路线，在全球开源生态里是**最务实的主流路线**。同类项目大多只做中间一节，全链路覆盖的极少。

---

## 二、开源项目核验清单

### A 类：图纸识别/算量 — 可直接对标或借用

| 项目 | 星标 | 许可证 | 与项目相关性 |
|---|---|---|---|
| [A-SHOJAEI/ConstructDrawingAI](https://github.com/A-SHOJAEI/ConstructDrawingAI) | 28 | PolyForm Noncommercial | **最高相关**。电气/建筑/P&ID 三种图纸的符号检测+连通图+算量，正是本项目"设备块识别→绑定→回写"的镜像实现。已公开基准数据：电气符号 [SkeySpot](https://github.com/pengkunliu/SkeySpot) 数据集上 mAP@50 0.847，P&ID 0.926。CIR 统一 schema + L0-L4 分层 + "每个量带置信度和溯源实体"的设计，与本项目的"候选卡片理由行、图例标定提升置信度"思路一致但更形式化 |
| [Kentucky-ai/opentakeoff](https://github.com/Kentucky-ai/opentakeoff) | 113 | Apache-2.0 | PDF 算量，MCP-native agent 工作流。已公布"12.3% 中位绝对误差"基准；**Refusal 文化**（答不了就报原因不给假数）值得借鉴 |
| [datadrivenconstruction/QuantityTakeoff-Python](https://github.com/datadrivenconstruction/QuantityTakeoff-Python) | 32 | — | IFC/Revit 视图过滤分组算量，与"绑定确认后按块聚合"同一思路的 BIM 侧实现 |
| [jeremylongshore/cad-ai-agent](https://github.com/jeremylongshore/cad-ai-agent) | 31 | — | **近邻项目**：ezdxf+FastAPI+LLM planner、"LLM 只出计划不出实体编辑"、4700 测试。**DWG 原生解析还未实现**——这正是本项目的护城河 |
| [anekhirun/Takeoff-Lens-Plugin](https://github.com/anekhirun/Takeoff-Lens-Plugin) | 5 | — | 电气/消防 PDF + MCP+Skill，与本项目目标场景高度贴近 |
| [SwanaWJ/pyrevit-CostEstimates.extension](https://github.com/SwanaWJ/pyrevit-CostEstimates.extension) | 7 | — | Revit 内生成 BOQ/总价的 pyRevit 插件，BOQ 反写口径可参考 |

### B 类：CAD×MCP 技能生态

| 项目 | 星标 | 许可证 | 说明 |
|---|---|---|---|
| [puran-water/autocad-mcp](https://github.com/puran-water/autocad-mcp) | 480 | — | AutoCAD LT MCP v3.1，AutoLISP 直执行 + 文件 IPC + **ezdxf 后端**，做 P&ID 符号。**方案B 实测首选候选** |
| [U-C4N/Autocad-MCP](https://github.com/U-C4N/Autocad-MCP) | 69 | MIT | **COM（实时 AutoCAD）+ headless ezdxf 双引擎**、122 个工具、ISO GD&T 校验、每版本 26 项回归基准。工程味最足 |
| [thepiruthvirajan/autocad-mcp-server](https://github.com/thepirithvirajan/autocad-mcp-server) | 62 | — | COM 建墙门窗构件，机电方向参考 |
| [Igualguana/AUTOCAD-ELECTRICAL-MCP](https://github.com/Igualguana/AUTOCAD-ELECTRICAL-MCP) | 14 | — | AutoCAD Electrical 专用 MCP，**与电气/消防设备方向最贴近** |
| [beiming183-cloud/AutoCAD-skills](https://github.com/beiming183-cloud/AutoCAD-skills) | 7 | — | GB/T CAD 技能包（Claude Code 技能格式）——"技能接入"的现成样例 |
| [xstaar/autocad-mcp](https://github.com/xstaar/autocad-mcp) | 6 | — | 源泉设计（YQArch，国产 AutoCAD 建筑插件）684 命令桥接 |

### C 类：视觉 / OCR / 多模态 / 数据集

| 资源 | 星标 | 许可证 | 说明 |
|---|---|---|---|
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | 88.9k | Apache-2.0 | **P0 级接入候选**：图例/材料表文字的 OCR 第二信道。PP-OCRv5 对中文小字、竖排、旋转标注效果成熟，可完全本地离线 |
| [QwenLM/Qwen3-VL](https://github.com/QwenLM/Qwen3-VL) | 20k | Apache-2.0 | 开源多模态模型。渲染图例/图签 → 多模态抽结构化文本 → 进现有 LLM 提示词 |
| [CubiCasa/CubiCasa5k](https://github.com/CubiCasa/CubiCasa5K) | 577 | — | 户型图数据集（检测9类户型元素）。**电气符号集**：DELP / SkeySpot（已可下载，ConstructDrawingAI 已用其训练到 SOTA 0.847 mAP@50） |
| [RasterScan/Floor-Plan-Recognition](https://github.com/RasterScan/Floor-Plan-Recognition) | 96 | — | 户型识别，含检测 |

### D 类：BIM/IFC 路线（期权）

| 项目 | 星标 | 许可证 | 说明 |
|---|---|---|---|
| [IfcOpenShell/IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell) | 2757 | LGPL-3.0 | IFC 引擎，DWG 直读路线之外若项目资料有 IFC 可作校验信道。不建议本阶段引入 |

---

## 三、ConstructDrawingAI 详细分析

### 3.1 架构

五层 + 统一 CIR schema：

| 层 | 目录 | 职责 |
|---|---|---|
| L0 Ingest | `ingest/` | PDF / DWG-DXF / IFC / image → gigapixel tiling → CIR |
| L1 Perception | `perception/` | 符号检测 + 连通图提取 |
| L2 Grounding | `grounding/` | IFC 类 + MasterFormat / UniFormat 代码映射 |
| L3 Engines | `engines/` | 算量（数量/面积/长度） |
| L4 Agent | `agent/` | 自然语言 Q&A + RFI 起草 |

每个提取值携带 confidence + source_entity_ids + source_sheet，所有层读写同一个 CIR schema。

### 3.2 基准数据（已发表，真实测试集）

| 能力 | 数据集 | 结果 | SOTA 对比 |
|---|---|---|---|
| 电气符号检测 | DELP / SkeySpot（官方划分） | **0.847 ± 0.024** mAP@50 | 超越 SkeySpot 0.825 |
| 建筑检测 | FloorPlanCAD（35 类） | **0.820 ± 0.005** mAP@50 | — |
| P&ID 检测 | PID2Graph OPEN100（6 类） | **0.926 ± 0.008** mAP@50 | — |
| P&ID 连通（端到端） | PID2Graph OPEN100 边 | **0.752** edge AP | 略低于 Relationformer 0.755 |

### 3.3 已知局限（README 自述）

- 结构/土木专业不支持（等待真实检测数据）
- 跨域泛化未经验证（当前检测器是领域特定的）
- 路线图：① 结构/土木 ② 联合数据集跨域训练 ③ 扩大合成预训练
- **许可证**：PolyForm Noncommercial 1.0.0——商业使用需单独授权

### 3.4 对本项目的直接借鉴

1. **CIR schema 思想**：各层统一中间表示，本项目可将"工程对象、绑定候选、计量结果、回写记录"统一到一个 schema，审核层可展开"这条量从哪来"
2. **连通图提取**：电气导线端点连接关系 → 回路拓扑图 → 按回路计量，正好对应本项目"平行线对 / 中心线跨图并集"痛点
3. **电气符号检测权重**：SkeySpot 数据集已公开，本项目匿名块场景可考虑在此基础上 fine-tune

---

## 四、cad-ai-agent 详细分析

### 4.1 架构

- **意图分类**（两轴）：RequestClass（what：edit/analyze/compare/query/generate）× ObjectiveTag（why：compliance/coordination/documentation/estimation/quality/general）
- **编辑管线**：`Planner → ChangeSet → Validator → Preview → EditEngine → Save-As DXF + RevisionNotes`
- **LLM 原则**：`LLM 只出计划不出实体`，Planner 返回结构化 ChangeSet，引擎校验后应用
- **分析管线**：确定性提取器（与分析请求隔离），不经过 LLM 编辑流程
- **测试**：4700 测试，10 层测试

### 4.2 已知局限（README 自述）

| 限制项 | 说明 |
|---|---|
| DWG 原生编辑 | 不支持（仅 DXF） |
| 3D 实体 | 不支持 |
| Xref | 不支持（检测到后跳过并警告） |
| 动态块 | 不支持（同上） |
| 标题栏修订表 | 不支持（V1 不在范围内） |
| 受保护图层 | TITLE/TITLEBLOCK/SEAL/REVISION 不可编辑 |
| 原文件修改 | 严格 save-as 工作流 |

### 4.3 对本项目的直接借鉴

- "LLM 出计划/分析，实体编辑走确定性逻辑"——与本项目"语义推断层（LLM）→ 绑定候选生成（确定性）"职责一致
- 分层测试文化（10 层测试，CI 含回归）
- Mock provider 只做关键词匹配，用于离线调试——本项目可参考此模式构建测试

---

## 五、OpenTakeoff 详细分析

### 5.1 架构

- **MCP-native**：stdio 服务端，52 个工具（默认构建），可在 Claude Code 等 AI 工具中直接调用
- **前端**：React 18 + Vite，纯 HTML5 Canvas + SVG（无图表框架）
- **PDF 渲染**：Mozilla pdf.js
- **几何**：TypeScript，单元测试覆盖
- **特点**：`propose_shapes` 拒绝模型虚构的几何，只接受墙网络产生的面

### 5.2 已知局限（README 自述）

| 限制项 | 说明 |
|---|---|
| One-Click Area | 暂时关闭 flood 引擎重新验证（可通过 `VITE_ONE_CLICK=1` 开启） |
| Snap | beta，不建议生产使用 |
| Revision compare | 仅数量级对比，不做几何级对比 |
| 跨分区测量 | 不支持（隔墙房间的门槛无法从迹线几何定位） |
| 模型不能猜比例 | 比例必须显式 `set_scale`，未设比例的图纸拒绝测量 |
| 模型不能凭空出多边形 | `propose_shapes` 拒绝任何无引用的几何 |
| Agent 不能签绿色批准章 | 只能签石墨色 `AGENT` 菱形 |
| 企业部署 | MSIX 打包/Win Sandbox/Intune 静默部署尚未构建 |

### 5.3 误差基准

| 指标 | 数值 | 说明 |
|---|---|---|
| 中位绝对百分比误差（有基准适配器） | **12.3%** | 51 个项目时间留存集 |
| 无基准基础模型 | **62.8%** | 同留存集对照 |

**核心工程原则**：误差基准公开，用户知道工具上限在哪里。

### 5.4 Refusal 文化

> "工具在无法回答时，应 withholding with a stated reason（保留并给出原因），而非返回一个看似合理的数字。静默的零不存在；拒绝会返回可操作的字符串，例如 'That space isn't enclosed on the plan linework—the fill spilled.'"

### 5.5 对本项目的直接借鉴

1. **Refusal 策略**：绑定候选生成时，若无法匹配应返回结构化原因，而非静默 skip
2. **误差基准**：建立量化评测体系，让准确率从"定性 78%"变为"可验证的 X%"
3. **"Markup is Label" 数据飞轮**：人工修正后的几何溯源 → 可验证语料 → 自动化反馈

---

## 六、AutoCAD MCP 生态分析

### 6.1 puran-water/autocad-mcp（480⭐）

- AutoCAD LT MCP v3.1，AutoLISP 直执行 + 文件 IPC + ezdxf 后端
- 8 个合并工具，支持 P&ID 符号
- 最成熟：480 星标，大量用户反馈

### 6.2 U-C4N/Autocad-MCP（69⭐，MIT）

- COM（实时 AutoCAD）+ headless ezdxf 双引擎
- 122 个工具，ISO GD&T 校验
- 每版本 26 项回归基准
- **与本项目"ezdwg 直读优先"原则最契合**：双引擎思路，ezdxf 做确定性解析，COM 做实时校验

### 6.3 Igualguana/AUTOCAD-ELECTRICAL-MCP（14⭐）

- AutoCAD Electrical 专用，**电气设备方向最贴近**
- Claude + Ollama + Web 仪表板，macOS + Windows

---

## 七、参考来源清单

| 编号 | 项目 | URL | 许可证 |
|---|---|---|---|
| 1 | ConstructDrawingAI | https://github.com/A-SHOJAEI/ConstructDrawingAI | PolyForm Noncommercial |
| 2 | cad-ai-agent | https://github.com/jeremylongshore/cad-ai-agent | — |
| 3 | opentakeoff | https://github.com/Kentucky-ai/opentakeoff | Apache-2.0 |
| 4 | puran-water/autocad-mcp | https://github.com/puran-water/autocad-mcp | — |
| 5 | U-C4N/Autocad-MCP | https://github.com/U-C4N/Autocad-MCP | MIT |
| 6 | autocad-mcp-server | https://github.com/thepirithvirajan/autocad-mcp-server | — |
| 7 | AUTOCAD-ELECTRICAL-MCP | https://github.com/Igualguana/AUTOCAD-ELECTRICAL-MCP | — |
| 8 | AutoCAD-skills | https://github.com/beiming183-cloud/AutoCAD-skills | — |
| 9 | autocad-mcp (YQArch) | https://github.com/xstaar/autocad-mcp | — |
| 10 | QuantityTakeoff-Python | https://github.com/datadrivenconstruction/QuantityTakeoff-Python | — |
| 11 | pyrevit-CostEstimates | https://github.com/SwanaWJ/pyrevit-CostEstimates.extension | — |
| 12 | Revit-Civil-AI-Estimator | https://github.com/Lynn-hh/Revit-Civil-AI-Estimator | — |
| 13 | Takeoff-Lens-Plugin | https://github.com/anekhirun/Takeoff-Lens-Plugin | — |
| 14 | CubiCasa5k | https://github.com/CubiCasa/CubiCasa5K | — |
| 15 | RasterScan/Floor-Plan-Recognition | https://github.com/RasterScan/Floor-Plan-Recognition | — |
| 16 | PaddleOCR | https://github.com/PaddlePaddle/PaddleOCR | Apache-2.0 |
| 17 | Qwen3-VL | https://github.com/QwenLM/Qwen3-VL | Apache-2.0 |
| 18 | IfcOpenShell | https://github.com/IfcOpenShell/IfcOpenShell | LGPL-3.0 |

---

## 八、合规与风险提示

1. **许可证红线**：PolyForm Noncommercial 的 ConstructDrawingAI（R=28）**只读代码/思路，不 merge 代码、不投训练权重**；PaddleOCR Apache-2.0、autocad-mcp MIT、Qwen3-VL Apache-2.0 可正当引用
2. **数据版权**：CubiCasa5K 等数据集仅供训练评估，不得混入客户实际图纸
3. **幻觉防护**：介入前一律用 `gh api repos/<owner>/<repo>` 核验真实存在性，本清单已全部核验
4. **多信道并发副作用**：OCR×MTEXT×VLM 三信道同时给分时可能产生不同答案，用现有置信度+去重+人工确认机制挡住
