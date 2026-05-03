## Context

The `历史交易` tab now keeps compact trade review inside the fixed right panel. This layout works well for focused review, but card-only navigation makes sequential review slower than it needs to be. Users often want to inspect trades as a stream: previous trade, current trade, next trade, while keeping the chart focus mode stable.

The implementation should extend the compact history page only. It should not alter trade review data generation, saved notes, chart rendering, or the right-panel tab model.

## Goals / Non-Goals

**Goals:**

- Add compact `上一笔` / `下一笔` controls to the history page.
- Show a selected-position readout in `current / total` form.
- Navigate within the current visible trade list order.
- Preserve the active `看入场` / `看出场` focus mode while moving between trades.
- Keep chart focus and selected card synchronized after navigation.
- Provide correct disabled states at list boundaries and empty state.

**Non-Goals:**

- Add wide-table sorting or filtering controls.
- Add keyboard shortcuts for trade navigation in this change.
- Change the trade-history model sort behavior or persisted session schema.
- Change how notes are saved or which actions store entry/review notes.

## Decisions

1. Place the controls near the history selection context.

   The control row should live in `TradeReviewSidebar` between the trade card list and entry/exit focus controls. This keeps navigation close to the list while leaving the detail and note fields below.

2. Navigate by visible model rows, not raw trade numbers.

   The previous/next target should be derived from `TradeHistoryTableModel.trade_numbers()` after refresh and sorting. This makes navigation follow the same order the user sees in the card list.

3. Preserve the current focus mode.

   Previous/next should call the same selection path as card clicks with `focus_view=self.owner._selected_trade_view`. This keeps `看入场` or `看出场` stable and reuses existing chart focus behavior.

4. Centralize navigation state refresh.

   Add a small refresh helper that updates button enabled states and the `current / total` label after any refresh, selection, or note save. If the selected trade is not in the visible list, show `0 / N` or the deterministic selected item chosen by the existing controller after refresh.

## Risks / Trade-offs

- [Risk] Navigation might feel inconsistent if future filters are added. -> Mitigation: define navigation against the visible model order, so filters naturally constrain the sequence.
- [Risk] Selected trade could be missing from the visible rows after a refresh. -> Mitigation: rely on the existing controller refresh selection, then recalculate index from `trade_numbers()`.
- [Risk] The fixed right panel has limited width. -> Mitigation: use short labels (`上一笔`, `下一笔`, `0 / 0`) and keep the row compact.
