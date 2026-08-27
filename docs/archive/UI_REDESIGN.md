# UI Redesign Proposal — cad-boq-tool

## 1. Target layout

The current shell is already close to a good basic layout, but it needs a clearer work-mode architecture.

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Project / Open / Save / More                                          │
├──────────────────────────────────────────────────────────────────────┤
│ Browse | Mapping | AI Binding | Takeoff | Output                     │
├───────────────┬───────────────────────────────┬──────────────────────┤
│ Project /     │            Canvas             │   Current Context    │
│ Sheet / Layer │                               │   BOQ / Mapping /    │
│ Panel         │                               │   Legend / Review    │
├───────────────┴───────────────────────────────┴──────────────────────┤
│ Current project / current sheet / current mode / stats / status      │
└──────────────────────────────────────────────────────────────────────┘
```

This is the target shape, adapted to the project’s actual structure.

## 2. Action hierarchy

### High-frequency actions

These should remain visible:

- open drawing
- new project
- project switch
- AI takeoff
- import BOQ
- export report
- project settings

### Current-mode actions

These should move into a context toolbar that updates by mode:

- Browse: fit, zoom, layer visibility, isolate layer
- Mapping: assign, clear, bulk associate, review selection
- AI Binding: accept, reject, rerun match, review suggestions
- Takeoff: recalc, conflict check, export detail
- Output: export BOQ, mapping, report

### Low-frequency actions

These should move to a “More” menu or settings menu:

- LLM settings
- help
- repair BOQ
- export layer list
- legend calibration utilities
- advanced project housekeeping

## 3. Dialog strategy

The app should use a consistent dialog system:

- confirm dialogs for short destructive actions
- config dialogs for team/project settings
- review dialogs for AI validation tables
- progress dialogs for long-running import / parse / batch jobs
- simple properties should not be modal dialogs unless necessary

Where possible, project metadata and simple settings should remain side panel content instead of a floating dialog.

## 4. Table strategy

The BOQ and legend tables should enforce stronger column policies:

- description column gets stretch priority
- code/id columns remain fixed width
- unit/qty columns remain compact
- action columns stay narrow
- the table should be scrollable vertically rather than compressing content into unreadable widths

## 5. Layer tree strategy

The left layer tree should become more searchable and easier to scan:

- search box
- filter by visible / mapped / unmapped
- group by category
- show counts
- allow expand / collapse state retention

## 6. Canvas strategy

The canvas should remain the center of gravity. It should always be the largest and most dominant visual area.

Recommended primitives:

- fit to drawing on open
- fit selection when a target is selected
- fit to sheet when switching sheets
- zoom controls with clear access
- mode-driven tool states rather than a global toolbar overload

## 7. Status clarity

Users should always know:

- which project is active
- which sheet is open
- which mode they are in
- how many entities / layers / BOQ rows are active
- whether the current task is ready, running, or blocked

The status bar should be concise and not become a technical log.

## 8. Recommended first refactor

The first implementation should not rewrite the business logic. It should only do the following:

1. shrink top-bar overload by moving secondary actions to a `More` menu
2. keep current-mode actions in a context toolbar
3. standardize dialog sizing and parent/modality behavior
4. preserve split proportions and restore state
5. standardize theme tokens and spacing

That is the safest and most valuable incremental refactor for this codebase.
