## ADDED Requirements

### Requirement: Trade review opens in a chart-safe sidebar
The system SHALL provide a right-side trade review sidebar that does not cover the candlestick chart.

#### Scenario: User opens trade review
- **WHEN** the user clicks the historical trade review entry point
- **THEN** the system shows the trade review sidebar beside the chart instead of covering the chart with a floating window

#### Scenario: User collapses the sidebar
- **WHEN** the user collapses or closes the sidebar
- **THEN** the chart expands into the freed space and trade review state is preserved for the next open

### Requirement: Sidebar uses compact trade cards
The system SHALL display historical trades in compact sidebar cards rather than a wide table.

#### Scenario: Sidebar lists trades
- **WHEN** historical trades are available
- **THEN** each card shows trade number, direction, PnL, exit reason, and a compact time label

#### Scenario: User selects a trade card
- **WHEN** the user selects a trade card
- **THEN** the system selects that trade, updates the sidebar detail, and focuses the chart using the active entry/exit focus mode

### Requirement: Sidebar supports per-trade review work
The system SHALL show selected-trade summary, entry/exit focus controls, entry thought, review summary, and save action in the sidebar.

#### Scenario: User edits notes in sidebar
- **WHEN** the user edits entry thought or review summary and saves
- **THEN** the system persists those notes through the existing per-trade action-note behavior

### Requirement: Full table remains available
The system SHALL provide an explicit full-table action from the sidebar for wide sorting and filtering workflows.

#### Scenario: User opens full table
- **WHEN** the user clicks the full-table action
- **THEN** the system opens the existing full trade history table view without losing the selected trade
