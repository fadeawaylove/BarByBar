## ADDED Requirements

### Requirement: Professional workbench shell
The system SHALL present the main review window as a professional chart-first workbench with distinct app header, training toolbar, chart workspace, right training panel, and bottom status bar regions.

#### Scenario: Main session shell is visible
- **WHEN** a user opens or creates a review session
- **THEN** the main window presents a stable workbench shell with clearly separated app-level navigation, training controls, chart workspace, right training panel, and status feedback.

#### Scenario: Empty startup shell is intentional
- **WHEN** the app starts with no active session
- **THEN** the shell presents a polished no-session state with clear next actions for importing data, opening a session, or creating a session without showing a broken or half-empty trading layout.

#### Scenario: Workbench hierarchy remains stable
- **WHEN** the user steps forward, steps back, changes timeframe, opens trade history, or toggles drawing/order-preview modes
- **THEN** the major workbench regions remain in stable positions without layout jumps.

### Requirement: Separated app and training controls
The system SHALL separate low-frequency application management actions from high-frequency training actions.

#### Scenario: App-level actions do not compete with replay
- **WHEN** a user is actively replaying a session
- **THEN** dataset management, session library, settings, logs, and update actions remain accessible but visually secondary to timeframe, replay, chart tool, and trade actions.

#### Scenario: Training toolbar exposes active mode
- **WHEN** the user activates a drawing tool or order-preview workflow
- **THEN** the training toolbar or chart workspace displays the active mode and a clear cancellation path.

#### Scenario: Timeframe selection is scannable
- **WHEN** the user views supported chart timeframes
- **THEN** the current timeframe is visually selected and inactive timeframes remain compact and readable.

### Requirement: Chart-dominant workspace
The system SHALL make the chart the dominant visual surface while keeping overlays, axes, labels, markers, links, and drawings readable.

#### Scenario: Chart remains primary
- **WHEN** a session is active
- **THEN** the chart occupies the largest and visually strongest area of the workbench.

#### Scenario: Overlays do not overpower candles
- **WHEN** trade markers, trade links, drawing handles, order previews, bar labels, hover labels, and measurement labels are visible
- **THEN** they remain readable without obscuring the candles or making the chart feel cluttered.

#### Scenario: Active chart interaction is obvious
- **WHEN** drawing mode, order-preview mode, measurement mode, marker hover, or trade-link hover is active
- **THEN** the chart provides clear state feedback without changing the underlying interaction semantics.

### Requirement: Right training state center
The system SHALL redesign the right sidebar as a training state center with clear sections for position, quick trade actions, line/order tools, session statistics, review entry points, display controls, and session utilities.

#### Scenario: Position state is immediately visible
- **WHEN** the user has no position, a long position, a short position, or a completed session
- **THEN** the position section presents a visually distinct, readable state for that condition.

#### Scenario: Quick trade actions are primary
- **WHEN** a session is active
- **THEN** buy, sell, close, and reverse actions are grouped as primary training actions with clear enabled, disabled, pressed, and role-specific states.

#### Scenario: Line and drawing actions are secondary
- **WHEN** the user needs entry, exit, stop, take-profit, adverse, reverse, or drawing tools
- **THEN** those actions are visible as secondary tools without competing with direct trade actions.

#### Scenario: Supporting controls are available but quiet
- **WHEN** the user needs display toggles, session notes, save/open actions, or other supporting controls
- **THEN** those controls remain discoverable while visually yielding to trade and replay controls.

### Requirement: Trade review center
The system SHALL redesign trade history as a review center that supports fast trade scanning, focused entry/exit navigation, note editing, and detail review.

#### Scenario: Trade list is decision-readable
- **WHEN** the user views trade history
- **THEN** each trade item emphasizes trade number, direction, PnL, outcome, entry/exit span, holding bars, and exit reason.

#### Scenario: Selected trade and focus are distinct
- **WHEN** a trade is selected and the user focuses entry or exit
- **THEN** selected-trade state and active entry/exit focus state are visually distinct in the trade list, detail panel, and chart feedback.

#### Scenario: Full trade history supports review workflow
- **WHEN** the user opens the full trade history dialog
- **THEN** the dialog presents filtering, sorting, trade list, trade detail, entry thought, review summary, focus controls, navigation, and empty/filter states as one coherent review workspace.

#### Scenario: Notes preserve current semantics
- **WHEN** the user edits entry thought or review summary
- **THEN** the notes continue to save through the existing entry/exit action and trade review persistence behavior.

### Requirement: Unified supporting dialogs
The system SHALL redesign settings, dataset manager, session library, log viewer, update dialogs, notice/error dialogs, and busy overlays as a coherent product family.

#### Scenario: Settings are grouped by user mental model
- **WHEN** the user opens settings
- **THEN** chart display, training behavior, trade visibility, default quantities, diagnostics, logs, and update-related controls are grouped into clear pages or sections.

#### Scenario: Data and session dialogs expose clear next actions
- **WHEN** the user opens dataset manager or session library
- **THEN** the dialog presents search/filter, empty states, primary actions, secondary actions, destructive actions, and failure feedback with consistent visual hierarchy.

#### Scenario: Logs and errors are diagnosable
- **WHEN** logs are missing, log reading fails, update checks fail, imports fail, or session loading fails
- **THEN** the UI shows the failed operation, relevant detail/path when available, and a clear recovery action.

#### Scenario: Busy state is scoped
- **WHEN** import, batch import, session loading, save flushing, or update checking is in progress
- **THEN** busy feedback communicates the operation without blocking unrelated recoverable actions longer than necessary.

### Requirement: Desktop visual system
The system SHALL define and use a consistent desktop visual system across the workbench.

#### Scenario: Theme tokens cover common roles
- **WHEN** UI components are styled
- **THEN** they use shared roles for shell, surface, border, text, primary, secondary, quiet, danger, long, short, selected, disabled, hover, pressed, focus, warning, error, and success states.

#### Scenario: Components use consistent density
- **WHEN** buttons, inputs, tabs, cards, tables, side panels, toolbars, and dialogs appear together
- **THEN** their spacing, height, border radius, typography, and alignment feel like one product system.

#### Scenario: Chinese labels fit
- **WHEN** Chinese labels appear in buttons, tabs, cards, dialogs, status rows, filters, and sidebars
- **THEN** text fits its container without clipping, overlap, or unreadable compression.

### Requirement: Interaction quality and accessibility
The system SHALL preserve fast desktop operation while improving focus, hover, selected, disabled, keyboard, and feedback states.

#### Scenario: Interactive elements communicate affordance
- **WHEN** an element is clickable, selectable, editable, draggable, or toggleable
- **THEN** it provides visible hover, focus, pressed, selected, disabled, or active feedback appropriate to the interaction.

#### Scenario: Keyboard and shortcut behavior remains intact
- **WHEN** the user uses existing replay shortcuts, focused text fields, dialogs, and chart interactions
- **THEN** existing keyboard behavior remains functional and accidental replay actions are still blocked from text-entry contexts.

#### Scenario: Error recovery does not strand the user
- **WHEN** a recoverable operation fails
- **THEN** the user can dismiss, retry, inspect details, or continue working without the app entering a confusing visual state.

### Requirement: Visual validation workflow
The system SHALL include validation for the redesigned UI beyond unit-level behavior checks.

#### Scenario: Screenshot set is generated
- **WHEN** the redesign is ready for review
- **THEN** screenshots or equivalent visual captures exist for empty startup, active session, active trade, drawing/order-preview state, trade history sidebar, full trade history dialog, settings, dataset manager, session library, log viewer, update/error dialog, and narrow desktop layout.

#### Scenario: Manual smoke criteria are explicit
- **WHEN** the change is prepared for implementation completion
- **THEN** manual smoke criteria cover visual hierarchy, text fit, no overlap, action discoverability, chart dominance, trade review workflow, dialog consistency, and packaged-app font rendering.

#### Scenario: Regression tests remain green
- **WHEN** the redesign is complete
- **THEN** existing tests for engine behavior, repository persistence, trade history, chart interactions, logging, updates, and session workflows continue to pass.
