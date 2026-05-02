## Why

BarByBar is increasingly limited by UI-thread work in chart interaction paths: panning, zooming, window extension, overlay rebuilds, and session updates can compete with the candlestick view the user is actively manipulating. This change creates a staged architecture and performance plan so the main chart remains responsive as data size, trade history, drawings, and diagnostics grow.

## What Changes

- Introduce explicit chart interaction performance requirements that prioritize immediate candlestick rendering over auxiliary overlays during high-frequency interactions.
- Add a coordinated background task model for session loading, viewport window extension, async saving, import work, and future compute-heavy chart preparation.
- Add performance diagnostics for chart rendering, overlay refreshes, data-window loading, and high-frequency UI workflows.
- Refactor responsibilities out of the main window over time into chart, session, settings, and async-task coordination boundaries.
- Optimize chart data structures for visible-range calculations, candlestick rendering, indicator calculation, hover hit testing, and overlay rebuilds.
- Improve interface efficiency by making common review workflows responsive, low-friction, and scoped to the UI layer being changed.

## Capabilities

### New Capabilities

- `chart-interaction-performance`: Defines responsiveness requirements for panning, zooming, chart window updates, overlay layering, visible-range calculations, and high-frequency chart interaction.
- `background-task-coordination`: Defines how asynchronous UI-related tasks are started, superseded, completed, failed, and applied without stale results disrupting current state.
- `performance-diagnostics`: Defines user/developer-visible diagnostics for measuring chart, data-window, overlay, and workflow latency.

### Modified Capabilities

- None.

## Impact

- Affected code includes `src/barbybar/ui/chart_widget.py`, `src/barbybar/ui/main_window.py`, session/window loading flows, async save/import workers, chart overlay rendering, and diagnostics UI.
- No database schema change is required for the initial phases.
- No breaking user-facing workflow changes are intended; the behavior change is that auxiliary chart overlays may update shortly after the candlestick view during high-frequency interaction.
- Tests will expand around viewport interaction, async task stale-result handling, performance instrumentation, and controller-level behavior as responsibilities are extracted.
