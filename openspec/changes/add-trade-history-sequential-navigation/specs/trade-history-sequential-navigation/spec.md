## ADDED Requirements

### Requirement: History page provides sequential navigation controls
The system SHALL provide `上一笔` and `下一笔` controls in the right-panel historical trade review page.

#### Scenario: Controls appear in history page
- **WHEN** the user opens the `历史交易` tab
- **THEN** the historical trade page shows `上一笔` and `下一笔` controls
- **AND** it shows a current-position readout in `当前 / 总数` form

### Requirement: Navigation follows visible trade order
The system SHALL navigate previous and next trades according to the currently visible historical trade list order.

#### Scenario: Move to next visible trade
- **WHEN** a historical trade is selected and the user clicks `下一笔`
- **THEN** the next visible trade card becomes selected
- **AND** the position readout advances by one

#### Scenario: Move to previous visible trade
- **WHEN** a historical trade is selected and the user clicks `上一笔`
- **THEN** the previous visible trade card becomes selected
- **AND** the position readout decreases by one

### Requirement: Sequential navigation preserves focus mode
The system SHALL preserve the active entry/exit focus mode when navigating between historical trades.

#### Scenario: Next trade keeps exit focus
- **WHEN** `看出场` is active and the user clicks `下一笔`
- **THEN** the next selected trade focuses its exit view on the chart
- **AND** `看出场` remains active

#### Scenario: Previous trade keeps entry focus
- **WHEN** `看入场` is active and the user clicks `上一笔`
- **THEN** the previous selected trade focuses its entry view on the chart
- **AND** `看入场` remains active

### Requirement: Sequential navigation handles boundaries and empty state
The system SHALL disable sequential navigation controls when movement is not possible.

#### Scenario: First trade disables previous
- **WHEN** the first visible historical trade is selected
- **THEN** `上一笔` is disabled
- **AND** `下一笔` is enabled if more visible trades exist

#### Scenario: Last trade disables next
- **WHEN** the last visible historical trade is selected
- **THEN** `下一笔` is disabled
- **AND** `上一笔` is enabled if more visible trades exist

#### Scenario: No visible trades disables both controls
- **WHEN** there are no visible historical trades
- **THEN** `上一笔` and `下一笔` are disabled
- **AND** the position readout shows `0 / 0`
