## Context

BarByBar is already a full desktop review trainer: it imports data, manages sessions, replays bars, records trades, draws chart annotations, persists trade history, shows a docked history sidebar, and exposes settings, logs, updates, and performance diagnostics. Recent changes have solved many correctness and workflow issues, so the next major version should make the current product feel finished rather than broaden the product surface.

The implementation should be a cross-cutting UI/UX polish pass over existing Qt widgets and flows. It should avoid database schema changes, new trading concepts, and large architectural rewrites unless a small extraction is needed to keep UI behavior testable.

## Goals / Non-Goals

**Goals:**

- Make the main review screen visually coherent, calm, and professional.
- Improve everyday interaction clarity without adding new user workflows.
- Keep the chart as the primary workspace and make side panels support it without visual clutter.
- Standardize component spacing, colors, button states, empty states, busy states, and error states.
- Improve perceived stability for load/save, timeframe switching, chart redraw, and trade-history navigation.
- Preserve existing keyboard/mouse behavior unless current behavior is confusing or inconsistent.

**Non-Goals:**

- Do not add new analytics, coaching, strategy-tagging, reporting, or AI features.
- Do not change trading engine calculations, order semantics, trade persistence rules, or chart data aggregation.
- Do not redesign the app as a landing page or introduce decorative visual themes.
- Do not add external UI frameworks or services.
- Do not remove existing settings or workflows without replacement.

## Decisions

### Treat this as a product polish pass, not a feature release

Implementation should improve the surfaces users already touch: main toolbar, chart, right sidebar, trade history, settings, session library, dataset manager, log viewer, dialogs, and transient states. New controls are acceptable only when they clarify existing actions or expose an existing setting more ergonomically.

Alternative considered: add a new training/coaching system. That would create more product scope before the current workbench is fully polished.

### Keep the existing three-zone workbench

The preferred layout remains top toolbar, central chart, and right sidebar with training/history tabs. Polish should improve hierarchy, alignment, density, and state feedback inside this structure rather than inventing a new navigation model.

Alternative considered: move to a multi-page app shell. That risks hiding the chart and disrupting the fast replay workflow.

### Use the current Qt theme system

Polish should extend `AppTheme`, existing stylesheets, object names, and local widget classes. The design should avoid introducing a second styling system or one-off widget palettes.

Alternative considered: rewrite the interface with a new frontend technology. That is outside a stability-focused major version.

### Verify with focused UI tests and screenshots where useful

Most changes should be protected by existing `test_main_window.py`, `test_chart_widget.py`, and `test_trade_history.py` patterns. For visual regressions that are hard to assert structurally, add focused rendering checks or screenshot-based manual validation notes rather than brittle pixel-perfect tests.

## Risks / Trade-offs

- Visual polish can become subjective -> Anchor changes to concrete acceptance criteria: hierarchy, density, contrast, alignment, state feedback, and no overlap.
- Touching central UI may regress workflows -> Use focused tests for session load, step, save, timeframe switch, trade history, settings, and chart interaction.
- Reducing clutter may accidentally hide needed actions -> Preserve all existing primary actions and keep secondary actions discoverable in stable locations.
- Broad scope can sprawl -> Execute in passes: audit, theme/layout foundation, workflow polish, stability/performance cleanup, validation.
