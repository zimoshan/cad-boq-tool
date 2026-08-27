# cad-boq-tool Web 化改造方案（评审稿 v1.0）

| 项目 | 内容 |
|---|---|
| 日期 | 2026-08-24 |
| 性质 | Web 化（桌面 PySide6 → 浏览器）完整方案 |
| 核心原则 | **业务逻辑 100% 复用，只重写展示层**；桌面版保留，双端共存 |
| 已确认决策 | 渲染引擎 = 自研 Canvas 2D；推进方式待启动确认 |

---

## 1. 为什么可以低成本 Web 化

现有代码分层清晰，UI 与业务完全解耦：

| 层 | 模块 | Web 化处理 |
|---|---|---|
| 业务逻辑（复用） | app/db.py、app/cad/*、app/engineering/*、app/binding/*、app/takeoff/*、app/boq/*、app/measure.py、app/report.py、app/llm/* | **零重写**，由新后端直接调用 |
| 展示层（重写） | app/ui/*（PySide6 控件） | 重写为 Web 前端 |
| 渲染层（重写） | app/ui/canvas.py（QGraphicsView） | 重写为 Canvas 2D 渲染器 |

估算：业务逻辑约占 60% 代码量，全部保留；新增后端 API 壳 + 前端渲染器，工作量集中在渲染器（约 40%）。

---

## 2. 目标架构

```text
浏览器 (http://localhost:8501)
 ┌─────────────┬──────────────────────┬──────────────┐
 │ 左侧导航     │  CAD 渲染画布          │ 右侧面板      │
 │ 项目/图纸列表 │  Canvas 2D            │ BOQ 清单     │
 │ 图层树/块树  │  缩放/平移/拾取/框选    │ 计量         │
 │ (checkbox)  │  定位高亮/图层显隐      │ 图例标定     │
 │             │                       │ 绑定工作台    │
 └─────────────┴──────────────────────┴──────────────┘
        │                    ▲
        │ REST API           │ WebSocket（解析/LLM 进度）
        ▼                    │
 ┌──────────────────────────────────────────────┐
 │ FastAPI 后端 (uvicorn, localhost:8501)        │
 │  /api/projects    /api/sheets                 │
 │  /api/entities/{sheet}?layer=..&block=..      │
 │  /api/geometry/{sheet}?bbox=..&layers=..      │  ← 分块几何（空间网格索引）
 │  /api/boq         /api/mapping                │
 │  /api/legend      /api/binding                │  ← 候选/确认/拒绝/批量
 │  /api/takeoff     /api/parse (缓存复用)        │
 │  /ws/progress                                  │
 │                                               │
 │  复用：db/cad/engineering/binding/takeoff/    │
 │        boq/measure/report/llm（零重写）        │
 └──────────────────────────────────────────────┘
```

---

## 3. 关键技术设计

### 3.1 几何 API + 空间网格索引（大图性能关键）

- 解析入库时按 **50m 网格** 预分桶（扩展 cad_parser 或 db 层，实体挂 grid_id）
- `GET /api/geometry/{sheet_id}?bbox=x0,y0,x1,y1&layers=...` 只返回视口覆盖网格内的实体几何
- 平移/缩放时视口变化 → 节流请求（300ms）→ 增量绘制
- 效果：6 万实体图纸，视口内通常只画几千 → 浏览器流畅

返回格式：
```json
{"entities": [
  {"id": 123, "type": "INSERT", "layer": "ELV-CCTV", "block": "CAM_DOME",
   "color": [255,0,0], "geom": {"type":"insert","insert":[x,y],"block":"CAM",...}},
  {"id": 456, "type": "LINE", "layer": "P-FIRE-DN100", "geom": {"type":"line","start":[..],"end":[..]}}
]}
```

### 3.2 Canvas 2D 渲染器（renderer.js）

- 实体绘制：line/polyline/arc/circle/ellipse/spline/hatch/insert（块展开几何复用后端返回）
- 视口管理：平移（中键拖拽/空格）、缩放（滚轮，锚点）、缩放记忆（前进/后退）
- 拾取：网格索引 + 最近命中；双击拾取、Shift 拖拽框选
- **定位高亮**：目标实体高亮色重绘 + 其余变暗（同桌面版交互）；ESC/空白取消
- 图层显隐：左侧树 checkbox → 重绘
- 设备块形态：INSERT 直接绘制块定义几何（后端下发块几何，无需展开）

### 3.3 前端交互映射（与桌面版一一对应）

| 桌面版 | Web 版 |
|---|---|
| BoqTable | 右侧 BOQ 表格（规则/比例可编辑） |
| MappingPanel | 映射模式选择 + 计量结果卡片 |
| LegendPanel | 图例标定表格（LLM 辅助/导入导出） |
| BindingWorkbench | 绑定工作台（对象列表/审核队列/确认/拒绝/批量） |
| CanvasToolbar | 顶部工具栏（模式/缩放/主题/类型过滤） |

### 3.4 技术选型

| 项 | 选择 | 理由 |
|---|---|---|
| 后端 | FastAPI + uvicorn | async、自动 OpenAPI 文档、生态好 |
| 前端 | 原生 HTML/CSS/JS + Canvas 2D | 零构建、零依赖、离线可用、易维护 |
| 实时 | WebSocket | 解析/LLM 进度推送 |
| 部署 | `start_web.bat` 双击启动 + 自动开浏览器 | 保持本地工具使用习惯 |
| 兼容 | 桌面版保留 | 双端共存，Web 化失败可回退 |

---

## 4. 新增文件结构

```text
web/
├── server.py              # FastAPI 入口：静态挂载 + 全部 API 路由
├── static/
│   ├── index.html         # 三栏主布局
│   ├── style.css          # 样式（浅色主题，与桌面版一致的蓝白）
│   ├── api.js             # fetch/WS 封装
│   ├── renderer.js        # Canvas 2D 渲染器（视口/拾取/高亮）
│   └── app.js             # 应用逻辑（项目/图纸/BOQ/映射/绑定/图例）
├── start_web.bat          # 一键启动
└── README.md              # 使用说明
```

---

## 5. 实施阶段（每阶段可独立验证）

| 阶段 | 内容 | 验证标准 |
|---|---|---|
| **W1** | server.py + API 骨架（projects/sheets/entities/boq 只读）+ index.html 三栏壳 + 图纸列表 | 浏览器能看项目/图纸列表 |
| **W2** | geometry API + 网格索引 + renderer.js（图层渲染/缩放/平移/拾取/框选/定位高亮） | 浏览器能看真实图纸、放大缩小、高亮定位 |
| **W3** | BOQ 表格 + 点选/框选/图层/块 四种映射 + 计量展示 | 浏览器完成一次完整映射计量 |
| **W4** | 图例标定 + 绑定工作台 + AI 候选/确认/拒绝 + 审计 | 浏览器完成绑定闭环（LLM 开关可用） |
| **W5** | 文件夹批量 + 报表下载 + 打磨（空态/错误/性能） | 全流程可用 |

---

## 6. 风险与对策

| 风险 | 对策 |
|---|---|
| 渲染器重写工作量大 | 网格索引控制渲染量；先 W2 验证渲染器再铺后续 |
| 6 万实体浏览器卡顿 | 空间网格 + 视口裁剪 + 增量绘制；必要时 WebGL 后置 |
| 与桌面版行为不一致 | 每阶段对照 gui_smoke 用例做 Web 版冒烟 |
| 现有功能回归 | 桌面版不动，Web 版独立目录；业务逻辑共用测试 |

---

## 7. 结论

业务逻辑全复用 + FastAPI 薄壳 + 自研 Canvas 2D 渲染器，是投入/收益最优路径。W1+W2 完成即可在浏览器看到真实图纸并完成"定位高亮"，价值立现；W3-W5 逐步补齐算量闭环。
