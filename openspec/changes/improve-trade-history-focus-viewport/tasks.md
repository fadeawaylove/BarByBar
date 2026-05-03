## 1. Viewport Focus Calculation

- [x] 1.1 Add constants for historical trade focus placement: target ratio `0.70` and minimum desired right context `12` bars.
- [x] 1.2 Extract a helper that computes review-focus `right_edge_index` from target bar, visible bar count, total bounds, and optional entry/exit span.
- [x] 1.3 Clamp computed right-edge values through existing chart viewport bounds so boundary trades stay visible.

## 2. Trade History Focus Flow

- [x] 2.1 Update `_focus_selected_trade_view()` to use the review-focus viewport helper instead of `target_index + 1`.
- [x] 2.2 Keep `viewport.follow_latest = False` and preserve the engine training cursor when focusing historical trades.
- [x] 2.3 Preserve existing window-extension behavior for trades outside the currently loaded chart window.
- [x] 2.4 Avoid clearing all right-side breathing room in the historical focus path.

## 3. Tests

- [x] 3.1 Add a regression test proving exit focus leaves right-side context and does not place the exit bar at the right edge.
- [x] 3.2 Add a regression test proving entry focus leaves right-side context.
- [x] 3.3 Add a test proving short trade spans keep entry and exit visible when they fit.
- [x] 3.4 Add a boundary test proving near-end trades remain visible when ideal right context is not available.
- [x] 3.5 Update existing historical focus tests that asserted exact right-edge placement.

## 4. Verification

- [x] 4.1 Run `uv run pytest -q tests/test_main_window.py -k trade_history`.
- [x] 4.2 Run `uv run pytest -q tests/test_main_window.py`.
