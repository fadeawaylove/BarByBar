## 1. Trade Review Model

- [x] 1.1 Audit current `TradeReviewItem` fields and existing trade history tests to confirm available display/filter data.
- [x] 1.2 Add a normalized trade history row/view-model structure for table and detail rendering.
- [x] 1.3 Implement `TradeHistoryTableModel` with stable row identity, column values, formatting helpers, and selection lookup by trade number.
- [x] 1.4 Add model sorting for time, PnL, direction, holding bars, and exit reason.
- [x] 1.5 Add filter state and filtering logic for direction, outcome, exit reason, discipline flags, holding-bar range, and PnL range.
- [x] 1.6 Add unit tests for model row normalization, sorting, filtering, and selection preservation.

## 2. Trade Review Controller

- [x] 2.1 Introduce a controller or equivalent state object for selected trade number, active focus mode, active filters, and chart focus requests.
- [x] 2.2 Move selected-trade lookup and focus-mode transitions out of `TradeHistoryDialog` where feasible.
- [x] 2.3 Implement deterministic behavior for refreshes where the selected trade still exists, is filtered out, or is no longer available.
- [x] 2.4 Add controller tests for focus-mode transitions, selection refresh, and unavailable-trade handling.

## 3. Trade History UI

- [x] 3.1 Replace the `QListWidget` trade history body with a `QTableView` backed by the trade history model.
- [x] 3.2 Add compact filter controls for direction, outcome, exit reason, discipline flags, holding bars, and PnL range.
- [x] 3.3 Add a selected-trade detail panel that shows entry/exit context, PnL, holding duration, exit reason, execution flags, and action summary.
- [x] 3.4 Replace the primary entry/exit toggle with explicit entry and exit focus controls while preserving an obvious active state.
- [x] 3.5 Add keyboard support for row navigation and row activation without breaking existing mouse behavior.
- [x] 3.6 Preserve selected trade, active focus mode, sort order, filters, and scroll position across trade history refreshes where possible.

## 4. Chart Integration

- [x] 4.1 Wire entry focus to the existing chart navigation path for the selected trade's entry context.
- [x] 4.2 Wire exit focus to the existing chart navigation path for the selected trade's exit context.
- [x] 4.3 Remove full-trade focus so the review workflow stays focused on entry and exit context.
- [x] 4.4 Ensure single-click selection updates details and focuses the chart using the active focus mode.
- [x] 4.5 Ensure double-click or keyboard activation focuses the chart using the active focus mode.
- [x] 4.6 Keep chart trade highlighting and current selected trade synchronized after engine refreshes.

## 5. Tests and Regression Coverage

- [x] 5.1 Update existing trade history UI tests that depend on list-widget internals to assert user-visible behavior instead.
- [x] 5.2 Add tests for table columns, selected-trade detail content, and focus button enablement.
- [x] 5.3 Add tests for filters, filter clearing, sorting, and preserving selection after refresh.
- [x] 5.4 Add tests for entry and exit chart focus behavior.
- [x] 5.5 Add tests that single-click and activation interactions both trigger chart focus.
- [ ] 5.6 Run focused main-window and chart-widget test subsets that cover trade history and trade marker interactions.

## 6. Cleanup and Documentation

- [x] 6.1 Remove obsolete `QListWidget` trade history label-building and tooltip-only detail paths after replacement is complete.
- [x] 6.2 Keep `MainWindow` integration narrow by moving reusable review model/controller code into dedicated modules.
- [x] 6.3 Document the new trade history review workflow in a short developer note or inline test names if no user docs exist.
- [x] 6.4 Verify OpenSpec status and mark completed tasks during implementation.
