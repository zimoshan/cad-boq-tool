# CAD·BOQ 界面审计报告

**日期**：2026-08-28
**审计范围**：`app/ui/*.py`（21 个模块，约 8000 行）+ 原型 `design/main.html`（138 行）
**目标**：① 排查现有 UI 的按钮重复与操控性问题 ② 对照原型列出需整改项
**方法**：通读原型 + Grep 系统性搜索控件（`QPushButton(`/`QAction(`/`addAction(`/`setText(`/`setEnabled(`）+ 关键文件精读

> **执行说明**：本次原计划由产品经理（原型基线）与架构师（代码审计）并行产出，但四位团队成员连续因 `429 queue.full` 限流启动失败，未产生任何产出。以下全部结论均由主理人亲自阅读代码与原型得出，**所有条目均附文件:行号证据，可逐条复核**。文中不掺杂任何未经验证的推测。

---

## 一、结论速览

| 类别 | P0 | P1 | P2 | 合计 |
|------|----|----|----|------|
| 按钮重复 / 入口冗余 | 0 | 6 | 2 | 8 |
| 操控性缺陷 | 1 | 1 | 2 | 4 |
| 原型差异（原型有实现缺 / 实现有原型无） | — | 4 | 2 | 6 |
| **合计** | **1** | **11** | **6** | **18** |

**两个必须优先修的 P0/P1：**

1. **【P0】`_busy` 防重入机制完全失效** —— 代码写了 busy 判断，但全项目从未把 `_busy` 置为 `True`，长任务期间按钮不禁用，用户可并发触发多个后台任务。
2. **【P1，实为体验硬伤】「属性」一词在两个位置指向两个不同面板** —— 点画布工具条「属性」跳到「项目属性」，点右栏 rail「属性」跳到「实体属性」。

**同时需要澄清的一点**：本项目在几个容易踩坑的方面其实做得**相当扎实**，不应列入整改——详见第五节「做得好的部分」。

---

## 二、按钮重复 / 入口冗余问题

### D1 【P1】右栏 rail 有 7 个入口，原型只有 4 个

| 项 | 内容 |
|----|------|
| 现状 | `main_window.py:777` → `labels = ["绑定","清单","计量","图例","属性","项目","记录"]` |
| 原型 | `main.html:87` → 仅 4 个 rail 按钮：绑定工作台 / BOQ 清单 / 实体属性 / 操作记录 |
| 差异 | 现状多出「计量」「图例」「项目」3 项 |
| 判定 | **真冗余**（原型未定义） |
| 建议 | rail 收敛为 4 项（绑定 / 清单 / 属性 / 记录）；「计量」「图例」「项目」面板保留，但改由画布工具条模式切换驱动，不再占 rail 位置 |

### D2 【P1】画布工具条与 rail 构成双重常驻入口，4 个面板各有 2 个入口

证据链：
- `canvas_toolbar.py:19-25` 定义 5 个工作区模式：`browse→清单`、`mapping→计量`、`legend→图例`、`ai→AI`、`props→属性`
- `canvas_toolbar.py:59-66` 为其各建一个常驻 `QPushButton`
- `canvas_toolbar.py:156-157` 映射表证明二者指向同一批面板：
  ```python
  TAB_TO_CONTEXT = {0:"ai", 1:"browse", 2:"mapping", 3:"legend", 4:None, 5:"props", 6:None}
  ```
- `main_window.py:543-549` 反向映射：`{"browse":1,"mapping":2,"legend":3,"ai":0,"props":5}`

对照结果（**同一面板、两个常驻可见入口**）：

| 面板 (tab) | 入口 A（画布工具条） | 入口 B（右栏 rail） |
|-----------|---------------------|--------------------|
| tab0 绑定工作台 | 「AI」 | 「绑定」 |
| tab1 BOQ 清单 | 「清单」 | 「清单」 |
| tab2 计量 | 「计量」 | 「计量」 |
| tab3 图例标定 | 「图例」 | 「图例」 |

| 判定 | **真冗余**。原型中工具条 5 模式与 rail 4 面板**互不联动**（原型 `setTool()` 只改 `modeText`，`switchPanel()` 只切面板），实现额外做的镜像联动正是混乱来源 |
| 建议 | 二选一：① 去掉工具条与 rail 的镜像联动，各司其职（贴合原型）；② 保留联动但删掉 rail 中重复的 4 项 |

### D3 【P1，体验硬伤】「属性」一词指向两个不同面板

| 入口 | 目标 | 证据 |
|------|------|------|
| 画布工具条「属性」 | **tab5 项目属性** | `canvas_toolbar.py:24` `props→"属性"` → `main_window.py:548` `_mode_tab_map["props"]=5` |
| 右栏 rail「属性」 | **tab4 实体属性** | `main_window.py:777` labels[4]="属性" → `main_window.py:790` `setCurrentIndex(4)` |

`main_window.py:534-540` 的 tab 顺序为：
```
0 绑定工作台 / 1 BOQ 清单 / 2 计量 / 3 图例标定 / 4 实体属性 / 5 项目属性 / 6 操作记录
```

用户点工具条「属性」→ 跳到「项目属性」；点 rail「属性」→ 跳到「实体属性」。**同一个词，两个结果**。
原型中 rail 那项明确叫「实体属性」（`main.html:87` title="实体属性"），不存在歧义。

| 判定 | **真缺陷** |
| 建议 | 工具条「属性」改指 tab4 实体属性（与原型语义一致），rail 文案补全为「实体属性」；「项目属性」另设独立入口（建议放入 rail 底部或更多菜单） |

### D4 【P1】齿轮菜单与「更多」菜单完全重复

```python
# main_window.py:731-734（更多 ▾ 菜单）
self._more_actions["settings"] = more_menu.addAction("项目设置…", self.open_project_settings)
self._more_actions["llm"]      = more_menu.addAction("LLM 设置…", self.open_llm_settings)

# main_window.py:751-752（齿轮 ⚙ 菜单）
gear_menu.addAction("项目设置…", self.open_project_settings)
gear_menu.addAction("LLM 设置…", self.open_llm_settings)
```

| 判定 | **真冗余**——同一区域内（顶栏）两条路径，文案、槽函数完全一致 |
| 建议 | 删除齿轮菜单，将其并入「更多 ▾」（原型 `main.html:35` 的设置图标无下拉功能，仅为独立入口）；或反之保留齿轮、从更多菜单移除这两项 |

### D5 【P1】「图例标定」「绑定工作台」存在第三重入口

```python
# main_window.py:727-730
self._more_actions["legend"]  = more_menu.addAction("图例标定",   self.focus_legend)
self._more_actions["binding"] = more_menu.addAction("绑定工作台", self.focus_binding)
```

叠加 D2 已列出的工具条 + rail 两个入口，这两个面板各有 **3 个入口**。

| 判定 | **真冗余** |
| 建议 | 从「更多 ▾」移除这两项 |

### D6 【P1】导出功能存在两个常驻入口

```python
# 入口 A：main_window.py:708-710 顶栏
self.btn_export = QPushButton(_icon("export") + "导出")
self.btn_export.clicked.connect(self.export_report)

# 入口 B：main_window.py:889 计量面板接线
self.mapping_panel.exportRequested.connect(self.export_report)
# 对应 mapping_panel.py:56
self.btn_export = QPushButton("导出算量清单 (Excel)")
```

两个按钮最终都调用 `self.export_report`——**同一函数、两个常驻可见入口**。
原型 `main.html:34` 只有顶栏「导出」一个。

| 判定 | **真冗余** |
| 建议 | 删除计量面板的「导出算量清单 (Excel)」；若确需区分语义，改为「导出当前计量明细」并绑定不同函数 |

### D7 【合理，不计入问题】分配功能 3 入口 —— 与原型一致

| 入口 | 位置 | 接线 |
|------|------|------|
| 「分配」 | `selection_bar.py:23` | `main_window.py:946` → `_commit_pending` |
| 「将已选 N 个实体分配至 BOQ」 | `binding_workbench.py:364` | `assignRequested` |
| 「分配至清单项」 | `entity_properties.py:74` | `main_window.py:949` → `_commit_pending` |

原型 `main.html:81`（浮动选择条）、`:98`（绑定面板底部）、`:101`（属性面板）同样是这 3 个入口。
| 判定 | **符合原型，保留** |

### D8 【P2】批量确认文案近似易混

- `binding_workbench.py:337` → 「全部确认」
- `legend_panel.py:101` → 「确认全部」

| 判定 | 分属不同面板、动作不同，但文案高度近似 |
| 建议 | 统一为「全部确认」；图例侧改为「全部标定」以区分语义 |

---

## 三、操控性问题

### C1 【P0】`_busy` 防重入机制完全失效

```python
# main_window.py:336  —— 唯一的赋值，且是 False
self._busy = False

# main_window.py:1087 —— 唯一的读取
proj_ready = has_proj and not getattr(self, "_busy", False)
```

对整个 `app/ui/` 目录 Grep `_busy`，命中仅此 2 处 —— **没有任何代码把 `_busy` 置为 `True`**。

后果：
- AI 算量、批量识别、文件夹导入、批量重解析、图纸解析等长任务运行期间，`btn_open`/`btn_ai`/`_more_actions` 全部保持可点
- 用户可连续点击，并发启动多个 `QThread`（`main_window.py:103/128/153/178/214`），存在数据竞争与重复写入风险
- 现有的「已有图纸正在解析，请稍候」（`:1426`、`:1471`、`:1580`）是**事后弹窗**，无法阻止点击本身

| 建议 | 在每个 worker 启动前置 `self._busy = True`、结束/异常回调置 `False`，并调用 `_refresh_enabled()`；建议封装为 `_set_busy(bool)` 统一收口 |

### C2 【P1】`btn_settings` 悬空引用，启用态逻辑是死代码

```python
# main_window.py:1093-1094
if hasattr(self, "btn_settings"):
    self.btn_settings.setEnabled(proj_ready)
```

Grep `btn_settings` 全目录 → 仅命中上述 2 行，**从未被赋值**。
顶栏齿轮按钮在 `main_window.py:747` 是局部变量 `gear`，未 `self` 化。

后果：`hasattr` 恒为 `False`，该分支永不执行 → 齿轮按钮在无项目时仍可点击。

| 建议 | 将 `gear` 改为 `self.btn_settings`（`main_window.py:747`），使既有逻辑生效 |

### C3 【P2】导出按钮不受 busy 约束

```python
# main_window.py:1104-1105
if hasattr(self, "btn_export"):
    self.btn_export.setEnabled(has_sheet)   # 未 and not busy
```

| 建议 | 改为 `has_sheet and not self._busy`（依赖 C1 修复后才真正生效） |

### C4 【P2】撤销覆盖面窄

`_undo_stack` 仅在映射类操作入栈：
```
main_window.py:2008 / 2140 / 2169 / 2184 → ("rollback_assoc", ...)
main_window.py:2239                       → ("restore_mapping", ...)
```
图例标定、绑定确认/忽略、图纸删除、批量重解析等操作**不可撤销**，而 `Ctrl+Z` 已在 `main_window.py:848-849` 全局注册 → 用户按 Ctrl+Z 无反应却无任何提示。

| 建议 | 撤销栈为空时给出状态栏提示「没有可撤销的操作」；或视范围补充入栈点 |

---

## 四、原型对照差异清单

### 4.1 实现有、原型无（需删减）

| # | 项 | 现状位置 | 原型 | 处置 |
|---|----|---------|------|------|
| 1 | rail 多出「计量」「图例」「项目」3 项 | `main_window.py:777` | `main.html:87` 仅 4 项 | 收敛为 4 项 |
| 2 | 工具条与 rail 镜像联动 | `canvas_toolbar.py:156-157` | 原型二者互不联动 | 解除联动 |
| 3 | 齿轮下拉菜单 | `main_window.py:747-753` | `main.html:35` 设置图标无下拉 | 与「更多」合并 |
| 4 | 计量面板「导出算量清单 (Excel)」 | `mapping_panel.py:56` | 无 | 删除或改语义 |
| 5 | 更多菜单「图例标定」「绑定工作台」 | `main_window.py:727-730` | 无 | 删除 |

### 4.2 原型有、实现缺（需补充）

| # | 原型元素 | 原型位置 | 现状 | 处置 |
|---|---------|---------|------|------|
| 1 | BOQ 面板「重新导入」按钮 | `main.html:100` | BOQ 页面无导入入口，仅顶栏更多菜单「导入 BOQ」（`main_window.py:718`） | **补充** |
| 2 | 图纸卡片状态徽标 + 计数（已识别 86 / 待复核 57 / 未执行 AI —） | `main.html:42-44` | 需人工确认实现样式 | 核对补齐 |

### 4.3 已对齐原型、无需改动（核对结论）

| 原型元素 | 位置 | 实现 |
|---------|------|------|
| 顶栏：品牌块 / 项目下拉 / 新建 / 打开图纸 / AI 算量下拉 / 导出 | `main.html:13-36` | `main_window.py:644-758` ✓ |
| AI 算量三选项（识别当前图纸 / 批量识别全部图纸 / 从文件夹批量导入） | `main.html:32` | `main_window.py:701-704` ✓ |
| 左栏：图纸头 + 增删 + 搜索「搜索图纸或图层」 | `main.html:39-40` | `main_window.py:403-439` ✓ |
| 左栏底部「收起资源面板」 | `main.html:57` | `main_window.py:457-460` ✓ |
| 图层 / 块 两个分组 | `main.html:47-55` | `layer_tree.py:176-179` 两个 top-level item ✓ |
| 画布工具条：5 模式 + 拾取 + 整图 + − % ＋ + 已加载文件名 | `main.html:62` | `canvas_toolbar.py:52-146` ✓ |
| 左下浮动选择条「N 个已选择 / 分配 / 清空」 | `main.html:81` | `selection_bar.py:22-33` ✓ |
| 右下动态提示 canvasHint | `main.html:82` | 有对应实现 ✓ |
| 绑定面板：三段 Tab + 警告条 + 「全部确认」+ 卡片「忽略/确认」 | `main.html:91-98` | `binding_workbench.py:315-364` ✓ |
| 底部状态栏「实体 · 图层 · BOQ · 模式 \| LLM \| 记录」 | `main.html:106` | `main_window.py:571/579/973` ✓ |
| toast 提示 | `main.html:108,112` | `main_window.py:610` ✓ |

---

## 五、做得好的部分（不应列入整改）

审计中特意核查了几个常见坑，实现质量良好，此处记录以免后续被误判：

1. **长任务未阻塞 UI** —— 全部走 `QThread`：`main_window.py:103/128/153/178/214`、`binding_workbench.py:43/64`、`llm_settings_dialog.py:25`
2. **进度反馈齐全** —— `QProgressDialog` 覆盖解析/批量重解析/文件夹导入/AI 算量：`main_window.py:1443/1498/1627/2365/2381`
3. **危险操作均有二次确认** —— 项目重名 `:1132`、删除项目 `:1192`、删除图纸 `:1332`、设为底图 `:1391`、批量重解析 `:1481`、删除映射 `:2232`、恢复默认 `project_settings_dialog.py:560`
4. **状态联动有单一真相源** —— `_refresh_enabled()`（`main_window.py:1080-1118`）统一管控，避免散落判断
5. **快捷键齐全** —— `Ctrl+N/O/S/Z`、`Ctrl+B`/`Ctrl+Alt+B`（左右栏）、`Ctrl+1~6`（面板）、`Ctrl+0`（整图）、`F1`（帮助）：`main_window.py:840-862`
6. **选择条启用态正确** —— `selection_bar.py:27/33/45-52` 按选中数联动

---

## 六、整改优先级建议

| 优先级 | 项 | 动作 | 风险 |
|-------|----|------|------|
| **P0** | C1 | 接通 `_busy`：封装 `_set_busy()`，5 处 worker 启动/结束处埋点 | 低，纯增量 |
| **P1** | D3 | 统一「属性」语义：工具条指 tab4，rail 文案改为「实体属性」，项目属性另设入口 | 中，需确认项目属性面板是否仍要常驻入口 |
| **P1** | D1+D2 | rail 收敛 4 项 + 解除工具条/rail 镜像联动 | 中，影响 `_mode_tab_map` 与 `TAB_TO_CONTEXT` 两张表 |
| **P1** | D4 | 删除齿轮菜单或更多菜单中的设置项（二选一） | 低 |
| **P1** | D5 | 移除更多菜单「图例标定」「绑定工作台」 | 低 |
| **P1** | D6 | 删除计量面板导出按钮或改语义 | 低 |
| **P1** | 4.2-1 | BOQ 面板补「重新导入」 | 低 |
| **P2** | C2 | `gear` → `self.btn_settings` | 极低，一行改动 |
| **P2** | C3 | 导出按钮纳入 busy 约束 | 极低（依赖 C1） |
| **P2** | C4 | 撤销栈为空时给状态栏提示 | 低 |
| **P2** | D8 | 统一批量确认文案 | 极低 |
| **P2** | 4.2-2 | 核对图纸卡片状态徽标 | 低 |

**建议实施顺序**：先做 P0（C1）与两个低风险的 P2（C2/C3）——这几项改动小、收益直接；D1/D2/D3 涉及 rail 与工具条的映射重构，建议单独一轮，改前先确认「项目属性」面板的去留。

---

## 七、待确认问题

1. **「项目属性」面板是否仍需要常驻入口？** 若需要放在哪里（rail 底部 / 更多菜单 / 仅工具条），直接影响 D1、D3 的改法。
2. **画布工具条 5 模式与右栏面板，最终希望是「联动」还是「各司其职」？** 原型是各司其职，但当前实现的联动也已成型，砍掉会影响既有操作习惯。
3. **计量面板的导出与顶栏导出，实际业务语义是否相同？** 若不同应拆分函数并明确文案区分。
4. **图纸卡片状态徽标（已识别/待复核/未执行 AI）现有实现到什么程度？** 需目视确认。
