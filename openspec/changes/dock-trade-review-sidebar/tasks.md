## 1. Sidebar Structure

- [x] 1.1 Audit the main-window splitter/layout to choose the sidebar insertion point beside the chart.
- [x] 1.2 Add a collapsible right-side trade review sidebar container with a stable object name for tests.
- [x] 1.3 Change the existing "历史交易" button to toggle the sidebar instead of opening the floating dialog by default.
- [x] 1.4 Preserve selected trade and active focus mode when the sidebar is collapsed and reopened.

## 2. Compact Review Cards

- [x] 2.1 Add a compact trade card/list widget backed by the existing trade history model/controller.
- [x] 2.2 Show trade number, direction, PnL, exit reason, and compact time on each card.
- [x] 2.3 Make single-click card selection focus the chart using the active entry/exit focus mode.
- [x] 2.4 Keep card selection synchronized when engine data refreshes.

## 3. Sidebar Detail and Notes

- [x] 3.1 Reuse or extract the selected-trade summary, entry/exit focus controls, entry thought, review summary, and save action.
- [x] 3.2 Ensure note saving from the sidebar writes to existing action notes and preserves selection.
- [x] 3.3 Add an empty state for no session or no historical trades.

## 4. Full Table Handoff

- [x] 4.1 Add a "完整表格" action in the sidebar.
- [x] 4.2 Keep the existing full table dialog available from that action.
- [x] 4.3 Ensure opening the full table preserves selected trade, sort/filter state where practical, and note edits.

## 5. Tests and Cleanup

- [x] 5.1 Update existing tests that expect "历史交易" to open a floating dialog by default.
- [x] 5.2 Add tests for sidebar toggle/collapse behavior and chart-safe layout presence.
- [x] 5.3 Add tests for card selection focusing the chart.
- [x] 5.4 Add tests for note editing and saving from the sidebar.
- [x] 5.5 Add tests for opening the full table from the sidebar.
- [x] 5.6 Document the sidebar workflow in the trade history review developer note.
