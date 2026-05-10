## ADDED Requirements

### Requirement: Arrow drawing uses a six-point swept polygon
The system SHALL render `DrawingToolType.ARROW` as a filled six-point swept polygon defined from the two drawing anchors, with a sharp tail tip, a long wedge-like body, and a short heavy arrow head.

#### Scenario: Arrow body is rendered from six ordered points
- **WHEN** the user creates or loads an `ARROW` drawing with two valid anchors
- **THEN** the rendered body SHALL be built from exactly six polygon vertices
- **AND** the polygon SHALL close back to the tail tip
- **AND** the silhouette MUST include one tail tip, one arrow tip, and two head-base vertices

#### Scenario: Arrow is not rendered as a regular shaft-plus-head shape
- **WHEN** the system renders an `ARROW` drawing
- **THEN** the body SHALL visually read as a long wedge rather than a narrow shaft with a separate standard triangle head

### Requirement: Arrow silhouette matches swept-wedge proportions
The system SHALL position the six vertices so the tail remains narrow, the body expands into a pronounced shoulder near the head, and the head remains shorter than the full body length while appearing heavier than the tail.

#### Scenario: Long arrow preserves wedge silhouette
- **WHEN** the distance between the two arrow anchors is large enough for proportional rendering
- **THEN** the tail-side edges SHALL remain narrow for most of the arrow length
- **AND** the largest lateral expansion SHALL occur near the arrow head rather than near the tail
- **AND** the head section SHALL occupy a minority of the total arrow length

#### Scenario: Short arrow clamps without losing identity
- **WHEN** the distance between the two arrow anchors is short
- **THEN** the system SHALL clamp internal dimensions to avoid degenerate or self-intersecting polygons
- **AND** the result SHALL still preserve a visible tail tip and arrow tip

### Requirement: Arrow geometry remains consistent across rendering modes
The system SHALL use the same swept-arrow polygon model for preview rendering, persisted drawing rendering, hover/selection body handling, and toolbar icon depiction.

#### Scenario: Preview matches final rendering
- **WHEN** the user is placing an `ARROW` drawing and the preview is shown
- **THEN** the preview silhouette SHALL match the final rendered silhouette apart from preview-specific styling such as opacity or line style

#### Scenario: Toolbar icon matches chart arrow language
- **WHEN** the application displays the `ARROW` tool icon
- **THEN** the icon SHALL depict the same swept-wedge silhouette used by the chart drawing
- **AND** it MUST NOT depict the older regular symmetric arrow polygon
