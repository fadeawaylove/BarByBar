# Performance Diagnostics

BarByBar records lightweight performance metrics for chart and workflow paths that commonly affect perceived responsiveness.

## Metrics Surface

Open `设置` -> `日志与诊断` -> `性能指标` to view recent measurements. The panel shows the newest metrics first and updates periodically while the dialog is open.

Common metric names:

- `chart.candles_rebuild`: candlestick picture rebuild time.
- `chart.viewport_apply`: viewport range application time.
- `chart.y_range`: visible Y range calculation time.
- `chart.overlay_refresh`: auxiliary overlay refresh time.
- `data_window.session_load_window`: chart window load during session open.
- `data_window.viewport_extension_window`: chart window load during async viewport extension.
- `data_window.forward_extension_window`: chart window load during forward stepping.
- `workflow.step_forward`: full step-forward workflow time after the user requests the next bar.
- `workflow.step_back`: full step-back workflow time after the user requests the previous bar.

## Initial Budgets

Use these as practical warning thresholds while the application is still local-first and PySide6-based:

- Interactive `chart.viewport_apply`: target below 16 ms for ordinary sessions.
- `chart.y_range`: target below 4 ms for ordinary visible windows.
- `chart.overlay_refresh`: target below 30 ms after interaction settles.
- `data_window.*`: target below 100 ms for local SQLite-backed windows.
- `workflow.step_forward`: target below 40 ms when no data-window extension is needed.

These are not hard correctness limits. Treat repeated measurements above the target as a signal to inspect the relevant layer.

## Release Smoke Checklist

Run this checklist before publishing a performance-sensitive release:

- Import a CSV dataset and confirm the session can be created.
- Open the latest session from startup.
- Step forward several bars.
- Step back several bars.
- Zoom in and out on the chart.
- Pan left until backward window extension is triggered.
- Toggle trade markers, trade links, bar count labels, and drawing visibility.
- Save the session and close the app.
- Reopen the app and confirm the same session restores.
- Open `设置` -> `日志与诊断` and confirm recent performance metrics are visible.

## Reading Results

If chart interaction feels slow, start with `chart.viewport_apply`. If that is low but the UI still feels delayed, inspect `chart.overlay_refresh` and `data_window.*`. If stepping feels slow without panning or zooming, inspect `workflow.step_forward` and any nearby `data_window.forward_extension_window` entries.
