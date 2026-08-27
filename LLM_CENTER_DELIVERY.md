# LLM 配置中心 交付总览（任务二十九 P1-P6）

> 实施日期：2026-08-25 · `cad-boq-tool` 项目 · SeniorDeveloper 工作流

## TL;DR

**6 阶段全部交付、回归全绿、5 张图端到端通**。本轮解决了 P0 级 BUG：硬编码 `OllamaBackend`（runner.py）+ 无 DB 持久化 + 无 fallback + 无测速 / 切换 UI。

## 一、交付清单

| 阶段 | 文件 | 内容 |
|---|---|---|
| **P1** | `app/db.py` | `llm_settings` 单例表（19 列）+ CRUD + activate；副修 `get_conn()` stale-shm 自愈 |
| **P2** | `app/llm/settings.py` ⭐新增 | `load_active()` + `to_settings_dict()` + `probe_backend()` + `resolve_runtime()` |
| **P3** | `app/llm/runner.py` | 删硬编码 → `create_backend(settings)` 工厂；fallback 路径修复 model 错位 BUG |
| **P4** | `app/ui/llm_settings_dialog.py` ⭐新增 | QDialog + 5 Tab + 状态条 + Fallback 区 + 后台测速线程 |
| **P5** | `app/ui/main_window.py` | 「⚙ LLM 设置」按钮 + 状态栏 LLM 标签（动态刷新 `〔+FB〕`） |
| **P6** | `test_llm_center_e2e.py` ⭐新增 | 5 张图端到端（147 EO）+ LLM 真实调用冒烟 |

## 二、关键技术决策

1. **单例 PK=1**：`llm_settings` 全局唯一行，不绑 project_id（所有项目共享同一 LLM 配置，可后续扩展为 per-project override）。
2. **配置中心 + factory 解耦**：5 个 backend 已在 `takeoff/llm_backends.py` 定义好，runner 只是缺调用层；本次终于把它接进配置 + UI。
3. **签名 100% 向后兼容**：`run_llm_with_retry` 入参（model/host/temperature/timeout/max_tokens）维持原签名，新增可选默认从 settings 灌。
4. **Fallback 模型选择**：fallback backend 应当用自己配置的 model（如 fallback=ollama 用 ollama_model 而非主 backend 的 gpt-4o）。原版 inherit 主 model 是 BUG，已修。
5. **测速后台线程**：避免 UI hang；最长 5s。
6. **Stale-shm 自愈**：发现 Windows + Python sqlite + WAL 三者某些组合下会出现 OS 级文件锁未释放，导致新连接 `PRAGMA journal_mode=WAL` 失败 + 写入 readonly。`get_conn()` 加两次重试 + 删 `-shm/-wal` 后退回 DELETE 模式。**属生产可用性的关键补丁**。
7. **api_key masked 输入**：默认 `QLineEdit.Password`，可勾选显示。

## 三、验证矩阵

| 验证项 | 结果 |
|---|---|
| `pyflakes app/...` | 0 警告 |
| `test_core.py` | ALL CORE TESTS PASSED |
| `test_binding.py` | ALL BINDING(P1+P2+P3+P4) TESTS PASSED |
| `test_legend.py` | ALL LEGEND TESTS PASSED |
| `test_e2e.py` | 17/17 PASS |
| `gui_smoke.py` | 11/11 PASS |
| `test_llm_center_e2e.py` | 6/6 PASS（5 张图 + LLM Smoke） |
| 真实 Ollama 调用 | `ok=True model=qwen2.5:7b tokens=29/6` |

### 5 张图端到端数据（Bengasi 项目）

| 图纸 | entities | EO | 耗时 |
|---|---|---|---|
| 08-LBH ups power point system | 46555 | 56 | 63.5s |
| 31-LBH medical device weak current | 42897 | 53 | 40.1s |
| 01-LBH lighting facade system | 107 | 4 | 3.4s |
| 01-LBH lighting ground floor outdoor | 11833 | 26 | 5.3s |
| 22-LBH emergency announcement (vertical) | 520 | 8 | 1.8s |
| **合计** | **101 912** | **147** | — |

## 四、用户实操步骤

1. **重启 GUI**（解决 stale-shm 锁）。
2. 顶部「⚙ LLM 设置」按钮 → 弹出 5 tab 配置对话框。
3. 选择 backend（默认 Ollama），调模型（qwen2.5:7b 已就绪）。
4. 「🔌 测试连接」→ 验证连接 + 看可用模型样本。
5. 启用 Fallback（可选）：主 backend 失败时自动切到备用。
6. 「💾 保存」→「⭐ 设为激活」即生效。
7. 状态栏右下角显示 `LLM: ollama/qwen2.5:7b` 或 `〔+FB〕`。

## 五、已知遗留（不影响本期）

- **ODA 27.1.0 在 Python 子进程下偶发 crash**（exit 0xC0000409）：pre-existing dwg.py 问题，与本轮无关。下游跟进建议 `creationflags=CREATE_NEW_CONSOLE` 或 `CREATE_NO_WINDOW` 测试。
- **openai SDK 未装**：所有云端 backend 走 `urllib` 直接 HTTP（probe 支持；runner 因 `OpenAIBackend` 仍依赖 SDK 暂未跑通）。如需云端 LLM：`pip install openai`。
- **5 张图中 139 个图层未归类**（之前项目级配置中心遗留）：用户需在「项目设置」用关键词批量归类。

## 六、回归全绿覆盖范围

- 数据层：9 张表 + llm_settings 单例 + ON DELETE CASCADE 完整保留
- 工程对象：4 桶常量 + 项目规则驱动提取 + 严格模式
- 绑定：candidate 全状态机 + LLM/Embedding/Rule 多路生成 + 拒绝后不再推荐
- LLM：JSON Schema 校验 + 自动重试 + 全量审计 + **fallback 切换**
- UI：浅色主题 + 画布英雄区 + 高亮 + 图例三层 + 绑定工作台
