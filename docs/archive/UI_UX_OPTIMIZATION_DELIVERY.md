# cad-boq-tool UI/UX 全面优化与响应式适配 — 最终交付报告

> 任务：将 `cad-boq-tool` 从“功能工程工具”升级为“专业桌面工程软件界面”，覆盖 1280×720 ~ 4K 屏幕、100% ~ 200% DPI，且保持现有 CAD/BOQ/AI 功能零回归。

---

## 一、三轮执行摘要

| 轮次 | 目标 | 主要交付 | 完成状态 |
|------|------|----------|----------|
| Round 1 | UI 审计 | `ui_audit.md`：12 章审计报告，识别 18 处硬编码颜色、4 个独立 QSS 块、0 处 QScrollArea/快捷键/面板折叠/窗口状态持久化 | ✅ |
| Round 2 | 布局与弹窗重构 | 4 个基础设施文件 + 8 个现有 UI 文件改造：响应式布局、Dialog 工厂、屏幕适配、面板折叠、快捷键、QScrollArea、状态持久化 | ✅ |
| Round 3 | 视觉精修 | 输入控件/进度条/ToolTip/斑马纹 QSS、硬编码颜色清零、DPI PassThrough、真实视觉验证截图 | ✅ |

---

## 二、新增/改造文件清单

### 2.1 新增基础设施

| 文件 | 作用 |
|------|------|
| `app/ui/theme.py` | 统一设计系统：颜色、字体、间距、布局常量、QSS 生成函数 |
| `app/ui/ui_utils.py` | 屏幕适配 clamp、窗口居中、完整状态持久化、按钮工厂、QScrollArea 包装 |
| `app/ui/dialogs.py` | BaseDialog / ConfirmDialog / ConfigDialog / DialogFactory |
| `app/ui/layouts.py` | 标准化布局工厂（vbox/hbox/form/tight_vbox/dialog_vbox） |
| `verify_round2.py` | Round 2 离屏验证：三档分辨率 clamp、QScrollArea、快捷键、状态持久化 |
| `verify_round3.py` | Round 3 视觉验证：全局 QSS 断言 + 主窗口/对话框离屏截图 |

### 2.2 修改的现有 UI 文件

| 文件 | 关键改动 |
|------|----------|
| `app/ui/main_window.py` | 应用 `T.MAIN_QSS`；屏幕自适应初始尺寸；`Ctrl+B/Ctrl+Alt+B` 面板折叠快捷键；完整窗口状态持久化；状态栏 token 化 |
| `app/ui/llm_settings_dialog.py` | 全局 QSS；`fit_dialog_to_screen(..., "medium")`；降低 minimumSize 避免小屏溢出；保存按钮 `primaryBtn` |
| `app/ui/project_settings_dialog.py` | 全局 QSS + 列表选中样式；`fit_dialog_to_screen(..., "config")`；LayerRulesTab 右侧 4 桶包 QScrollArea；底部按钮层级 |
| `app/ui/ai_results_dialog.py` | 屏幕适配；接受/拒绝按钮层级 |
| `app/ui/layer_tree.py` | 选中样式改用 `T.generate_item_selected_qss()` |
| `app/ui/legend_panel.py` | 提示文字 token 化 |
| `app/ui/binding_workbench.py` | 提示文字 token 化；BOQ 表格斑马纹 |
| `app/ui/boq_table.py` | 状态显示从“纯颜色”改为“图标 + 文字 + 颜色”（WCAG AA）；颜色 token 化；斑马纹 |
| `app/ui/canvas.py` | 画布点阵颜色改用 theme token |
| `main.py` | 高 DPI PassThrough 策略；全局默认字体 `Microsoft YaHei UI` |

---

## 三、设计系统（Design Token）

全部集中在 `app/ui/theme.py`：

- **颜色**：`BACKGROUND`, `SURFACE`, `BORDER`, `TEXT_PRIMARY/SECONDARY/DISABLED`, `ACCENT`, `SUCCESS`, `WARNING`, `ERROR`, `SELECTION`, `HOVER`
- **字体**：`FONT_FAMILY`（微软雅黑优先）、`FONT_SIZE_APP_TITLE/SECTION/BODY/CAPTION`
- **间距**：`SP_1=4` 基准网格，`DIALOG_MARGIN=16`, `PANEL_MARGIN=8`
- **布局**：主窗口最小 1024×600、左/右侧面板默认宽度、画布最小宽度
- **对话框尺寸策略**：small/medium/large/review/config/fullscreen 的屏幕相对比例与期望尺寸

QSS 通过 `generate_main_qss()` 统一生成，主窗口与所有对话框均应用同一份 `T.MAIN_QSS`，保证视觉一致。

---

## 四、响应式与适配策略

### 4.1 主窗口

- 初始尺寸：`min(1440, 屏幕宽度×0.95) × min(900, 屏幕高度×0.9)`
- 最小尺寸：`1024×600`
- 三分栏 `QSplitter`：左/中/右拉伸因子 0:5:2，支持拖拽与折叠
- 左右面板可通过按钮或 `Ctrl+B / Ctrl+Alt+B` 切换显隐
- 面板宽度、分隔条位置、tab 索引、可见性、最近项目 ID 均持久化到 `QSettings`

### 4.2 对话框

- `fit_dialog_to_screen(dialog, preferred, policy, avail)` 按策略 clamp 到屏幕可用区域
- 支持 6 种 policy：small / medium / large / review / config / fullscreen
- 处理 `setMinimumSize` 与屏幕 clamp 的冲突：屏幕放不下时主动降低 minimumSize，避免对话框超出屏幕
- 复杂配置对话框内容区包 `QScrollArea`（Header 固定 + Content 滚动 + Footer 固定）

### 4.3 DPI

- `main.py` 设置 `HighDpiScaleFactorRoundingPolicy.PassThrough`，保留 125%/150%/175% 等非整数缩放，避免取整导致模糊
- 全局默认字体 `QFont("Microsoft YaHei UI", 13)`，缺失时按 `SansSerif` 回退

---

## 五、关键交互改进

| 功能 | 实现 |
|------|------|
| 面板折叠 | 工具栏按钮 + `Ctrl+B`（左栏）/ `Ctrl+Alt+B`（右栏） |
| 窗口状态 | 恢复 geometry、splitter、tab 索引、面板可见性、最近项目 ID |
| 按钮层级 | primaryBtn（蓝色填充）、dangerBtn（红色填充）、默认 secondary（白底蓝边） |
| 状态可访问性 | BOQ 表格状态使用 `✓ 1.2` / `— 0` 等“图标 + 文字 + 颜色”，不单纯依赖颜色 |
| 表格体验 | BOQ/工程对象/审核队列/图纸来源表格均开启斑马纹 + 统一 hover/selected 样式 |
| 输入控件 | QLineEdit/QTextEdit/QSpinBox 等统一圆角边框、聚焦态 |

---

## 六、测试回归结果

全部使用项目 `.venv` 直接运行：

| 测试 | 结果 |
|------|------|
| `test_core.py` | ALL CORE TESTS PASSED |
| `test_legend.py` | ALL LEGEND TESTS PASSED |
| `test_binding.py` | 15/15 PASS (A–J) |
| `test_e2e.py` | 17/17 PASS |
| `test_llm_center_e2e.py` | 6/6 OK |
| `gui_smoke.py` | 11/11 PASS |
| `verify_round2.py` | 15/15 PASS（分辨率 clamp / QScrollArea / 快捷键 / 持久化） |
| `verify_round3.py` | 12/12 PASS（QSS 样式 / 主窗口 + 对话框截图 / 斑马纹） |

---

## 七、真实视觉验证

通过 `verify_round3.py` 在离屏平台加载系统字体 `C:\Windows\Fonts\msyh.ttc` 后抓取：

1. **`verify_round3_mainwindow.png`**：主窗口构建正常，顶栏/工具栏/状态栏/浮动操作条均渲染，按钮层级样式生效。
2. **`verify_round3_project_settings.png`**：项目设置对话框应用全局 QSS，4 个分类桶由 QScrollArea 包裹，primary 保存按钮蓝色白字，绿色强调按钮正常。
3. **`verify_round3_llm_settings.png`**：LLM 设置对话框输入控件/下拉框/复选框/数字框样式统一，保存按钮 primary 样式生效。

（截图文件与本文档同目录，可直接查看。）

---

## 八、已知说明与后续建议

1. **离屏字体**：`verify_round3.py` 已显式加载 `msyh.ttc` 以保证截图可读；生产环境由 `app.setFont()` 指定并自动回退。
2. **暗色模式**：主窗口已保留 `_dark` 切换与 canvas 主题，当前 QSS 为浅色专业主题；暗色 QSS 可在 `theme.py` 中扩展 `generate_dark_qss()`。
3. **图标**：当前按钮统一使用 emoji 图标（🔌 💾 ⭐ ⚡ 等），风格一致；如需 SVG 图标，可在 `ui_utils.create_*_button` 中注入 `QIcon`。
4. **进一步可优化**：
   - 绑定工作台审核队列增加行内操作按钮（确认/拒绝）
   - 为 legend_panel 增加图例状态色块 + 文字
   - 暗色主题完整 QSS 化

---

*交付时间：2026-08-25*  
*执行环境：Windows / PySide6 6.7.2 / Python 3.11（项目 .venv）*
