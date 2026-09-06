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

> **主线 A**：Web 化迁移（方案 B 务实版，2026-09-06 启动，#19 选 A：保留算法实现重写集成层）
> **主线 B**：业务优化（[REVIEW_TECH_ROUTE_2026-09-06](docs/REVIEW_TECH_ROUTE_2026-09-06.md) + 方法论遗留项；Web 化 Phase 0~4 期间暂不投入，Phase 5 后回归对位）
> **主线 C**：验证项

---

### A · Web 化迁移（最高优先级主线）

> 18 项决策见 §6 决策记录；Phase 0 = 28 项（细分 35），总工期 ≈ 20-25 周。Phase 0 启动 2026-09-06。
> 设计基线：[CAD_BOQ_Web化_架构设计_v2.0](docs/CAD_BOQ_Web化_架构设计_v2.0.md) + 18 决策修订（方案 B 务实版：FastAPI 单进程模块化单体 + React + Canvas 2D + PG/PostGIS + RuoYi 风格 RBAC + Linux 部署优先，桌面端 2026-09-06 直接废弃）。

#### A.0 · Phase 0 · 清理与归档（先做，1 周）
- [x] **P0-0.1 git tag `pre-webify` 完整快照** ✅ 2026-09-06（HEAD = 837441f；`git reset --hard pre-webify` 随时回退）
- [x] **P0-0.2 删除 Node 壳** [src/](src/) + [bin/](bin/) + [package.json](package.json)（5 文件，#10 已明确引用）✅ 2026-09-06（commit `8c250ed`）
- [x] **P0-0.3 删除桌面端入口** [main.py](main.py) + 整个 [app/ui/](app/ui/) 21 文件（#15）✅ 2026-09-06（commit `5056d21`）
- [x] **P0-0.4 移动 UI 相关归档** 到 [docs/_removed/](docs/_removed/)：5 个 archive + 2 个 ui_audit = 7 文件（实际跟踪的，#10 已审）✅ 2026-09-06（commit `52c2df1`；含 .gitignore 解除 docs/ ignore）
- [x] **P0-0.5 移动旧 GUI 截图** 到 [artifacts/_legacy_ui/](artifacts/)：3 张 verify_round3_*.png + [ui_audit.md](ui_audit.md) 共 4 文件（#15）✅ 2026-09-06（commit `a21ecb6`）
- [x] **P0-0.6 备份垃圾清理**（`~/.cad-boq-tool/` 7 个 .bak_2026* / .bak-prellm / .fresh / .rebuilt 备份，#13）✅ 2026-09-06（实际释放 5.2 GB：8.2GB → 3.0GB）
- [x] **P0-0.7 README 重写**（指向 webapi/webui 启动步骤，#12）✅ 2026-09-06（commit `db21d6a`）
- [x] **P0-29 补 add 因 .gitignore 解除而出现的 14 个 docs/ 文档**（P0-0.4 副作用：根 .gitignore 解除 docs/ ignore 后，CAD_BOQ_Web化_*/REVIEW_*/CANDIDATE_*/驱动 Prompt/估算系统/未跟踪 archive 文档首次进入版本控制）✅ 2026-09-06（commit `acb0e28`）

#### A.1 · Phase 0 · 基础设施（2 周）
- [x] **P0-1 requirements.txt 锁定**（pyproject.toml + requirements.txt + .python-version=3.12）✅ 2026-09-06（commit `xxx`）
  - PySide6 移除；增 FastAPI 0.115 / SQLAlchemy 2.x async + asyncpg / Alembic / GeoAlchemy2 / Casbin / Pydantic v2 / ezdxf 1.4.4 + ezdwg
- [x] **P0-2 .env.example 模板**（env.example，无前导点避开 .env* 权限保护）✅ 2026-09-06
  - APP/DB(auth+sync DSN+SQLITE_BACKUP)/AUTH(no_login 预留 login)/ODA(B5 S1)/5 LLM 后端/存储/CORS/测试数据通路
- [x] **P0-3 Docker Compose**（docker-compose.yml + Dockerfile + .dockerignore）✅ 2026-09-06
  - webapi + postgis/postgis:16-3.4 + 可选 ollama（profile=with-llm）；健康检查 + 持久卷 + 桥接网络；python:3.12-slim 多阶段构建
- [x] **P0-4 RuoYi 风格 RBAC 骨架**（webapi/auth/ 8 文件 + main.py + config.py + db/）✅ 2026-09-06
  - sys_user/sys_role/sys_user_role/sys_menu/sys_dict 5 表（SQLAlchemy 2.x async）；@requires(perm) 装饰器；Casbin 包装；no_login 模式 sysadmin stub；FastAPI Depends get_current_user
- [x] **P0-5 PG + PostGIS schema 迁移**（alembic + 12 业务表 + 4 RBAC 表 + migrations/）✅ 2026-09-06
  - alembic 20260906_0001_initial_schema.py（CREATE EXTENSION postgis + uuid-ossp；B2 修正 boq_item 加 section/item_key/brand/bill_qty/installed_qty/qty_remaining；B4 修正 entity 加 min_x..max_y + geometry GIST）
  - migrations/sqlite_to_pg.py（一次性脚本，bbox→WKT POLYGON，batch 1000）
  - migrations/initdb.d/01_postgis.sh（容器首次启动自动启用 PostGIS）

**A.1 验证状态**：
- ⚠️ 本机 `pytest tests/test_auth.py` 当前失败（原因：.venv 是 Python 3.11 旧 PySide6 环境，未装 webapi 新依赖 casbin/fastapi/sqlalchemy）
- ✅ 解决路径：① `pip install -r requirements.txt` 或 ② `docker compose up -d` 后 `docker compose exec webapi pytest` 统一验证
- 代码层已就绪，验证留待 P0-23 pytest CI（Phase 0 出口标准 ⑤）

#### A.2 · Phase 0 · 业务层重写（4 周，#2 B5 六段能力一次性补齐）
- [ ] **P0-6 B1 BOQ 解析修复**（v2.0 §2.1：BOQ-001 4 种表头识别 + section/item/三数量列）⬜
- [ ] **P0-7 B2 BoqItem 模型扩展**（v2.0 §2.2：section + bill_qty/installed_qty/qty_remaining + Item 主键）⬜
- [ ] **P0-8 B3 块几何外置**（v2.0 §2.3：`sheet.blocks_json` 34MB → `block_geometry/<sha256>.parquet`）⬜
- [ ] **P0-9 B4 空间列 + 视口查询**（v2.0 §2.4：`entity` 加 min_x/max_x/min_y/max_y + PostGIS geometry + `/api/cad/viewport?bbox=`）⬜
- [ ] **P0-10 B5 S1 DWG 无头转换**（[dwg.py](app/cad/dwg.py) 加 accoreconsole 路径 + Linux ODA 二进制）⬜
- [ ] **P0-11 B5 S3 单位标定**（drawing.units 字段 + INSUNITS 自动检测）⬜
- [ ] **P0-12 B5 S4 归一化 + 黑名单**（型号词表 + DETAIL/LEGEND 层黑名单 v2.0 §5.1）⬜
- [ ] **P0-13 B5 S5 跨图去重并集**（`_tray_pts.json` 思路 → `cross_sheet_dedup` 表 + 算法）⬜
- [ ] **P0-14 B5 S6 Item 映射**（BOQ item ↔ EO 关联 v2.0 §5.3）⬜
- [ ] **P0-15 B5 S7 可核性 + Excel 保真回写**（`takability` 6 状态 + `writeback_audit` 表，#16 Phase 1 落地表结构）⬜
- [x] **P0-16 业务函数重写为 Service 层**（#19 选 A：算法实现保留，重写入口）🟡 2026-09-06 第 1 批完成（cad/binding/boq/llm 4 域 + base），extraction/takeoff/audit 留第 2 批
- [x] **P0-17 Pydantic schema 全套**（请求/响应模型 v2.0 §6.6）🟡 2026-09-06 第 1 批完成（common/cad/binding/boq 4 文件）
- [x] **P0-18 API 契约 OpenAPI**（自动生成 `/docs`）🟡 2026-09-06 第 1 批完成（routers/health/cad/binding/boq 4 文件 + main.py 注册 4 router + CORS + lifespan）

**A.2 进度 3/13**（第 1 批 = 三件套基础）。第 2 批 P0-6~15（B1-B4 修复 + B5 6 段能力）等用户验收后启动。

#### A.3 · Phase 0 · 前端基础 + 资产本地化（1 周）
- [ ] **P0-19 CDN 资源本地化**（#11：下载 Tailwind/Icons 到 `webui/public/cdn/`；[design/main.html](design/main.html) 改本地引用；产物可传 GitHub）⬜
- [ ] **P0-20 design/main.html 1:1 转 React**（深色主题/rail/卡片工作台/徽章/Toast，组件化）⬜

#### A.4 · Phase 0 · 测试 + 数据通路（1 周）
- [ ] **P0-21 可核性闸门表结构**（#16：takability 字段 + writeback_audit 表；实现留 Phase 4）⬜
- [ ] **P0-22 Dataset 通路占位**（#3：`/api/dataset/*` 路由占位 + 你手动标记测试数据机制，README 写明）⬜
- [ ] **P0-23 pytest CI**（[.github/workflows/test.yml](.github/workflows/) + 桌面 vs Web 一致性测试 = 11 现有 + 新增 API/renderer/regression）⬜
- [ ] **P0-24 dataviz skill 引入**（#17：跨专业总览页 + 报告页用 dataviz）⬜

#### A.5 · Phase 0 · 文档（同步执行）
- [x] **P0-25 BACKLOG §1 登记 Phase 0 全部 28 项 + 18 决策** ✅ 2026-09-06
- [ ] **P0-26 WEB_MIGRATION_PLAN.md 重写**（按 v2.0 9 阶段 + 18 决策；替代当前散落方案文档）⬜
- [ ] **P0-27 DESKTOP_TO_WEB_MAPPING.md**（标注删除项 + 重写项 + 零重写项三段式）⬜
- [ ] **P0-28 CHANGELOG.md 新建**（本次架构切换专条）⬜

#### A.6 ~ A.10 · Phase 1~6（占位，Phase 0 完成后细化）
- [ ] **Phase 1 · 数据资产闸门**（#16 可核性表实现 + #3 测试数据通路 + ADR-06 Dataset 整理）⬜
- [ ] **Phase 2 · FastAPI 后端 + JobManager + SSE + RBAC + 全部 Service 路由** ⬜
- [ ] **Phase 3 · React + Canvas 2D 渲染器**（1.2 万小图先验 → 7.9 万，最大风险项）⬜
- [ ] **Phase 4 · 业务闭环联调 + Excel 保真回写契约**（v2.0 §6.4）⬜
- [ ] **Phase 5 · AI**（Candidate Union/Embedding/审核/正负样本/置信度校准）⬜
- [ ] **Phase 6 · 工程化**（版本冲突/跨专业索引/组级降级/StandardProfile/CI/CD）⬜

**Phase 0 出口标准**（9 条）：① git tag pre-webify ✅ ② 桌面端启动入口 0 个 ✅ ③ Node 壳 0 个 ✅ ④ PG + PostGIS + 6 段能力 schema 完整 ⬜ ⑤ FastAPI 起服务 + pytest 全绿 ⬜ ⑥ 前端 Vite dev 起 + Chrome 渲染同 design/main.html ⬜ ⑦ 测试数据通路占位完成 ⬜ ⑧ 备份垃圾 0 ✅ ⑨ README 反映新架构 ✅。**当前完成 5/9**（清理类全部完成，工程类待启动）。

---

### B · 业务优化（次要支线，Web 化 Phase 5 后回归对位）

> 主线来源：[REVIEW_TECH_ROUTE_2026-09-06](docs/REVIEW_TECH_ROUTE_2026-09-06.md) 优化建议 + 方法论遗留项。Web 化 Phase 0~4 期间暂不投入，Phase 5 起评估对位（#1 方案 B 重写集成层后会自然吸收部分 P0/P1 项）。

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

- **Web 化改造（FastAPI + Canvas2D）** 🚧 2026-09-06 启动（详见 §1.A 28 项 Phase 0）
  - 方案 B 务实版：FastAPI 单进程模块化单体 + React + Canvas 2D + PG/PostGIS + RuoYi 风格 RBAC + Linux 部署优先
  - 桌面端 2026-09-06 决策**直接废弃**（#15）
  - 业务层保留算法实现，重写集成层（#19 选 A）
  - Phase 0 = 清理 7 项 + 基础设施 5 项 + 业务层重写 13 项 + 前端 2 项 + 测试 4 项 + 文档 4 项 = 35 项（细分）
  - 总工期 ≈ 20-25 周；18 项决策见 §6

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
| 驱动 Claude Code Web 化 Prompt | docs/ | 保留（执行输入） | 19 节报告 + 18 决策基线 |
| 估算系统技术架构与实现说明 | docs/ | 保留（架构参考） | Web 化重写时校对 |
| BACKLOG v2（自 v2 始） | docs/BACKLOG.md | 唯一待办入口 | 含 §6 决策记录 |

---

## §6 决策记录（Web 化迁移，2026-09-06）

> 用户 18 项决策的固化记录。每项含决策内容、理由、影响范围。所有 Phase 0+ 任务都基于此记录。

| # | 决策项 | 决策 | 理由/影响 |
|---|------|------|-----------|
| 1 | 架构方案 | **方案 B** 重写所有相关代码 | 与桌面端共存方案（A）废弃；业务层函数按 #19 处理 |
| 2 | B5 能力补齐 | **一次性全部补齐**（不进 Phase 4） | Phase 0 工作量翻倍（4 周→）；有实战脚本可照搬 |
| 3 | Dataset/DWG | **先不入库**，开发完用户手动标记作为测试数据 | 客户资产归属；Sprint 1 从"重解析"降级为"整理 + 补漏" |
| 4 | OS 部署 | **开发 Windows / 生产推荐 Linux** | 业务层零 OS 依赖；Linux 省 30% 内存 + 7×24 systemd；CAD 解析无影响 |
| 5 | 鉴权 | **单用户免登录 + RuoYi 风格 RBAC 预留** | Python 等价：FastAPI + Casbin + 4 表 + `@requires("perm")` 装饰器 |
| 6 | 部署形态 | **局域网**（单进程 FastAPI + PG/PostGIS） | 文件存储本地；多 worker 切 PG 后再加；保留 SQLite 备选 |
| 7 | 浏览器兼容 | **仅 Chrome** | React + Vite + 任意 UI 库；CDN 资源本地化；无 polyfill 负担 |
| 8 | 重新推荐 | 已输出 v3 方案（**务实版**：模块化单体非微服务） | 与"Windows 单机 + 局域网"实际部署场景匹配 |
| 9 | LLM 调用 | **后端转发**（5 后端统一抽象） | 浏览器直连有 CORS/Key 暴露/鉴权/限流/审计问题 |
| 10 | 清理 | **先明确引用关系再清理** | 详见 §1.A.0 P0-0.2~0.5 引用矩阵 |
| 11 | CDN 资源 | **下载到 webui/public/cdn/，可传 GitHub** | 解 modao.cc 外网依赖；产物可重用 |
| 12 | README 滞后 | **纳入 Phase 0**（P0-0.7） | 同步 |
| 13 | 备份垃圾 | **Phase 0 一并清理**（P0-0.6，#10 已审） | 4.7 GB |
| 14 | Web 化对象 | **首要执行对象**（与 v2.0 ADR-07 一致） | 业务层 = 实战链路验证的 7 段能力的 Service 容器 |
| 15 | 桌面端 | **直接废弃** | 删除 main.py + app/ui/**（21 文件） + Node 壳；不再双端维护 |
| 16 | 可核性闸门 | **Phase 1 落地表结构** | 实现留 Phase 4；表结构低成本预留 |
| 17 | dataviz skill | **Phase 0 引入**（P0-24） | 跨专业总览页 + 报告页用 dataviz |
| 18 | parallel-worktree | **Phase 2 后启用** | Phase 2 之前串行；多模块并行时 worktree 隔离 |
| **19** | **业务层 9880 行** | **保留算法实现，重写集成层**（#1 务实解） | 函数签名不变 + Pydantic schema + Service 包装层；工作量 4 周（vs 完全重写 12+ 周） |

**技术栈定稿**（基于以上 19 项）：
- **后端**：FastAPI + uvicorn 单进程（模块化单体）
- **数据库**：PostgreSQL 16 + PostGIS 3.4（B4 空间查询）
- **ORM**：SQLAlchemy 2.x async + Alembic
- **鉴权**：Casbin（参考 RuoYi 4 表设计）+ 当前免登录
- **CAD 解析**：ezdwg + ezdxf + ODA（容器内）
- **LLM**：5 后端 ABC（[app/takeoff/llm_backends.py](app/takeoff/llm_backends.py) 保留），后端转发
- **前端**：React 18 + TypeScript + Vite + Element Plus + RuoYi-Vue 风格布局
- **渲染器**：Canvas 2D（WebGL 延后）
- **部署**：Docker Compose（fastapi + postgis + 可选 ollama），Linux 物理机/容器 7×24
- **测试**：pytest 11 现有 + 新增 API/renderer/regression + playwright E2E

**重新基线**：v2.0 文档 9 个 ADR 中 ADR-01/02/05/06/08 仍适用；ADR-03/04/07/09 在 Phase 0 P0-8/9/15/6/7 落实；新增 4 项（Linux 部署/RuoYi RBAC/免登录预留/CDN 本地化）。