## 1. Cursor State Mapping

- [x] 1.1 Refactor drawing-related cursor mapping in `ChartWidget._sync_cursor()` so anchor hover and drawing-body hover no longer share the same cursor.
- [x] 1.2 Differentiate anchor dragging from whole-drawing dragging in cursor synchronization.
- [x] 1.3 Keep active drawing placement on a stable `CrossCursor`.

## 2. Directional Feedback

- [x] 2.1 Identify drawing edits with clear vertical-only constraints and map them to a vertical resize cursor.
- [x] 2.2 Identify drawing edits with clear horizontal-only constraints and map them to a horizontal resize cursor.
- [x] 2.3 Preserve existing order-line and trade-link cursor behaviors unless a higher-priority drawing state is active.

## 3. Regression Coverage

- [x] 3.1 Add tests for drawing placement cursor behavior before and after the first anchor is placed.
- [x] 3.2 Add tests that distinguish anchor hover, drawing-body hover, anchor drag, and body drag cursor states.
- [x] 3.3 Add tests that verify constrained drawing edits use directional cursors without regressing existing non-drawing cursor behavior.
