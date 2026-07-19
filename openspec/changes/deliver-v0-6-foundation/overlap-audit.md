# v0.6 Existing Change Overlap Audit

Audit date: 2026-07-19

## Summary

`openspec list --json` reports three older changes that are still in progress and overlap the v0.6 foundation milestone. Their remaining implementation is not to be recreated under a second code path. The older focused change remains the detailed implementation record; the v0.6 task is a milestone gate that consumes its result.

Twelve older changes report all tasks complete but remain unarchived. They should be archived as housekeeping only after confirming their specs still match the current implementation. Archiving them is not a prerequisite for starting v0.6 behavior work.

## Active Overlap Mapping

### `optimize-chart-performance-architecture` — 28/38 complete

Remaining source tasks:

- Migrate async save and batch import where the shared coordinator fits.
- Extract chart-window, replay/session, and settings responsibilities from `MainWindow`.
- Add chunked candlestick rebuilding, incremental indicators, viewport-aware hit testing, and large-session verification.

v0.6 mapping:

- Source task 4.4 maps to v0.6 tasks 2.3, 3.5, and 4.6 where coordination is actually required.
- Source tasks 5.1–5.5 map to v0.6 tasks 2.1–2.4 and must be extracted incrementally, not as an independent rewrite.
- Source tasks 6.1–6.4 map directly to v0.6 tasks 2.6–2.9.
- Implementation and focused technical evidence stay in `optimize-chart-performance-architecture`; v0.6 records the release-level completion gate.

### `redesign-professional-review-workbench` — 173/176 complete

Remaining source tasks:

- Capture normal, missing, and failed log viewer states where feasible.
- Capture update, error, and notice dialog states.
- Run a packaged-app manual smoke pass for real fonts, text fit, and dialog sizing.

v0.6 mapping:

- Source tasks 15.14 and 15.15 are consumed by v0.6 task 5.6.
- Source task 15.18 is consumed by v0.6 task 5.7 and release task 6.4.
- No second workbench redesign will be started in v0.6; only evidence gaps and small foundation corrections are in scope.

### `improve-trade-history-review-workflow` — 31/32 complete

Remaining source task:

- Run focused main-window and chart-widget test subsets covering trade history and marker interactions.

v0.6 mapping:

- Complete this focused verification during v0.6 task 6.1, then close the older change.
- No trade-history model or UI reimplementation is required for v0.6.

## Completed but Unarchived Changes

The following changes report all tasks complete and should be validated and archived in a separate housekeeping slice:

- `improve-drawing-cursor-feedback`
- `redefine-arrow-four-point-geometry`
- `refine-arrow-drawing-polygon`
- `polish-stable-review-workbench`
- `optimize-logging-retention`
- `improve-trade-history-focus-viewport`
- `isolate-trades-by-chart-timeframe`
- `fix-trade-history-bar-focus`
- `add-trade-history-sequential-navigation`
- `integrate-trade-history-right-panel`
- `improve-release-publishing-workflow`
- `dock-trade-review-sidebar`

## Tracking Rule

When an older focused task and a v0.6 task describe the same implementation:

1. Implement the code once under the older focused change.
2. Run the focused tests and mark the older source task complete.
3. Link or summarize the evidence in the v0.6 milestone checkpoint.
4. Mark the v0.6 gate complete only when the source change and release-level verification both pass.

