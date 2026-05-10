## ADDED Requirements

### Requirement: Drawing placement uses a stable placement cursor
The system SHALL use a stable drawing-placement cursor while the user is actively placing a new drawing.

#### Scenario: Drawing tool is active
- **WHEN** a drawing tool is active and the chart is in drawing placement mode
- **THEN** the cursor SHALL be `CrossCursor`

#### Scenario: First anchor already placed
- **WHEN** the user has already placed the first anchor of a multi-anchor drawing and is positioning the next anchor
- **THEN** the cursor SHALL remain `CrossCursor`

### Requirement: Editable anchors and drawing bodies use different hover cursors
The system SHALL distinguish anchor-edit hover from whole-drawing movement hover.

#### Scenario: Hover editable anchor
- **WHEN** the pointer is over an editable drawing anchor
- **THEN** the cursor SHALL indicate point editing rather than whole-object movement

#### Scenario: Hover movable drawing body
- **WHEN** the pointer is over a movable drawing body
- **THEN** the cursor SHALL indicate whole-object movement rather than point editing

### Requirement: Dragging feedback reflects the drag intent
The system SHALL use different cursor feedback for anchor dragging and whole-drawing dragging.

#### Scenario: Drag drawing body
- **WHEN** the user is dragging a drawing body to translate the whole drawing
- **THEN** the cursor SHALL indicate active object grabbing

#### Scenario: Drag drawing anchor
- **WHEN** the user is dragging a drawing anchor
- **THEN** the cursor SHALL indicate anchor editing rather than whole-object grabbing

### Requirement: Constrained drawing edits use directional cursors where appropriate
The system SHALL use directional cursor feedback for clearly constrained drawing edits.

#### Scenario: Vertical-only adjustment
- **WHEN** the current drawing edit is constrained to vertical movement
- **THEN** the cursor SHALL use the corresponding vertical resize cursor

#### Scenario: Horizontal-only adjustment
- **WHEN** the current drawing edit is constrained to horizontal movement
- **THEN** the cursor SHALL use the corresponding horizontal resize cursor

### Requirement: Drawing cursor changes preserve other chart interaction feedback
The system SHALL preserve existing non-drawing cursor semantics unless a drawing-specific state has higher precedence.

#### Scenario: Order-line hover remains directional
- **WHEN** the pointer is over a movable order line and no higher-priority drawing drag or placement state is active
- **THEN** the existing order-line cursor behavior SHALL remain unchanged

#### Scenario: Trade-link hover remains unchanged
- **WHEN** the pointer is over a trade link and no higher-priority drawing drag or placement state is active
- **THEN** the existing trade-link cursor behavior SHALL remain unchanged
