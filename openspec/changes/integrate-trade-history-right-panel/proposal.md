## Why

The current historical trade review surface feels like a temporary side route: the user clicks into history, then relies on internal buttons to get back to the replay controls. BarByBar already has a fixed right panel that users treat as the control center for replay work, so historical trade review should become a first-class mode in that panel instead of an extra window or hidden page switch.

## What Changes

- Add an always-visible right-panel tab switch with `训练` and `历史交易`.
- Keep `训练` as the default tab with the existing order, replay display, statistics, and session controls.
- Move historical trade cards, selected-trade detail, entry/exit focus controls, entry thought, review summary, and save action into the `历史交易` tab.
- Remove the right-panel `历史交易` utility button and the temporary history-page `复盘` / `刷新` header buttons.
- Keep the candlestick chart width stable when the user reviews historical trades.
- Ensure clicked trade records navigate by using that record's own `entry_bar_index` / `exit_bar_index`, not a row-derived secondary lookup.
- Route every historical trade entry point to the `历史交易` tab instead of creating a floating trade-history window.
- Update tests and developer docs to reflect the tabbed right-panel workflow.

## Capabilities

### New Capabilities

- `right-panel-trade-review`: Covers the integrated `训练` / `历史交易` right-panel tabs, compact historical trade review page, chart-safe layout, and direct trade-record navigation.

### Modified Capabilities

None.

## Impact

- Affected UI code: main-window splitter construction, right-panel tab header, trade history entry points, and compact trade review widget/page.
- Affected tests: main-window layout tests, historical trade selection/focus tests, note-saving tests, and trade-history model tests.
- Affected docs: trade history review developer note.
- No database schema changes and no change to saved session/action note data.
