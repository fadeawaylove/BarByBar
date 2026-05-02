## Context

The current trade history experience is implemented as `TradeHistoryDialog` inside `src/barbybar/ui/main_window.py`. It uses a `QListWidget` with one-line labels, a sort combo, tooltips for details, and a toggle button that switches selected trades between entry and exit focus. The underlying trade review data comes from `ReviewEngine.trade_review_items()` and is synchronized through `MainWindow` helpers such as `_sorted_trade_review_items()`, `_selected_trade_review_item()`, and chart focus methods.

This is functional, but it mixes presentation, sorting, selection, and chart navigation in the same UI path. It also makes the review workflow hard to extend with filters, detail panes, keyboard navigation, and richer analytics.

## Goals / Non-Goals

**Goals:**

- Turn trade history into a review workspace: table, filters, selected-trade detail, and chart focus controls.
- Preserve the existing ability to open historical trades and jump to chart context.
- Make sorting/filtering stable and testable through a model instead of rebuilding ad hoc list labels.
- Separate review state and chart navigation from dialog widgets so future trade-review features can be added without growing `MainWindow`.
- Keep the first implementation local to UI/domain view-model code without changing database schema.

**Non-Goals:**

- Do not change the training engine's execution semantics.
- Do not change persisted trade/action storage in the first phase.
- Do not implement advanced analytics such as MAE, MFE, R-multiple, notes, or tagging unless the current data already supports them cheaply.
- Do not replace the main chart interaction model.
- Do not make chart item creation or Qt widgets run off the UI thread.

## Decisions

### Use a table model instead of a list widget

Create a `TradeHistoryTableModel` backed by normalized trade review rows. The model will expose columns for trade number, direction, entry time, exit time, holding bars, quantity, PnL, exit reason, and execution flags.

Rationale: `QTableView/QAbstractTableModel` gives native sorting, selection, keyboard navigation, and scalable rendering. It also makes tests cleaner because the view model can be validated without rendering every row as a string.

Alternative considered: keep `QListWidget` and enrich row labels. This is faster to patch, but it keeps filtering/sorting and presentation tightly coupled and will not scale for a proper review workflow.

### Add a controller for selected trade review state

Introduce a small `TradeReviewController` or equivalent owner-level state object that tracks selected trade number, selected focus mode, filters, and chart focus requests. The dialog should emit user intent; the controller should decide how to update selection and focus the chart.

Rationale: chart focus rules are application behavior, not widget rendering. Keeping them outside the dialog prevents `TradeHistoryDialog` from becoming the place where engine state, chart state, and UI state all meet.

Alternative considered: continue using `MainWindow` as the controller. This avoids one new module but worsens the existing large-window coupling.

### Keep detail rendering separate from table rows

The table should be optimized for scanning. A selected-trade detail panel should show the richer review story: entry/exit values, PnL, holding bars, exit reason, discipline flags, and a short action summary.

Rationale: the current tooltip hides important context and is hard to compare. A detail panel allows compact table rows while making the selected trade easy to understand.

Alternative considered: put every field into table columns. This makes the table dense and less useful on smaller screens.

### Provide explicit focus modes

Replace the single entry/exit toggle as the main navigation control with explicit focus actions: entry and exit. The selected focus mode should remain visible and should be preserved when moving between trades.

Rationale: review intent is different depending on whether the user wants setup or result context. Keeping the controls to entry and exit avoids adding a third mode that looks helpful but can interrupt the review flow.

Alternative considered: keep a two-state toggle. This preserves current behavior but misses the most useful review mode and makes current state less obvious.

### Add filters in the first model pass

Support practical filters in the first version: direction, outcome, exit reason, plan/discipline flags, holding-bar range, and PnL range. Filters should be represented as a value object that can be applied to the table model and tested independently.

Rationale: the review workflow becomes valuable when users can ask focused questions, such as which losing trades violated plan or which exit reasons dominate drawdowns.

Alternative considered: ship the table first and defer filters. This is lower risk, but it would still leave the workflow mostly as a better-looking list.

## Risks / Trade-offs

- [Risk] Refactoring trade history while chart-performance work is also in progress could create merge friction in `main_window.py`. -> Mitigation: isolate new model/controller code in separate modules and keep `MainWindow` changes narrow.
- [Risk] Full-trade focus may need bars outside the current window. -> Mitigation: use existing chart/session loading behavior where possible and degrade to focusing the available range until window extension completes.
- [Risk] Too many filters can make the dialog visually noisy. -> Mitigation: start with compact combo boxes and numeric range fields, then tune layout after usage.
- [Risk] Existing tests may assume list-widget internals. -> Mitigation: add model-level tests and update UI tests to assert user-visible behavior rather than widget implementation details.
- [Risk] Derived trade data may not include every desired metric. -> Mitigation: first expose only fields already present in `TradeReviewItem`; add optional enrichment later behind separate tasks.

## Migration Plan

1. Add new model/controller code while keeping the existing dialog entry point.
2. Replace the dialog body with table, filters, detail panel, and focus controls.
3. Wire the controller to existing `MainWindow` selection and chart focus helpers.
4. Update tests to cover both existing preserved behavior and new review workflow behavior.
5. Remove old list-widget-specific code after the new dialog passes tests.

Rollback is straightforward because the change is UI-local: restore the previous `TradeHistoryDialog` implementation and bypass the new model/controller wiring.

## Open Questions

- Should the improved review surface remain a dialog, or later become a dockable side panel? The first implementation can keep it as a dialog while designing the model/controller so a dock can reuse it.
- Should trade review notes/tags be persisted in this change? This proposal intentionally defers persistence until the basic review workflow is stable.
