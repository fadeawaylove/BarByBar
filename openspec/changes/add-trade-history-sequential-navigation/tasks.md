## 1. Navigation Controls

- [x] 1.1 Add `上一笔` and `下一笔` buttons to the compact historical trade review page.
- [x] 1.2 Add a selected-position label that displays `current / total`.
- [x] 1.3 Place the controls between the trade card list and the entry/exit focus buttons.

## 2. Navigation Behavior

- [x] 2.1 Implement helper logic to read the current visible trade order from `TradeHistoryTableModel.trade_numbers()`.
- [x] 2.2 Implement previous-trade navigation that selects the prior visible trade and refreshes the page.
- [x] 2.3 Implement next-trade navigation that selects the next visible trade and refreshes the page.
- [x] 2.4 Preserve the active entry/exit focus mode while navigating.
- [x] 2.5 Keep the chart focus and selected card synchronized after navigation.

## 3. Boundary and Empty States

- [x] 3.1 Disable `上一笔` when the selected trade is the first visible trade.
- [x] 3.2 Disable `下一笔` when the selected trade is the last visible trade.
- [x] 3.3 Disable both controls and show `0 / 0` when there are no visible trades.
- [x] 3.4 Refresh navigation state after item refresh, card selection, focus changes, and note saves.

## 4. Tests and Verification

- [x] 4.1 Add main-window tests for next/previous trade navigation and position readout.
- [x] 4.2 Add tests for first/last boundary disabled states.
- [x] 4.3 Add tests for empty historical trade state.
- [x] 4.4 Add tests that navigation preserves active entry/exit focus mode.
- [x] 4.5 Run `uv run pytest -q tests/test_main_window.py -k trade_history`.
- [x] 4.6 Run `uv run pytest -q tests/test_trade_history.py`.
