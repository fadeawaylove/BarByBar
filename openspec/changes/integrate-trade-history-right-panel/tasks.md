## 1. Right Panel Navigation

- [x] 1.1 Add a top-level segmented tab header to the right panel with `训练` and `历史交易` buttons.
- [x] 1.2 Wire the tab buttons to the existing right-panel `QStackedWidget` with exclusive checked state.
- [x] 1.3 Make `训练` the default selected tab when the main window is created.
- [x] 1.4 Centralize programmatic page switching so stack page and tab checked state stay synchronized.

## 2. Training and History Pages

- [x] 2.1 Keep current order controls, position summary, statistics, display toggles, and session actions in the `训练` tab.
- [x] 2.2 Move compact trade review content into the `历史交易` tab at fixed right-panel width.
- [x] 2.3 Remove the right-panel `历史交易` utility button from the display controls.
- [x] 2.4 Remove temporary `复盘` and `刷新` buttons from the history page header.

## 3. Historical Trade Behavior

- [x] 3.1 Route `open_trade_history_dialog()` to select the `历史交易` tab and refresh trade review items.
- [x] 3.2 Route `open_full_trade_history_dialog()` to the same `历史交易` tab without creating a floating dialog.
- [x] 3.3 Preserve selected-trade detail, note editing, note saving, and empty-state behavior in the compact history tab.
- [x] 3.4 Ensure selected trade focus uses the selected `TradeReviewItem` entry and exit bar indices.

## 4. Tests and Verification

- [x] 4.1 Update main-window tests for two-tab right-panel navigation and default `训练` selection.
- [x] 4.2 Update history entry tests to assert no `_trade_history_dialog` is created.
- [x] 4.3 Update legacy button tests to assert the tab header instead of the removed utility button.
- [x] 4.4 Run `uv run pytest -q tests/test_main_window.py`.
- [x] 4.5 Run `uv run pytest -q tests/test_trade_history.py`.
