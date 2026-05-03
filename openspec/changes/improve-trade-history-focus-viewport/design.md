## Context

Historical trade selection already resolves the correct entry or exit bar and calls `_focus_selected_trade_view()` in `src/barbybar/ui/main_window.py`. The current viewport positioning sets `right_edge_index` to `target_index + 1` and clears right padding, which places the selected K-line against the chart's right price axis. That makes the jump technically correct but visually cramped, especially when reviewing an exit and wanting to see what happened immediately after it.

This change is UI-local: the trade item, bar resolution, window loading, and training cursor behavior should stay as they are. Only the chart viewport placement after a historical trade focus needs to become more review-friendly.

## Goals / Non-Goals

**Goals:**

- Keep focusing the exact selected trade entry or exit bar.
- Place the focused bar inside the visible viewport instead of against the right axis.
- Reserve at least 12 visible bars of right-side context whenever chart bounds allow it.
- Use a stable target placement around 70% of the visible viewport for single-bar focus.
- Prefer showing the whole trade span when entry and exit fit comfortably in the current viewport.
- Preserve current behavior that historical review focus does not move the training cursor.

**Non-Goals:**

- Do not change trade selection, sorting, filtering, numbering, or note persistence.
- Do not change how target bars are resolved from timestamps.
- Do not add user settings for focus ratios in this change.
- Do not redesign chart zoom, pan, or follow-latest behavior outside historical trade focus.
- Do not change database, engine, or repository behavior.

## Decisions

### Use a deterministic review-focus viewport helper

Add or extract a small helper used by `_focus_selected_trade_view()` to compute the desired `right_edge_index` from the active target bar, current `bars_in_view`, and optional entry/exit span.

Rationale: the current inline `target_index + 1` is too blunt. A helper makes the behavior testable without depending on Qt rendering.

Alternative considered: manually pan by a fixed number of bars after applying the current focus. This is harder to reason about near chart bounds and repeats the same right-edge issue under different zoom levels.

### Position single-bar focus at 70% of the viewport

For normal focus, calculate `right_edge_index` so the target bar lands around 70% from the left edge, leaving roughly 30% of the viewport on the right. Enforce a minimum right-context target of 12 bars by using the larger of 12 and `bars_in_view * 0.30`.

Rationale: 70% keeps the target visually near the review point while preserving enough future context. A fixed minimum keeps small/narrow viewports usable.

Alternative considered: always center the target bar. Centering is comfortable for entry review but less useful for exit review because it spends too much space on bars after the exit and less on the trade path.

### Prefer fitting the whole trade span when practical

When both entry and exit bars are available and the span fits within the current visible bar count with modest margins, compute a viewport that includes both bars and still preserves right-side breathing room after the active focus bar.

Rationale: for short trades, seeing the entire path is more useful than isolating only the selected point.

Alternative considered: always focus only the active entry/exit bar. This is simpler, but it can hide the other side of short trades even though there is enough room to show it.

### Preserve existing window loading and cursor semantics

If the selected trade is outside the current loaded window, continue using the existing `_ensure_window_contains_trade_time()` flow before applying the improved viewport. Set `follow_latest` to false during historical focus and do not call engine cursor movement.

Rationale: the bug is visual placement, not target resolution or data-window loading. Keeping the existing sequence limits regression risk.

Alternative considered: navigate the engine cursor to the selected trade bar. That would mix review navigation with training state and undo the existing non-mutating review behavior.

## Risks / Trade-offs

- [Risk] Near the right edge of the available chart data, there may not be 12 bars of future context. -> Mitigation: clamp through the chart's existing viewport bounds and assert the target is not worse than current behavior when bounds prevent ideal spacing.
- [Risk] Very large trade spans may not fit with margins. -> Mitigation: fall back to active-bar focus using the 70% placement rule.
- [Risk] Existing tests may assert exact `right_edge_index = target + 1`. -> Mitigation: update those tests to assert target placement ratio and preserved cursor semantics.
- [Risk] Applying right padding and `right_edge_index` together can double-count space. -> Mitigation: keep right padding small or unchanged for this focus path, and make right-edge calculation the source of visible context.

## Migration Plan

1. Add focused viewport calculation in the historical trade focus path.
2. Update regression tests for entry/exit focus and outside-window focus to assert the target bar is inside the viewport with right-side context.
3. Run focused main-window tests, then the main-window suite.
4. Rollback is local: restore the previous `target_index + 1` right-edge assignment.

## Open Questions

None for the first implementation. Use 70% target placement and at least 12 bars of desired right-side context.
