## Why

After historical trades move into the fixed right-panel `历史交易` tab, reviewing trades only by clicking cards is too manual. A compact previous/next control lets users walk through completed trades one by one, which matches the natural replay review workflow.

## What Changes

- Add `上一笔` and `下一笔` navigation controls to the right-panel historical trade review page.
- Show the selected trade position as `当前 / 总数`, such as `3 / 12`.
- Navigate through the currently visible trade card list in its active order.
- Keep the current `看入场` / `看出场` focus mode when moving between trades.
- Automatically select the target trade card and focus the chart on that trade's entry or exit view.
- Disable `上一笔` at the first visible trade and `下一笔` at the last visible trade.
- Disable both controls and show `0 / 0` when there are no visible trades.

## Capabilities

### New Capabilities

- `trade-history-sequential-navigation`: Covers previous/next navigation, position readout, disabled boundary states, and chart focus behavior for the compact historical trade review page.

### Modified Capabilities

None.

## Impact

- Affected UI code: compact trade review sidebar/page in the main window.
- Affected state logic: selected trade number, visible trade card order, and entry/exit focus mode.
- Affected tests: historical trade sidebar selection, focus, empty state, and boundary navigation tests.
- No database schema, repository API, engine model, or saved action note changes.
