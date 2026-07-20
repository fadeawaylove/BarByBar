# Replay Fast-Path Transition Coverage

The v0.6 fast path skips stable workbench regions only during deferred step-forward refreshes. Full load, restore, step-back, jump, and timeframe refreshes retain the complete path.

## New focused coverage

- `test_unchanged_step_forward_skips_stable_workbench_regions`: unchanged position, orders, tick size, and controls are skipped while cursor, header, and current price still update.
- `test_unchanged_deferred_step_skips_trade_and_stats_regions`: unchanged trade and statistics regions are skipped while cursor-dependent overlays still refresh.
- `test_complete_engine_refresh_reapplies_stable_workbench_regions`: the full refresh path reapplies every stable region even when signatures match.
- `test_fast_refresh_invalidates_cached_regions_for_position_transitions`: flat, long, short, flat, and completed transitions invalidate the necessary cached regions.
- `test_triggered_order_invalidates_trade_and_workbench_fast_paths`: an entry order trigger refreshes position, order, control, trade, review, and focus regions.

## Existing transition coverage retained

- Timeframe changes: `test_main_window_keeps_trade_state_isolated_when_switching_timeframes`, `test_main_window_reopens_with_last_selected_chart_timeframe`, and unavailable-timeframe recovery tests.
- Save states: `test_case_header_summarizes_open_session_and_save_state`, async step-forward save, stale save, failure, and pending-save tests.
- Trade review changes: training-stat population, trade-review item chart propagation, history selection/focus, notes, filters, and navigation tests.
- Order and position semantics: engine tests cover entry, exit, partial exit, reverse, protective triggers, gap fills, and terminal flatten behavior.

