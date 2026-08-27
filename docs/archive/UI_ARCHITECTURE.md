# UI Architecture — cad-boq-tool

## 1. Main window structure

The actual app shell in the current codebase is a single `MainWindow` with a three-panel layout:

```text
MainWindow
├── TopBar
│   ├── Brand / project selector
│   ├── Project actions
│   ├── Import / BOQ actions
│   ├── AI actions
│   ├── Export actions
│   └── Secondary actions
├── CentralSplitter
│   ├── LeftPanel
│   │   ├── Project / Sheet list
│   │   ├── Add / Delete sheet actions
│   │   ├── Layer / Block tree
│   │   └── Collapse button
│   ├── CanvasArea
│   │   ├── CanvasView
│   │   ├── CanvasToolbar (floating top-left)
│   │   ├── SelectionBar (floating bottom-left)
│   │   └── Hint label (floating bottom-right)
│   └── RightPanel
│       └── QTabWidget
│           ├── BOQ清单
│           ├── 计量
│           ├── 图例标定
│           └── 绑定工作台
└── StatusBar
    ├── Stats label
    └── LLM status label
```

This structure is assembled in [app/ui/main_window.py](../app/ui/main_window.py).

## 2. State model

The main window keeps key runtime state in member variables, including:

- `_project_id`
- `_sheet_id`
- `_mode` (`pick`, `layer`, `block`)
- `_current_item_id`
- `_current_blocks`
- `_stat_entities`
- `_stat_layers`
- `_stat_boq`

The UI is driven mainly by signals from child widgets. Examples:

- `CanvasToolbar.modeChanged` -> `_on_mode_changed()`
- `selection_bar.assignRequested` -> `_commit_pending()`
- `layer_tree.layerVisibilityChanged` -> `canvas.set_layer_visible()`
- `boq_table.itemSelected` -> `_on_item_selected()`
- `legend_panel.locateRequested` -> `_on_legend_locate()`

## 3. Current action ownership

The central action surface is currently concentrated in the top bar created by `_build_topbar()`:

- project creation
- project switching
- open drawing
- batch import
- BOQ import
- repair BOQ
- export layer list
- project settings
- AI takeoff
- export report
- legend panel focus
- binding workbench focus
- help
- LLM settings

This is the main reason the top toolbar becomes overloaded and harder to scan.

## 4. Dialog inventory

Current dialogs and windows are created in the app via QWidget/QDialog patterns and progress dialogs, including:

- project creation dialog flow (`QFileDialog.getSaveFileName`)
- file open dialogs (`QFileDialog.getOpenFileName`)
- folder import dialogs (`QFileDialog.getExistingDirectory`)
- confirmation dialogs (`QMessageBox.question`)
- progress dialogs (`QProgressDialog`)
- project settings configuration dialog in [app/ui/project_settings_dialog.py](../app/ui/project_settings_dialog.py)
- LLM settings dialog in [app/ui/llm_settings_dialog.py](../app/ui/llm_settings_dialog.py)
- AI results dialog in [app/ui/ai_results_dialog.py](../app/ui/ai_results_dialog.py)

Several of these are implemented without a single shared dialog sizing policy, which is why the screen-fit pattern is inconsistent.

## 5. UI utility layer already exists

The project has already started a shared UI foundation:

- [app/ui/theme.py](../app/ui/theme.py) — global palette, spacing, sizing constants, QSS generator
- [app/ui/ui_utils.py](../app/ui/ui_utils.py) — `fit_dialog_to_screen`, `center_on_parent`, `save_window_state`, `restore_window_state`
- [app/ui/dialogs.py](../app/ui/dialogs.py) — `BaseDialog`, `ConfirmDialog`, `ConfigDialog`, `DialogFactory`
- [app/ui/layouts.py](../app/ui/layouts.py) — talk-to-layout factory utilities

This is important because the redesign should build on this foundation instead of replacing the whole UI layer.

## 6. Architectural issue to solve

The current architecture is functionally complete but not optimized for action hierarchy:

- high-frequency tasks: too mixed with low-frequency tasks in the top bar
- canvas is visually strong, but the toolbar logic is still global instead of mode-aware
- right-side BOQ / mapping / legend panel is rich but not structured as a clear work mode context
- dialog sizing is not universally consistent

This is the design issue the next refactor will address.
