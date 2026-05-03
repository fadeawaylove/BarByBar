## Context

The right-panel history sidebar shows `TradeReviewItem` records sorted by time descending. The chart focus code already knows how to position the viewport from a trade item's `entry_bar_index` or `exit_bar_index`, but the sidebar click path currently goes through `trade_number` before resolving the selected trade again. That extra lookup can drift when visible order, selected state, and trade numbering do not line up.

## Goals / Non-Goals

**Goals:**
- Make the clicked or navigated `TradeReviewItem` the object passed into chart focus.
- Keep entry/exit focus behavior driven by the existing active focus mode.
- Keep history navigation and selected-trade readouts compatible with the current UI.

**Non-Goals:**
- Redesign the history sidebar layout or tabs.
- Change how trades are numbered, persisted, or displayed.
- Change the chart widget focus API unless implementation proves a local helper is needed.

## Decisions

- Use object-level selection for history clicks. The sidebar should resolve the clicked card to its `TradeReviewItem` from the row/list item and call the existing object-aware `select_trade_review_item(...)` path so the chart focus receives the exact trade object.
- Keep `trade_number` as identity metadata, not as a chart target. It may continue to drive selected labels, detail text, and navigation index lookup, but K-line positioning must read `entry_bar_index` or `exit_bar_index` from the selected `TradeReviewItem`.
- For previous/next navigation, resolve the target visible row to its `TradeReviewItem` before focusing. Navigation can still compute the target position from the visible history order, but the final chart jump must use the target object's bar indices.
- Preserve the current focus-mode rule. Clicking a history card follows the current mode: `entry` uses `entry_bar_index`; `exit` uses `exit_bar_index`.

## Risks / Trade-offs

- [Risk] Tests that only use sequential trade numbers can miss this bug. -> Add regression cases where trade numbers, visible order, and bar indices are intentionally not correlated.
- [Risk] Selection refresh can overwrite the clicked item after focusing. -> Assert click and refresh paths preserve the selected trade object/number after the chart focus call.
- [Risk] Previous/next could still select by number but focus a stale object. -> Add a navigation test that checks the chart focus points after moving between trades.
