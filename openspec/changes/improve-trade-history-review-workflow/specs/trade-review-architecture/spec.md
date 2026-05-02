## ADDED Requirements

### Requirement: Trade review data is exposed through a testable model
The system SHALL expose trade history rows through a model that can be sorted, filtered, and queried independently from widget rendering.

#### Scenario: Model receives trade review items
- **WHEN** the model is populated with trade review items
- **THEN** the model exposes normalized row values for table display and detail rendering

#### Scenario: Model applies filters
- **WHEN** filters are applied to the model
- **THEN** the model exposes only rows matching the active filter criteria

### Requirement: Trade review selection and focus are coordinated outside the dialog widget
The system SHALL coordinate selected trade state and focus mode through a controller or equivalent application-level component rather than embedding all behavior in the dialog widget.

#### Scenario: Dialog requests focus change
- **WHEN** the dialog requests entry or exit focus
- **THEN** the controller updates focus state and delegates chart navigation through the existing chart/main-window integration

#### Scenario: Engine refresh changes available trades
- **WHEN** trade review data refreshes and the selected trade is no longer available
- **THEN** the controller clears or reassigns selection according to deterministic rules

### Requirement: Dialog code remains presentation-focused
The system SHALL keep trade history dialog code focused on layout, input controls, and binding to the model/controller.

#### Scenario: Sorting behavior is tested
- **WHEN** tests verify sorting behavior
- **THEN** they can exercise the trade history model without constructing the full dialog where feasible

#### Scenario: Chart focus behavior is tested
- **WHEN** tests verify chart focus behavior
- **THEN** they can exercise controller decisions separately from table rendering where feasible
