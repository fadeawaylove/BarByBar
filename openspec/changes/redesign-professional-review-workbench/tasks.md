## 1. Audit, Inventory, and Design Acceptance

- [x] 1.1 Inventory every visible control in the current main window and classify it as app-level, training-level, chart-level, trade-level, review-level, or diagnostic.
- [x] 1.2 Map every current top-toolbar action to its redesigned location in the app header or training toolbar.
- [x] 1.3 Map every current right-sidebar control to its redesigned section: position, quick trade, line/order tools, stats, review, display, or session utility.
- [x] 1.4 Map every current trade-history sidebar and dialog control to the redesigned review-center workflow.
- [x] 1.5 Map every settings, dataset manager, session library, log viewer, update dialog, notice dialog, error dialog, and busy overlay control to a redesigned surface.
- [x] 1.6 Identify controls that are duplicated, low-frequency, or visually noisy and decide whether they remain visible, move to a secondary section, or move into a menu.
- [x] 1.7 Define the desktop target sizes for visual validation: standard desktop, wide desktop, and narrow supported desktop.
- [x] 1.8 Define the screenshot acceptance set for empty startup, active session, active position, drawing mode, order-preview mode, trade-history sidebar, full trade-history dialog, settings, dataset manager, session library, log viewer, update/error dialog, and narrow layout.
- [x] 1.9 Create a redesign acceptance checklist covering chart dominance, action hierarchy, text fit, no overlap, visual consistency, state clarity, and packaged-app font rendering.
- [x] 1.10 Document the old-to-new information architecture before implementation begins.

## 2. Visual System Foundation

- [x] 2.1 Define AppTheme tokens for shell background, header background, toolbar background, chart surround, sidebar background, status bar background, panel surface, section surface, card surface, dialog surface, input surface, table surface, and overlay surface.
- [x] 2.2 Define border tokens for hairline borders, section dividers, selected borders, focus borders, danger borders, long borders, short borders, and muted borders.
- [x] 2.3 Define text tokens for title, subtitle, section title, body, secondary, muted, disabled, numeric, positive, negative, warning, error, and success.
- [x] 2.4 Define action tokens for primary, secondary, quiet, danger, long, short, toggle, selected, checked, pressed, hover, focus, and disabled states.
- [x] 2.5 Define chart-specific tokens for candle background, plot background, grid, axes, labels, bar numbers, hover readout, measurement, order preview, drawing handles, trade markers, and trade links.
- [x] 2.6 Define spacing tokens for shell margins, toolbar gaps, sidebar section gaps, card padding, dialog padding, form row spacing, table density, and status bar height.
- [x] 2.7 Define component dimensions for top action buttons, icon buttons, timeframe buttons, replay controls, trade buttons, sidebar inputs, status chips, table rows, and dialog controls.
- [x] 2.8 Define typography sizes and weights for app title, session title, toolbar labels, section headers, body text, dense metadata, numeric values, buttons, and table cells.
- [x] 2.9 Create reusable stylesheet helpers for app shell, header, toolbar, sidebar section, status bar, panel, card, table, dialog, form, button roles, input roles, and focus states.
- [x] 2.10 Replace one-off hard-coded color/style snippets in UI code with shared theme helpers where practical.
- [x] 2.11 Add automated tests that assert key theme roles and component constants exist.
- [x] 2.12 Add a lightweight visual-system documentation section describing role usage and anti-patterns to avoid.

## 3. Workbench Shell Redesign

- [x] 3.1 Split the current top area into a dedicated app header and training toolbar.
- [x] 3.2 Add app header structure for product name, current session summary, current dataset/symbol/timeframe context, save/status feedback, and app-level actions.
- [x] 3.3 Move dataset manager, session library, settings, log viewer, and update check actions into the app-level action area.
- [x] 3.4 Ensure app-level actions are accessible but visually secondary during active training.
- [x] 3.5 Add training toolbar structure for timeframe selection, previous/next replay actions, jump/reset controls, chart tools, drawing templates, and active mode feedback.
- [x] 3.6 Make timeframe buttons compact, stable, and visibly selected.
- [x] 3.7 Make replay controls read as one stable control group with consistent sizing and disabled states.
- [x] 3.8 Make chart tool buttons icon-first where an existing icon or clear symbol is available, with tooltips for less obvious tools.
- [x] 3.9 Add active training-mode feedback for browse, drawing, and order-preview states.
- [x] 3.10 Add a redesigned bottom status bar with current bar, current timestamp, chart timeframe, source dataset, save status, and transient hints.
- [x] 3.11 Ensure shell regions do not jump when no session, loading session, active session, completed session, or error state is shown.
- [x] 3.12 Add tests for app header contents, training toolbar grouping, selected timeframe state, replay group state, and status bar contents.

## 4. No-Session, Loading, and Recovery States

- [x] 4.1 Redesign the no-session startup state as an intentional start workspace rather than an empty chart.
- [x] 4.2 Provide primary no-session action for importing data or opening an existing session.
- [x] 4.3 Provide secondary no-session actions for dataset manager, session library, and settings.
- [x] 4.4 Show helpful empty-state copy without turning the screen into a marketing landing page.
- [x] 4.5 Redesign session-loading feedback so it appears in the shell without permanently covering recoverable controls.
- [x] 4.6 Redesign session-load failure feedback with retry, open session library, and log/detail paths.
- [x] 4.7 Ensure the app returns cleanly from loading, failed loading, no-session, and active-session states.
- [x] 4.8 Add tests for no-session state, loading state, failed-load notice, and state recovery.

## 5. Chart Workspace Redesign

- [x] 5.1 Reduce chart container chrome so the chart reads as the main work surface rather than a card preview.
- [x] 5.2 Tune chart background and plot area colors for professional light-mode contrast.
- [x] 5.3 Tune candle body, wick, border, and selection colors against the new chart background.
- [x] 5.4 Tune grid, axes, tick labels, bar numbers, and session markers so they are readable but subdued.
- [x] 5.5 Redesign hover readout placement and styling so it does not cover important candles or controls.
- [x] 5.6 Redesign temporary measurement label styling and clamping behavior for readability.
- [x] 5.7 Redesign drawing handles, anchor highlights, and selected drawing styling for clear interaction state.
- [x] 5.8 Redesign order-preview lines and hints for entry, exit, stop, take-profit, adverse, and reverse order types.
- [x] 5.9 Redesign active drawing/order-preview chart hint so the user always knows the active mode and cancel action.
- [x] 5.10 Tune trade marker size, opacity, shape, and hover/selected states for chart readability.
- [x] 5.11 Tune trade-link color, opacity, width, hover, selected, and note-edit states.
- [x] 5.12 Ensure trade markers and links from persisted trade review items remain the primary path for completed trades.
- [x] 5.13 Ensure defensive fallback from actions remains available without becoming the normal rendering path.
- [x] 5.14 Add chart-widget tests for active mode hints, order-preview styling, drawing active state, marker opacity, link opacity, hover states, and no-overlap positioning where feasible.

## 6. Right Training Panel Redesign

- [x] 6.1 Replace the current right training tab content with a structured training state center.
- [x] 6.2 Create a position snapshot section with state-specific layouts for no position, long position, short position, and completed session.
- [x] 6.3 Show current direction, quantity, average price, floating PnL where available, realized PnL, and status text in the position snapshot.
- [x] 6.4 Redesign quick trade buttons for buy, sell, close, and reverse as the primary action group.
- [x] 6.5 Ensure quick trade buttons have distinct long, short, close, reverse, disabled, pressed, and focus states.
- [x] 6.6 Redesign quantity input placement so it is stable and easy to adjust without shifting buttons.
- [x] 6.7 Redesign line/order tools as a secondary section with entry, exit, stop, take-profit, adverse, reverse, and cancel-preview controls.
- [x] 6.8 Redesign draw-order quantity and price inputs so they align with line/order tools and stay stable.
- [x] 6.9 Redesign chart drawing tools and template controls as supporting chart tools, not primary trade actions.
- [x] 6.10 Redesign session statistics section with compact metrics for trade count, win rate, PnL, and current replay progress.
- [x] 6.11 Redesign display controls for bar labels, drawings, markers, and links as quiet toggles.
- [x] 6.12 Redesign session utilities such as save/open/notes so they are available but tertiary.
- [x] 6.13 Ensure sidebar scroll behavior works on narrow desktop height without hiding primary trade actions.
- [x] 6.14 Add tests for section existence, action hierarchy, position states, button roles, input widths, disabled states, and sidebar scroll behavior.

## 7. Trade History Sidebar Redesign

- [x] 7.1 Redesign compact trade-history sidebar card layout around trade number, direction, PnL, outcome, entry/exit span, holding bars, and exit reason.
- [x] 7.2 Make selected trade state visually distinct from active entry-focus and exit-focus states.
- [x] 7.3 Add compact entry/exit focus controls that clearly indicate current focus target.
- [x] 7.4 Redesign previous/next trade navigation and boundary-disabled states.
- [x] 7.5 Redesign no-trade, no-selection, and filtered-out states in the sidebar.
- [x] 7.6 Ensure selecting a trade scrolls the selected card into view without awkward jumps.
- [x] 7.7 Ensure sidebar trade selection updates chart focus, marker/link highlight, and detail text together.
- [x] 7.8 Add tests for card text hierarchy, selected state, entry/exit focus state, navigation boundaries, empty states, and chart-focus integration.

## 8. Full Trade Review Center Redesign

- [x] 8.1 Redesign the full trade-history dialog into a list/detail review center.
- [x] 8.2 Build a left trade list optimized for scanning trade number, direction, PnL, outcome, time span, and exit reason.
- [x] 8.3 Build a right detail panel for selected trade summary, entry detail, exit detail, PnL, holding bars, and review metadata.
- [x] 8.4 Redesign filter and sort controls so they are compact, readable, and do not dominate the dialog.
- [x] 8.5 Redesign entry thought and review summary editors with clear labels, save feedback, and dirty/saved states.
- [x] 8.6 Add clear entry-focus and exit-focus controls with chart positioning feedback.
- [x] 8.7 Add clear-filter action and empty filtered state.
- [x] 8.8 Preserve note storage semantics by continuing to write through entry/exit action notes and trade review snapshots.
- [x] 8.9 Preserve existing sorting/filtering behavior while changing presentation.
- [x] 8.10 Add tests for filters, sorting, selected trade, focus controls, note editing feedback, empty states, and persistence semantics.

## 9. Settings Redesign

- [x] 9.1 Redesign settings as a professional multi-section dialog with clear navigation.
- [x] 9.2 Group chart display settings separately from training behavior settings and diagnostics settings.
- [x] 9.3 Redesign color controls as swatches with readable labels and reset actions.
- [x] 9.4 Redesign marker/link visibility and alpha controls with compact sliders and numeric feedback.
- [x] 9.5 Redesign default order quantity and draw-order quantity controls with stable sizing.
- [x] 9.6 Redesign flatten-at-session-end setting with clear wording and state.
- [x] 9.7 Redesign diagnostics/log settings with log paths, open/copy actions, and performance metrics.
- [x] 9.8 Ensure settings changes still persist immediately where current behavior expects persistence.
- [x] 9.9 Add tests for settings page grouping, control roles, persistence, reset colors, log actions, and performance metrics display.

## 10. Dataset Manager Redesign

- [x] 10.1 Redesign dataset manager layout around import actions, search/filter, dataset list, selected dataset detail, and destructive actions.
- [x] 10.2 Make single CSV import the primary dataset action.
- [x] 10.3 Make folder import a secondary dataset action with clear batch-progress feedback.
- [x] 10.4 Add selected dataset detail area showing name, symbol, timeframe, bar count, start/end time, and source path where available.
- [x] 10.5 Redesign no-dataset and filtered-out dataset empty states.
- [x] 10.6 Redesign duplicate dataset feedback so the skipped reason is clear.
- [x] 10.7 Redesign import failure detail display for readable file/reason lists.
- [x] 10.8 Ensure delete dataset remains a clear destructive action with confirmation.
- [x] 10.9 Add tests for empty state, filtering, selected detail, import action hierarchy, duplicate feedback, batch progress, failure detail, and delete confirmation.

## 11. Session Library Redesign

- [x] 11.1 Redesign session library layout around search/filter, session list, selected session detail, and open/delete actions.
- [x] 11.2 Make session rows show title, symbol, timeframe, status, PnL, updated time, and tags in a readable hierarchy.
- [x] 11.3 Add selected session detail area with dataset, replay progress, stats, notes preview, and tags where available.
- [x] 11.4 Visually distinguish the currently open session from other sessions.
- [x] 11.5 Redesign no-session and filtered-out session empty states.
- [x] 11.6 Redesign open-session loading and open-session failure feedback.
- [x] 11.7 Ensure delete session remains a clear destructive action with confirmation.
- [x] 11.8 Add tests for filtering, row hierarchy, current session visibility, selected detail, empty states, open failure, and delete confirmation.

## 12. Logs, Updates, Notices, and Busy States

- [x] 12.1 Redesign log viewer with clear file selection, refresh action, readable log text area, status path, and auto-refresh feedback.
- [x] 12.2 Redesign missing-log state with explicit missing file path and recovery copy.
- [x] 12.3 Redesign failed-log-read state with the exception detail and readable status.
- [x] 12.4 Redesign update check dialog states for up-to-date, update available, update download, update failure, and release-note detail.
- [x] 12.5 Redesign notice dialogs with consistent heading, summary, detail area, primary action, secondary action, and danger action roles.
- [x] 12.6 Redesign busy overlays for import, batch import, session load, save flush, and update check.
- [x] 12.7 Ensure busy overlays do not remain after success, cancel, or failure.
- [x] 12.8 Add tests for log viewer states, update dialogs, notice roles, busy overlay lifecycle, and failure recovery.

## 13. Responsive Desktop and Text Fit

- [x] 13.1 Define minimum supported main-window width and height for the redesigned workbench.
- [x] 13.2 Verify the app header does not clip Chinese labels at standard and narrow desktop widths.
- [x] 13.3 Verify the training toolbar remains usable at standard and narrow desktop widths.
- [x] 13.4 Verify the right training panel remains usable at standard and narrow desktop heights.
- [x] 13.5 Verify trade cards do not clip long Chinese notes, symbols, reasons, or PnL text.
- [x] 13.6 Verify settings, dataset, session, log, update, and notice dialogs fit common desktop sizes.
- [x] 13.7 Add structural tests or screenshot checks for key text-fit and no-overlap cases.

## 14. Interaction Continuity and Behavior Preservation

- [x] 14.1 Verify direct trade actions still call the existing engine action paths.
- [x] 14.2 Verify line/order tools still create and trigger existing order line types with unchanged semantics.
- [x] 14.3 Verify drawing tools still create, select, edit, and persist existing drawing objects.
- [x] 14.4 Verify step forward, step back, reset view, and shortcut behavior remain unchanged.
- [x] 14.5 Verify text-entry widgets still block replay shortcuts where current behavior requires it.
- [x] 14.6 Verify timeframe switching still saves source timeframe state and does not clear source trades/drawings.
- [x] 14.7 Verify session load/save, async step-forward save, and save-failure fallback behavior remain intact.
- [x] 14.8 Verify trade review notes still write to the same entry/exit action notes and trade review item snapshots.
- [x] 14.9 Add focused regression tests for each preserved behavior touched by the redesign.

## 15. Screenshot and Manual Visual Review

- [x] 15.1 Add or update a local screenshot smoke script for the redesigned workbench.
- [x] 15.2 Capture empty startup screenshot.
- [x] 15.3 Capture active session screenshot with no position.
- [x] 15.4 Capture active session screenshot with long position.
- [x] 15.5 Capture active session screenshot with short position.
- [x] 15.6 Capture completed session screenshot.
- [x] 15.7 Capture drawing-mode screenshot.
- [x] 15.8 Capture order-preview-mode screenshot.
- [x] 15.9 Capture trade-history sidebar screenshot with selected entry focus.
- [x] 15.10 Capture full trade review center screenshot.
- [x] 15.11 Capture settings dialog screenshot.
- [x] 15.12 Capture dataset manager screenshot with empty, populated, and batch-progress states.
- [x] 15.13 Capture session library screenshot with empty, populated, and filtered states.
- [ ] 15.14 Capture log viewer screenshot with normal, missing-log, and failed-read states where feasible.
- [ ] 15.15 Capture update/error/notice dialog screenshots.
- [x] 15.16 Capture narrow desktop layout screenshot.
- [x] 15.17 Review screenshots against the redesign acceptance checklist and document remaining visual issues.
- [ ] 15.18 Run a packaged-app manual smoke pass to verify real font rendering, text fit, and dialog sizing.

## 16. Tests and Final Validation

- [x] 16.1 Update main-window tests for app header, training toolbar, status bar, no-session state, right-panel sections, and preserved action wiring.
- [x] 16.2 Update chart-widget tests for visual states and interaction feedback touched by the redesign.
- [x] 16.3 Update trade-history tests for sidebar and full review center workflows.
- [x] 16.4 Update settings tests for redesigned grouping, persistence, and diagnostics actions.
- [x] 16.5 Update dataset manager tests for import hierarchy, filtering, selected detail, empty states, and batch states.
- [x] 16.6 Update session library tests for row hierarchy, selected detail, current session, empty states, and open/delete behavior.
- [x] 16.7 Update log/update/notice/busy overlay tests for redesigned states.
- [x] 16.8 Run focused main-window UI tests.
- [x] 16.9 Run focused chart-widget tests.
- [x] 16.10 Run focused trade-history tests.
- [x] 16.11 Run focused settings/dataset/session/log/update tests.
- [x] 16.12 Run repository, engine, async save, logging retention, and release/update regression tests to confirm no core behavior changed.
- [x] 16.13 Run full test suite with `uv run pytest -q`.
- [x] 16.14 Run `openspec validate redesign-professional-review-workbench --strict`.
- [x] 16.15 Confirm screenshots/manual smoke notes are attached or documented before marking the change complete.

## 17. Audit-Driven Polish Corrections

- [x] 17.1 Add a restrained product identity and hide unused drawing-template slots from the primary toolbar.
- [x] 17.2 Widen the replay sidebar to fit four-action rows and remove horizontal scrolling from trade review lists and tables.
- [x] 17.3 Make settings pages scroll safely, constrain color controls, and ensure readable text contrast on dark swatches.
- [x] 17.4 Improve dataset/session row hierarchy, centered empty states, and compact destructive-action footers.
- [x] 17.5 Re-run focused UI tests, the complete suite, strict OpenSpec validation, and screenshot smoke review.
