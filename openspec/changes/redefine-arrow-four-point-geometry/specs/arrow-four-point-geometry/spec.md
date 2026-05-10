## ADDED Requirements

### Requirement: Arrow drawing uses a four-point symmetric polygon
The system SHALL render `DrawingToolType.ARROW` as a filled four-point polygon symmetric about the axis from the tail tip to the arrow tip.

#### Scenario: Arrow body uses four ordered points
- **WHEN** the system creates or renders an `ARROW` drawing from two valid anchors
- **THEN** the polygon SHALL contain exactly four vertices
- **AND** the polygon outline SHALL follow tail tip -> upper side point -> arrow tip -> lower side point -> tail tip

#### Scenario: Arrow remains symmetric about the main axis
- **WHEN** the system constructs the `ARROW` polygon
- **THEN** the upper and lower side points SHALL be mirrored about the tail-tip to arrow-tip axis

### Requirement: Arrow head is short and the tail is long
The system SHALL place the side points closer to the arrow tip than to the tail tip so the rendered shape reads as a short head attached to a long narrow tail.

#### Scenario: User-normalized geometry
- **WHEN** the arrow is described in normalized local coordinates
- **THEN** the geometry SHALL be representable by a form equivalent to `tail=(0,0)`, `tip=(L,0)`, `upper=(kL,+w)`, `lower=(kL,-w)`
- **AND** `k` MUST be greater than `0.5`

#### Scenario: Side points do not collapse into a centered diamond
- **WHEN** the system renders an `ARROW` drawing
- **THEN** the maximum width SHALL occur closer to the arrow tip than to the midpoint of the full arrow length

### Requirement: Arrow geometry is shared across rendering modes
The system SHALL use the same four-point geometry for chart rendering, preview rendering, body hit detection, and toolbar icon rendering.

#### Scenario: Preview matches final arrow outline
- **WHEN** the user previews an `ARROW` drawing before the second anchor is committed
- **THEN** the preview outline SHALL match the final four-point geometry apart from preview styling

#### Scenario: Toolbar icon advertises the same shape
- **WHEN** the application displays the `ARROW` drawing tool icon
- **THEN** the icon SHALL depict the same four-point, long-tail short-head silhouette used on the chart

### Requirement: Short arrows clamp without losing topology
The system SHALL clamp internal dimensions for short arrows while preserving a valid four-point polygon and axis symmetry.

#### Scenario: Short anchor distance remains valid
- **WHEN** the two arrow anchors are very close together
- **THEN** the polygon SHALL remain non-degenerate
- **AND** the four-point ordering and symmetry SHALL still hold
