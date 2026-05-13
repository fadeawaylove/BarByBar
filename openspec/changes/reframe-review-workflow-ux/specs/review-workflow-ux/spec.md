## ADDED Requirements

### Requirement: Mode-aware review workflow
The system SHALL present the active review workflow through explicit mode states for Replay, Plan, Annotate, and Review without changing existing trading, drawing, order-line, or persistence semantics.

#### Scenario: Replay mode is active during bar stepping
- **WHEN** a user opens an active session and is stepping forward or backward through bars
- **THEN** the workbench presents Replay as the active workflow and emphasizes timeframe, step, progress, position state, and quick trade actions.

#### Scenario: Plan mode is active during order-line work
- **WHEN** a user starts entry, exit, stop-loss, take-profit, adverse, reverse, or protective-line placement
- **THEN** the workbench presents Plan as the active workflow and shows the active line type, target price context, confirmation path, and cancellation path.

#### Scenario: Annotate mode is active during drawing work
- **WHEN** a user activates a drawing, text, measurement, template, or chart annotation tool
- **THEN** the workbench presents Annotate as the active workflow and shows the active tool, drawing guidance, style context, and cancellation path.

#### Scenario: Review mode is active during trade inspection
- **WHEN** a user selects a completed trade, opens trade history, or focuses a trade entry or exit
- **THEN** the workbench presents Review as the active workflow and emphasizes trade cards, entry/exit focus, notes, and chart highlight feedback.

#### Scenario: Mode state does not alter engine behavior
- **WHEN** the user switches between Replay, Plan, Annotate, and Review workflows
- **THEN** existing trade execution, order trigger, drawing persistence, session save, and shortcut behavior remains unchanged unless an existing interaction already requires a mode-specific action.

### Requirement: Chart-first attention hierarchy
The system SHALL keep the chart as the dominant visual and interaction surface during active review sessions.

#### Scenario: Active session prioritizes chart space
- **WHEN** a session is active
- **THEN** the chart occupies the largest central area and surrounding controls visually yield to chart reading and chart interaction.

#### Scenario: Toolbar describes chart intent
- **WHEN** a mode or tool changes what clicking, dragging, or hovering the chart will do
- **THEN** the toolbar and chart hint display that intent in a concise and visible way.

#### Scenario: Chart overlays preserve candle readability
- **WHEN** markers, trade links, drawings, order previews, hover labels, measurement labels, and session markers are visible together
- **THEN** the visual hierarchy keeps candles, current price context, and active interaction feedback readable.

#### Scenario: Empty startup is not a chart failure
- **WHEN** no session is active
- **THEN** the central area presents intentional next actions for import, session library, and recent work instead of a broken or half-empty chart workspace.

### Requirement: Stable mode-aware state center
The system SHALL provide a right-side state center that keeps critical trading state stable while adapting secondary content emphasis to the active mode.

#### Scenario: Critical state remains visible
- **WHEN** the user changes active mode
- **THEN** current position, quantity, average price, realized PnL, primary trade actions, and session status remain accessible without requiring navigation to a hidden page.

#### Scenario: Replay emphasis supports stepping
- **WHEN** Replay mode is active
- **THEN** the state center emphasizes current progress, current bar context, position state, quick trade actions, display toggles, and quick notes.

#### Scenario: Plan emphasis supports order-line setup
- **WHEN** Plan mode is active
- **THEN** the state center emphasizes order-line tools, line type, quantity, price context, active preview status, and cancel/clear actions.

#### Scenario: Annotate emphasis supports chart markup
- **WHEN** Annotate mode is active
- **THEN** the state center emphasizes drawing tools, templates, selected drawing properties, style presets, and annotation-specific guidance.

#### Scenario: Review emphasis supports trade analysis
- **WHEN** Review mode is active
- **THEN** the state center emphasizes selected trade summary, entry/exit focus controls, review note status, and previous/next trade navigation.

### Requirement: Trade review workspace
The system SHALL present completed trades as reviewable decisions with scanning, detail, entry/exit focus, and note editing workflows.

#### Scenario: Compact trade cards are scannable
- **WHEN** the user views trade history in the side panel
- **THEN** each trade item presents trade number, direction, PnL, result, entry/exit span, holding bars, exit reason, and note status in a readable hierarchy.

#### Scenario: Trade selection and focus are distinct
- **WHEN** a trade is selected and entry or exit focus is active
- **THEN** the selected trade state and active focus target are visually distinct in the trade card, detail view, and chart feedback.

#### Scenario: Full review workspace supports detail
- **WHEN** the user opens the full trade review view
- **THEN** the UI presents trade filtering, sorting, trade list, selected trade detail, entry thought editor, review summary editor, focus controls, navigation, and empty states as one coherent workflow.

#### Scenario: Notes preserve existing persistence
- **WHEN** the user edits entry thought or review summary from the review workspace
- **THEN** the notes save through the existing action note and trade review snapshot semantics.

### Requirement: Sharper professional light visual system
The system SHALL use a cooler, sharper, high-density professional light visual direction for the reframed workflow.

#### Scenario: Visual tokens support the new direction
- **WHEN** the workbench, state center, toolbar, cards, tables, dialogs, and chart overlays are styled
- **THEN** they use shared tokens for cool shell backgrounds, chart canvas, panel surfaces, dividers, focus, selected, disabled, long, short, warning, danger, success, and numeric emphasis.

#### Scenario: Controls feel precise
- **WHEN** buttons, segmented controls, inputs, cards, lists, tabs, and status chips appear in the same view
- **THEN** their radii, heights, spacing, typography, borders, and hover/focus states feel like one precise desktop system.

#### Scenario: Surface noise is reduced
- **WHEN** the user views an active session for long periods
- **THEN** nested cards, heavy borders, decorative gradients, and visually loud low-frequency controls are minimized so the chart and active workflow remain calm.

#### Scenario: Chinese and numeric labels fit
- **WHEN** Chinese labels, prices, PnL values, timestamps, symbols, and exit reasons appear in controls or cards
- **THEN** they fit without clipping, overlap, or layout jumps at supported desktop sizes.

### Requirement: Low-fidelity design validation before implementation
The system SHALL include reviewable structural sketches and acceptance criteria before application code implementation starts.

#### Scenario: Structure sketches exist
- **WHEN** implementation planning begins
- **THEN** low-fidelity sketches or equivalent documented layouts exist for active session shell, Replay mode, Plan mode, Annotate mode, Review mode, compact trade cards, and full trade review workspace.

#### Scenario: Control mapping exists
- **WHEN** existing controls are moved, grouped, renamed, or visually demoted
- **THEN** an old-to-new control map identifies where each existing user-facing control will live.

#### Scenario: Visual acceptance criteria are explicit
- **WHEN** the reframed UX is ready for review
- **THEN** acceptance criteria cover chart dominance, mode clarity, state center stability, trade review workflow, text fit, no overlap, action discoverability, and screenshot/manual smoke evidence.

#### Scenario: Existing behavior remains testable
- **WHEN** the reframed UX is implemented
- **THEN** tests or manual validation confirm replay shortcuts, direct trade actions, order-line creation, drawing creation, trade review note persistence, session save/load, and chart timeframe switching still work.
