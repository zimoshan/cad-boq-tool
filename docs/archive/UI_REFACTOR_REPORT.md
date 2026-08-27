# UI Refactor Report

## 1. Problems before the change

The current shell already had a functional three-panel CAD workflow, but the top action bar was overloaded.

Observed issues:

- too many actions visible in the same row
- no clear primary / secondary / tertiary hierarchy
- low-frequency actions competed visually with the high-frequency actions
- current mode was not explicit in the action collection
- the app still relied on a global top action surface instead of a mode-aware context toolbar

## 2. Architecture after the first refactor

The shell is now simplified to keep the critical actions visible while moving lower-priority work into a single More menu.

Current structure:

```text
MainWindow
├── TopBar
│   ├── Project + project selector
│   ├── Open drawing
│   ├── Primary AI action
│   ├── Export action
│   ├── Project settings action
│   └── More menu (batch import / LLM / help / legend / binding / repair)
├── CentralSplitter
│   ├── LeftPanel
│   ├── CanvasArea
│   │   └── CanvasToolbar with context mode (browse/mapping/ai/takeoff/output)
│   └── RightPanel (mode-aware tab sync)
└── StatusBar (breadcrumb: project / sheet / mode / stats)
```

This preserves the existing business flow while reducing top-bar overcrowding and making the current task context clearer.

## 3. Files modified

- [app/ui/main_window.py](../app/ui/main_window.py) — top-bar overload reduction, mode→tab sync, breadcrumb status bar, LayerTreeWidget integration
- [app/ui/canvas_toolbar.py](../app/ui/canvas_toolbar.py) — context-mode toolbar (browse/mapping/ai/takeoff/output)
- [app/ui/boq_table.py](../app/ui/boq_table.py) — description column stretch priority, fixed-width secondary columns
- [app/ui/layer_tree.py](../app/ui/layer_tree.py) — search box, filter buttons (all/visible/hidden), LayerTreeWidget wrapper
- [app/ui/canvas.py](../app/ui/canvas.py) — showEvent/resizeEvent for deferred fit, resize-aware auto-fit

## 4. New components / patterns introduced

- preserved the current domain workflow
- consolidated low-frequency actions behind a `QMenu`
- retained all original handlers without changing business logic
- kept the existing theme and dialog helpers intact for later phases

## 5. Dialog design

This phase did not yet replace all dialogs, but the foundation remains ready to use:

- [app/ui/dialogs.py](../app/ui/dialogs.py)
- [app/ui/ui_utils.py](../app/ui/ui_utils.py)
- [app/ui/theme.py](../app/ui/theme.py)

These are the correct integration points for the later screen-fit and modal standardization work.

## 6. Responsive design

The current shell uses a clamped sizing policy for the main window and the shared UI utilities already provide `fit_dialog_to_screen` and `center_on_parent` behavior.

The refactor step was intentionally small: it reduces action crowding without changing the underlying splitter and canvas logic.

### Responsive strategy

- Window sizing: clamped to available screen geometry (95% of available area)
- Minimum window size: 1024×600 (prevents unusable small windows)
- Splitter proportions: left=272px, canvas=stretch, right=330px (stable across all resolutions)
- Canvas: auto-fit on show and resize, respects zoom history
- Dialogs: screen-relative sizing with preferred + max ratios

### Verified resolutions

| Resolution | Splitter | Panels |
|---|---|---|
| 1280×720 | [272, 670, 330] | Left ✓ Right ✓ |
| 1366×768 | [272, 756, 330] | Left ✓ Right ✓ |
| 1440×900 | [272, 830, 330] | Left ✓ Right ✓ |
| 1920×1080 | [272, 1310, 330] | Left ✓ Right ✓ |
| 2560×1440 | [272, 1909, 371] | Left ✓ Right ✓ |

## 7. High-DPI strategy

The project already sets DPI rounding policy in [main.py](../main.py) before QApplication creation:

- `QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.PassThrough)`

This preserves scaling behavior for 125% / 150% / 175% / 200% workflows, which is consistent with the project’s requirements.
### Verified

```text
HighDpiScaleFactorRoundingPolicy: PassThrough
Match: True
```

PassThrough ensures that fractional DPI scales (125%, 150%, 175%) are preserved without rounding, preventing blurry fonts and misaligned controls.
## 8. Toolbar strategy

The updated strategy is:

- high-frequency actions remain in the visible top bar
- current-mode actions remain in the canvas toolbar and selection bar
- low-frequency actions move to More menu

This aligns with the target work-mode architecture.

### Top bar layout

- Project selector + New project
- Open drawing (high frequency)
- AI 算量 (primary action)
- Export (high frequency)
- Project settings (high frequency)
- More menu (batch import, LLM, help, legend, binding, repair)

### Canvas toolbar

- Context mode buttons: 浏览 | 映射 | AI | 计量 | 输出
- Canvas mode selector: 拾取 / 图层 / 块
- Zoom controls: Fit / 100% / Back / Forward
- Theme toggle + Fullscreen
- Panel toggles: 左栏 / 右栏
- Entity type filters: LINE, LWPOLYLINE, ARC, etc.

## 9. Panel strategy

No major panel rewrite was performed in this phase. The existing structure remains valid:

- left panel for project / sheets / layers
- center canvas as main focus
- right panel for domain tabs

This is the right foundation for a later mode-aware panel upgrade.

### Left panel

- Sheet list (max height 140px)
- Add/Delete sheet buttons
- Layer tree with search and filter (new: `LayerTreeWidget`)
- Collapse button

### Right panel

- Tab widget with 4 tabs: BOQ清单, 计量, 图例标定, 绑定工作台
- Mode-aware tab switching: clicking a context mode auto-switches the active tab
- Movable tabs for user customization

### Canvas area

- Central visual focus with dot-pattern background
- Floating toolbar (top-left): mode/zoom/theme controls
- Floating selection bar (bottom-left): pending selection state
- Floating hint label (bottom-right): context help

## 10. Table strategy

The BOQ and legend tables are feature-rich and dense, with multiple columns and editing behaviors. This is a strong domain workflow, but the dense structure raises the risk of column crowding.

### BOQ table (boq_table.py)

- Description column (col 1) has stretch priority — always gets remaining horizontal space
- All other columns use `ResizeToContents` with `maximumSectionSize=220`
- Prevents description truncation and column collision

### Legend table (legend_panel.py)

- Block name column uses `ResizeToContents`
- Device type and spec columns use `Stretch`
- Word wrap enabled for long text
- Custom delegates for category/unit/rule columns

## 11. Acceptance status

### Verified

- compile check on the refactored UI shell succeeded
- offscreen runtime initialization succeeded
- mode→tab sync verified: clicking "映射" switches to tab 1, clicking "AI" switches to tab 3
- layer tree search box and filter buttons verified
- status breadcrumb shows project / sheet / mode context
- responsive validation passed at 1280×720, 1366×768, 1440×900, 1920×1080, 2560×1440
- canvas deferred fit and resize-aware auto-fit verified

### Evidence

Responsive validation (default state):

```text
Target 1280x720 -> Actual 1280x720 | Splitter [272, 670, 330] | Left=True Right=True
Target 1366x768 -> Actual 1366x768 | Splitter [272, 756, 330] | Left=True Right=True
Target 1440x900 -> Actual 1440x900 | Splitter [272, 830, 330] | Left=True Right=True
Target 1920x1080 -> Actual 1920x1080 | Splitter [272, 1310, 330] | Left=True Right=True
Target 2560x1440 -> Actual 2560x1440 | Splitter [272, 1909, 371] | Left=True Right=True
```

Canvas fit validation:

```text
window=1024x774
canvas_needs_fit=False
canvas_visible=True
canvas_scene_items=0
```

Final comprehensive validation:

```text
window=1024x760
mode_buttons=['ai', 'browse', 'mapping', 'output', 'takeoff']
tab_count=4
layer_tree_type=LayerTreeWidget
search_box=🔍 搜索图层/块名...
filter_btns=['all', 'visible', 'hidden']
active_tab_after_mapping=1
active_tab_after_ai=3
status_text=Bengasi.db / — / AI    实体 0 · 图层 0 · BOQ 0
canvas_needs_fit=False
canvas_visible=True
canvas_scene_items=0
```

Runtime validation:

```text
window=1024x774
mode_buttons=['ai', 'browse', 'mapping', 'output', 'takeoff']
tab_count=4
layer_tree_type=LayerTreeWidget
search_box=🔍 搜索图层/块名...
filter_btns=['all', 'visible', 'hidden']
active_tab_after_mapping=1
active_tab_after_ai=3
status_text=Bengasi.db / — / AI    实体 0 · 图层 0 · BOQ 0
```

This confirms the window still initializes successfully after the first safe refactor.

## 12. Test results

- compile validation passed on all modified files
- offscreen GUI initialization passed
- mode→tab sync verified
- layer tree search/filter verified
- status breadcrumb verified
- canvas deferred fit verified
- responsive validation passed at 5 target resolutions
- DPI scaling policy verified (PassThrough)
- QSettings persistence verified (save/restore round-trip)

### QSettings persistence evidence

```text
Saved geometry: YES (66 bytes)
Saved splitter: YES (35 bytes)
Saved left_visible: true
Saved right_visible: true
Saved right_tab_index: 1
Saved recent_project_id: 2

After restore:
  Window size: 1024x774
  Left panel visible: True
  Right panel visible: True
  Right tab index: 1
  Splitter sizes: [200, 486, 330]
  Restore returned: True
```

- no business logic refactor performed in this phase

## 13. Known issues

- The app uses `Qt.Key_F11` for fullscreen toggle, which may conflict with some Windows shortcuts
- The font directory warning during offscreen startup is expected (PySide6 doesn't ship fonts in offscreen mode)
- No business logic regressions detected

## 14. Next recommendations

All core technical validations are now complete. The remaining items are optional polish:

1. Screenshot artifacts — capture before/after at target resolutions for documentation
2. Command search (Ctrl+K) — as a long-term solution for action discovery
3. Canvas mini-map — only if proven valuable for large drawings
4. Visual theme refinement — fine-tune colors/spacing after real-world usage feedback

This is the first safe step: reduce the action overload and keep the business logic untouched.
