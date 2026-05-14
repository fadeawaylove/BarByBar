## Context

BarByBar already supports the core review loop and has an in-progress professional workbench redesign. The remaining UX problem is that the interface can still feel like many available controls competing for attention. This design treats the next pass as a workflow reframing: make the chart the main surface, make the user's current mode explicit, and arrange controls by review intent rather than by implementation category.

Current mental model:

```text
tools + chart + side panels + dialogs
```

Target mental model:

```text
review case -> active mode -> chart action -> state feedback -> trade review
```

The change is UI/UX-only. It must preserve engine behavior, order-line semantics, persistence, chart aggregation, CSV import, update checks, and release workflow.

## Goals / Non-Goals

**Goals:**

- Define a mode model that makes Replay, Plan, Annotate, and Review feel distinct without fragmenting the app into separate pages.
- Make the chart the visual and interaction center for all active-session work.
- Make the right panel behave like a stable state center whose emphasis adapts to mode.
- Turn trade history into a reflective review workflow, not just a table or utility panel.
- Establish a cooler, sharper professional light visual direction that reduces softness and surface noise.
- Produce low-fidelity structure and acceptance criteria before implementation.

**Non-Goals:**

- Do not add AI coaching, strategy scoring, new analytics, or broker connectivity.
- Do not introduce a web frontend, new UI framework, or external dependency.
- Do not change trade calculations, order triggers, FIFO allocation, session persistence, or database schema.
- Do not remove existing capabilities unless they are remapped to an equally discoverable location.
- Do not switch the product to a dark-only trading terminal.

## Decisions

### Use four explicit work modes

The workbench will expose four mode families:

```text
Replay    step through bars, use shortcuts, monitor state
Plan      place and adjust entry/exit/stop/take-profit/reverse lines
Annotate  draw, measure, write chart context
Review    inspect completed trades, focus entry/exit, edit notes
```

Rationale: The user should always know what clicking or dragging the chart will do. Existing interactions already imply these modes; naming them turns hidden state into visible state.

Alternative considered: Keep one generic browse mode plus transient tool toggles. This preserves the current model but keeps users guessing when tools are active.

### Keep one workbench, not separate pages

The main shell remains one integrated desktop workspace:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Case Header: current session, dataset, save state, app actions        │
├──────────────────────────────────────────────────────────────────────┤
│ Mode Toolbar: mode tabs, timeframe, replay, active tool, cancel       │
├──────────────────────────────────────────────────────┬───────────────┤
│                                                      │ State Center  │
│                                                      │ mode-aware    │
│                    Chart Workspace                   │ sections      │
│                                                      │               │
├──────────────────────────────────────────────────────┴───────────────┤
│ Feedback Bar: current bar, time, progress, hints, save/worker status  │
└──────────────────────────────────────────────────────────────────────┘
```

Rationale: Splitting into pages would interrupt the trading review loop. The user needs chart, position, actions, and review context visible together.

Alternative considered: Data page, training page, review page. This may look cleaner but slows the core bar-by-bar workflow.

### Make the right state center stable but mode-aware

The right panel keeps a stable top section for current position and emergency trade state. Below that, the active mode changes section priority:

```text
Always visible:
  Position Snapshot
  Primary Trade Actions

Replay emphasis:
  Progress, current bar, quick notes, display toggles

Plan emphasis:
  Order line tools, quantity/price inputs, active preview

Annotate emphasis:
  Drawing tools, templates, style controls

Review emphasis:
  Trade cards, entry/exit focus, note summary
```

Rationale: Primary trading state must not disappear, but the rest of the panel should help the task the user is actually doing.

Alternative considered: Full tabs for every area. Tabs save space but hide state and create more mode switching.

### Treat trade history as a review workspace

The compact sidebar uses cards for scanning. The full dialog uses a list/detail layout:

```text
┌──────────────────────┬──────────────────────────────────────────────┐
│ Trade List            │ Trade Detail                                 │
│ #12 Long +580         │ Summary / entry / exit / risk context         │
│ #11 Short -240        │ Entry thought editor                          │
│ #10 Long +120         │ Review summary editor                         │
│ filters + sort        │ Focus entry / focus exit / chart feedback     │
└──────────────────────┴──────────────────────────────────────────────┘
```

Rationale: Trade review is reflective work. A table remains useful for sorting, but the primary object should be a decision and its outcome.

Alternative considered: Keep table-first. Tables are dense but weak for note writing and understanding decision context.

### Use a sharper professional light visual direction

The next visual pass should shift from warm, soft panels toward a cooler, clearer review terminal:

- Backgrounds: cool gray and near-white surfaces, less beige.
- Chart: quiet light canvas with high candle legibility.
- Primary: deep steel blue for focus, selection, and current mode.
- Action colors: consistent long/short/close/reverse tokens across buttons, lines, cards, and chart markers.
- Geometry: tighter 4-8px radii for toolbars, controls, lists, and cards.
- Typography: tighter numeric hierarchy, tabular numbers where practical, smaller section labels, stronger PnL contrast.
- Density: fewer nested cards, more dividers and bands, stable control dimensions.

Rationale: BarByBar is a daily-use financial review tool. It should feel calm, durable, and precise rather than decorative.

Alternative considered: Dark terminal theme. It is visually dramatic but a larger chart, accessibility, and settings migration.

### Design before code

Implementation should start with structural sketches and a mode/action inventory, then proceed through UI changes. The first deliverable should be reviewable without touching engine or storage behavior.

Rationale: The user is dissatisfied with the feel of the product. Coding immediately risks producing another technically correct but experientially unsatisfying iteration.

Alternative considered: Continue incremental polish. This has already improved the app but does not fully address the attention-flow issue.

## Risks / Trade-offs

- Mode model feels heavier than current controls -> Keep mode switching visible, keyboard-friendly, and compatible with existing shortcuts.
- Right panel becomes too dynamic -> Keep position and primary actions stable; only reorder secondary emphasis by mode.
- Visual direction regresses readability -> Validate screenshots for active session, drawing, order preview, and review states before implementation is considered complete.
- Existing tests assume current widget hierarchy -> Update UI tests around behavior and named roles rather than brittle layout internals.
- Users may miss moved controls -> Produce an old-to-new control map and keep low-frequency actions reachable from header or overflow menus.
- New UX overlaps with `redesign-professional-review-workbench` -> Treat this as a second-stage refinement that builds on the existing professional shell instead of replacing its completed work wholesale.

## Migration Plan

1. Capture the existing visible controls and classify them by mode.
2. Create low-fidelity structure sketches for the main workbench, each mode state, right panel, compact trade cards, and full review dialog.
3. Update theme tokens and component roles to support the sharper light-terminal direction.
4. Implement shell and mode state without changing engine or repository behavior.
5. Implement right-panel mode emphasis while preserving primary position/trade controls.
6. Implement trade review card/list/detail improvements while preserving persistence semantics.
7. Run focused UI tests, then screenshot/manual smoke validation.

Rollback is straightforward at the git level because no database migration or domain behavior change is expected.

## Open Questions

- Should Replay, Plan, Annotate, and Review be top-level segmented mode buttons, or should Replay remain implicit with Plan/Annotate/Review as overlays?
- Should the right panel physically reorder sections by mode, or keep section order fixed while changing expansion and emphasis?
- Should the full trade review center remain a dialog, become a docked panel, or support both?
- Should the visual direction include an optional dark theme later, or remain light-only until the core UX is settled?
