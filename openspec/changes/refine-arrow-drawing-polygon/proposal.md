## Why

The current `ARROW` drawing renders as a regular, symmetric filled arrow polygon. It does not match the user's expected visual language from the provided reference, where arrows read as long swept wedges with a very sharp tail, a single major shoulder expansion, and a short heavy arrow head.

## What Changes

- Redefine the existing `ARROW` drawing geometry as a six-point swept polygon instead of the current regular filled arrow shape.
- Keep the existing `DrawingToolType.ARROW` tool, persistence path, and two-anchor interaction model unchanged.
- Update the chart rendering path so preview, hover, hit testing, and persisted arrow drawings all use the same swept-arrow polygon.
- Update the toolbar icon for `ARROW` so it reflects the new in-chart shape language.
- Add regression tests for arrow polygon point generation, rendering integration, and icon/preview consistency.

## Capabilities

### New Capabilities
- `arrow-drawing-polygon`: Defines the required visual geometry and rendering behavior for the existing filled arrow drawing tool.

### Modified Capabilities

## Impact

- Affects arrow geometry generation and drawing rendering in `src/barbybar/ui/chart_widget.py`.
- Affects toolbar icon rendering for the arrow tool in `src/barbybar/ui/main_window.py`.
- May require small style-normalization adjustments in `src/barbybar/domain/models.py` if arrow-specific geometry defaults are introduced.
- Adds regression coverage in `tests/test_chart_widget.py` and potentially `tests/test_main_window.py`.
