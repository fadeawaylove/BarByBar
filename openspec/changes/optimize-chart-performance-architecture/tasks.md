## 1. Performance Baseline and Diagnostics

- [x] 1.1 Add a lightweight timing utility for chart, overlay, data-window, and workflow measurements.
- [x] 1.2 Instrument viewport apply, Y range calculation, candlestick rebuild, overlay refresh, and chart window loading with bounded context fields.
- [x] 1.3 Add rolling in-memory metric storage that avoids unbounded growth and expensive formatting in hot paths.
- [x] 1.4 Extend the existing logs or diagnostics UI to show recent chart interaction and data-window metrics.
- [x] 1.5 Add baseline regression tests for repeated pan, zoom, step forward, step back, and backward window extension workflows.

## 2. Chart Layer Invalidation and Refresh

- [x] 2.1 Define explicit dirty state for candlestick data, indicators, session markers, order lines, trade geometry, trade marker items, drawings, and hover or preview overlays.
- [x] 2.2 Ensure pan and zoom update only the primary chart fast path before scheduling deferred overlay work.
- [x] 2.3 Coalesce deferred overlay refreshes so only the latest viewport state is rebuilt after interaction settles.
- [x] 2.4 Scope display toggles so trade markers, trade links, bar count labels, and drawing visibility invalidate only affected layers.
- [x] 2.5 Add tests that heavy overlay rebuilds are not executed for every intermediate pan or zoom event.

## 3. Visible-Range Chart Optimizations

- [x] 3.1 Constrain session marker rebuilds to the visible viewport plus a bounded buffer while preserving visible labels and end markers.
- [x] 3.2 Constrain trade marker and link preparation to visible or near-visible actions where full-history reconstruction is not required.
- [x] 3.3 Update order line handling so horizontal viewport changes relayout labels without rebuilding line items when line data is unchanged.
- [x] 3.4 Add a bounded high/low query path or cache for repeated visible Y range calculation.
- [x] 3.5 Add tests for visible-range correctness in blank space, right padding, zoomed views, and large loaded windows.

## 4. Background Task Coordination

- [x] 4.1 Create a shared async task coordinator for request tokens, worker ownership, stale-result discard, failure logging, cleanup, and bounded shutdown.
- [x] 4.2 Migrate backward viewport window extension to the shared coordinator with latest-pending request coalescing.
- [x] 4.3 Migrate session loading to the shared coordinator while preserving stale load discard behavior.
- [ ] 4.4 Migrate async session saving and batch import lifecycle handling where the shared coordinator fits the workflow.
- [x] 4.5 Add tests for stale result discard, worker failure cleanup, close-event shutdown, and latest-pending request behavior.

## 5. Main Window Responsibility Extraction

- [ ] 5.1 Extract chart data-window and viewport coordination into a chart controller or equivalent module.
- [ ] 5.2 Extract replay step, jump, session state transition, and save scheduling into a session controller or equivalent module.
- [ ] 5.3 Extract UI settings persistence and application into a settings controller or equivalent module.
- [ ] 5.4 Update `MainWindow` to act primarily as UI composition and signal wiring for the extracted controllers.
- [ ] 5.5 Add focused controller tests while keeping existing main window regression tests passing.

## 6. Deeper Chart Data Performance

- [ ] 6.1 Add chunked or cached candlestick picture rebuilding so window updates avoid unnecessary full-window redraw work.
- [ ] 6.2 Add incremental or cached EMA and indicator updates for cursor and window changes.
- [ ] 6.3 Add x-range prefiltering or a lightweight spatial index for hover hit testing of drawings, trade markers, and trade links.
- [ ] 6.4 Verify large sessions with many actions and drawings remain responsive during repeated pan and zoom workflows.

## 7. Interface Efficiency and Release Guardrails

- [ ] 7.1 Review common replay workflows and ensure frequent controls update without blocking chart interaction.
- [ ] 7.2 Make display settings and chart toggles affect only the intended chart layer.
- [x] 7.3 Add a release smoke checklist covering import, open session, step forward, step back, zoom, backward window extension, save, and reopen.
- [x] 7.4 Document performance budgets and diagnostics interpretation for future maintenance.
