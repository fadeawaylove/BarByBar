## ADDED Requirements

### Requirement: Historical trade focus leaves right-side chart context
When historical trade focus moves the chart to a selected trade entry or exit bar, the system SHALL position the target bar inside the visible viewport instead of placing it against the right price axis.

#### Scenario: Exit focus leaves future context
- **WHEN** the user selects a historical trade while the history focus mode is `exit`
- **THEN** the selected trade's exit bar SHALL be visible
- **AND** the viewport SHALL keep at least 12 bars of desired right-side context after the exit bar when chart bounds allow it
- **AND** the exit bar MUST NOT be positioned at the viewport's right edge

#### Scenario: Entry focus leaves review context
- **WHEN** the user selects a historical trade while the history focus mode is `entry`
- **THEN** the selected trade's entry bar SHALL be visible
- **AND** the viewport SHALL keep at least 12 bars of desired right-side context after the entry bar when chart bounds allow it
- **AND** the entry bar MUST NOT be positioned at the viewport's right edge

### Requirement: Historical focus uses stable target placement
The system SHALL place the active historical focus bar around 70% of the visible chart width from the left edge when the available chart bounds allow that placement.

#### Scenario: Target fits away from chart bounds
- **WHEN** the selected trade focus bar has enough bars before and after it to satisfy the review-focus viewport
- **THEN** the focus bar SHALL appear near 70% of the visible bar range from the left
- **AND** the viewport SHALL remain in non-follow-latest mode

#### Scenario: Target is near chart boundary
- **WHEN** the selected trade focus bar is too close to the beginning or end of available chart data for ideal placement
- **THEN** the viewport SHALL clamp to the available chart range
- **AND** the focus bar SHALL remain visible

### Requirement: Short trade spans can be reviewed together
When the selected trade's entry and exit bars fit comfortably within the current visible bar count, the system SHALL prefer a viewport that keeps both bars visible during historical trade focus.

#### Scenario: Entry and exit fit in current viewport
- **WHEN** a selected historical trade's entry and exit bars both fit within the current visible bar count with review margins
- **THEN** focusing either entry or exit SHALL keep both entry and exit bars visible
- **AND** the active focus bar SHALL still keep right-side breathing room when chart bounds allow it

#### Scenario: Trade span is too wide
- **WHEN** the selected historical trade's entry and exit span cannot fit comfortably within the current visible bar count
- **THEN** the system SHALL focus the active entry or exit bar using the single-bar review placement rule

### Requirement: Historical viewport focus preserves training state
The system SHALL adjust only the chart viewport for historical trade focus and MUST NOT move the replay training cursor.

#### Scenario: Focus selected historical trade
- **WHEN** the user selects a historical trade from the history panel
- **THEN** the chart viewport SHALL move to the selected trade context
- **AND** the engine's current training bar index SHALL remain unchanged
