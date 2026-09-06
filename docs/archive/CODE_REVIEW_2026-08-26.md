# 图纸算量工具 (cad-boq-tool) 代码审计报告

**审计日期**: 2026-08-26
**审计范围**: 全量源码（app/ 目录 60+ 模块，~8000 行 Python）
**审计方法**: 结构审查 + 逐文件通读 + 交叉引用分析

---

## 一、项目概览

| 维度 | 内容 |
|---|---|
| 项目定位 | 轻量桌面应用：CAD 图纸 → BOQ 清单 → 人工映射 → 自动算量 → Excel 导出 |
| 技术栈 | Python 3.11+ / PySide6 / ezdxf / ezdwg / openpyxl / SQLite (WAL) |
| 架构 | 五层：`cad`（解析）→ `boq`（清单）→ `engineering`（工程对象）→ `binding`（绑定）→ `ui`（界面） |
| 外部依赖 | LLM (Ollama/DashScope/OpenAI/DeepSeek)，ODA File Converter (DWG 转 DXF) |

---

## 二、整体架构评价

### ✅ 优点

1. **模块化清晰**：`cad/`, `boq/`, `engineering/`, `binding/`, `llm/`, `takeoff/`, `ui/` 职责边界明确
2. **数据层稳定**：SQLite WAL + FK + 事务，schema 设计合理（12 表 + 索引），`entity.handle` 跨会话稳定
3. **LLM 抽象层设计好**：`llm_backends.py` 的 `LLMBackend` ABC + 5 个实现 + 工厂方法，切换 backend 零修改
4. **双后端 CAD 解析**：`reader.py` 统一 ezdxf/ezdwg 接口，`_EntityWrapper`/`_DxfProxy` 桥接层设计精巧
5. **容错机制完善**：`db.py` WAL→DELETE 降级、stale-shm 自愈；`cad_parser.py` 单实体异常不中断整图
6. **审计追溯体系**：`llm_run` 表记录每次 LLM 调用（prompt 版本/输入输出 hash/token 用量/耗时），便于复现和成本分析
7. **LLM 三重兜底**：规则→知识库→LLM 分类，离线优先，成本可控

### ⚠️ 架构级风险

1. **db.py 过于臃肿**（1370+ 行）：包含 schema 定义、迁移、12 个表的 CRUD、业务逻辑（`reparse_boq`、`summarize_layers`）。建议拆分为 `db/schema.py`、`db/migrate.py`、`db/project.py`、`db/sheet.py` 等。
2. **main_window.py 过度膨胀**（1915+ 行）：承载了项目管理、图纸解析、BOQ 导入、映射操作、AI 算量、图例标定、绑定工作台、导出等所有交互逻辑。建议按功能域拆分为独立 Controller/Presenter。

---

## 三、按模块审计详情

### 3.1 `app/config.py` — 全局配置

| 级别 | 问题 | 位置 |
|---|---|---|
| 🟡 中 | `MODEL_NAME = ""` / `EMBEDDING_MODEL = ""` 已被 `llm_settings` 表取代，但 `config.py` 的常量仍被 `runner.py` 第 84 行引用（`temperature` fallback 逻辑），存在两套配置源 | config.py:40-41 |

**建议**：删除 `MODEL_NAME`/`EMBEDDING_MODEL`/`MODEL_PROVIDER`，统一从 `db.get_llm_settings()` 读取。

---

### 3.2 `app/db.py` — 数据层

| 级别 | 问题 | 位置 |
|---|---|---|
| 🔴 高 | **SQL 注入风险（低概率但存在）**：`get_entities` 第 677 行 `sql += f" LIMIT {int(limit)}"` — `limit` 来自调用方参数，虽然做了 `int()` 转换，但不是参数化查询 | db.py:677 |
| 🔴 高 | **SQL 注入风险**：`import_project_config` 第 497 行 `f"UPDATE project_config SET {k}=?"` — `k` 来自 `config_dict` 的 key，未做白名单校验（与 `set_project_config` 不同） | db.py:494-498 |
| 🟡 中 | **性能风险**：`replace_entities` 先 DELETE 再 executemany INSERT，大图（10 万+ 实体）时耗时高。建议用事务包装 + 考虑 `INSERT OR REPLACE` 或临时表 swap | db.py:651-664 |
| 🟡 中 | **连接泄漏隐患**：每次 `get_conn()` 都创建新连接，`with get_conn() as conn:` 模式在异常时依赖 SQLite 自动 rollback，但 `get_entities_by_ids` 循环内多次创建连接 | db.py:773-785 |
| 🟢 低 | `_migrate` 仅做 ADD COLUMN，无版本号机制。未来列变更复杂时会失控 | db.py:281-291 |

---

### 3.3 `app/cad/reader.py` — CAD 读取抽象层

| 级别 | 问题 | 位置 |
|---|---|---|
| 🔴 高 | **ezdwg Rust panic 不可捕获**：文档已说明但代码中 `_EntityWrapper.__getattr__` 的 fallback 路径仍可能触发。`_DocWrapper` 的 layer 缓存预建（第 429-438 行）是正确修复，但 `probe_dwg_support` 只测了 `graph()` 不测实体迭代 | reader.py:583-599 |
| 🟡 中 | **乱码判定启发式可能误判真中文图层名**：`is_garbled_layer_name` 在 codepoint span < 0x1500 时判定为乱码（第 96 行），3 个字符的真中文名（如"配电室"）可能被误判 | reader.py:90-98 |
| 🟡 中 | **`_MspWrapper.__len__` 对 ezdwg 走 `sum(1 for _ in self)`**：需要完整迭代一次 modelspace，O(N) 且可能触发 Rust panic（虽有 layer 缓存） | reader.py:410-417 |

---

### 3.4 `app/cad/cad_parser.py` — DXF 解析

| 级别 | 问题 | 位置 |
|---|---|---|
| 🟡 中 | **SPLINE 长度计算过于保守**：仅用控制点多边形近似（第 78-82 行），对高曲率样条误差可达 30%+。注释已说明"保守估算"，但未告知用户精度损失 | geometry.py:71-82 |
| 🟡 中 | **INSERT 块属性序列化**：`_entity_geom` 第 163-165 行 `attribs = entity.attribs or {}` 对 ezdwg 返回的可能是复杂对象，`json.dumps` 序列化时可能失败 | cad_parser.py:162-165 |
| 🟢 低 | `_collect_block_geometry` 嵌套展开深度限制 8 层，但无总实体数限制，超深嵌套块可能导致内存暴涨 | cad_parser.py:296-303 |

---

### 3.5 `app/boq/boq_parser.py` — BOQ 解析

| 级别 | 问题 | 位置 |
|---|---|---|
| 🟡 中 | **表头探测只扫前 5 行**：部分工程 BOQ 表头在第 8-10 行（多级表头合并单元格），此时回退到 `code=0, desc=1, unit=2` 硬编码，大概率错位 | boq_parser.py:63-74 |
| 🟡 中 | **列错位自愈过于激进**：`re.search(r"[A-Z0-9._-]{4,}", unit)` 匹配到合法型号（如 DN100）时会错误交换 desc/unit | boq_parser.py:90-91 |
| 🟢 低 | `_to_float` 对 `","` 千分位做了替换，但不处理 `" "` 空格千分位（如 `"1,234.56"` → 正确，`"1 234.56"` → 0.0） | boq_parser.py:31-36 |

---

### 3.6 `app/llm/runner.py` — LLM 调用编排

| 级别 | 问题 | 位置 |
|---|---|---|
| 🔴 高 | **`temperature` 赋值逻辑错误**：第 83-84 行 `temperature = llmc.quality_threshold and 0.1 or 0.1` — 当 `quality_threshold=0.7` 时表达式结果恒为 `0.1`，这行代码实际是 no-op（永远 0.1），与设计意图（"缺省从 settings 读"）不符 | runner.py:83-84 |
| 🟡 中 | **Fallback 链中 `attempts_fb` 可能未定义**：若 `fallback_backend_name` 为空（不触发 fallback），第 227 行 `attempts_fb if fallback_backend_name else 0` 中 `attempts_fb` 未赋值，但 Python 短路求值不会触发。不过代码可读性差 | runner.py:225-231 |
| 🟡 中 | **重试时追加错误提示到 user prompt**：第 123 行 `user = user + f"\n\n# 上次输出未通过校验..."` — 修改了函数参数 `user`（字符串），不影响调用方，但 fallback 分支第 178 行 `retry_user = user` 拿到的是已被污染的 user | runner.py:123, 178 |

---

### 3.7 `app/binding/matcher.py` — 绑定匹配

| 级别 | 问题 | 位置 |
|---|---|---|
| 🟡 中 | **`already_bound` 性能问题**：`db.get_mappings(sheet_id=eo.sheet_id)` 取该图纸全部映射再逐条比对 block_name/layer_name，当映射量大时 O(N)。建议加 `block_name`/`layer_name` 索引或反查 | rule_matcher.py:89-100 |
| 🟡 中 | **`historical_confirmed` 逐条查 `get_engineering_object`**：第 79 行在循环内 N+1 查询，候选多时性能差 | rule_matcher.py:74-86 |

---

### 3.8 `app/takeoff/orchestrator.py` — AI 算量主流程

| 级别 | 问题 | 位置 |
|---|---|---|
| 🟡 中 | **LLM fallback 替换逻辑脆弱**：第 259-269 行用 `code == fb_it.get("code")` 匹配需要替换的条目，但 LLM 输出的 code 不稳定（同一设备可能返回不同 code），导致替换失败或误替 | orchestrator.py:259-269 |
| 🟡 中 | **`TakeoffConfig` 的 `fallback_backend` 类型是 `object`**：实际期望 `LLMBackend` 实例，但类型注解为 `object`，缺少运行时检查 | orchestrator.py:48 |

---

### 3.9 `app/ui/main_window.py` — 主窗口

| 级别 | 问题 | 位置 |
|---|---|---|
| 🔴 高 | **线程安全：QThread 信号回调中直接操作 DB**：`_AiTakeoffWorker.run()` 中 `takeoff_pipeline` 内部调用 `db.get_conn()`，与主线程的 DB 操作无锁保护。SQLite WAL 模式允许并发读但写入仍需序列化 | main_window.py:56-66 |
| 🟡 中 | **`_recalc_and_refresh` 被重复调用**：第 1593 行 `self._refresh_mappings(item_id) if item_id else None` 和第 1595 行 `if item_id: self._refresh_mappings(item_id)` — 两次调用相同逻辑 | main_window.py:1593-1595 |
| 🟡 中 | **`_current_item` 线性搜索**：第 1397-1400 行遍历全部 BOQ 条目找 id，BOQ 条目多时 O(N)。建议缓存 `item_id → BoqItem` 映射 | main_window.py:1394-1400 |
| 🟡 中 | **`_find_boq_for_entity` 双重 O(N)**：遍历全部 BOQ × 每条目查映射，最坏 O(N×M)。大型项目（1000+ BOQ 条目）可能卡顿 | main_window.py:1463-1476 |
| 🟢 低 | **导入的 `QFileDialog` 重复**：`ai_takeoff_single` 第 1615 行 `from PySide6.QtWidgets import QFileDialog` 重复导入（顶部已导入） | main_window.py:1615 |

---

### 3.10 `app/takeoff/llm_backends.py` — LLM 后端

| 级别 | 问题 | 位置 |
|---|---|---|
| 🟡 中 | **API Key 明文存储**：`llm_settings` 表中 `dashscope_api_key`/`openai_api_key` 等以明文存储在 SQLite。虽然 SQLite 是本地文件，但无加密保护 | db.py:170-199 |
| 🟡 中 | **`OllamaBackend.is_available` 用 `urllib` 直连**：未使用项目统一的 HTTP 客户端，异常处理较粗糙 | llm_backends.py:92-98 |
| 🟢 低 | **`estimate_cost` 输出 token 按 3x 计费**：硬编码比例（第 250 行），不同模型差异大（DeepSeek 14x），参考价值有限 | llm_backends.py:246-250 |

---

### 3.11 `app/measure.py` — 计量引擎

| 级别 | 问题 | 位置 |
|---|---|---|
| 🟡 中 | **面积因子平方处理**：第 46 行 `factor_eff = factor * factor` — 当 `scale_factor=0.001`（mm→m）时，面积因子为 `0.000001`，正确。但如果用户误填 `scale_factor=1000`（m→mm 反了），面积会放大 100 万倍，无校验 | measure.py:43-48 |
| 🟢 低 | **圆面积兜底用 `3.14159...` 而非 `math.pi`**：第 28 行硬编码 π，而 `cad_parser.py` 用 `math.pi`，两处不一致 | measure.py:28 |

---

## 四、安全审计

| 类别 | 严重程度 | 详情 |
|---|---|---|
| SQL 注入 | 🟡 中 | `import_project_config` 的 `k` 未做白名单校验（第 497 行）；`get_entities` 的 `limit` 做了 `int()` 但不是参数化 |
| API Key 泄露 | 🟡 中 | LLM API Key 明文存储在 `~/.cad-boq-tool/projects.db`，无加密。建议用 `keyring` 或至少 Base64 + OS 隔离 |
| 路径遍历 | 🟢 低 | `read_cad` 接受任意路径，但只读不写，风险可控 |
| 线程安全 | 🟡 中 | QThread + SQLite WAL 无显式锁，高并发写入可能 `database is locked` |
| 临时文件 | 🟢 低 | `tempfile.mkdtemp(prefix="cadboq_")` 创建临时目录但未见清理逻辑，长期运行会积累 |

---

## 五、性能审计

| 位置 | 问题 | 建议 |
|---|---|---|
| `db.get_entities` | 每次调用都做 `json.loads(bbox)` / `json.loads(color)`，大图（10 万实体）时 JSON 反序列化耗时显著 | 考虑 bbox 用 4 列 REAL 替代 TEXT JSON |
| `db.get_entities_by_ids` | 循环内多次 `get_conn()`，应复用连接 | 改为单连接内分批查询 |
| `_recalc_and_refresh` | 遍历全部 BOQ 条目重新计算，即使只需更新一条 | 仅更新目标条目 |
| `_find_boq_for_entity` | O(N×M) 遍历 | 建立 entity_id → boq_item_id 反向索引 |
| `mapping_count` | 调用 `mapped_entity_ids` 再 `len()`，后者做了完整实体查询 + 去重 | 对于纯计数，用 SQL COUNT 替代 |
| `summarize_layers` | 跨全部图纸查全量 entity 行（仅取 layer/dxf_type/block_name），大项目时 I/O 重 | 用 SQL GROUP BY 聚合 |

---

## 六、代码质量

| 类别 | 状态 | 说明 |
|---|---|---|
| 类型注解 | ✅ 良好 | 全部函数有参数/返回值类型注解，使用 `from __future__ import annotations` |
| Docstring | ✅ 良好 | 每个模块、核心函数都有中文 docstring |
| 命名规范 | ✅ 良好 | snake_case 函数/变量，PascalCase 类，语义清晰 |
| 异常处理 | ⚠️ 部分过度 | 多处 `except Exception: pass`（如 `reader.py`、`cad_parser.py`），吞掉所有异常可能导致静默失败 |
| 测试覆盖 | ❌ 不可见 | 未找到 `test/` 目录下的测试文件（README 提到 `test_core.py`、`test_e2e.py`、`gui_smoke.py` 但不在仓库中） |
| 日志 | ✅ 良好 | `RotatingFileHandler` 5MB×3 轮转，关键路径有 `logger.debug/info/exception` |
| 代码重复 | ⚠️ 中等 | `db.py` 多个 `get_conn() + execute + fetchall + [Model(**dict(r)) for r in rows]` 模式高度重复，可提取泛型 CRUD |

---

## 七、关键修复建议（按优先级）

### P0 — 必须修复

1. **`runner.py:83-84` temperature 赋值 bug**
   ```python
   # 修复前（恒为 0.1）
   temperature = llmc.quality_threshold and 0.1 or 0.1
   # 修复后
   temperature = 0.1  # 或从 llmc 读取配置值
   ```

2. **`db.py:494-498` SQL 注入风险**
   ```python
   # 修复：加白名单
   _PROJECT_CONFIG_ALLOWED = {"layer_rules", "block_rules", "meta"}
   for k in _PROJECT_CONFIG_ALLOWED:
       if k in config_dict:
           conn.execute(f"UPDATE project_config SET {k}=?, ...")
   ```

3. **`main_window.py:1593-1595` 重复调用**
   ```python
   # 删除重复行
   # self._refresh_mappings(item_id) if item_id else None  # 删除
   if item_id:
       self._refresh_mappings(item_id)
   ```

### P1 — 建议修复

4. **API Key 加密存储**：迁移到 OS keyring 或至少做混淆
5. **`db.get_entities_by_ids` 连接复用**：改为单连接分批查询
6. **`rule_matcher.py:79` N+1 查询**：批量查 `engineering_object`
7. **SPLINE 长度精度**：对高曲率样条用 De Boor 算法采样近似

### P2 — 建议优化

8. **`db.py` 拆分**：schema / migrate / crud / business 逻辑分离
9. **`main_window.py` 拆分**：按功能域提取 Controller
10. **补充单元测试**：核心链路（parse → measure → export）至少 80% 覆盖
11. **临时文件清理**：注册 `atexit` 或用 `tempfile.TemporaryDirectory`

---

## 八、总结

| 维度 | 评分 | 说明 |
|---|---|---|
| 架构设计 | ⭐⭐⭐⭐ | 模块化好，LLM 抽象层精巧，双后端 CAD 解析是亮点 |
| 代码质量 | ⭐⭐⭐ | 类型注解/文档良好，但有 SQL 注入风险和重复代码 |
| 错误处理 | ⭐⭐⭐ | 关键路径有容错，但部分 `except Exception: pass` 过于宽泛 |
| 性能 | ⭐⭐⭐ | 大图场景有优化空间（JSON bbox、N+1 查询、重复计算） |
| 安全 | ⭐⭐⭐ | 无严重漏洞，API Key 明文存储是最大风险 |
| 可维护性 | ⭐⭐⭐ | `db.py` 和 `main_window.py` 过大，需拆分 |
| 测试 | ⭐ | 测试文件不在仓库中，无法评估覆盖度 |

**综合评价**：这是一个功能完整、架构合理的 demo 级产品。核心业务流程（CAD 解析 → BOQ 映射 → 计量 → 导出）实现正确，LLM 集成设计前瞻。主要技术债集中在 `db.py` 和 `main_window.py` 的规模膨胀、SQL 注入防护、以及测试缺失。建议在进入生产前优先修复 P0 项并补充核心链路测试。
