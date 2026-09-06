# cad-boq-tool

> **当前状态（2026-09-06）**：Web 化迁移 **Phase 0** 进行中。桌面端 PySide6 已于本日起**直接废弃**（决策 #15）。本 README 在 Phase 0 完成后更新启动方式。

轻量级工程量算量工具：**读取 CAD 图纸 → 导入 BOQ 清单 → 自动绑定 → 人工审核 → Excel 保真回写**。原桌面端基于 PySide6；本仓库当前仅保留业务算法层（[app/cad](app/cad)、[app/engineering](app/engineering)、[app/binding](app/binding)、[app/takeoff](app/takeoff)、[app/boq](app/boq)、[app/llm](app/llm) 共 ~6000 行纯 Python，零 Qt 依赖），Web 化外壳（`webapi/` + `webui/`）在 Phase 0 完成后上线。

## 仓库结构（Phase 0 清理后）

```
.
├── app/                    # 业务算法层（保留，将重写为 webapi/services/* 包装层）
│   ├── cad/                # CAD 解析（ezdwg / ezdxf / ODA 三层）
│   ├── engineering/        # 工程对象提取 + 三重兜底分类
│   ├── binding/            # 四层绑定（历史 / 规则 / 语义 / LLM）
│   ├── takeoff/            # 5 LLM 后端 ABC + 实战管线
│   ├── boq/                # BOQ 解析 + Excel 回写
│   ├── llm/                # LLM 统一 runner / 审计 / 嵌入
│   ├── models.py           # 数据模型 dataclass
│   └── db.py               # SQLite 1.6K 行 SQL（Phase 0 迁 PG/PostGIS）
├── tests/                  # pytest 11 个集成测试
├── scripts/                # bench_perf.py 等运维脚本
├── docs/                   # 设计 / 决策 / 归档
│   ├── BACKLOG.md          # 唯一待办入口（v2，2026-09-06）
│   ├── _removed/           # 已废弃的 UI 相关文档归档
│   └── archive/            # 历史技术方案 / 评审归档
├── design/                 # 设计稿（main.html 等 v3 蓝本）
├── artifacts/              # 截图与产物（含 _legacy_ui/ 历史截图）
├── .gitignore              # 解除 docs/ ignore（2026-09-06）
├── CLAUDE.md               # Claude Code 项目级指令
└── README.md               # 本文件
```

## 当前启动

**Phase 0 期间**：业务层 Python 模块仍可 import，但**没有 GUI 入口**（main.py 已删除）。验证业务层完整性：

```bash
# 模块导入自检
.venv/Scripts/python.exe -c "import app.cad, app.engineering, app.binding, app.takeoff, app.boq, app.llm; print('OK')"

# pytest 11 集成测试
.venv/Scripts/python.exe -m pytest tests/ -v
```

**Phase 0 完成后**（预计 6-8 周）将补充：

```bash
# 后端
.venv/Scripts/python.exe -m uvicorn webapi.main:app --host 0.0.0.0 --port 8521

# 前端
cd webui && npm install && npm run dev
# Chrome 打开 http://localhost:5173
```

## Web 化迁移设计

- **总体方案**：方案 B 务实版（模块化单体 + FastAPI + React + Canvas 2D + PostgreSQL/PostGIS + RuoYi 风格 RBAC + Linux 部署）
- **19 项决策**（2026-09-06）：详见 [docs/BACKLOG.md §6 决策记录](docs/BACKLOG.md)
- **Phase 0（28 项细分 35）**：清理 7 + 基础设施 5 + 业务层重写 13 + 前端 2 + 测试 4 + 文档 4
- **总工期**：≈ 20-25 周
- **现状 commit 链**：
  - `pre-webify` annotated tag（Phase 0 启动前完整快照）
  - `837441f` chore: pre-webify snapshot
  - `8c250ed` chore(webify): 删除 Node 壳
  - `5056d21` chore(webify): 删除桌面端入口
  - `52c2df1` chore(webify): 归档 7 份 UI 历史文档
  - `xxx` chore(webify): 归档 4 份旧 GUI 截图
  - `xxx` chore(docs): 补 add 14 个 docs/ 文档

## 关键文档

- 唯一待办入口：[docs/BACKLOG.md](docs/BACKLOG.md) v2（§1 当前待办 / §2 暂缓 / §3 已完成 / §4 使用规则 / §5 来源文档 / §6 决策记录）
- 架构设计基线：[docs/CAD_BOQ_Web化_架构设计_v2.0.md](docs/CAD_BOQ_Web化_架构设计_v2.0.md)（9 个 ADR + 13 待确认 + 7 段能力缺口）
- 19 节逆向分析输入：[docs/驱动 Claude Code 进行桌面端程序 Web 化改造的 Prompt.md](docs/驱动%20Claude%20Code%20进行桌面端程序%20Web%20化改造的%20Prompt.md)
- 2026-09-06 评审：[docs/REVIEW_TECH_ROUTE_2026-09-06.md](docs/REVIEW_TECH_ROUTE_2026-09-06.md)、[docs/REVIEW_OPEN_SOURCE_ECOSYSTEM_2026-09-06.md](docs/REVIEW_OPEN_SOURCE_ECOSYSTEM_2026-09-06.md)
- 估算系统架构参考：[docs/估算系统技术架构与实现说明.md](docs/估算系统技术架构与实现说明.md)

## 桌面端状态

**2026-09-06 决策 #15：直接废弃**。删除范围（已在 git 历史中）：
- `main.py`（PySide6 入口）
- `app/ui/**`（21 个 Qt UI 模块）
- `src/`、`bin/`、`package.json`（Node 占位壳）
- 7 份 UI 历史文档 → `docs/_removed/`
- 4 张旧 GUI 截图 + `ui_audit.md` → `artifacts/_legacy_ui/`
- `~/.cad-boq-tool/` 下 7 个 ~5.2 GB 备份 DB

## 测试

```bash
# 11 个集成测试（pytest 框架）
.venv/Scripts/python.exe -m pytest tests/ -v

# 性能基准
.venv/Scripts/python.exe scripts/bench_perf.py
```

Phase 0 完成后新增：API 一致性测试、渲染器回归、playwright E2E。

## 贡献 / 反馈

Phase 0 期间以单人推进为主；遇到关键决策请先在 [BACKLOG §6](docs/BACKLOG.md) 查阅既有记录，并在 §1 追加新待办（按 §0 状态标准）。
