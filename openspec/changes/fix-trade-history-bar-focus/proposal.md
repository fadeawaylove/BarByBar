## Why

History trade review currently allows the chart focus path to pass through trade numbers or UI ordering before resolving the clicked trade. That indirection can select the wrong trade when the visible history order and internal selection state diverge, such as clicking the newest trade and landing on the second-newest trade.

## What Changes

- Make the clicked history record's `TradeReviewItem` the source of truth for K-line focusing.
- Use the selected trade object's `entry_bar_index` or `exit_bar_index` to determine the chart target, following the active entry/exit focus mode.
- Keep `trade_number` for display, selection readout, and detail labels only; it must not determine the chart target bar.
- Preserve the existing history sidebar tabs, card layout, and previous/next navigation behavior.

## Capabilities

### New Capabilities
- `trade-history-bar-focus`: Defines deterministic chart focusing from history trade records using each trade item's entry and exit bar indices.

### Modified Capabilities

## Impact

- Affects the right-panel history trade card click path and previous/next history navigation in `src/barbybar/ui/main_window.py`.
- Adds regression coverage in `tests/test_main_window.py` for non-correlated trade numbers, visible order, and entry/exit bar indices.
- No database, serialization, dependency, or public API changes.
