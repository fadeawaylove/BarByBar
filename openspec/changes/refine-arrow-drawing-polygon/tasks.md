## 1. Arrow Geometry

- [x] 1.1 Replace the current `ARROW` polygon math with a six-point swept-wedge geometry in `ChartWidget`.
- [x] 1.2 Add minimum and proportional clamps so short arrows do not collapse or self-intersect.
- [x] 1.3 Ensure body rendering, preview rendering, and polygon-path creation all consume the same canonical arrow geometry.

## 2. UI Consistency

- [x] 2.1 Update the `ARROW` toolbar icon silhouette to match the new swept-arrow geometry.
- [x] 2.2 Verify hover, selection, and body hit detection still align with the rendered polygon after the geometry change.

## 3. Regression Coverage

- [x] 3.1 Add chart-widget tests that assert the arrow polygon uses six points and preserves the long-wedge silhouette.
- [x] 3.2 Add tests for short-arrow clamping to ensure the polygon stays valid for small anchor distances.
- [x] 3.3 Add icon or UI-facing tests where practical to prove the arrow tool advertises the updated silhouette.
