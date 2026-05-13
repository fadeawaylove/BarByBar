## 1. UX Inventory and Structure

- [x] 1.1 Inventory all current main-window, chart, right-panel, and trade-history controls and classify each as Replay, Plan, Annotate, Review, app-level, or diagnostic.
- [x] 1.2 Create an old-to-new control map for every visible action affected by the reframed workflow.
- [x] 1.3 Document low-fidelity structure sketches for active session shell, empty startup, Replay mode, Plan mode, Annotate mode, and Review mode.
- [x] 1.4 Document compact trade card and full trade review workspace sketches.
- [x] 1.5 Define UX acceptance criteria for chart dominance, mode clarity, state center stability, trade review flow, text fit, and no overlap.
- [x] 1.6 Review the existing `redesign-professional-review-workbench` implementation state and mark which pieces should be reused instead of rebuilt.

## 2. Mode Model Foundation

- [x] 2.1 Add a UI-level mode model for Replay, Plan, Annotate, and Review without changing domain engine behavior.
- [x] 2.2 Map existing drawing activation to Annotate mode and existing order-preview activation to Plan mode.
- [x] 2.3 Map trade selection, trade-history focus, and full trade review entry to Review mode.
- [x] 2.4 Ensure normal session stepping, direct trade actions, and chart browsing keep Replay mode active unless a specific tool is active.
- [x] 2.5 Add mode state tests for activation, cancellation, and preservation of existing shortcuts.

## 3. Visual System Direction

- [x] 3.1 Revise theme tokens toward a cooler professional light-terminal palette with reduced beige/warm surface dominance.
- [x] 3.2 Tighten radius, border, surface, divider, and toolbar density tokens for a sharper desktop feel.
- [x] 3.3 Add numeric, PnL, long, short, reverse, close, selected, focus, and active-mode visual roles where missing.
- [x] 3.4 Reduce nested-card styling in shell and panel areas in favor of bands, dividers, and stable sections.
- [x] 3.5 Add theme tests that assert the required workflow and visual role tokens exist.

## 4. Workbench Shell and Toolbar

- [x] 4.1 Update the main shell so current case context, dataset/session state, save state, and app actions form a clear case header.
- [x] 4.2 Add a mode-aware toolbar that exposes active workflow, timeframe, replay controls, active tool summary, and cancellation path.
- [x] 4.3 Ensure active mode feedback appears consistently in the toolbar and chart hint area.
- [ ] 4.4 Redesign empty startup so import, session library, and recent work are the main next actions.
- [x] 4.5 Update status feedback to show current bar, timestamp, progress, save/worker state, and contextual hints without competing with the chart.
- [ ] 4.6 Add main-window tests for shell regions, mode toolbar state, empty startup, and status feedback.

## 5. Chart Workspace Interaction Feedback

- [ ] 5.1 Tune chart container styling so the chart reads as the main work surface instead of a framed preview.
- [ ] 5.2 Update chart hints for Replay, Plan, Annotate, and Review states.
- [ ] 5.3 Tune order-preview, drawing, measurement, hover, trade marker, and trade-link visuals against the revised palette.
- [ ] 5.4 Ensure chart overlays preserve candle readability when several overlay types are visible.
- [ ] 5.5 Add chart-widget tests for mode hint visibility, active overlay feedback, and existing interaction behavior preservation.

## 6. Right State Center

- [ ] 6.1 Keep position snapshot and primary trade actions stable across all modes.
- [ ] 6.2 Implement Replay emphasis for progress, current bar context, quick notes, display toggles, and session status.
- [ ] 6.3 Implement Plan emphasis for order-line tools, quantity/price context, active preview status, and cancel/clear actions.
- [ ] 6.4 Implement Annotate emphasis for drawing tools, templates, selected drawing properties, and style context.
- [ ] 6.5 Implement Review emphasis for selected trade summary, entry/exit focus, review note status, and previous/next navigation.
- [ ] 6.6 Verify right-panel scroll behavior keeps critical position and trade actions reachable at supported desktop heights.
- [ ] 6.7 Add tests for state center stability and mode-specific section emphasis.

## 7. Trade Review Workspace

- [ ] 7.1 Redesign compact side-panel trade cards around trade number, direction, PnL, result, time span, holding bars, exit reason, and note state.
- [ ] 7.2 Make selected trade, entry focus, exit focus, hover, and disabled/no-trade states visually distinct.
- [ ] 7.3 Redesign the full trade review view as a list/detail workspace with filters, sorting, summary, notes, and focus controls.
- [ ] 7.4 Preserve entry thought and review summary persistence through existing action-note and trade-review snapshot semantics.
- [ ] 7.5 Add trade-history tests for card hierarchy, selection/focus state, filtering/sorting, note persistence, and chart focus integration.

## 8. Behavior Preservation

- [ ] 8.1 Verify direct trade actions still call existing engine paths with unchanged action types and quantities.
- [ ] 8.2 Verify order-line creation, update, cancellation, and trigger semantics remain unchanged.
- [ ] 8.3 Verify drawing creation, selection, editing, deletion, templates, and persistence remain unchanged.
- [ ] 8.4 Verify replay shortcuts still work and text-entry widgets still block accidental replay.
- [ ] 8.5 Verify timeframe switching preserves per-timeframe trades, drawings, and chart state semantics.
- [ ] 8.6 Verify async save, session load, session save failure handling, and recovery behavior remain unchanged.

## 9. Screenshot and Manual Validation

- [ ] 9.1 Add or update a local screenshot smoke script for the reframed workbench states.
- [ ] 9.2 Capture screenshots for empty startup, Replay mode, Plan mode, Annotate mode, Review mode, active long/short position, and completed session.
- [ ] 9.3 Capture screenshots for compact trade cards, full trade review workspace, settings entry, dataset manager entry, and session library entry.
- [ ] 9.4 Capture a narrow supported desktop screenshot and verify text fit, no overlap, and reachable primary actions.
- [ ] 9.5 Document screenshot review notes against the UX acceptance criteria.

## 10. Final Validation

- [ ] 10.1 Run focused main-window UI tests.
- [ ] 10.2 Run focused chart-widget tests.
- [ ] 10.3 Run focused trade-history tests.
- [ ] 10.4 Run repository, engine, async save, update, and logging regression tests.
- [ ] 10.5 Run the full test suite with `uv run pytest -q`.
- [ ] 10.6 Run `openspec validate reframe-review-workflow-ux --strict`.
- [ ] 10.7 Confirm screenshots/manual smoke notes are complete before marking the change ready for archive.
