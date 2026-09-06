# CAD·BOQ 图纸算量系统 Web 化改造与数据资产规范

> 版本：v1.0  
> 日期：2026-08-29  
> 用途：指导 WorkBuddy / Copilot 进行 Web 化改造、数据集整理与后续算量功能迁移。

## 1. 改造目标

当前系统已经具备 DWG/DXF 解析、Parse Cache、EngineeringObject、规则/Embedding/LLM 候选、BindingCandidate、人工审核、确定性计量、BOQ 导入/回写等能力。本次目标不是重写这些核心算法，而是：

1. 将 Windows/PySide6 交互逐步迁移为 Web。
2. 把 CAD 解析、算量、AI、数据库与浏览器渲染彻底解耦。
3. 将 WorkBuddy 当前已经生成的图纸 JSON 作为真实测试数据集。
4. 建立 DWG、DXF、JSON、Parquet、Render 数据的统一目录与命名规范。
5. 为后续 CAD 对象绑定、人工标定、AI Binding 和 Quantity 回归测试建立稳定数据基础。

## 2. Web 化是否会改善卡顿

Web 本身不会自动消除卡顿。

如果把几十万 Entity 的完整 JSON 一次性发送到浏览器，再用 DOM/SVG 每个对象渲染，浏览器同样会卡顿。

真正应该利用的是：

```text
现有桌面单体
UI + CAD解析 + 数据库 + AI + 计算 + 渲染

↓

Web架构
Browser
  ↓
API
  ↓
CAD/Data/Quantity/AI Services
```

主要收益来自：

- CAD 解析不在浏览器线程运行；
- LLM 不阻塞 UI；
- 大图计算由后端完成；
- 浏览器只接收当前需要的数据；
- 使用 Canvas/WebGL 进行批量渲染；
- Viewport、LOD、Tile 实现按需加载。

结论：

> 值得 Web 化，但必须同时进行“后端异步 + Viewport 数据 + LOD/GPU 渲染”改造，而不是简单把 PySide6 页面复制成网页。

## 3. 推荐技术架构

```text
Browser
├── React + TypeScript
├── Canvas/WebGL
└── REST + SSE/WebSocket
           ↓
FastAPI
├── CAD Data Service
├── Quantity Service
├── BOQ Service
├── Binding Service
└── AI Service
    ├── Ollama
    ├── Embedding
    └── LLM Audit
           ↓
Data Layer
├── SQLite：业务数据
├── JSON：元数据/配置/API/调试/中小规模交换
├── Parquet：大量 CAD Entity 和离线分析
└── Render Cache：浏览器专用显示数据
           ↓
Source / Dataset
└── DWG / DXF / JSON / Parquet
```

第一阶段建议保持 Python 核心算法不变，仅增加 FastAPI API 层和 Web 前端。

## 4. JSON 是否更适合 Web

是，但应限定用途。

### JSON 的优点

- 浏览器原生支持；
- API 传输方便；
- JavaScript 直接解析；
- 调试简单；
- 非常适合测试数据；
- AI Context 提取方便；
- 前后端 Schema 容易定义。

### JSON 的缺点

- 几何坐标全部文本化，文件体积较大；
- 全量 `JSON.parse()` 对大图开销很高；
- 随机查询能力弱；
- 不适合长期承载数十万/百万实体的全部数据；
- Schema 升级需要版本管理。

因此：

> JSON 适合作为交换、测试、调试和 API 中小规模响应格式，不建议把“大型 CAD 全量 JSON”直接作为浏览器长期渲染格式。

## 5. 推荐三层 CAD 数据

### Canonical Data

用于计算、查询和溯源：

```text
metadata
layers
blocks
entities
geometry
attributes
measurements
```

### Render Data

用于浏览器：

```text
LOD0
LOD1
LOD2
viewport tiles
GPU-friendly geometry
```

### Business Data

用于：

```text
EngineeringObject
BOQ
Binding
Quantity
Review
Calibration
LLM Audit
```

三者不要混成一个数据结构。

## 6. 推荐存储分工

```text
DWG
= Original Source

DXF
= Derived Conversion Artifact

JSON
= Metadata / Config / Dataset Exchange / API / Test Data

Parquet
= 大量 CAD Entity / Geometry / Offline Analysis

Render Cache
= Web Canvas/WebGL专用数据

SQLite
= Project / Drawing / BOQ / EO / Mapping / Binding / Review / Calibration
```

不要继续让一个文件格式承担全部任务。

## 7. 现有 WorkBuddy JSON 必须作为测试数据集

当前已经产生的真实 LBH 图纸 JSON 不要废弃。

将它们整理为：

```text
datasets/
└── lbh/
    ├── README.md
    ├── manifest.json
    ├── source/
    │   └── dwg/
    ├── converted/
    │   └── dxf/
    ├── parsed/
    │   ├── json/
    │   └── parquet/
    ├── render/
    ├── boq/
    ├── labels/
    │   ├── engineering_objects/
    │   ├── bindings/
    │   ├── rejected_bindings/
    │   ├── takability/
    │   ├── drawing_types/
    │   └── specifications/
    ├── expected/
    │   └── quantities/
    └── snapshots/
```

该目录作为不可随意修改的 Regression Dataset。

## 8. Dataset Manifest

每个项目建立 `manifest.json`：

```json
{
  "dataset_id": "LBH-2026-08",
  "project": "Euesperides Medical Hospital",
  "schema_version": "cad-1.0",
  "parser_version": "2.x",
  "source_revision": "R4",
  "files": []
}
```

每张图：

```json
{
  "drawing_id": "LBH-E-101",
  "filename": "E-101.dwg",
  "sha256": "...",
  "discipline": "Electrical",
  "drawing_type": "plan",
  "floor": "L01",
  "revision": "R4",
  "entity_count": 41511,
  "json_path": "parsed/json/LBH-E-101/",
  "parquet_path": "parsed/parquet/LBH-E-101/"
}
```

必须记录：

- source SHA256
- parser version
- schema version
- generated_at

## 9. 数据不可变原则

Regression Dataset 不允许算法运行时覆盖。

例如 Parser v2 和 Parser v3：

```text
parsed/
├── v2/
└── v3/
```

而不是覆盖原文件。

人工标定结果属于新的 Label 数据，可以新增版本。

## 10. DXF 管理规则

DXF 只属于 Derived Artifact。

永久保留的测试 DXF：

```text
datasets/<dataset>/converted/dxf/<version>/<drawing_id>/
```

临时 DXF：

```text
data/temp/
```

解析完成后自动清理。

禁止在项目根目录产生大量散落：

```text
test.dxf
new.dxf
output.dxf
final.dxf
```

## 11. JSON 管理规则

推荐：

```text
parsed/json/<drawing_id>/
├── metadata.json
├── layers.json
├── blocks.json
└── entities.json
```

不要把所有东西都放进一个无限增长的 `entities.json`。

其中：

- `metadata.json`：图纸信息、版本、单位、范围；
- `layers.json`：Layer 元数据；
- `blocks.json`：Block Definition；
- `entities.json`：Entity；
- 业务知识不要写入 CAD Entity 原始数据。

## 12. Entity Schema

建议：

```json
{
  "schema_version": "cad-1.0",
  "entity_id": "8A12",
  "handle": "8A12",
  "type": "LWPOLYLINE",
  "layer_id": "layer-001",
  "block_id": null,
  "geometry": {
    "type": "polyline",
    "points": [],
    "closed": false
  },
  "bbox": [0, 0, 100, 100],
  "measurement": {
    "length": 12.52,
    "area": 0
  },
  "attributes": {},
  "source": {
    "drawing_id": "LBH-E-101"
  }
}
```

不要在每个 Entity 重复写：

```text
discipline
system
layer_name
```

应使用 ID 引用 Layer/Block 表。

## 13. Web CAD 渲染策略

禁止：

```text
全部 Entity JSON
→
JSON.parse
→
每个Entity一个DOM/SVG
```

推荐：

```text
打开图纸
→ metadata
→ overview
→ LOD0
→ 根据 viewport 请求局部数据
→ LOD1/LOD2
→ 选中实体时再请求完整属性
```

推荐 API：

```text
GET /api/drawings/{id}
GET /api/drawings/{id}/metadata
GET /api/drawings/{id}/layers
GET /api/drawings/{id}/blocks
GET /api/drawings/{id}/viewport
GET /api/entities/{id}
```

## 14. CAD Render 数据

建议：

```text
render/
└── <drawing_id>/
    ├── overview.json
    ├── lod0.bin
    ├── lod1.bin
    ├── lod2.bin
    └── tiles/
```

具体二进制格式可以在 POC 阶段根据浏览器渲染库确定。

原则：

> 原始 CAD 数据为“精确”，Render Data 为“高性能”。

## 15. Web 端工程量工作流

```text
项目
 ↓
图纸
 ↓
预检
 ↓
可核性
 ↓
Engineering Object
 ↓
人工标定
 ↓
Candidate
 ↓
Rule
 ↓
Embedding
 ↓
Qwen
 ↓
人工审核
 ↓
Confirmed Binding
 ↓
Deterministic Quantity
 ↓
Coverage / Conflict / Version / Dedup
 ↓
BOQ
 ↓
原文件回写
```

## 16. 人工标定设计

第一阶段导入项目后不立即全量 AI。

先挑选：

- 高频 Block
- 高频 Layer
- 新 Block
- 低置信对象
- Top1/Top2 接近
- Rule/Embedding/LLM 冲突对象

用户确认：

```text
Layer
Block
设备类型
系统
规格
计量规则
BOQ
```

确认后保存为项目知识。

## 17. 人工确认数据必须形成正负样本

确认：

```text
CAM_DOME → BOQ-001
```

保存为 positive sample。

拒绝：

```text
CAM_DOME ≠ BOQ-003
```

保存为 negative sample。

之后用于：

- 候选抑制；
- 规则优化；
- Confidence Calibration；
- 回归测试。

## 18. Candidate 算法

当前分层候选逻辑保留：

```text
历史确认
→ Rule
→ Embedding
→ Lexical
→ Qwen
```

但推荐形成 Candidate Union：

```text
Historical
+
Rule
+
Embedding
+
Lexical
↓
去重
↓
Top 15~30
↓
Qwen Top 5
```

不要过早硬截断。

## 19. 规格匹配

规格比较必须分：

```text
EXACT
NORMALIZED_EQUAL
COMPATIBLE
UNKNOWN
CONFLICT
```

例如：

```text
4MP == 4 MP
```

属于 `NORMALIZED_EQUAL`。

```text
4MP != 8MP
```

属于 `CONFLICT`。

出现硬冲突：

```text
needs_review = true
```

不能让 LLM 的文字理由覆盖硬冲突。

## 20. Confidence Calibration

不能直接信任模型自报：

```text
confidence = 0.96
```

最终置信度应综合：

```text
LLM confidence
Rule score
Embedding similarity
Spec score
Historical accuracy
Top1-Top2 margin
Conflict
```

初始可采用 Logistic Regression / Isotonic Regression。

后续按：

```text
discipline
+
system
```

分层校准。

## 21. 可核性必须是 Web 一级功能

导入项目之后先：

```text
预检
```

输出：

```text
MEASURABLE
GROUP_ONLY
NOT_MEASURABLE
NO_DRAWING
VERSION_CONFLICT
PROVISIONAL
```

例如：

```text
Electrical    82%
Mechanical     7%
Architecture  95%
Structure     41%
```

不可核项目不允许回填伪精确数字。

## 22. 几何算法后续优化

优先：

1. SPLINE 真实弧长；
2. 平行线对 → 中心线，避免桥架/风管双边界双倍计量；
3. HATCH 多环、孔洞；
4. 非均匀缩放 Block；
5. 跨图空间去重。

这些都应该通过真实 Dataset 建立回归样本。

## 23. CAD 制图规范

推荐：

```text
Layer = DISCIPLINE-SYSTEM-OBJECT
```

例如：

```text
ELV-CCTV-CAMERA
ELV-ACS-READER
ELV-PA-SPEAKER

E-LTG-FIXTURE
E-PWR-SOCKET

P-FIRE-PIPE
P-DWS-PIPE
P-DRA-PIPE

M-HVAC-SADUCT
M-HVAC-RADUCT
```

Layer 不承担全部规格信息。

设备规格放在 Block Attribute。

## 24. Block Attribute 标准

建议：

```text
TAG
TYPE
SYSTEM
MODEL
SPEC
SIZE
UNIT
QTY_RULE
LEVEL
ZONE
```

例如：

```text
CAM_DOME

TAG=CAM-001
TYPE=DOME_CAMERA
SYSTEM=CCTV
MODEL=XXX
SPEC=4MP
UNIT=No.
QTY_RULE=COUNT
LEVEL=L01
ZONE=WARD-A
```

这样：

```text
Layer → 专业/系统/对象
Block → 设备族
Attribute → 精确规格
```

## 25. 图纸元数据标准

建议 Title Block / Drawing Metadata 增加：

```text
DISCIPLINE
SYSTEM
DRAWING_TYPE
LEVEL
ZONE
REVISION
STATUS
DESIGN_STAGE
```

图纸本身成为机器可识别的上下文。

## 26. 项目 CAD Standard Profile

新增：

```text
cad_standard/
├── layer_rules.json
├── block_rules.json
├── attribute_rules.json
├── drawing_type_rules.json
└── specification_rules.json
```

用于适配不同设计院。

系统第一次导入项目时，可以自动分析并生成：

```text
Project CAD Standard Profile
```

以后在同一项目中优先使用人工确认的规则。

## 27. Web UI 设计

不要复制当前 Windows 顶部的大量按钮。

推荐一级导航：

```text
项目
图纸
预检
标定
映射
AI绑定
计量
报告
更多
```

主界面：

```text
┌──────────────────────────────────────────────────────┐
│ 项目 | 打开 | 保存 | 更多                             │
├──────────────────────────────────────────────────────┤
│ 图纸 | 预检 | 标定 | 映射 | AI绑定 | 计量 | 报告      │
├──────────────┬───────────────────────┬───────────────┤
│ 图纸/图层     │      CAD Canvas       │ 当前任务       │
│              │                       │ BOQ/Binding   │
│ 搜索         │                       │ Object/AI     │
│              │                       │               │
├──────────────┴───────────────────────┴───────────────┤
│ 当前图纸 | 当前模式 | 实体 | 可核率 | BOQ | 状态       │
└──────────────────────────────────────────────────────┘
```

功能按当前任务动态显示，低频功能进入“更多”，不要再通过横向压缩导致按钮自动折叠。

## 28. AI Binding 工作台

```text
左：CAD对象
中：CAD Canvas
右：BOQ候选
下：证据/历史/规格/冲突
```

显示：

```text
AI推荐
97%
```

而不是：

```text
已确定
```

只有人工确认以后才显示：

```text
已确认
```

## 29. 预检页面

必须显示：

```text
图纸类型
可核性
覆盖率
粒度
版本
暂定
无图
```

这是正式算量前的第一道闸门。

## 30. API 与异步任务

长任务：

```text
DWG解析
批量导入
AI Binding
Embedding
重算
```

不要阻塞 HTTP。

推荐：

```text
Job
 ↓
Background Worker
 ↓
SSE / WebSocket
 ↓
Browser Progress
```

第一版可以继续使用 ProcessPool，不必立即引入 Redis/Celery。

## 31. 第一阶段 Web MVP

暂时不要求 Web 直接解析 DWG。

先使用现有 JSON Dataset：

```text
Dataset
→ API
→ React
→ CAD Canvas
→ Layer
→ Block
→ Entity
→ Attribute
→ BOQ
→ Manual Binding
→ Quantity
```

这样可以把“Web UI 改造”和“DWG 解析重构”解耦。

## 32. 第二阶段

再增加：

```text
Browser Upload DWG
→ FastAPI Job
→ ezdwg / ODA
→ Parser
→ Dataset
→ API
→ Browser
```

## 33. 文件统一目录

正式运行数据：

```text
data/
├── projects/
├── datasets/
├── cache/
├── temp/
├── logs/
└── exports/
```

定义：

```text
source = 原始输入
derived = 可重新生成
cache = 可删除
dataset = 回归测试资产
export = 用户交付物
temp = 临时文件
```

## 34. 文件命名

建议：

```text
<project_id>__<drawing_id>__<artifact>__v<version>.<ext>
```

例如：

```text
LBH__E-101__entities__v2.json
LBH__E-101__entities__v2.parquet
LBH__E-101__converted__ACAD2018.dxf
LBH__E-101__render__lod1__v1.bin
```

禁止：

```text
new.json
final.json
final2.json
latest.json
test.dxf
```

## 35. 第一阶段开发任务

严格按照以下顺序：

### Sprint 1：数据资产

1. 创建 `datasets/lbh/`；
2. 整理现有 JSON；
3. 建立 manifest；
4. JSON Schema；
5. Dataset Validator；
6. Regression Test。

### Sprint 2：Web 数据层

1. FastAPI；
2. Drawing API；
3. Layer API；
4. Block API；
5. Entity API；
6. Viewport API。

### Sprint 3：Web CAD Viewer

1. React；
2. Canvas/WebGL；
3. LOD；
4. Viewport；
5. Layer Filter；
6. Entity Selection；
7. Properties。

### Sprint 4：业务

1. BOQ；
2. Mapping；
3. Quantity；
4. Trace。

### Sprint 5：AI

1. Candidate；
2. Embedding；
3. Qwen；
4. Human Review；
5. Calibration。

### Sprint 6：工程化

1. Takability；
2. Coverage；
3. Version Conflict；
4. Group Only；
5. Cross Drawing Dedup；
6. Preserve Writeback。

## 36. 验收标准

### Web

- 1280×720、1920×1080、2560×1440均可使用；
- 不需要寻找被隐藏的关键按钮；
- CAD Canvas 始终保持主体空间；
- 大图不会一次性加载全部 Entity；
- Layer、Block、Entity 可筛选；
- Entity 可定位；
- 属性可查看。

### Dataset

- LBH 数据可重复加载；
- Parser 结果可版本化；
- Dataset 不被测试覆盖；
- manifest 可追溯；
- JSON/Parquet 可校验。

### Binding

- AI 只能生成 PENDING；
- 人工确认后才写正式 Mapping；
- Reject 形成负样本；
- Historical Binding 可以复用；
- 置信度经过校准；
- 规格冲突可触发人工审核。

### Quantity

- Count / Length / Area 均由确定性引擎计算；
- Quantity 可追溯到 Entity；
- 不可核条目不得输出伪精确数字。

## 37. 关键架构结论

最终不要做：

```text
DWG
→
巨大JSON
→
浏览器全量渲染
```

应做：

```text
DWG
→
Parser
→
Canonical Dataset
├── JSON
├── Parquet
└── Render Cache
→
FastAPI
→
React/WebGL
```

业务独立：

```text
EngineeringObject
→ Binding
→ Review
→ Quantity
→ BOQ
```

AI独立：

```text
Historical Knowledge
→ Rule
→ Embedding
→ Qwen
→ Candidate
→ Human Review
```

测试独立：

```text
真实 LBH Dataset
→ Regression
→ 算法升级
→ 再验证
```

最终目标：

> **把现有 CAD 算量系统从“Windows 单体工程工具”升级为“数据、计算、AI 与交互解耦的 Web 工程量平台”，同时把当前已经积累的真实 DWG 解析 JSON 变成长期可复用的 Golden Dataset。**
