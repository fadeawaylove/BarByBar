## Why

Clicking a historical trade currently jumps to the correct K-line but places it against the right price axis, leaving little context after the target bar. Trade review needs a more comfortable focus viewport so users can inspect the setup/result without immediately panning away.

## What Changes

- Adjust historical trade chart focus so the target entry or exit bar is positioned inside the visible chart area instead of flush against the right edge.
- Preserve the existing rule that entry focus targets the selected trade entry bar and exit focus targets the selected trade exit bar.
- Keep right-side breathing room after focused bars, with a minimum amount of post-trade context.
- Prefer showing the whole trade span when entry and exit are close enough to fit comfortably in the current viewport.
- Keep focus navigation independent from the training cursor and from trade number or UI row order.

## Capabilities

### New Capabilities

- `trade-history-focus-viewport`: Defines how historical trade focus positions the chart viewport around selected trade entry/exit bars.

### Modified Capabilities

None.

## Impact

- Affected UI code: `src/barbybar/ui/main_window.py`, especially `_focus_selected_trade_view()`.
- Possible affected chart state helpers: `src/barbybar/ui/chart_widget.py` only if a small helper is needed for viewport positioning.
- Affected tests: trade history focus tests in `tests/test_main_window.py`, with possible focused chart viewport assertions in `tests/test_chart_widget.py`.
- No database, engine, or trade-review data model changes are expected.
