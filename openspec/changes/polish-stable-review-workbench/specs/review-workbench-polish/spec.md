## ADDED Requirements

### Requirement: Coherent review workbench layout
The system SHALL present the existing review workspace as a stable three-zone interface with a top toolbar, primary chart area, and supporting right sidebar.

#### Scenario: Main review screen is loaded
- **WHEN** a review session is open
- **THEN** the chart SHALL remain the dominant workspace
- **AND** the top toolbar and right sidebar SHALL align visually with consistent spacing and hierarchy
- **AND** existing dataset, session, settings, log, update, replay, drawing, trading, and history actions SHALL remain reachable

### Requirement: Consistent existing-action feedback
The system SHALL provide clear visual and interaction feedback for existing user actions.

#### Scenario: User interacts with replay, trade, drawing, and sidebar controls
- **WHEN** an existing action is enabled, disabled, hovered, pressed, checked, selected, loading, or failed
- **THEN** the control SHALL expose a visually distinct state without changing the underlying action semantics

### Requirement: Polished visual system
The system SHALL use a consistent visual language across existing windows, panels, dialogs, tables, cards, and chart overlays.

#### Scenario: User moves between primary surfaces
- **WHEN** the user opens the main window, settings dialog, session library, dataset manager, trade history, log viewer, or chart tool surfaces
- **THEN** typography, spacing, border radius, color roles, focus treatment, empty states, and density SHALL feel consistent
- **AND** text SHALL not overlap, truncate awkwardly, or overflow common desktop window sizes

### Requirement: Stable busy, empty, and error states
The system SHALL make existing loading, empty, invalid, and failure states understandable without interrupting the review workflow more than necessary.

#### Scenario: Existing workflow has no data or is busy
- **WHEN** there is no dataset, no session, no trade history, no selected trade, a session load is in progress, or a save/load error occurs
- **THEN** the UI SHALL show a clear state message and keep safe actions available

### Requirement: Responsive existing workflows
The system SHALL preserve or improve responsiveness for existing high-frequency review workflows.

#### Scenario: User performs common review actions
- **WHEN** the user steps bars, switches timeframe, edits settings, selects trade history, focuses entry/exit, toggles markers/links, or opens dialogs
- **THEN** the UI SHALL avoid unnecessary layout jumps, stale selections, overlapping controls, and visibly frozen interactions
- **AND** persisted settings and session state SHALL remain consistent with the current behavior

### Requirement: No new product feature scope
The system SHALL keep the major version focused on polish of existing functionality.

#### Scenario: Workbench polish is implemented
- **WHEN** the change is complete
- **THEN** it SHALL NOT introduce new trading calculations, new analytics/coaching/reporting workflows, new database schema requirements, or new external service dependencies
