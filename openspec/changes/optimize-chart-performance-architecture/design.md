## Context

BarByBar is a Python/PySide6 desktop replay application centered on a pyqtgraph candlestick chart. The current UI works, but chart interactions share the main thread with viewport range updates, overlay rebuilds, repository-backed window extension, session state updates, async save coordination, settings sync, and diagnostics/logging. Recent optimization already started separating the candlestick fast path from auxiliary overlay refreshes and moved backward viewport extension to a worker. This change formalizes that direction into a staged architecture.

The main stakeholders are active replay users who need panning, zooming, stepping, drawing, and trade review to feel immediate, and maintainers who need clearer boundaries before adding more chart tools, diagnostics, and performance-sensitive features.

## Goals / Non-Goals

**Goals:**

- Keep candlestick panning and zooming responsive even when overlays, drawings, trade markers, or data-window work are expensive.
- Establish explicit chart layers with independent dirty state, visible-range filtering, and refresh timing.
- Centralize worker lifecycle handling so async tasks apply only current results and clean up consistently.
- Reduce `MainWindow` responsibilities by extracting chart, session, settings, and async coordination over time.
- Add measurable diagnostics for chart rendering, overlay rebuilds, data-window loading, and high-frequency workflows.
- Improve interface efficiency by ensuring common display toggles and review actions update only the affected UI layer.

**Non-Goals:**

- No database schema migration is required for the first implementation pass.
- No change to replay trading semantics, order execution rules, drawing behavior, or persisted session data.
- No requirement to move Qt item creation off the UI thread; only pure data preparation and repository work should move to workers.
- No broad visual redesign is required as part of this architecture change.

## Decisions

1. Prioritize a chart fast path over full synchronous visual completeness.

   Panning and zooming will update the candlestick view, X range, Y range, and essential cursor state immediately. Session markers, order labels, trade markers, trade links, and other auxiliary overlays can be marked dirty and refreshed after interaction settles. This preserves perceived responsiveness while keeping visual correctness after the short deferred refresh.

   Alternative considered: rebuild every overlay during every viewport change. That keeps all visuals synchronous, but it makes the highest-frequency path pay for work users are not primarily looking at while dragging or scrolling.

2. Use layer-local dirty state and visible-range filtering.

   Chart layers will own their own invalidation state. Overlay rebuilds must use the visible x-range plus a small buffer whenever possible, instead of scanning the full loaded window or all historical actions.

   Alternative considered: keep one global viewport refresh path. That is simpler, but it hides the cost of each layer and makes it difficult to optimize one layer without affecting all others.

3. Centralize async task coordination with latest-result semantics.

   Session load, viewport window extension, async save, import, and future expensive chart preparation should share a small coordination pattern: request token, worker ownership, stale result discard, failure reporting, cleanup, and optional latest-pending coalescing.

   Alternative considered: continue adding one-off workers per feature. That is quick for individual fixes, but it spreads lifecycle bugs and makes stale result behavior inconsistent.

4. Extract controllers incrementally rather than rewriting the main window.

   `MainWindow` should gradually become a UI shell. `ChartController` should own chart data-window and viewport coordination, `SessionController` should own replay state transitions, `SettingsController` should own persistent UI preferences, and an async coordinator should own worker lifecycle. Extraction should preserve existing tests and behavior at each step.

   Alternative considered: perform a full upfront rewrite. That would create a large regression surface in a tool where interaction details matter.

5. Add diagnostics before deeper data-structure optimization.

   Instrumentation should be added before chunked candlestick caches, high/low range caches, or hover indexes are heavily refactored. The diagnostics will confirm which hot paths deserve deeper work and provide regression signals afterward.

   Alternative considered: optimize suspected hotspots first. Some hotspots are known, but diagnostics reduce guesswork and help validate results on real sessions.

## Risks / Trade-offs

- Overlay refresh latency could make trade markers or labels appear to lag behind during interaction → Keep deferred delays short, flush immediately when interaction ends, and test that overlays converge to the current viewport.
- Async task coordination could discard useful work if token rules are too aggressive → Use latest-result semantics only for stateful UI tasks where older results are invalid by definition.
- Controller extraction could temporarily increase indirection → Move one responsibility at a time and keep old public behavior covered by tests.
- Diagnostics could add overhead to hot paths → Use lightweight timers, aggregate small rolling windows, and avoid expensive formatting in high-frequency paths.
- Visible-range filtering could hide context-dependent overlays if a layer depends on offscreen history → Define per-layer buffer rules and keep trade state reconstruction conservative where needed.

## Migration Plan

- Phase 1: Add diagnostics and performance baseline tests around chart interaction, overlay rebuilds, window loading, stepping, and common display toggles.
- Phase 2: Complete chart layer separation and visible-range filtering for overlays, while preserving existing user-visible behavior after deferred refresh.
- Phase 3: Introduce shared async task coordination and migrate viewport extension, session load, async save, and import flows.
- Phase 4: Extract chart/session/settings responsibilities from `MainWindow` into controllers with focused tests.
- Phase 5: Add deeper chart data optimizations such as high/low caches, candlestick chunk caches, incremental indicators, and hover indexes.
- Phase 6: Refine interface efficiency so common toggles and review actions affect only their target layer and remain non-blocking.
- Phase 7: Add long-term regression coverage and release smoke checks for performance-sensitive workflows.

Rollback for each phase should be local: disable the new controller or cache path behind the existing synchronous behavior, keep file-by-file changes small, and preserve current tests until replacement tests are in place.

## Open Questions

- What target interaction latency should become the user-facing performance budget for panning and zooming on representative datasets?
- Should the diagnostics panel be always available under settings/logs, or gated behind a developer setting?
- Which chart indicators beyond EMA are expected soon enough to influence the layer abstraction now?
