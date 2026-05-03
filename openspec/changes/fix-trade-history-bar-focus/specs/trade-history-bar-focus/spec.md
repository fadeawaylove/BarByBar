## ADDED Requirements

### Requirement: History trade clicks focus by trade bar indices
When a user clicks a history trade record, the system SHALL focus the chart using that clicked trade item's `entry_bar_index` or `exit_bar_index`, according to the active history focus mode.

#### Scenario: Click focuses the clicked trade exit
- **WHEN** the history sidebar is in exit focus mode and the user clicks a visible history trade record
- **THEN** the chart target SHALL be the clicked trade item's `exit_bar_index`
- **AND** the chart focus points SHALL come from the clicked trade item's entry and exit prices and bar indices

#### Scenario: Click focuses the clicked trade entry
- **WHEN** the history sidebar is in entry focus mode and the user clicks a visible history trade record
- **THEN** the chart target SHALL be the clicked trade item's `entry_bar_index`
- **AND** the clicked trade SHALL remain the selected history trade after the sidebar refreshes

### Requirement: History chart focus must not derive target bars from UI order or trade number
The system MUST NOT use the list row index, visible order position, or `trade_number` to determine which K-line bar the chart should jump to for a history trade focus action.

#### Scenario: Non-correlated trade data still focuses correctly
- **WHEN** history trades have trade numbers, visible positions, and entry/exit bar indices that do not numerically correspond
- **THEN** clicking a history trade SHALL focus the chart using only that trade item's entry or exit bar index

#### Scenario: Previous and next navigation focus the navigated trade
- **WHEN** the user moves through visible history trades with previous or next controls
- **THEN** the selected trade SHALL update according to visible history order
- **AND** the chart SHALL focus using the navigated trade item's entry or exit bar index
