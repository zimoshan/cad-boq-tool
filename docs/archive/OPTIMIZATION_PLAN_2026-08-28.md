# CAD·BOQ 界面优化实施清单

**日期**：2026-08-28
**上游文档**：`docs/ui_audit/UI_AUDIT_REPORT_2026-08-28.md`（审计报告，18 条问题）
**状态**：✅ 决策已全部收齐，第一批、第二批均可执行

---

## 0. 已确认决策

| # | 决策项 | 结论 |
|---|--------|------|
| 1 | 整改节奏 | **分两批**：第一批低风险项，第二批映射重构 |
| 2 | 项目属性面板(tab5) | **移出 rail**，仅保留在「更多 ▾」菜单 |
| 3 | 工具条 5 模式 vs 右栏 rail | **解耦，各司其职**（贴合原型）：工具条只切画布模式，rail 独立切面板 |
| 4 | 齿轮按钮 | **完全移除**，设置项并入「更多 ▾」 |
| 5 | 计量面板导出按钮 | **删除**，全局只留顶栏一个导出入口 |
| 6 | 第二批附加范围 | 补齐原型缺失项 + 删减更多菜单冗余项 + 操控性打磨项 |
| 7 | 计量面板入口 | **rail 保留 5 项**（绑定/清单/计量/属性/记录） |
| 8 | busy 防重入范围 | **纳入** binding_workbench 内部两个 worker |

---

## 0.1 ⚠️ 解耦后的面板可达性推演（重要）

解除工具条与 rail 联动后，7 个面板中不在 rail 上的必须有替代入口。逐一核对结果：

| tab | 面板 | rail 入口 | 替代入口 | 结论 |
|-----|------|----------|---------|------|
| 0 | 绑定工作台 | ✅「绑定」 | 更多菜单（拟删） | rail 直达，菜单项可删 |
| 1 | BOQ 清单 | ✅「清单」 | — | rail 直达 |
| 2 | 计量 | ✅「计量」 | — | **由决策 7 保留**，否则无入口 |
| 3 | 图例标定 | ❌ | 更多菜单「图例标定」 | **必须保留菜单项**（见 B2-7 修正） |
| 4 | 实体属性 | ✅「属性」 | — | rail 直达，tooltip 需补全 |
| 5 | 项目属性 | ❌ | 更多菜单（B2-5 新增） | 已安排 |
| 6 | 操作记录 | ✅「记录」 | 状态栏「🕘 记录」 | rail 直达 |

**由此产生的两处修正**（已体现在下方清单）：
- **B2-2**：rail 由 4 项改为 **5 项**（决策 7）
- **B2-7**：更多菜单**只删「绑定工作台」，保留「图例标定」**——它是图例面板解耦后的唯一入口

---

## 1. 第一批：低风险项（可立即执行，5 项）

### B1-1 【P0】接通 `_busy` 防重入机制

**问题**：`main_window.py:336` 只赋过 `False`，全项目无处置 `True`；`:1087` 的 busy 判断形同虚设。

**改动**：
1. 新增统一方法（建议放在 `_refresh_enabled` 附近）：
   ```python
   def _set_busy(self, busy: bool):
       self._busy = busy
       self._refresh_enabled()
   ```
2. 在 **6 处**主窗口 worker 启动前置 `True`、结束/异常回调置 `False`：

   | 位置 | Worker |
   |------|--------|
   | `main_window.py:2361` | `_AiTakeoffWorker`（AI 算量单图） |
   | `main_window.py:2376` | `_AiTakeoffFolderWorker`（AI 算量文件夹） |
   | `main_window.py:1433` | `ParseWorker`（重新解析） |
   | `main_window.py:1591` | `ParseWorker`（图纸解析） |
   | `main_window.py:1492` | `_BatchReparseWorker`（批量重解析） |
   | `main_window.py:1622` | `_ImportFolderWorker`（文件夹导入） |

3. **（决策 8）** 纳入 `binding_workbench.py:403`（`_BindingWorker`）与 `:417`（`_ClassifyWorker`），通过信号回调主窗口 `_set_busy`。

**验收**：AI 算量运行中，顶栏「新建/打开图纸/AI 算量」及更多菜单项目级动作应置灰；任务结束后自动恢复。

---

### B1-2 删除 `btn_settings` 死代码

**问题**：`main_window.py:1093-1094` 引用从未赋值的 `self.btn_settings`，`hasattr` 恒为 `False`。

**改动**：因决策 4 已确定移除齿轮按钮，此处**直接删除**该 4 行（而非修复引用）。

---

### B1-3 导出按钮纳入 busy 约束

**改动**：`main_window.py:1104-1105`
```python
# 现：self.btn_export.setEnabled(has_sheet)
self.btn_export.setEnabled(has_sheet and not self._busy)
```
**依赖**：B1-1 生效后才真正起作用。

---

### B1-4 统一批量确认文案

**改动**：`legend_panel.py:101` 「确认全部」→ 「全部标定」
（`binding_workbench.py:337` 「全部确认」保持不变，二者语义由此区分）

---

### B1-5 撤销栈为空时给出提示

**问题**：`Ctrl+Z` 已全局注册（`main_window.py:848-849`），但撤销栈仅覆盖映射类操作（`:2008/2140/2169/2184/2239`），无操作时按键静默无反应。

**改动**：`main_window.py:2093` `_undo_last()` 中，在 `if not self._undo_stack:` 分支加状态栏提示「没有可撤销的操作」。

---

## 2. 第二批：结构重构（8 项）

### B2-1 移除顶栏齿轮按钮

**改动**：删除 `main_window.py:746-758`（注释 + `gear` 定义 + `gear_menu` + 字体设置 + `addWidget`）。

---

### B2-2 右栏 rail 收敛为 5 项，建立显式索引映射

**问题**：rail 现有 7 项（`main_window.py:777`），且 `main_window.py:790` 用 `idx=i` 直接当 tab 索引。收敛后索引不再一一对应，**必须改为显式映射**。

**改动**：
1. `main_window.py:777` → `labels = ["绑定", "清单", "计量", "属性", "记录"]`
2. `main_window.py:778-779` tips 同步精简为 5 项
3. 新增模块级常量：
   ```python
   # rail 按钮序 → right_tabs 索引
   # 0 绑定工作台 / 1 BOQ 清单 / 2 计量 / 4 实体属性 / 6 操作记录
   RAIL_TAB_INDEX = [0, 1, 2, 4, 6]
   ```
4. `main_window.py:790` → `self.right_tabs.setCurrentIndex(RAIL_TAB_INDEX[idx])`
5. tooltip 文案补全：「属性」→「实体属性（当前选择）」，消除与「项目属性」的歧义

**注**：`main_window.py:834` 的 `setCurrentIndex(6)`（记录）保持不变。

---

### B2-3 解除工具条与 rail 的镜像联动

**问题**：4 组双重常驻入口（AI↔绑定、清单↔清单、计量↔计量、图例↔图例）。原型中二者互不联动（原型 `setTool()` 只改 `modeText`，`switchPanel()` 只切面板）。

**改动**：

| 文件:行 | 动作 |
|---------|------|
| `canvas_toolbar.py:154-166` | 删除 `TAB_TO_CONTEXT` 常量与 `sync_context_from_tab()` 方法 |
| `main_window.py:811` | 删除 `self.canvas_toolbar.sync_context_from_tab(idx)` 调用 |
| `main_window.py:543-549` | 删除 `_mode_tab_map` |
| `main_window.py:957-963` | `_on_context_mode_changed()` 中删除 tab 切换分支，只保留 `_refresh_status_breadcrumb()` |

**保留**：`_on_mode_changed()`（`main_window.py:952`）与状态栏「模式 X」——对应原型 `main.html:125` 的 `setTool()` 行为。

---

### B2-4 项目属性移入「更多 ▾」菜单

**改动**：
1. 新增 `focus_project_properties()` 方法（仿 `focus_legend` @ `main_window.py:2484`），内设 `setCurrentWidget(self.project_properties)`
2. 在 `main_window.py:731` 附近 `more_menu` 中注册：`more_menu.addAction("项目属性…", self.focus_project_properties)`

---

### B2-5 删除计量面板导出按钮

**改动**：
1. 删除 `mapping_panel.py:56` `self.btn_export = QPushButton("导出算量清单 (Excel)")`
2. 删除 `main_window.py:889` `self.mapping_panel.exportRequested.connect(self.export_report)`
3. 清理 `mapping_panel.py` 中 `exportRequested` 信号的声明与触发点

---

### B2-6 精简「更多 ▾」菜单（**修正版**）

**改动**：**只删除「绑定工作台」**（`main_window.py:729-730`）。

| 项 | 处置 | 理由 |
|----|------|------|
| 「图例标定」(`:727-728`) | **保留** | 图例面板解耦后**唯一入口**，删了就到不了 |
| 「绑定工作台」(`:729-730`) | **删除** | rail「绑定」已直达，属第三重入口 |

---

### B2-7 补齐原型缺失项

| 项 | 原型位置 | 改动 |
|---|---------|------|
| BOQ 面板「重新导入」按钮 | `main.html:100` | 在 `boq_page`（`main_window.py:520-521`）补按钮，绑定 `self.import_boq`（`:1797`） |
| 图纸卡片状态徽标 | `main.html:42-44` | 核对现有实现是否已呈现「已识别 / 待复核 / 未执行 AI」+ 计数，否则补齐 |

---

### B2-8 操控性打磨

- 撤销栈空提示（若 B1-5 未合并执行）
- 逐一核对关键面板（绑定候选列表、BOQ 表格、图层树、图纸列表）的空状态引导文案

---

## 3. 执行顺序与风险

| 批次 | 项 | 改动量 | 风险 |
|------|----|--------|------|
| **第一批** | B1-1 ~ B1-5 | 约 45 行 | 低——纯增量，不动布局 |
| **第二批** | B2-1/2/4/5/6/7/8 | 约 60 行 | 中——涉及 rail 索引映射、菜单增删 |
| **第二批** | B2-3（解耦） | 约 30 行删除 | **较高**——三处互逆映射表联动，需完整回归 |

**建议**：
1. **第一批可直接执行**。完成后你用真实数据验证「AI 算量期间按钮置灰」。
2. **第二批中 B2-3 解耦建议单独提交一次**，便于回滚。
3. **回归检查清单**（第二批完成后）：
   - 工具条 5 模式切换 → 状态栏「模式 X」正确、右栏不跳面板
   - rail 5 项切换 → 各自跳到正确面板
   - 更多菜单全部项可用（尤其「图例标定」「项目属性…」）
   - `Ctrl+1~6` 快捷键（`main_window.py:860-862` `_on_ctrl_tab_shortcut`）——**改 rail 数量后需同步核对索引**
   - 状态栏「🕘 记录」→ 跳操作记录面板

---

## 4. 遗留待确认（不阻塞实施）

1. **图纸卡片状态徽标**现有实现到什么程度？需目视确认后才能定 B2-7 的具体补法。
2. **`Ctrl+1~6` 快捷键语义**：当前是按 tab 序号 1-6 跳面板（`main_window.py:992-993` `setCurrentIndex(idx-1)`）。rail 收敛后 tab 索引未变，但**快捷性能否到达 tab3（图例）、tab5（项目属性）需一并确认**——若希望与 rail 5 项一致，需改为按 `RAIL_TAB_INDEX` 映射。
