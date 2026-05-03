## ADDED Requirements

### Requirement: Trade state is scoped to chart timeframe
The system SHALL persist and load trade actions and order lines for the active chart timeframe independently from other chart timeframes in the same session.

#### Scenario: Save trades on separate timeframes
- **WHEN** a session saves trade actions and order lines on `5m` and later saves different trade actions and order lines on `60m`
- **THEN** loading `5m` SHALL return only the `5m` trade actions and order lines
- **AND** loading `60m` SHALL return only the `60m` trade actions and order lines

#### Scenario: Saving one timeframe preserves another timeframe
- **WHEN** the session saves updated trade actions or order lines on the active chart timeframe
- **THEN** trade actions and order lines belonging to other chart timeframes in the same session MUST remain stored unchanged

### Requirement: Trading engine rebuilds from current timeframe trades only
The system SHALL rebuild position state, completed trades, statistics, and trade review items from trade actions and order lines belonging to the active chart timeframe only.

#### Scenario: Load isolated timeframe state
- **WHEN** a session with existing `5m` trades is loaded on `60m`
- **THEN** the engine SHALL NOT include the `5m` actions when rebuilding the `60m` position, statistics, completed trades, or trade review items

#### Scenario: New trading actions belong to active timeframe
- **WHEN** the user records a trade action or places an order line while the active chart timeframe is `15m`
- **THEN** the stored action or order line SHALL be associated with `15m`

### Requirement: Chart and review surfaces show current timeframe trades only
The system SHALL show chart trade markers, trade links, active order lines, historical trade review entries, and trade review notes for the active chart timeframe only.

#### Scenario: Switch to timeframe without trades
- **WHEN** the user switches from a timeframe with completed trades to a different timeframe with no completed trades
- **THEN** the chart SHALL show no trade markers or trade links from the previous timeframe
- **AND** the historical trade review surface SHALL show no completed trades from the previous timeframe

#### Scenario: Return to timeframe with trades
- **WHEN** the user returns to a timeframe that has previously saved trades and review notes
- **THEN** the chart and historical trade review surface SHALL restore that timeframe's trade markers, trade links, order lines, completed trades, and notes

### Requirement: Timeframe switching does not clone trade state
The system SHALL save the source timeframe before switching but MUST NOT copy source timeframe trade actions or order lines into the target timeframe.

#### Scenario: Switch from populated timeframe to blank timeframe
- **WHEN** the active timeframe has trades and the user switches to another supported chart timeframe with no saved trades
- **THEN** the source timeframe trades SHALL remain available when returning to the source timeframe
- **AND** the target timeframe SHALL start with no copied trade actions, order lines, position, statistics, or completed-trade history

### Requirement: Legacy trades migrate to saved chart timeframe
The system SHALL migrate legacy trade actions and order lines that do not have a chart timeframe into the related session's saved chart timeframe.

#### Scenario: Open legacy session after migration
- **WHEN** a legacy session has action and order-line rows without chart timeframe metadata
- **THEN** those rows SHALL be associated with the session's saved `chart_timeframe`
- **AND** loading that saved chart timeframe SHALL preserve the legacy trading state
