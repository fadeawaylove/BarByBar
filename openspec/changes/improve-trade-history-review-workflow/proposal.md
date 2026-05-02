## Why

The current trade history view works as a basic jump list, but it is not strong enough for structured review: users cannot quickly filter, compare, inspect, or understand why historical trades performed well or poorly. Improving this workflow now turns historical trades from a passive record into an active training surface that helps users find patterns, review execution quality, and navigate the chart with less friction.

## What Changes

- Replace the single-line trade history list with a review-oriented table that supports richer columns, stable sorting, filtering, and selection persistence.
- Add a detail panel for the selected trade, showing entry/exit context, PnL, holding duration, exit reason, execution flags, and trade action summary.
- Add explicit chart focus controls for entry and exit so users can inspect the correct chart context without relying on a single toggle.
- Add practical filters for direction, outcome, exit reason, plan/discipline flags, holding duration, and PnL range.
- Keep trade selection synchronized with the chart while allowing lightweight interactions such as row selection, keyboard navigation, and hover/preview without unnecessary viewport jumps.
- Introduce internal model/controller boundaries so trade review state, sorting/filtering, and chart navigation are not embedded directly in dialog widgets.
- Preserve existing user-visible trade history behavior where possible, including access from the main window and chart focus on selected trades.

## Capabilities

### New Capabilities

- `trade-history-review`: Defines the improved historical trade review workflow, including table review, filters, selected-trade detail, chart focus controls, and interaction expectations.
- `trade-review-architecture`: Defines internal model/controller responsibilities for trade review data, selection state, sorting/filtering, and chart synchronization.

### Modified Capabilities

None.

## Impact

- Affected UI code: `src/barbybar/ui/main_window.py`, especially `TradeHistoryDialog` and trade-selection/focus helpers.
- Affected domain/view-model code: `src/barbybar/domain/models.py` and `src/barbybar/domain/engine.py` if additional review fields or normalized trade review data are needed.
- Expected new or extracted UI/model modules under `src/barbybar/ui/` for trade history model/controller code.
- Affected tests: trade history dialog behavior, selection persistence, sorting/filtering, keyboard navigation, and chart focus semantics in `tests/test_main_window.py` or new focused tests.
- No database schema change is expected in the first implementation phase.
