# Reframe Review Workflow UX Screenshot Review

Screenshot output directory: `C:\tmp\reframe-review-workflow-shots`

## Coverage

- `01-empty-startup.png`: empty startup next actions
- `02-replay-mode.png`: replay mode baseline
- `03-plan-mode.png`: order preview / plan mode
- `04-annotate-mode.png`: drawing / annotate mode
- `05-review-mode-sidebar.png`: review mode with compact trade cards
- `06-active-long-position.png`: active long position
- `07-active-short-position.png`: active short position
- `08-completed-session.png`: completed session state
- `09-full-trade-review-workspace.png`: full trade review list/detail workspace
- `10-settings-entry.png`: settings entry
- `11-dataset-manager-entry.png`: dataset manager entry
- `12-session-library-entry.png`: session library entry
- `13-narrow-supported-desktop.png`: narrow supported desktop layout

## Acceptance Review

- Chart dominance: active-session captures keep the chart as the largest and visually strongest surface; the empty-startup state intentionally replaces the chart with next actions.
- Mode clarity: replay, plan, annotate, and review each show explicit mode language in toolbar and/or chart hint and right-side focus card.
- State center stability: position snapshot and primary trading actions stay in place while mode emphasis shifts below them.
- Trade review workflow: compact sidebar cards show trade number, direction, outcome, PnL, timing, holding bars, exit reason, and note state; full dialog supports list/detail, filters, notes, and focus controls.
- Text fit and overlap: narrow desktop capture keeps primary actions reachable, text contained, and no obvious overlaps in header, toolbar, sidebar, or dialog surfaces.
- Action discoverability: empty startup foregrounds import, case library, dataset manager, and recent work; settings/dataset/session entries remain directly reachable and captured.

## Notes

- Screenshot smoke is structural rather than pixel-perfect; final packaged-app release review can still use these captures as a baseline.
- No blocking visual issues found during this pass.
