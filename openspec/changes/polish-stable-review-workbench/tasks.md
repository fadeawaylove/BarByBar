## 1. UX Audit and Baseline

- [x] 1.1 Audit the top toolbar grouping and document current issues in workspace actions, timeframe buttons, replay controls, chart tools, log actions, and update actions.
- [x] 1.2 Audit the chart area for visual noise, card nesting, axis/readout contrast, marker/link dominance, hover overlay placement, and chart-as-primary-workspace clarity.
- [x] 1.3 Audit the right sidebar training tab for trade controls, position status, training stats, display controls, and session controls hierarchy.
- [x] 1.4 Audit the trade-history sidebar/dialog for card hierarchy, selected state, entry/exit focus state, note editing, filters, and empty-selection states.
- [x] 1.5 Audit settings, session library, dataset manager, log viewer, update dialogs, busy overlays, and error dialogs for spacing, text fit, action order, and recoverability.
- [x] 1.6 Create or update a workbench polish checklist covering layout hierarchy, text overflow, button states, empty states, loading states, error states, and no-overlap acceptance.
- [x] 1.7 Map existing tests to each major workflow and identify missing test coverage before implementation.

## 2. Visual System Foundation

- [x] 2.1 Consolidate shared theme roles for background, surface, border, primary, long/short, danger, muted text, focus, hover, pressed, checked, disabled, and selected states.
- [x] 2.2 Normalize spacing, control heights, border radius, table/card density, and section gaps in existing theme/style helpers.
- [x] 2.3 Reduce visual noise from nested cards and heavy borders while preserving clear grouping.
- [x] 2.4 Ensure all common Chinese labels fit within buttons, tabs, cards, status labels, dialogs, and fixed-width right sidebar controls.
- [x] 2.5 Standardize disabled, active, checked, hover, pressed, focus, loading, warning, and error visual states across existing controls.

## 3. Main Workbench Layout

- [x] 3.1 Reorganize top toolbar visual grouping into workspace management, timeframe, replay controls, chart tools, and secondary diagnostics/update actions.
- [x] 3.2 Polish dataset, session, settings, log, and update buttons so low-frequency actions remain reachable without dominating the replay workflow.
- [x] 3.3 Polish timeframe buttons so the selected timeframe is obvious and inactive choices remain compact.
- [x] 3.4 Polish replay controls so previous, next, jump, reset view, and clear lines read as one stable control strip.
- [x] 3.5 Reduce chart frame noise and make the K-line canvas the dominant visual surface.
- [x] 3.6 Tune chart background, axis, labels, bar numbers, and grid/readout colors for professional contrast without clutter.

## 4. Right Sidebar Training Panel

- [x] 4.1 Polish the right sidebar tab header so "训练" and "历史交易" behave as stable navigation within the fixed sidebar.
- [x] 4.2 Rework the trade section hierarchy so direct trade actions are primary and line/order-drawing actions are clearly secondary.
- [x] 4.3 Stabilize quantity, price, draw quantity, and tick-size input widths so numeric changes do not shift layout.
- [x] 4.4 Make empty-position, long-position, short-position, and completed-session status readouts visually distinct and easy to scan.
- [x] 4.5 Compress low-frequency display/session controls so they remain available but do not compete with trading controls.
- [x] 4.6 Ensure open-long/open-short/close/reverse buttons expose clear enabled, disabled, pressed, and role-specific states.

## 5. Chart Interaction Polish

- [x] 5.1 Improve drawing-tool active state and cancellation feedback without changing existing drawing behavior.
- [x] 5.2 Improve order-preview activation, cancellation, and cursor/preview feedback for existing line-order workflows.
- [x] 5.3 Improve trade marker and trade link visual hierarchy so they remain readable without overpowering candles.
- [x] 5.4 Improve trade link hover/selection/note-entry feedback and keep it consistent with the trade-history sidebar.
- [x] 5.5 Check chart hover labels, measurement feedback, drawing handles, and anchor highlights for overlap and readability.

## 6. Trade History Review Polish

- [x] 6.1 Rework trade cards so trade number, direction, PnL, and entry/exit span are primary while secondary metadata is subdued.
- [x] 6.2 Separate selected-trade state from active entry/exit focus state in card, detail, and chart feedback.
- [x] 6.3 Polish previous/next trade navigation, disabled-at-boundary behavior, and scroll-selected-card-into-view behavior.
- [x] 6.4 Polish selected-trade detail layout for entry information, exit information, notes, and review metadata.
- [x] 6.5 Improve entry thought and review summary editing feedback while preserving existing note storage semantics.
- [x] 6.6 Add clear empty states for no trades, filtered-out trades, and no selected trade, including a clear-filter action where appropriate.
- [x] 6.7 Ensure the full trade-history dialog remains visually consistent with the sidebar and preserves sorting/filtering workflows.

## 7. Settings, Data, Session, Logs, and Update Surfaces

- [x] 7.1 Polish settings categories and pages so chart display, replay behavior, and diagnostics settings are visually grouped and immediately understandable.
- [x] 7.2 Polish color controls, alpha sliders, quantity defaults, flatten behavior, trade visibility, and persistence feedback in settings.
- [x] 7.3 Polish session library rows, search/filter empty state, current-session visibility, open-session loading, and open-session failure feedback.
- [x] 7.4 Polish dataset manager no-data state, single import, batch import progress, duplicate handling, and failure-detail readability.
- [x] 7.5 Polish log viewer file selection, refresh behavior, status path display, and missing-log/failed-read states.
- [x] 7.6 Polish update dialogs and error dialogs so primary/secondary actions, detail text, log references, and recovery instructions are clear.

## 8. Stability and Responsiveness Hardening

- [x] 8.1 Review session load/save and async step-forward save paths for stale UI state, accidental blocking, and confusing save-failure behavior.
- [x] 8.2 Review step back and rapid step-forward behavior to ensure chart markers, links, history cards, stats, and notes update together.
- [x] 8.3 Review timeframe switching so source timeframe data is preserved, target timeframe loads clearly, and returning to the source restores trade history and links.
- [x] 8.4 Preserve selected trade, sidebar tab, chart focus mode, scroll position, and settings state across refreshes where existing behavior implies continuity.
- [x] 8.5 Ensure busy overlays do not cover recoverable actions longer than necessary and error dialogs do not leave the app in a confusing state.
- [x] 8.6 Confirm the polish pass does not change database schema, trading engine calculations, order semantics, trade persistence semantics, or chart aggregation.

## 9. Tests and Validation

- [x] 9.1 Add or update tests for toolbar grouping, right sidebar hierarchy, button states, settings persistence, and dialog empty/error states.
- [x] 9.2 Add or update tests for trade-history card selection, entry/exit focus distinction, note editing feedback, empty/filter states, and navigation boundaries.
- [x] 9.3 Add or update chart-widget tests for drawing/order-preview state feedback, trade marker/link visibility, and hover/selection behavior where feasible.
- [x] 9.4 Run focused tests for main window, chart widget, trade history, repository/session persistence, logging/settings, and async save workflows.
- [x] 9.5 Run `uv run pytest -q`.
- [x] 9.6 Run `openspec validate polish-stable-review-workbench --strict`.
- [x] 9.7 Perform a manual smoke pass covering no-data startup, CSV import, session open/create, replay, trade actions, drawing/order preview, trade-history review, timeframe switching, settings persistence, logs, and update/error dialogs.
