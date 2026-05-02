## ADDED Requirements

### Requirement: Candlestick interaction fast path
The system SHALL prioritize candlestick viewport updates during high-frequency chart interactions before rebuilding auxiliary overlays.

#### Scenario: Pan updates primary chart first
- **WHEN** the user drags the chart horizontally
- **THEN** the candlestick X range and visible Y range update without synchronously rebuilding trade markers, order line items, or session marker items

#### Scenario: Zoom updates primary chart first
- **WHEN** the user zooms the chart with the mouse wheel
- **THEN** the candlestick X range, visible Y range, and zoom anchor behavior update before deferred overlay rebuild work runs

### Requirement: Deferred overlay convergence
The system SHALL refresh dirty auxiliary chart overlays after high-frequency interaction settles so overlays match the latest viewport.

#### Scenario: Interaction finishes
- **WHEN** pan or zoom interaction stops
- **THEN** dirty session markers, order line items, trade geometry, and trade marker items are refreshed against the latest viewport

#### Scenario: Multiple interactions coalesce
- **WHEN** several pan or zoom events occur before the deferred refresh fires
- **THEN** the system performs overlay refresh work for the latest viewport state rather than each intermediate state

### Requirement: Visible-range overlay filtering
The system SHALL constrain expensive overlay preparation to the visible chart range plus a bounded buffer when the overlay does not require full-window history.

#### Scenario: Session markers rebuild
- **WHEN** session marker overlays are rebuilt
- **THEN** marker creation considers only bars near the visible viewport and preserves correct visible session labels and end markers

#### Scenario: Trade markers rebuild
- **WHEN** trade marker overlays are rebuilt during normal chart viewing
- **THEN** marker item creation is based on trade geometry relevant to the visible viewport plus buffer

### Requirement: Layer-specific invalidation
The chart SHALL track invalidation independently for primary chart data, session markers, order lines, trade geometry, trade marker items, drawings, and hover or preview overlays.

#### Scenario: Display toggle changes one layer
- **WHEN** the user toggles trade markers, trade links, bar count labels, or drawing visibility
- **THEN** only the affected chart layer and dependent hover state are invalidated

#### Scenario: Data window changes
- **WHEN** chart window data is replaced while preserving the viewport
- **THEN** candlestick data updates immediately and auxiliary overlays are marked dirty for deferred refresh

### Requirement: Chart calculations remain bounded
The system SHALL provide bounded or cached calculations for high-frequency visible-range operations when datasets grow beyond the current loaded window size.

#### Scenario: Y range calculation
- **WHEN** the visible chart range changes repeatedly
- **THEN** high/low calculation uses a bounded visible-range scan or cache rather than scanning unrelated bars

#### Scenario: Indicator calculation
- **WHEN** cursor or window data changes
- **THEN** indicator updates avoid recomputing unchanged historical values when an incremental or cached value is available
