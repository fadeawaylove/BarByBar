# Workbench Polish Audit

This audit supports `openspec/changes/polish-stable-review-workbench`. The scope is a stability, usability, and visual polish pass over existing workflows; it intentionally avoids new trading features, database behavior changes, or order semantics changes.

## Current Surface Audit

### Top Toolbar

The current top bar exposes workspace actions, timeframe choices, chart tools, diagnostics, and update actions in one horizontal band. Timeframe and drawing controls are useful during replay, while dataset, session library, settings, logs, and update checks are lower-frequency actions. The current grouping works functionally, but low-frequency actions compete visually with daily replay controls.

Target direction:

- Keep dataset, session library, settings, logs, and update actions reachable as workspace/diagnostic actions.
- Make timeframe selection visually compact but clearly selected.
- Keep chart drawing tools grouped together and avoid mixing them with session-management actions.
- Keep replay controls visually stable as one control strip, even if they remain below the chart.
- Ensure Chinese labels such as `常用模板`, `检查更新`, `清除画线`, and `隐藏交易连线` fit without truncation.

### Chart Area

The chart is already the primary workspace, but its frame and surrounding controls can feel like another card inside the app shell. Trade markers, trade links, order previews, drawing anchors, bar numbers, and hover/readout overlays all compete on a dense K-line surface.

Target direction:

- Reduce chart frame noise and keep the K-line canvas visually dominant.
- Keep axis labels, bar numbers, and readouts readable but subdued.
- Ensure trade markers and links stay inspectable without overpowering candles.
- Keep hover overlays, note editing, drawing handles, and order-preview feedback from covering important candles or controls.
- Preserve existing chart interaction behavior.

### Right Sidebar Training Tab

The right sidebar contains direct trade actions, line/order drawing actions, position status, training stats, display toggles, and session controls. The tab header is stable, but the content hierarchy can be tightened: direct trade actions are the most important controls, while display/session toggles are supporting utilities.

Target direction:

- Make direct trade actions primary and line/order drawing actions secondary.
- Stabilize numeric input widths so quantity and price changes do not shift controls.
- Make empty, long, short, flat, and completed-session states easy to scan.
- Compress display and session controls without hiding them.
- Ensure long/short/close/reverse buttons have clear enabled, disabled, pressed, and role-specific states.

### Trade History Sidebar and Dialog

The docked trade-history sidebar keeps the chart visible during review, while the full dialog keeps wide filtering and sorting available. Selection, entry/exit focus, notes, filters, and empty-selection states need to read as separate states rather than one blended card state.

Target direction:

- Make trade number, direction, PnL, and entry/exit span the primary card information.
- Separate selected trade from active entry/exit focus in card, detail, and chart feedback.
- Make previous/next navigation and boundary-disabled states obvious.
- Keep note editing feedback clear while preserving existing note storage semantics.
- Add clear empty states for no trades, filters with no results, and no selected trade.
- Keep the full dialog consistent with the sidebar and preserve sorting/filtering workflows.

### Settings, Data, Session, Logs, Updates, and Errors

Settings, session library, dataset manager, log viewer, update dialogs, busy overlays, and error dialogs are mostly functional surfaces. They need consistent spacing, action ordering, recoverability language, and failure-detail treatment so problems feel diagnosable.

Target direction:

- Group settings pages by chart display, replay behavior, and diagnostics.
- Keep color controls, alpha sliders, quantity defaults, trade visibility, and persistence feedback aligned.
- Improve no-data, importing, duplicate, failed import, missing log, failed log read, update failure, and session load failure states.
- Keep busy overlays scoped to work that is actually blocking.
- Make primary and secondary actions clear in dialogs.

## Polish Checklist

- [x] Layout hierarchy: primary replay and review workflows are visually stronger than maintenance actions.
- [x] Text overflow: all Chinese labels fit in fixed-width controls, cards, tabs, dialogs, and status rows.
- [x] Button states: enabled, disabled, hover, pressed, checked, selected, long, short, danger, and quiet states are consistent.
- [x] Empty states: no data, no trades, filtered-out trades, no selection, missing logs, and failed reads are explicit.
- [x] Loading states: import, session open, update check, and async save surfaces do not leave stale UI behind.
- [x] Error states: failures identify the failed operation and provide a recoverable next action or detail path.
- [x] No overlap: chart overlays, buttons, labels, card content, and dialogs do not collide at the fixed sidebar width or common desktop sizes.

## Test Coverage Map

| Area | Existing Coverage | Missing or Weak Coverage |
| --- | --- | --- |
| Main workbench | `tests/test_main_window.py` covers toolbar construction, right sidebar controls, settings, trade-history integration, timeframe/session behavior, and async save paths. | Visual hierarchy assertions, disabled/checked style consistency, text-fit regressions, busy/error recovery copy. |
| Chart widget | `tests/test_chart_widget.py` covers drawing tools, trade markers, trade links, hover/selection behavior, and session/chart interactions. | Visual dominance of markers/links, overlay placement, and manual screenshot/no-overlap checks. |
| Trade history | `tests/test_trade_history.py` covers table model, controller filtering/sorting, selection, and focus behavior. | Sidebar card visual states, empty/filter states, note-editing feedback, navigation boundary controls. |
| Repository/session | `tests/test_repository.py` and `tests/test_main_window.py` cover session persistence, actions, timeframe behavior, and trade persistence paths. | UI polish must avoid changing persistence semantics; tests should be rerun after layout/state changes. |
| Logging/settings | `tests/test_logging_config.py` and main-window settings tests cover log retention and settings persistence. | Log viewer missing-file/failed-read visual state assertions. |
| Release/update/error flows | Main-window tests cover update checks and dialogs in focused paths. | Primary/secondary action ordering, failure detail readability, and manual recovery smoke coverage. |

## Manual Smoke Flow

Use this flow before closing the change:

- Start with no active dataset and verify the startup/empty state.
- Import one CSV and a batch with at least one duplicate or failure.
- Create or open a session, step forward, step back, and rapidly step forward.
- Place direct trades, line/order previews, and drawing tools without changing order semantics.
- Review trades in the sidebar, switch entry/exit focus, edit notes, and open the full dialog.
- Switch timeframes and return to the original timeframe.
- Change chart/trade visibility settings and restart the app if needed.
- Open logs, refresh logs, run update check, and inspect an error/failure dialog.

Automated smoke coverage was run for the same surfaces through focused Qt tests and the full suite. An offscreen Qt smoke pass also rendered screenshots for startup, main session, dataset manager, session library, trade history, settings, missing-log viewer, and update-failure dialog under `C:\tmp\barbybar_polish_smoke`. The offscreen capture environment rendered Chinese glyphs as square fallback boxes in screenshots, so a final hands-on packaged-app smoke pass is still recommended before publishing the major release build.

## Stability Review Notes

- Session saves continue through the existing `save_session` and async step-forward save worker paths; the polish pass only changes UI state/copy and does not introduce new persistence calls.
- Step-forward async saves carry a full `SessionSaveRequest`, including actions, order lines, drawings, and trade review items. Generation tracking still prevents stale save completion from becoming the latest save.
- Step back still performs a synchronous save after engine rollback, so chart markers, trade links, history cards, stats, and notes are refreshed from the same engine snapshot.
- Timeframe switching still saves the source timeframe first, then performs the target timeframe state save with trade and drawing persistence disabled, preserving source timeframe actions/trades/drawings.
- Trade-history selection, entry/exit focus, sidebar tab state, chart focus mode, and settings controls are refreshed from explicit owner state rather than hidden widget-local state.
- Busy overlays remain scoped to CSV import, batch import, session open, and update checks; recoverable dialogs use existing primary/secondary/danger button roles.
- No database schema, trading engine calculation, order semantics, trade persistence semantics, or chart aggregation code was changed as part of this polish pass.
