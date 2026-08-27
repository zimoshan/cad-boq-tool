# UI Audit — cad-boq-tool

## A. Layout

### Findings

- The main window already has a strong canvas-first composition, which is good.
- The top bar is overloaded: project actions, import actions, AI actions, export, settings, help, and LLM configuration are all competing for the same row.
- The left panel is useful but can become dense with both sheet list and layer tree.
- The right panel is heavily task-mixed: BOQ / mapping / legend / binding all live in a single `QTabWidget`, which is valid but not a clear mode-based architecture.

### Risk

The panel structure is workable, but the top row becomes difficult to parse at smaller widths. The app will suffer from visual clutter when the screen width shrinks.

## B. Responsive behavior

### Current behavior

- Window sizing is clamped by available screen in [app/ui/main_window.py](../app/ui/main_window.py).
- Minimum sizes are defined in [app/ui/theme.py](../app/ui/theme.py).
- State persistence is already implemented in [app/ui/ui_utils.py](../app/ui/ui_utils.py).

### Concern

The app has responsive protections, but the action density is still too high for smaller windows. The controls are likely to feel crowded in 1280×720 and mid-size laptop layouts.

## C. Dialog quality

### Current situation

The project contains a growing dialog abstraction layer, but not all windows use it.

Examples of current dialog-like flows:

- file dialogs
- progress dialogs
- confirmation dialogs
- project settings dialog
- AI results dialog
- LLM settings dialog

### Key issue

The dialog sizing strategy is mixed. Some windows are screen-fit aware, while others still rely on ad hoc sizes or modal behavior. This is the main reason the project needs a stronger dialog policy.

## D. Information architecture

### Observed problem

The UI does not yet clearly separate:

- browse mode
- mapping mode
- AI review mode
- takeoff mode
- output mode

Instead, the app exposes many functions globally without a clean current-context action model. This is the core UX problem.

## E. Table behavior

### BOQ and legend tables

The BOQ and legend tables are feature-rich and dense, with multiple columns and editing behaviors. This is a strong domain workflow, but the dense structure raises the risk of:

- column crowding
- truncated descriptions
- inconsistent width ratios
- reduced scanning speed

The app must ensure the description column has priority and the control column does not crowd the content region.

## F. CAD canvas

### Strengths

- Canvas remains the visual anchor, which is good.
- The toolbar provides zoom and mode controls.
- Selection state is visible and non-invasive.

### Risks

- The toolbar is still global and not context-aware.
- There is no strong mode-driven toolset separating browse from mapping from AI review.
- Initial layout and fit behavior should be confirmed in real runtime check.

## G. Usability

### Strength

Domain workflow is clear to users who already know the software.

### Weak points

- user does not always know which current task they are in
- action hierarchy is not obvious
- essential tasks are competing visually with lower-priority tasks
- a user cannot reliably infer “what is primary vs secondary vs tertiary” without scanning the top row

Overall, the app is functional, but the action hierarchy is not yet professional for a CAD/BOQ workflow.

## H. Verified design observations

The practical issues are visible in the current source structure itself:

- top bar does too much work
- QTabWidget mixes task context without a mode overlay
- there is no strict context-toolbar policy yet
- dialog sizing and action hierarchy are inconsistent

These are concrete UI architecture problems, not speculative style issues.
