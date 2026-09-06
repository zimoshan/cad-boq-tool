# 项目管理功能优化建议

## 现状评估

当前项目管理功能覆盖以下操作：

| 功能 | 数据层(db) | UI 层 | 状态 |
|---|---|---|---|
| 新建项目 | `create_project` | 顶栏「新建」按钮 | **UI 入口是文件对话框，交互不当** |
| 切换项目 | — | 顶栏下拉框 | 可用 |
| 删除项目 | `delete_project` | **无** | db 有接口，UI 缺失 |
| 重命名项目 | **无** | **无** | 完全缺失 |
| 项目设置 | `get/set_project_config` | 4 tab 对话框 | 可用，功能较全 |
| 配置导入/导出 | `import/export_project_config` | 设置对话框底部 | 可用 |
| 图纸增删 | `add/delete_sheet` | 左栏按钮 + 右键底图 | 可用 |
| 图纸重命名 | **无** | **无** | 缺失 |
| 图纸排序 | — | 按 ID 固定序 | 不可调序 |
| 项目概览 | — | 设置对话框 SourcesTab | 仅在设置弹窗内，主界面不可见 |

## 核心痛点

### 1. 新建项目交互不当
当前 `new_project()` 用 `QFileDialog.getSaveFileName`（保存文件对话框）来创建项目。用户看到的是一个"保存文件"对话框，但实际上只是在 SQLite 里 INSERT 一行记录，不产生任何文件。

**影响**：用户困惑——选了路径为什么没有文件生成？项目名取的是 `os.path.basename(name)`，用户可能输入了完整路径导致项目名异常。

### 2. 无法删除/重命名项目
`db.delete_project()` 已实现级联清理（binding_candidate → engineering_object → llm_run → block_legend → mapping → boq_item → entity → sheet → project_config → project），但 UI 上没有任何入口。用户只能通过手动操作数据库删除。

### 3. 缺少项目概览
用户在主界面无法一眼看到：
- 有几张图纸、多少实体
- BOQ 导入了多少条、映射了多少条
- 图例标定完成率
- 底图是否已设置

这些信息只在「项目设置 → 来源」tab 里，且需要打开弹窗才能看。

### 4. 图纸管理薄弱
- 不能重命名（显示名与文件名不一致时无法改）
- 不能调序（按 ID 固定，导入顺序决定显示顺序）
- 不能批量操作（一次只能删一张）
- 底图标记虽有右键菜单，但无视觉区分（仅有 `[底图]` 前缀，缺少图标/颜色）

## 优化建议（按优先级排序）

### P0：必须做（交互阻断级）

| # | 建议 | 说明 | 涉及文件 |
|---|---|---|---|
| 1 | **新建项目改为文本输入对话框** | 弹 `QInputDialog.getText`，输入项目名 + 类型/区域/专业（meta），一步到位。去掉文件保存对话框 | `main_window.py` |
| 2 | **顶栏项目下拉加右键菜单** | 右键项目项 →「重命名」「删除」「复制配置到新项目」「设为模板」。下拉框设 `setContextMenuPolicy` | `main_window.py` |
| 3 | **项目删除带确认 + 概要** | 删除前弹出确认框，列出"图纸 N 张 / BOQ N 条 / 映射 N 条"，二次确认后执行 | `main_window.py` |
| 4 | **状态栏项目概览** | 切换项目时，状态栏显示 `项目「X」· 5 图 · 3200 实体 · 128 BOQ · 已映射 45%` | `main_window.py` |

### P1：应该做（效率提升级）

| # | 建议 | 说明 | 涉及文件 |
|---|---|---|---|
| 5 | **项目列表升级为可搜索** | 项目数 > 10 时下拉框不便。加一个搜索框过滤，或改为 list view 弹出 | `main_window.py` |
| 6 | **图纸重命名** | 右键图纸 →「重命名」，修改 `sheet.filename`（db 加 `rename_sheet` 接口） | `db.py` + `main_window.py` |
| 7 | **图纸拖拽排序** | `sheet_list.setDragDropMode(InternalMove)`，拖拽后更新 `sheet.sort_order`（db 加字段） | `db.py` + `layer_tree.py` + `main_window.py` |
| 8 | **项目模板** | 项目设置对话框加「存为模板」按钮，保存 config 到 `templates/` 目录。新建项目时可选择模板 | `project_settings_dialog.py` |
| 9 | **跨项目图例复用** | 导出当前项目 block_legend → 新项目导入。已有 JSON 导入/导出，但需在新建项目时自动推荐"从已有项目导入图例" | `legend_panel.py` |
| 10 | **批量图纸操作** | 图纸列表支持 Ctrl+多选，右键「批量删除」「批量重新解析」 | `main_window.py` |

### P2：可以做（锦上添花级）

| # | 建议 | 说明 | 涉及文件 |
|---|---|---|---|
| 11 | **项目标签/分组** | `project` 表加 `tags TEXT`，顶栏加标签过滤。如 `电气 / 消防 / 给排水` | `db.py` + `main_window.py` |
| 12 | **项目归档** | `project` 表加 `archived INTEGER`，归档项目从下拉框隐藏，单独入口查看 | `db.py` + `main_window.py` |
| 13 | **项目仪表盘** | 独立面板或弹窗，展示：图纸统计/BOQ 覆盖率/图例完成率/LLM 调用历史/底图状态 | 新文件 |
| 14 | **项目间 BOQ 对比** | 选择两个项目，对比 BOQ 条目差异（哪些多了/少了/改了） | 新文件 |
| 15 | **最近项目列表** | 状态栏 / 菜单显示最近 5 个项目，点击快速切换 | `main_window.py` |
| 16 | **图纸缩略图** | 图纸列表项加缩略图图标（解析时生成 QPixmap 缩略） | `main_window.py` |
| 17 | **底图标记视觉增强** | 底图行加图标 🔵 或背景色区分，不只靠 `[底图]` 前缀 | `main_window.py` |

## 建议实施路径

```
第一批（P0，1~2 轮）：
  1. 新建项目 → 文本输入对话框
  2. 项目右键 → 重命名 + 删除
  3. 状态栏项目概览

第二批（P1，2~3 轮）：
  4. 图纸重命名
  5. 项目模板
  6. 跨项目图例复用
  7. 批量图纸操作

第三批（P2，按需）：
  8. 项目标签/归档
  9. 项目仪表盘
  10. 图纸缩略图
```

## 数据层改动清单（若实施 P0+P1）

```sql
-- project 表
ALTER TABLE project ADD COLUMN tags TEXT DEFAULT '';          -- 标签（逗号分隔）
ALTER TABLE project ADD COLUMN archived INTEGER DEFAULT 0;    -- 归档标记

-- sheet 表
ALTER TABLE sheet ADD COLUMN sort_order INTEGER DEFAULT 0;   -- 拖拽排序
-- is_base 已在本轮添加
```

```python
# db.py 新增接口
def rename_project(pid: int, name: str) -> None: ...
def rename_sheet(sid: int, filename: str) -> None: ...
def reorder_sheets(project_id: int, sheet_ids: list[int]) -> None: ...
def clone_project_config(src_pid: int, dst_pid: int) -> None: ...
def project_stats(pid: int) -> dict:  # 返回概览数据
    """{sheets, entities, boq_items, mappings, legend_calibrated, legend_total, has_base}"""
```
