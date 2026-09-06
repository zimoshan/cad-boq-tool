# cad-boq-tool Web 化迁移计划

> 单一权威迁移计划（2026-09-06 Phase 0 启动版）。
> 替代早期散落文档：[CAD_BOQ_Web化_架构设计_v1.0.md](CAD_BOQ_Web化_架构设计_v1.0.md) / [CAD_BOQ_Web化_架构设计_v2.0.md](CAD_BOQ_Web化_架构设计_v2.0.md) / [WEB_PLATFORM_ARCHITECTURE_2026-08-28.md](WEB_PLATFORM_ARCHITECTURE_2026-08-28.md) / [CAD_BOQ_Web化改造_数据资产与实施方案_v1.0.md](CAD_BOQ_Web化改造_数据资产与实施方案_v1.0.md)。
> 配套：[BACKLOG.md §1.A Web 化迁移](BACKLOG.md) 进度跟踪 + [BACKLOG §6 决策记录](BACKLOG.md) 19 项决策固化。

---

## 0. 设计原则

- **演进而非重写 + #19 选 A**：业务算法实现保留（app/cad|engineering|binding|takeoff|boq|llm ~6000 行），集成层重写（webapi/services/ 包装）
- **Web 化首要对象**（#14）：v2.0 §1.4 双轨现状——cad-boq-tool 是产品壳（轨道 A），实战链路（轨道 B `D:\ifc_2026-08-24_0536`）的 7 段能力工程化装入 Service 容器
- **模块化单体 + 清晰 API**（#8 务实版）：FastAPI 单进程，不拆 K8s 微服务（Windows 单机 + 局域网部署不匹配微服务场景）
- **#19 选 A 落地**：业务函数包装而非重写
- **6 段能力一次性补齐**（#2）：B5 S1/S3/S4/S5/S6/S7 在 Phase 0 完成，不留 Phase 4

---

## 1. 技术栈定稿（基于 19 项决策）

| 层 | 选型 | 决策 |
|---|---|---|
| 后端 | FastAPI 0.115 + uvicorn[standard] + Python 3.12 | 单进程模块化单体 |
| 数据库 | PostgreSQL 16 + PostGIS 3.4 | #6 局域网；B4 空间查询 |
| ORM | SQLAlchemy 2.x async + asyncpg + Alembic | #5 |
| 鉴权 | Casbin + RuoYi 风格 RBAC（sys_user/role/menu/dict 4 表）| #5 免登录预留 login |
| CAD 解析 | ezdwg（Rust 直读 R14-R2018）→ ezdxf → ODA 回退 | #10 S1 跨平台 |
| LLM | 5 后端 ABC（Ollama/DashScope/OpenAI/DeepSeek/CustomOpenAI）| #9 后端代理 |
| 前端 | React 18 + TypeScript + Vite + Tailwind 3.4 | #7 Chrome only |
| 渲染 | Canvas 2D（WebGL 延后）| v2.0 ADR-01 |
| 部署 | Docker Compose（fastapi + postgis + 可选 ollama）| #4 Linux 优先 |
| 测试 | pytest 11 现有 + 新增 API + GitHub Actions CI | #23 P0-23 |

---

## 2. 6 段能力缺口（v2.0 §2.5 B5，#2 一次性补齐）

| 段 | 能力 | 现状 | 落地 |
|---|---|---|---|
| S1 | DWG 无头转换 | 仅 ODA 探测，无 accoreconsole/Linux ODA | [app/cad/dwg.py](../app/cad/dwg.py) `find_oda_converter`/`find_accoreconsole` 跨平台 |
| S2 | 图层减法（底图） | 已有 | 既有 `get_block_insert_layers` |
| S3 | 单位标定 | 无 | [app/cad/cad_parser.py](../app/cad/cad_parser.py) `ParsedDrawing.units/insunits_code` + `_detect_units` + alembic 0002 `sheet.units` + `entity.units` |
| S4 | 归一化 + 黑名单 | 无 | [app/cad/cad_parser.py](../app/cad/cad_parser.py) `_classify_drawing_type` 5 分类 + `LAYER_BLACKLIST_KEYWORDS` + alembic 0002 `sheet.drawing_type` |
| S5 | 跨图去重并集 | 无 | [app/engineering/cross_sheet_dedup.py](../app/engineering/cross_sheet_dedup.py) bbox 重叠 ≥0.5 贪心聚类 + alembic 0002 `cross_sheet_dedup` 表 |
| S6 | Item 映射 | 部分（reviewer.confirm_binding）| 已实现，标 ✅ |
| S7 | 可核性 + Excel 保真回写 | 无 | [app/boq/writeback.py](../app/boq/writeback.py) `Takability` 6 状态 + `classify_takability` + alembic 0002 `writeback_audit` 表 |

---

## 3. 演进路线（7 阶段 + 28 项 Phase 0）

### Phase 0 · 清理与基础（已完成 2026-09-06）

| 子组 | 项 | 状态 |
|---|---|---|
| A.0 清理 | P0-0.1~0.7 + P0-29 | ✅ 7/7 + P0-29 |
| A.1 基础设施 | P0-1~5 | ✅ 5/5（pyproject/Docker/RBAC/alembic） |
| A.2 业务层重写 | P0-6~18 | ✅ 13/13（B1-B4 + B5 6 段 + 三件套） |
| A.3 前端基础 | P0-19~20 | ✅ 2/2（webui/ Vite+React+TS 骨架） |
| A.4 测试+数据通路 | P0-21~24 | ✅ 4/4（dataset/CI/dataviz） |
| A.5 文档 | P0-25~28 | 🟡 1/4（P0-25 ✅） |

**出口标准 8.5/9**（剩前端 npm install 待执行）。

### Phase 1 · 数据资产（2 周）

- [ ] 可核性闸门实现（#16）：[app/boq/writeback.py](../app/boq/writeback.py) Takability 6 状态完整逻辑
- [ ] Dataset 整理（ADR-06）：`D:\ifc_2026-08-24_0536` 37 电气 + 6 机械 + 26 建筑 + 医疗 → `datasets/lbh/` 归档
- [ ] 测试数据通路（#3）：用户手动标记 + 自动加载（Phase 0 占位，Phase 1 完整）
- [ ] 前端依赖装 + Vite dev 验证（Phase 0 出口 ⑥）

### Phase 2 · FastAPI 后端（3 周）

- [ ] 进程内 JobManager + SSE（v2.0 ADR-05）
- [ ] 全部 Service 路由（cad/extraction/binding/takeoff/boq/llm/audit/dataset）
- [ ] RuoYi 鉴权（切 login 模式预留入口）
- [ ] 文件上传 / 任务状态 / 幂等性 / 错误处理
- [ ] OpenAPI `/docs` 自动生成

### Phase 3 · 前端 + 渲染器（4-6 周，最大风险项）

- [ ] React + Canvas 2D 渲染器（先 1.2 万小图 sheet 73 验证，再上 7.9 万）
- [ ] 视口查询（PostGIS GIST 索引，毫秒级）
- [ ] 拾取/框选/LOD/块/图层/网格/floating tag
- [ ] 7 面板完整实现（绑定/清单/计量/图例/属性/项目/记录）
- [ ] 1366×768 / 1920×1080 / 2560×1440 响应式

### Phase 4 · 业务闭环（2 周）

- [ ] 7 面板联调
- [ ] Excel 保真回写契约（v2.0 §6.4）
- [ ] LBH 电气 66.4% 核对率 + 140 条吻合结论重现

### Phase 5 · AI（3 周）

- [ ] Candidate Union（Top20→LLM Top5）
- [ ] Embedding 召回
- [ ] 审核工作台（dataviz 集成）
- [ ] 正负样本 + 置信度校准

### Phase 6 · 工程化（3 周）

- [ ] 版本冲突检测 + 跨专业索引 + 组级降级 + StandardProfile
- [ ] 覆盖率/冲突/版本三类闸门
- [ ] dataviz 跨专业总览页（4 专业核对率对比）
- [ ] L3/L4 回归全绿

---

## 4. 关键工程契约

### 4.1 数据库 schema（alembic 2 迁移）

- **0001 initial**：12 业务表 + 5 RBAC 表 + PostGIS 扩展 + B2（boq_item +6 字段）+ B4（entity +min_x..max_y +geometry GIST）
- **0002 b5_capabilities**：entity.units / sheet.units / sheet.drawing_type / cross_sheet_dedup / writeback_audit

### 4.2 Service 层（webapi/services/）

包装而非重写（#19）：
```
webapi/services/cad.py  →  app.cad.reader.read_cad + app.cad.cad_parser.parse_dxf + B4 viewport
webapi/services/binding.py  →  app.binding.matcher.generate_candidates + app.binding.reviewer.confirm_binding
webapi/services/boq.py  →  app.boq.boq_parser.parse_boq + app.boq.writeback.write_back_quantities
webapi/services/dataset.py  →  JSON 文件存储（Phase 0）→ DB 表（Phase 1）
webapi/services/llm.py  →  app.llm.runner.run_llm_with_retry + app.takeoff.llm_backends.create_backend
```

### 4.3 前端 API 客户端

[webui/src/api/client.ts](../webui/src/api/client.ts) 统一封装 `api.{health,cad,binding,boq,dataset}`，dev 期 Vite proxy 转发到 `:8521`。

### 4.4 测试

- **pytest** 11 现有（业务层） + 1 新增（RBAC test_auth.py）
- **GitHub Actions**（[.github/workflows/test.yml](../.github/workflows/test.yml)）：backend-tests + frontend-build

---

## 5. 风险登记

| 风险 | 等级 | 缓解 |
|---|---|---|
| **Phase 3 渲染器性能** | 高 | 1.2 万小图先验 → 7.9 万；视口裁剪 + LOD |
| **桌面端直接废弃** | 中 | `pre-webify` tag 完整快照可回退 |
| **B5 六段能力补齐工作量** | 高 | 实战脚本可照搬（电气 30+ py/机械 20+ py/建筑 7 py + 2 SKILL）|
| **PG 切换 SQL 重写** | 中 | SQLAlchemy 2.x async + Alembic；增量迁移 |
| **单用户免登录 → 升级 RBAC** | 低 | `@requires(perm)` 抽象；当前 `lambda u: True` |
| **可核性 6 状态语义** | 中 | 实战核对率（v2.0 §1.3 45.9%）反向校准 |

---

## 6. 决策追溯

详见 [BACKLOG.md §6 决策记录](BACKLOG.md) 19 项决策。
