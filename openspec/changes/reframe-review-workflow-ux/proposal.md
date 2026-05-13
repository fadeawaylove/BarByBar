## Why

BarByBar has already moved toward a professional workbench, but the remaining dissatisfaction is deeper than styling: the interface still needs a stronger training rhythm, clearer interaction modes, and a more chart-centered attention flow. This change reframes the daily review experience so users can move through prepare, replay, plan, annotate, trade, and review without feeling like they are operating a dense control panel.

## What Changes

- Define a second-stage UX direction for the main workbench around explicit work modes: Replay, Plan, Annotate, and Review.
- Redesign the primary shell around attention flow: current case context, chart-first workspace, mode-aware toolbar, right-side state center, and bottom feedback.
- Reframe the right panel as a state and action center that changes emphasis by mode while keeping critical position and trade actions stable.
- Reframe trade history as a review workspace with trade cards, entry/exit focus, decision notes, and a full detail view.
- Define a sharper professional visual direction: cooler light terminal palette, tighter radii, lower surface noise, stronger numeric hierarchy, and consistent long/short/outcome treatment.
- Add low-fidelity structural sketches and acceptance criteria before implementation so visual and interaction decisions can be reviewed deliberately.
- Preserve existing trading engine behavior, persistence semantics, CSV import, chart aggregation, order-line behavior, drawing persistence, update flow, and release workflow.

## Capabilities

### New Capabilities

- `review-workflow-ux`: Covers the reframed review workflow, mode model, attention hierarchy, chart-first shell, right state center behavior, trade review workspace, and visual acceptance criteria.

### Modified Capabilities

None.

## Impact

- Affected UI areas: main window shell, app header, training toolbar, chart workspace, right sidebar, trade-history sidebar/dialog, empty startup, status feedback, settings entry points, dataset/session entry points, and visual system tokens.
- Affected code areas when implemented: `src/barbybar/ui/main_window.py`, `src/barbybar/ui/chart_widget.py`, `src/barbybar/ui/trade_history.py`, `src/barbybar/ui/theme.py`, and related UI tests.
- Affected tests: main-window interaction tests, chart-widget visual/interaction state tests, trade-history tests, settings/session/dataset entry-point tests, and screenshot/manual smoke workflow.
- No database schema changes are expected.
- No trading engine, order execution, performance metric, update service, or repository behavior changes are expected.
