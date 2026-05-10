## Why

The current arrow workstream explored six-point swept polygons, but that shape model is not the one the user wants. The intended arrow is a simpler axis-symmetric four-point polygon: the tail tip and arrow tip lie on the main axis, and the two side points sit near the arrow head to create a short, wide head and a long, sharp tail.

## What Changes

- Redefine the existing `DrawingToolType.ARROW` geometry as a four-point polygon symmetric about the tail-tip to arrow-tip axis.
- Use a parameterized shape model equivalent to `P4=(0,0)`, `P0=(L,0)`, `P2=(kL,+w)`, `P3=(kL,-w)` after rotation into chart space.
- Keep the existing `ARROW` drawing tool, persistence format, and two-anchor interaction unchanged.
- Update chart rendering, preview rendering, hit detection, and toolbar icon rendering to use the same four-point geometry.
- Add regression tests for the four-point topology, symmetry, and short-arrow clamping behavior.

## Capabilities

### New Capabilities
- `arrow-four-point-geometry`: Defines the required four-point, axis-symmetric geometry for the existing filled arrow drawing tool.

### Modified Capabilities

## Impact

- Affects arrow polygon generation and arrow-body hit testing in `src/barbybar/ui/chart_widget.py`.
- Affects the `ARROW` toolbar icon silhouette in `src/barbybar/ui/main_window.py`.
- Adds regression coverage in `tests/test_chart_widget.py` and `tests/test_main_window.py`.
- Supersedes the earlier six-point design direction captured in `refine-arrow-drawing-polygon`.
