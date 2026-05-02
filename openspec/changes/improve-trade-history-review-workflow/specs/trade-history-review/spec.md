## ADDED Requirements

### Requirement: Trade history uses a scannable review table
The system SHALL present historical trades in a tabular review view with columns for trade number, direction, entry time, exit time, holding duration, quantity, PnL, exit reason, and execution flags.

#### Scenario: User opens trade history
- **WHEN** the user opens the trade history view
- **THEN** the system displays historical trades in rows with the review columns visible or available through the table header

#### Scenario: User sorts by review column
- **WHEN** the user sorts the trade history by a supported column
- **THEN** the system reorders rows without losing the selected trade when that trade still exists

### Requirement: Trade history supports practical review filters
The system SHALL allow users to filter historical trades by direction, outcome, exit reason, plan/discipline flags, holding duration range, and PnL range.

#### Scenario: User filters losing long trades
- **WHEN** the user selects long direction and losing outcome filters
- **THEN** the system displays only trades matching both filters

#### Scenario: User clears filters
- **WHEN** the user clears trade history filters
- **THEN** the system restores the full trade history list using the active sort order

### Requirement: Selected trade details are visible without relying on tooltips
The system SHALL show a detail panel for the selected trade with entry/exit context, PnL, holding duration, exit reason, execution flags, and a concise action summary.

#### Scenario: User selects a trade row
- **WHEN** the user selects a trade in the history table
- **THEN** the system updates the detail panel to describe that trade

#### Scenario: No trade is selected
- **WHEN** no trade is selected in the history table
- **THEN** the detail panel shows an empty or instructional state without stale trade data

### Requirement: Chart focus controls support entry and exit
The system SHALL provide explicit focus controls for entry and exit for the selected historical trade.

#### Scenario: User focuses trade entry
- **WHEN** the user chooses entry focus for a selected trade
- **THEN** the chart navigates to the selected trade's entry context

#### Scenario: User focuses trade exit
- **WHEN** the user chooses exit focus for a selected trade
- **THEN** the chart navigates to the selected trade's exit context

### Requirement: Trade history selection stays synchronized with chart review state
The system SHALL keep the selected historical trade and selected focus mode synchronized between the trade history view and the chart review state.

#### Scenario: User moves selection with keyboard
- **WHEN** the user changes the selected row using keyboard navigation
- **THEN** the system updates the selected trade and preserves the active focus mode

#### Scenario: Trade history refreshes
- **WHEN** trade review data refreshes after engine state changes
- **THEN** the system preserves the selected trade, filters, sort order, and scroll position when possible

### Requirement: Trade history row selection focuses the chart
The system SHALL focus the chart using the active focus mode when a user selects a historical trade row.

#### Scenario: User single-clicks a row
- **WHEN** the user single-clicks a historical trade row
- **THEN** the system selects the trade, updates details, and focuses the chart using the active focus mode

#### Scenario: User activates a row
- **WHEN** the user double-clicks or activates a row with the keyboard
- **THEN** the system focuses the chart using the active focus mode
