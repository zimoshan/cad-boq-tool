# cad-boq-tool UI 审计报告

> 生成时间：2026-08-25
> 审计范围：`app/ui/*.py` + `app/config.py`
> 审计目的：为 Round 2/3 布局重构与视觉精炼建立完整问题清单

---

## 一、UI 文件清单与职责

| # | 文件 | 类型 | 主要职责 |
|---|------|------|----------|
| 1 | `main_window.py` | QMainWindow | 三栏布局组装、信号中枢、QSettings 持久化 |
| 2 | `canvas.py` | QGraphicsView | CAD 渲染、缩放/平移、点选/框选、主题色、定位高亮 |
| 3 | `canvas_toolbar.py` | QToolBar | 模式切换、缩放按钮、主题/全屏/面板折叠、实体类型过滤 |
| 4 | `layer_tree.py` | QTreeWidget | 图层/块名树、显隐开关、右键菜单（隔离/锁定/颜色覆盖） |
| 5 | `legend_panel.py` | QWidget+QTableWidget | 图例标定（块名→设备语义映射） |
| 6 | `boq_table.py` | QTableWidget | BOQ 清单表格、计量规则/比例编辑 |
| 7 | `mapping_panel.py` | QWidget | 映射列表 + 计量结果 + 导出按钮 |
| 8 | `selection_bar.py` | QWidget | 拾取状态条（已选 N 个 + 分配/清空 + 缩放显示） |
| 9 | `ai_results_dialog.py` | QDialog | AI 算量结果展示（筛选/接受/拒绝/导出） |
| 10 | `binding_workbench.py` | QWidget | 绑定工作台（工程对象 + 审核队列 + 候选确认） |
| 11 | `llm_settings_dialog.py` | QDialog | LLM 配置中心（5 backend tab + 测速 + Fallback） |
| 12 | `project_settings_dialog.py` | QDialog | 项目设置（4 tab：图层规则/设备规则/来源/元信息） |
| 13 | `config.py` | — | 全局配置（数据路径、模型默认值、BOQ 表头） |
| 14 | `__init__.py` | — | 空 |

---

## 二、窗口/弹窗清单与问题分析

### 2.1 主窗口（MainWindow）

| 属性 | 当前值 | 问题 |
|------|--------|------|
| 初始尺寸 | `resize(1440, 900)` | 固定值，1280×720 下太大 |
| 最小尺寸 | 未设置 | 无下限保护，极端缩放下控件会挤压 |
| 最大尺寸 | 未设置 | — |
| Splitter stretch | 左0/中5/右2 | 左栏 stretch=0 导致拉伸窗口时左栏不增长（合理） |
| 左栏 min/max | 200/320 | 合理但无折叠动画 |
| 右栏 min | 330 | 合理 |
| Canvas min | 400 | 合理 |
| 顶栏高度 | `setFixedHeight(52)` | 固定高度，DPI 150%+ 时可能太矮 |
| QSettings 持久化 | geometry + splitter + dark | **缺失**：当前 tab、面板折叠状态、recent project |
| resizeEvent | 无 | 无法响应式调整（如小窗口自动折叠面板） |
| QScrollArea | **无** | — |
| QDockWidget | **无** | — |

**主要问题**：
1. **初始 1440×900 在 1280×720 下超出屏幕** — 需根据屏幕可用尺寸 clamp
2. **无最小窗口尺寸保护** — 极端缩放时三栏挤压
3. **顶栏固定 52px** — DPI 缩放后按钮文字可能被截断
4. **QSettings 仅保存 3 项** — 缺 tab index、面板可见性、recent project
5. **无 Ctrl+B / Ctrl+Alt+B 快捷键** — 面板折叠仅靠按钮
6. **顶栏 12 个按钮水平排列** — 1280 宽度下会换行/溢出（无 wrap 策略）

### 2.2 ProjectSettingsDialog

| 属性 | 当前值 | 问题 |
|------|--------|------|
| 初始尺寸 | `resize(1200, 800)` | 1366×768 下超出屏幕高度 |
| 最小尺寸 | 未设置 | — |
| 模态 | 默认 ApplicationModal | 合理 |
| QScrollArea | **无** | 图层规则 tab 内容多时无法滚动 |
| Splitter | 内含 QSplitter（图层列表/4桶） | 合理 |
| QSS | 自定义 `_LIST_QSS` | 与全局 LIGHT_QSS 独立，样式割裂 |

**主要问题**：
1. **1200×800 在 1366×768 下高度超出** — 800 > 768-任务栏
2. **无 QScrollArea** — 图层规则 tab 有 315 个图层时，4 个桶的 QListWidget 高度不足
3. **QSS 独立于主窗口** — `_LIST_QSS` 与 `LIGHT_QSS` 中 QListWidget 样式重复定义
4. **恢复默认用 QMessageBox.question** — 返回值比较 `!= QMessageBox.Yes` 可能平台行为不一致

### 2.3 LLMSettingsDialog

| 属性 | 当前值 | 问题 |
|------|--------|------|
| 最小尺寸 | `setMinimumSize(720, 600)` | 合理 |
| 初始尺寸 | 未 resize（由 min size 决定） | 实际可能 720×600，在小屏上 OK |
| 模态 | 默认 ApplicationModal | 合理 |
| QScrollArea | **无** | 5 tab + Fallback 区在 720×600 下可能挤压 |
| QSS | 内联大段 setStyleSheet | 与全局样式完全独立，颜色硬编码 |
| 硬编码颜色 | #185FA5 / #16A34A / #94A3B8 / #DC2626 / #5A6675 / #E3E8EF | 6 种颜色散落内联 |

**主要问题**：
1. **内联 QSS 与全局 LIGHT_QSS 割裂** — 按钮颜色 / tab 样式不一致
2. **无 QScrollArea** — Fallback 区 + 5 tab + 底部按钮在 600 高度下紧凑
3. **颜色全硬编码** — 无法统一换主题
4. **QPushButton 的 hover/pressed 状态在自定义 QSS 中覆盖了全局样式**

### 2.4 AiResultsDialog

| 属性 | 当前值 | 问题 |
|------|--------|------|
| 初始尺寸 | `resize(1100, 600)` | 合理 |
| 最小尺寸 | 未设置 | — |
| 模态 | 默认 ApplicationModal | 合理 |
| QScrollArea | **无** | 大量条目时表格自身可滚但筛选区固定 |
| 表格列宽 | `_auto_resize()` 手动设固定宽度 | 描述列 Stretch，其余固定 |

**主要问题**：
1. **按钮排列** — [全部接受][接受选中][拒绝选中][导出Excel][关闭] 5 个按钮右对齐，无主次区分
2. **按钮样式** — 全部使用默认 QPushButton，无 primary/secondary/danger 层级
3. **AI推荐 vs 已确认状态不明确** — 标题写 "AI 算量结果" 但接受后直接 accept()，无"待人工复核"中间态
4. **1100×600 在 1280×720 下可用但边距紧**

### 2.5 QProgressDialog（图纸解析 / 批量导入 / AI算量 / LLM标定）

| 实例 | 模态 | 问题 |
|------|------|------|
| `_parse_dialog` | WindowModal | OK |
| `_import_dialog` | WindowModal | OK |
| `_ai_dialog` | WindowModal | OK |
| `_legend_dialog` | WindowModal | OK |

**问题**：
1. 全部使用不确定进度（range 0,0），无法显示百分比
2. 无取消按钮的对话框（`setCancelButton(None)`）— 用户无法中止

---

## 三、QSS / 主题审计

### 3.1 QSS 分布

| 位置 | 变量名 | 行数 | 作用域 |
|------|--------|------|--------|
| `main_window.py` L33-208 | `LIGHT_QSS` | ~175 行 | 全局（setStyleSheet on QMainWindow） |
| `layer_tree.py` L14-41 | `_SELECTED_QSS` | ~28 行 | LayerTree 局部 |
| `project_settings_dialog.py` L448-475 | `_LIST_QSS` | ~28 行 | ProjectSettingsDialog 局部 |
| `llm_settings_dialog.py` L199-208 | 内联 QSS | ~10 行 | LLMSettingsDialog 局部 |
| 各文件 `setStyleSheet("color:#...")` | 散落 | 1-3 行 | 单控件局部 |

### 3.2 硬编码颜色清单

| 颜色值 | 用途 | 出现文件 |
|--------|------|----------|
| `#F4F6F9` | BACKGROUND | main_window.py |
| `#FFFFFF` | SURFACE | main_window.py, llm_settings_dialog.py |
| `#1F2733` | TEXT_PRIMARY | main_window.py |
| `#5A6675` | TEXT_SECONDARY | main_window.py, llm_settings_dialog.py, binding_workbench.py, legend_panel.py, selection_bar.py |
| `#185FA5` | ACCENT | main_window.py, llm_settings_dialog.py, canvas.py |
| `#E3E8EF` | BORDER | main_window.py, layer_tree.py, project_settings_dialog.py, llm_settings_dialog.py |
| `#D5DCE6` | BORDER_INPUT | main_window.py |
| `#0C447C` | ACCENT_HOVER | main_window.py |
| `#DBE9F7` | SELECTION | layer_tree.py, project_settings_dialog.py |
| `#16A34A` | SUCCESS | llm_settings_dialog.py, project_settings_dialog.py |
| `#DC2626` | ERROR | llm_settings_dialog.py |
| `#94A3B8` | BUTTON_DISABLED | llm_settings_dialog.py |
| `#666` | TEXT_HINT | legend_panel.py, binding_workbench.py, project_settings_dialog.py |
| `#1a7a2f` | STATUS_OK | legend_panel.py |
| `#b8860b` | STATUS_WARN | legend_panel.py |
| `#EEF1F5` | CANVAS_BG | main_window.py, canvas.py |
| `#CDD6E2` | CANVAS_DOT | canvas.py |
| `#C9D2DE` | SCROLLBAR | main_window.py |

**总计 18 种硬编码颜色散布在 9 个文件中**。

### 3.3 QSS 重复与冲突

| 选择器 | LIGHT_QSS | _SELECTED_QSS | _LIST_QSS | LLM 内联 |
|--------|-----------|---------------|-----------|----------|
| `QListWidget::item:selected` | background:#185FA5; color:#FFF | background:#DBE9F7; color:inherit | background:#DBE9F7; color:inherit | — |
| `QTabBar::tab:selected` | border-bottom:2px solid | — | — | font-weight:bold |
| `QPushButton` | border:1px solid #D5DCE6 | — | — | border:none; background:#185FA5 |

**冲突**：LIGHT_QSS 全局 `QListWidget::item:selected` 用蓝底白字，但 layer_tree 和 project_settings 局部 QSS 覆盖为浅蓝底保字色。这意味着同一个 QListWidget 在不同窗口有不同选中样式。

---

## 四、布局/响应式审计

### 4.1 QSplitter 配置

| Splitter | 方向 | Stretch Factor | 问题 |
|---------|------|---------------|------|
| 主窗口 `_split_main` | Horizontal | 左0/中5/右2 | 合理但无 collapsible 属性设置 |
| ProjectSettings 内部 | Horizontal | 左2/右3 | 合理 |
| BindingWorkbench 内部 | Vertical | 默认 sizes [260,380] | 用 setSizes 而非 stretchFactor |

**问题**：
- 主 Splitter 未设置 `setChildrenCollapsible(True)` — 默认 True 但未显式确认
- 折叠机制是 `setVisible(False)` 而非 Splitter 原生 collapsible — 折叠后 splitter handle 仍可见
- 无 min size per panel when collapsed

### 4.2 QSizePolicy 使用情况

**搜索结果：零。** 整个项目未使用 `QSizePolicy` 任何地方。所有控件使用默认 size policy。

### 4.3 QScrollArea 使用情况

**搜索结果：零。** 无任何 QScrollArea。所有 Dialog 内容超高时直接溢出。

### 4.4 表格列宽策略

| 表格 | 列数 | Stretch 列 | 固定列 | 问题 |
|------|------|-----------|--------|------|
| BoqTable | 8 | 描述(col 1) | 无 | 编号/单位/数量列未设固定宽度，ResizeToContents 未使用 |
| LegendPanel | 8 | 设备类型 + 规格 | 块名(ResizeToContents) | 其余列无策略 |
| MappingPanel | 4 | 目标(col 1) | 无 | 方式/时间列可能过宽 |
| AiResultsDialog | 8 | 描述(col 2) | 0/3/4/5/6 固定宽度 | 合理但手动设宽度 |
| BindingWorkbench obj_table | 9 | 块名/图层(col 2) | 无 | 其余列无策略 |
| BindingWorkbench queue_table | 6 | BOQ描述(col 1) | 无 | 其余列无策略 |
| ProjectSettings sheet_table | 5 | 全部 Stretch | ID 列 ResizeToContents | 全部 Stretch 导致编号列过宽 |

### 4.5 DPI 适配

| 检查项 | 状态 |
|--------|------|
| `QApplication.setHighDpiScaleFactorRoundingPolicy` | **未设置** |
| `QT_AUTO_SCREEN_SCALE_FACTOR` | 未设置 |
| `QT_SCALE_FACTOR` | 未设置 |
| 图标尺寸 | 未使用 QIcon，全部文字按钮 |
| 字体尺寸 | QSS 全局 13px + 各处 11px/12px/14px/15px 硬编码 |
| 顶栏高度 | `setFixedHeight(52)` — DPI 150% 时实际 78px（Qt 自动缩放）但内容不缩放 |

---

## 五、弹窗/Dialog 类型审计

### 5.1 弹窗清单

| 弹窗 | 类 | 父窗口 | 模态 | 尺寸策略 | 滚动 | 按钮 |
|------|----|----|------|----------|------|------|
| 项目设置 | ProjectSettingsDialog | main_window | AppModal | resize(1200,800) | **无** | 6 按钮无层级 |
| LLM 设置 | LLMSettingsDialog | main_window | AppModal | minSize(720,600) | **无** | 5 按钮自定义颜色 |
| AI 结果 | AiResultsDialog | main_window | AppModal | resize(1100,600) | **无** | 5 按钮无层级 |
| 图纸解析进度 | QProgressDialog | main_window | WindowModal | 默认 | — | 无取消 |
| 批量导入进度 | QProgressDialog | main_window | WindowModal | 默认 | — | 无取消 |
| AI 算量进度 | QProgressDialog | main_window | WindowModal | 默认 | — | 有取消 |
| LLM 标定进度 | QProgressDialog | main_window | WindowModal | 默认 | — | 有取消 |
| 各类 QMessageBox | — | 各 parent | AppModal | 自动 | — | 标准按钮 |

### 5.2 弹窗问题汇总

| # | 问题 | 严重度 | 涉及弹窗 |
|---|------|--------|----------|
| 1 | **无屏幕适配** — 固定 resize 不 clamp 到可用区域 | 高 | ProjectSettings, AiResults |
| 2 | **无 QScrollArea** — 内容超高时溢出 | 高 | ProjectSettings, LLMSettings |
| 3 | **无统一 DialogFactory** — 每个弹窗自行设计 | 中 | 全部 |
| 4 | **按钮无层级** — 全部默认样式，无 Primary/Secondary/Danger | 高 | 全部 |
| 5 | **按钮位置不统一** — 有的右对齐，有的左对齐 | 中 | ProjectSettings(左+右), AiResults(右), LLMSettings(右) |
| 6 | **QSS 割裂** — LLMSettings 内联 QSS 与全局不同 | 中 | LLMSettings |
| 7 | **无多显示器适配** — dialog 始终在 primaryScreen | 中 | 全部 |
| 8 | **进度对话框无取消** — 解析/导入不可中止 | 中 | parse, import |
| 9 | **QMessageBox.question 返回值比较** — 用 `!= Yes` 而非 `== Yes` | 低 | ProjectSettings 恢复默认 |

---

## 六、信号/快捷键审计

### 6.1 快捷键

| 快捷键 | 功能 | 来源 |
|--------|------|------|
| F11 | 全屏切换 | main_window.keyPressEvent |
| Enter | 提交待选 | main_window.keyPressEvent |
| Esc | 清空待选 / 取消高亮 | main_window + canvas |
| Ctrl+滚轮 | 缩放 | canvas.wheelEvent |
| Ctrl+0 | 整图 | canvas.keyPressEvent |
| Ctrl+1 | 100% | canvas.keyPressEvent |
| Alt+Left/Right | 缩放历史 | canvas.keyPressEvent |
| **Ctrl+B** | **未实现** — 左栏折叠 | — |
| **Ctrl+Alt+B** | **未实现** — 右栏折叠 | — |

### 6.2 面板折叠

| 功能 | 当前实现 | 问题 |
|------|----------|------|
| 左栏折叠 | `setVisible(False)` + 按钮 | 1. 无快捷键 2. 无保存折叠状态到 QSettings 3. 折叠后 splitter handle 仍可见 |
| 右栏折叠 | 同上 | 同上 |
| 全屏 | 隐藏左右栏 + 保留工具栏 | 1. 无动画 2. 工具栏可能被遮挡 |

---

## 七、QSettings 持久化审计

| 持久化项 | 当前保存 | 问题 |
|---------|----------|------|
| 窗口 geometry | ✅ `saveGeometry` | OK |
| Splitter sizes | ✅ `saveState` | OK |
| 暗色主题 | ✅ `"dark"` | OK |
| 当前 Tab index | ❌ | 重启后回到默认 tab |
| 左栏可见性 | ❌ | 重启后默认可见 |
| 右栏可见性 | ❌ | 重启后默认可见 |
| 最近项目 ID | ❌ | 重启后回到列表第一个 |
| Layer tree 展开状态 | ❌ | — |
| 全屏状态 | ❌ | — |

---

## 八、信息层级审计

### 8.1 当前视觉层级问题

| 层级 | 期望 | 实际 |
|------|------|------|
| 一级（主视觉） | CAD Canvas | ✅ stretch=5 最大 |
| 二级（任务面板） | BOQ / Mapping / Legend / Binding | ✅ 右栏 Tab |
| 三级（配置） | 项目设置 / LLM 设置 | ✅ 弹窗 |
| 四级（状态） | 状态栏统计 + LLM 状态 | ✅ 底部状态栏 |

**但存在以下层级问题**：
1. **顶栏 12 个按钮视觉权重相同** — 新建/打开/导入BOQ/修复BOQ/导出图层/项目设置/AI算量/导出/图例/绑定/帮助/LLM设置 全部同级排列
2. **右栏 4 个 Tab 标题无主次** — BOQ / 计量 / 图例标定 / 绑定工作台 全部相同样式
3. **状态栏 2 个标签** — 统计标签和 LLM 状态标签视觉权重接近，但 LLM 状态有边框
4. **BOQ 表格状态列** — 只有颜色（灰/蓝/绿），无图标+文字

### 8.2 BOQ 表格状态表达

| 状态 | 当前表达 | 问题 |
|------|----------|------|
| 有映射数 | 蓝色数字 | 仅颜色 |
| 无映射 | 灰色 "0" | 仅颜色 |
| 有计量结果 | 深绿数字 | 仅颜色 |
| 无计量结果 | 灰色空 | 仅颜色 |

**违反 WCAG**：仅依靠颜色传达状态，无图标或文字辅助。

---

## 九、AI 状态区分审计

| 状态 | 当前 UI 表达 | 问题 |
|------|-------------|------|
| AI 推荐 | 表格行 + 置信度颜色 | 标题写"AI 算量结果"但无"推荐"标签 |
| 待人工复核 | 无中间态 | 接受后直接 accept()，无"待复核"标记 |
| 已确认 | 无视觉区分 | 接受后关闭弹窗，BOQ 表格中无"AI来源"标记 |
| 已拒绝 | 无反馈 | reject 信号发出但主窗口未连接 |

---

## 十、问题汇总优先级

### P0 — 必须在 Round 2 修复

| # | 问题 | 影响 |
|---|------|------|
| 1 | Dialog 无屏幕适配（resize 固定值不 clamp） | 小屏超出 |
| 2 | 无 QScrollArea（Dialog 内容溢出） | 配置项多时不可用 |
| 3 | 主窗口无最小尺寸保护 | 极端缩放控件挤压 |
| 4 | QSettings 缺失项（tab/panel/recent） | 体验不一致 |
| 5 | 无 Ctrl+B / Ctrl+Alt+B 快捷键 | 效率低 |
| 6 | 顶栏 12 按钮无分组/换行策略 | 1280 宽溢出 |

### P1 — Round 2/3 修复

| # | 问题 | 影响 |
|---|------|------|
| 7 | 按钮无层级（Primary/Secondary/Danger） | 主操作不明确 |
| 8 | 颜色硬编码 18 种散布 9 文件 | 无法统一换主题 |
| 9 | QSS 割裂（4 套独立 QSS） | 选中样式不一致 |
| 10 | 表格列宽策略不统一 | 编号列过宽/描述列不足 |
| 11 | BOQ 状态仅靠颜色 | WCAG 违规 |
| 12 | AI 状态无推荐/复核/确认区分 | 用户不知哪些是 AI 说的 |
| 13 | 无 QSizePolicy 使用 | 控件无法正确伸缩 |
| 14 | 顶栏 setFixedHeight(52) | DPI 150%+ 按钮截断 |

### P2 — Round 3 修复

| # | 问题 | 影响 |
|---|------|------|
| 15 | 进度对话框无百分比 | 体验差 |
| 16 | 无 DPI rounding policy | 高 DPI 模糊 |
| 17 | LLM Dialog 内联 QSS | 维护困难 |
| 18 | 面板折叠无保存状态 | 重启不一致 |

---

## 十一、架构建议

### 11.1 新增文件建议

```
app/ui/
├── theme.py          # 统一颜色/字体/间距常量 + QSS 生成器
├── dialogs.py        # DialogFactory + 基础 Dialog 类型
├── ui_utils.py       # center_window / fit_dialog_to_screen / window_state
└── layouts.py        # 统一 spacing/margin 常量 + 布局工厂
```

### 11.2 重构顺序（Round 2）

1. `theme.py` — 提取所有颜色/字体/间距常量
2. `ui_utils.py` — 实现 `fit_dialog_to_screen()` / `center_window()` / `save/restore_window_state()`
3. `dialogs.py` — 实现 `DialogFactory` + `BaseDialog`（含 QScrollArea）
4. `main_window.py` — 加最小尺寸 + QSettings 扩展 + Ctrl+B/Ctrl+Alt+B
5. `project_settings_dialog.py` — 加 QScrollArea + 屏幕适配
6. `llm_settings_dialog.py` — 加 QScrollArea + 统一 QSS
7. `ai_results_dialog.py` — 按钮层级 + AI 状态标记
8. `boq_table.py` — 状态列加图标+文字 + 列宽策略

### 11.3 重构顺序（Round 3）

1. `theme.py` 替换所有硬编码颜色
2. 统一 QSS（删除 `_SELECTED_QSS` / `_LIST_QSS` / LLM 内联 QSS）
3. 顶栏按钮分组（主操作 / 工具 / 设置）
4. 表格列宽统一策略
5. DPI 适配策略
6. 间距系统统一（4/8/12/16/20/24/32）

---

## 十二、验收基线

### 现有测试（不可破坏）

| 测试文件 | 用例数 | 状态 |
|---------|--------|------|
| `test_core.py` | — | PASS |
| `test_binding.py` | — | PASS |
| `test_legend.py` | — | PASS |
| `test_e2e.py` | 17 | PASS |
| `gui_smoke.py` | 11 | PASS |
| `test_llm_center_e2e.py` | 6 | PASS |

### UI 回归要求

| 分辨率 | DPI | 验收标准 |
|--------|-----|---------|
| 1280×720 | 100% | 主窗口不超出，三栏可用，顶栏不溢出 |
| 1366×768 | 100% | 同上 |
| 1440×900 | 100% | 布局舒展 |
| 1920×1080 | 100% | 画布主导，无过大留白 |
| 2560×1440 | 100% | 无过大留白 |
| 1920×1080 | 125% | 不重叠不截断 |
| 1920×1080 | 150% | 同上 |
| 1920×1080 | 175% | 同上 |
| 1920×1080 | 200% | 同上 |

---

**审计结论**：现有 UI 功能完整但布局/响应式/弹窗/主题/状态表达存在系统性问题。需按 P0→P1→P2 顺序逐步修复，不破坏现有业务逻辑与测试。
