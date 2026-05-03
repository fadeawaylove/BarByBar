## ADDED Requirements

### Requirement: Right panel exposes training and history tabs
The system SHALL show a right-panel tab switch with exactly two top-level modes labeled `训练` and `历史交易`.

#### Scenario: Default training tab
- **WHEN** the main window is created
- **THEN** the `训练` tab is selected
- **AND** the existing training controls are visible in the right panel

#### Scenario: User switches to history tab
- **WHEN** the user selects the `历史交易` tab
- **THEN** the right panel shows historical trade review content
- **AND** the candlestick chart area keeps its current splitter width

### Requirement: Training tab preserves replay controls
The system SHALL keep the current order controls, position summary, training statistics, display toggles, and session actions in the `训练` tab.

#### Scenario: Training controls remain available
- **WHEN** the `训练` tab is selected
- **THEN** direct order controls, limit order controls, position readout, training statistics, display toggles, and session actions are visible

### Requirement: History tab provides compact trade review
The system SHALL show compact historical trade cards, selected-trade detail, entry/exit focus controls, entry thought, review summary, and save action in the `历史交易` tab.

#### Scenario: Completed trades appear as cards
- **WHEN** the current replay session has completed trades and the user selects `历史交易`
- **THEN** the right panel lists those trades as compact review cards
- **AND** selecting a card shows that trade's detail and editable notes

#### Scenario: Empty history state
- **WHEN** the current replay session has no completed trades and the user selects `历史交易`
- **THEN** the right panel shows an empty historical-trades state
- **AND** note editing controls are disabled

### Requirement: History navigation does not open a floating window
The system SHALL route historical trade entry points to the `历史交易` tab instead of opening a separate trade history window.

#### Scenario: Display history command
- **WHEN** code invokes the historical trade review entry point
- **THEN** the right panel selects `历史交易`
- **AND** no floating trade history dialog is created

#### Scenario: Full history command
- **WHEN** code invokes the full historical trade command
- **THEN** the right panel selects `历史交易`
- **AND** no floating trade history dialog is created

### Requirement: Trade selection focuses by selected trade data
The system SHALL focus chart navigation using the selected trade item's own entry and exit bar indices.

#### Scenario: Select historical trade
- **WHEN** the user selects a historical trade card
- **THEN** the chart focuses the selected trade's active entry or exit view
- **AND** the focused trade points come from that selected trade item

#### Scenario: Toggle entry and exit focus
- **WHEN** a historical trade is selected and the user switches between entry and exit focus
- **THEN** the chart navigates to the selected trade's corresponding entry or exit bar without changing the training cursor
