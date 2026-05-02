# Trade History Review Workflow

The trade history review surface is intentionally split into three parts:

- `TradeHistoryTableModel` owns normalized rows, sorting, filtering, and table-facing values.
- `TradeReviewController` owns selected trade state, active focus mode, and deterministic refresh behavior.
- `TradeHistoryDialog` owns the Qt layout and binds user actions to the model/controller.

The primary review surface is the docked `TradeReviewSidebar` in the main window. It keeps the K-line chart visible while showing compact trade cards, selected-trade detail, entry/exit focus controls, and per-trade notes. The floating `TradeHistoryDialog` remains available from the sidebar's `完整表格` action for wide filtering and sorting workflows.

Both the sidebar and full dialog should stay presentation-focused. New review logic should usually be added to `src/barbybar/ui/trade_history.py` first, then wired into the Qt surfaces. This keeps sorting, filtering, and selection behavior testable without constructing the full main window.

Current focus modes are:

- `entry`: jump to the selected trade's entry bar.
- `exit`: jump to the selected trade's exit bar.

Single-click card selection in the sidebar updates the detail panel and focuses the chart using the active focus mode. The full dialog uses the same selection/controller state, so switching between compact sidebar review and the full table preserves the selected trade where possible.

Per-trade thoughts are stored on existing action notes instead of a separate trade table:

- The entry thought uses the selected trade's entry action `SessionAction.note`.
- The review summary uses the selected trade's exit/reduce action `SessionAction.note`.
- `TradeReviewItem.entry_action_index` and `TradeReviewItem.exit_action_index` are transient indexes rebuilt from the session action list.
