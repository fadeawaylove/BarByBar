## Why

The current trade history dialog can block the candlestick chart, but reviewing trades requires seeing both the chart and trade notes at the same time. Moving the primary review workflow into a docked sidebar keeps the chart visible while giving users a compact place to select trades, jump to entry/exit, and write review notes.

## What Changes

- Add a right-side collapsible trade review sidebar in the main window.
- Replace the default floating trade-history workflow with a narrow review list made of compact trade cards.
- Show selected-trade summary, entry/exit focus controls, entry thought, and review summary in the sidebar.
- Keep the current full table as an advanced view opened from the sidebar with an "完整表格" action.
- Preserve chart-first behavior: the sidebar must not cover the chart, and selecting a trade still focuses the chart.
- Allow the sidebar to be hidden/collapsed and reopened from the existing "历史交易" button.
- Reuse the existing trade history model/controller and per-trade note storage.

## Capabilities

### New Capabilities

- `trade-review-sidebar`: Defines the docked review sidebar, compact trade cards, chart-safe layout, collapse behavior, and full-table handoff.

### Modified Capabilities

None.

## Impact

- Affected UI code: main-window layout, historical trade entry point, trade review detail widgets, and the existing trade-history dialog/table reuse path.
- Affected tests: main-window UI tests for opening/collapsing the sidebar, selecting trade cards, note editing, and full-table access.
- No storage or database schema changes.
- No change to chart rendering semantics beyond available width when the sidebar is visible.
