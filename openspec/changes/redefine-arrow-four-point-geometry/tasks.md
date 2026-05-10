## 1. Geometry Redefinition

- [x] 1.1 Replace the current `ARROW` polygon generator with the four-point symmetric model.
- [x] 1.2 Encode the side points as near-tip control points along the anchor axis with mirrored offsets.
- [x] 1.3 Add clamps so short arrows keep a valid four-point topology and remain axis-symmetric.

## 2. Rendering Consistency

- [x] 2.1 Update arrow preview rendering and persisted drawing rendering to use the same four-point polygon.
- [x] 2.2 Update arrow body hit detection to evaluate the new four-point polygon instead of the superseded six-point shape.
- [x] 2.3 Update the `ARROW` toolbar icon silhouette to match the four-point geometry.

## 3. Regression Coverage

- [x] 3.1 Add chart-widget tests that assert the arrow polygon has exactly four points and preserves mirror symmetry.
- [x] 3.2 Add tests that assert the side points sit nearer the arrow tip than the tail in normalized geometry.
- [x] 3.3 Add tests for short-arrow clamping and an icon-facing regression check for the updated silhouette.
