## Why

BarByBar already has enough review-training functionality for a major version, but the current interface still feels like a collection of Qt utility panels rather than a professional trading review workbench. The next major version should make the existing product feel coherent, beautiful, fast to operate, and worthy of long-term daily use.

## What Changes

- Redesign the main workbench information architecture around a professional trading-review terminal: application-level navigation, training toolbars, chart-first workspace, right-side training state center, and bottom status feedback.
- Rebuild the visual system for the desktop UI: typography scale, color roles, spacing, surfaces, button hierarchy, inputs, cards, tables, tabs, dialogs, focus states, disabled states, selected states, busy states, and error states.
- Redesign the top area so low-frequency app management actions no longer compete with high-frequency replay, timeframe, drawing, and order-preview actions.
- Redesign the right sidebar as a training state center with clear sections for current position, quick trade actions, line/order tools, replay statistics, display controls, and review entry points.
- Redesign trade history from a utility list/table into a review center that supports scanning trades, focusing entry/exit points, editing review notes, and understanding each trade at a glance.
- Redesign settings, dataset manager, session library, log viewer, update dialogs, notice/error dialogs, and busy overlays so they feel like one product family instead of unrelated default dialogs.
- Add a UI acceptance workflow with screenshots and manual smoke criteria, because this change is primarily visual and interaction-driven.
- Preserve existing review functionality, trading engine behavior, database semantics, chart aggregation, trade persistence, and user data compatibility unless a specific UI refactor requires a strictly internal implementation change.

## Capabilities

### New Capabilities

- `professional-review-workbench`: Covers the redesigned professional desktop review workbench, including layout, visual system, chart workspace, right training panel, trade review center, supporting dialogs, interaction states, and UI validation expectations.

### Modified Capabilities

None.

## Impact

- Affected UI: main window layout, top application/navigation area, replay/timeframe/tool controls, chart widget presentation and overlays, right sidebar, trade-history sidebar/dialog, settings dialog, dataset manager, session library, log viewer, update/error/notice dialogs, busy overlays, and status feedback.
- Affected code areas: `src/barbybar/ui/theme.py`, `src/barbybar/ui/main_window.py`, `src/barbybar/ui/chart_widget.py`, trade-history UI/model integration points, and UI tests.
- Affected tests: main-window UI tests, chart-widget interaction tests, trade-history tests, settings persistence tests, dialog state tests, focused screenshot/manual smoke checks, and existing regression tests for persistence and trading workflows.
- No new database schema is expected.
- No new trading engine behavior, order semantics, trade calculation changes, chart aggregation changes, or external service dependencies are expected.
