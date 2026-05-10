## Why

The chart already supports drawing creation, anchor editing, and whole-shape dragging, but the cursor feedback is too coarse. Different interaction intents such as "edit a control point", "move the whole drawing", and "continue placing a drawing" currently feel too similar, which makes the interaction less legible than it should be.

## What Changes

- Refine drawing-related cursor states so anchor editing, drawing-body movement, and drawing placement communicate different meanings.
- Keep `CrossCursor` for active drawing placement, but distinguish anchor hover/drag from drawing-body hover/drag.
- Add directional cursor feedback where the dragged geometry is constrained, especially for horizontal and vertical line editing.
- Preserve existing drawing behavior, hit testing, and persistence; this change affects interaction feedback, not drawing data or geometry.
- Add regression tests for cursor transitions across hover, drag, and drawing-placement states.

## Capabilities

### New Capabilities
- `drawing-cursor-feedback`: Defines the cursor and interaction-state feedback rules for drawing placement, anchor editing, and whole-drawing dragging on the chart.

### Modified Capabilities

## Impact

- Affects interaction state handling and cursor synchronization in `src/barbybar/ui/chart_widget.py`.
- May add small helper logic for mapping hover/drag states to cursor shapes.
- Adds regression coverage in `tests/test_chart_widget.py`.
