## Context

BarByBar already supports the core training loop: data import, session creation, bar replay, direct trades, line/order tools, chart drawing, trade history, notes, settings, logs, updates, and persisted review records. The functional surface is large enough for a major release, but the current interface reads as a set of accumulated Qt controls rather than a designed trading-review workstation.

This change treats the next major version as a UI and interaction redesign. The product direction is a professional desktop review terminal: calm, high-density, chart-first, fast to operate, and visually coherent. The redesign must preserve existing training behavior while reorganizing and restyling the surfaces users touch every day.

Current working model:

```text
Current feel:
feature controls + chart + side widgets + utility dialogs

Target feel:
professional training workbench with chart-first workflow
```

Target shell:

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ App Header: brand, current case, save/status, workspace actions            │
├────────────────────────────────────────────────────────────────────────────┤
│ Training Toolbar: timeframe, replay, chart tools, order/drawing state      │
├─────────────────────────────────────────────────────────────┬──────────────┤
│                                                             │ Position     │
│                                                             │ Quick Trade  │
│                         Chart Workspace                     │ Line Tools   │
│                                                             │ Stats        │
│                                                             │ Review       │
├─────────────────────────────────────────────────────────────┴──────────────┤
│ Status Bar: current bar/timeframe/data source/save feedback/context hints  │
└────────────────────────────────────────────────────────────────────────────┘
```

## Goals / Non-Goals

**Goals:**

- Make BarByBar look and feel like a professional trading review product, not a default Qt utility.
- Redesign the information architecture around the training loop: prepare, replay, trade, annotate, review, and continue.
- Keep the chart as the dominant surface and reduce visual competition around it.
- Separate low-frequency application management from high-frequency training actions.
- Turn the right sidebar into a training state center rather than a mixed control stack.
- Turn trade history into a review center with a strong scanning/detail/editing workflow.
- Establish a reusable desktop visual system for all workbench surfaces and dialogs.
- Define screenshot and manual smoke acceptance criteria for visual quality.
- Preserve existing data, persistence, trading calculations, order semantics, chart aggregation, and user workflows.

**Non-Goals:**

- Do not add new training concepts such as AI coaching, strategy scoring, new analytics, or reporting dashboards.
- Do not introduce a web frontend, external UI framework, or new service dependency.
- Do not change trade execution rules, order-line semantics, FIFO allocation, session persistence semantics, or database schema unless a later approved change explicitly requires it.
- Do not hide existing capabilities behind obscure menus without a discoverable replacement.
- Do not chase decorative styles such as glassmorphism, oversized marketing layouts, gradients, or one-note dark terminal aesthetics.

## Decisions

### Use a two-tier top area

The main window will separate application-level actions from training-level tools.

```text
App Header
  Brand / current session / save status / dataset / sessions / settings / logs / update

Training Toolbar
  Timeframe / replay / jump/reset / chart tools / drawing templates / active mode
```

Rationale: data/session/settings/log/update actions are important but low-frequency. Replay, timeframe, chart tools, and active mode feedback are high-frequency during training and must stay visually stable.

Alternative considered: keep one compact toolbar. This preserves space but keeps unrelated actions competing visually.

### Keep the three-zone workbench, but redesign each zone

The app will keep a top area, central chart, and right sidebar because that supports fast replay. The redesign changes hierarchy, density, state feedback, and visual language rather than moving to a multi-page shell.

Rationale: the current workflow depends on seeing the chart while trading and reviewing. A multi-page app would interrupt the training loop.

Alternative considered: create separate pages for data, training, and history. This may look cleaner but would make replay and review slower.

### Make the chart workspace visually dominant

The chart area will use restrained surrounding chrome, subdued axes/labels, controlled overlay opacity, and a clear active-mode hint layer. Trade markers, links, drawing handles, order previews, measurement labels, and bar labels must be readable without overpowering candles.

Rationale: this is a trading review tool; the chart is the work surface, not a preview card inside an app.

Alternative considered: put the chart inside a stronger card frame. This makes layout easier but visually shrinks the primary workspace.

### Rebuild the right sidebar as a training state center

The right sidebar will be organized into stable sections:

```text
Position Snapshot
Quick Trade
Line / Order Tools
Session Stats
Review / Display / Session Utilities
```

Each section must have a clear priority, stable dimensions, and state-specific feedback. Direct trading actions are primary. Line/order tools are secondary. Display/session utilities are tertiary.

Rationale: the current sidebar mixes high-frequency, low-frequency, and status information, which makes it hard to scan.

Alternative considered: use tabs for every section. This reduces vertical density but hides important training state.

### Redesign trade history as a review center

Trade history will use a list/detail model:

```text
┌─────────────────────┬────────────────────────────────────────────┐
│ Trade List           │ Trade Detail                               │
│ #12 Long +580        │ Entry / Exit / PnL / Holding bars          │
│ #11 Short -240       │ Entry thought / Review summary             │
│ #10 Long +120        │ Entry focus / Exit focus / chart actions   │
└─────────────────────┴────────────────────────────────────────────┘
```

The sidebar version remains compact. The full dialog becomes a serious review workspace with filters, sorting, detail, note editing, focus controls, and empty states.

Rationale: the existing trade data is valuable, but the interface should help users understand and review decisions, not just inspect rows.

Alternative considered: keep a table-first dialog. Tables are good for dense sorting, but poor for reflective review and note editing.

### Build a real desktop visual system

The redesign will extend the existing Qt theme layer with explicit component roles:

- Shell: app background, header, toolbar, chart canvas, sidebar, status bar.
- Surfaces: panel, section, card, dialog, input, table, popover.
- Text: title, section title, body, secondary, muted, numeric, warning, error.
- Actions: primary, secondary, quiet, danger, long, short, toggle, selected, disabled.
- States: hover, pressed, focus, checked, active mode, loading, empty, success, warning, error.

Rationale: one-off styles will recreate the current inconsistency.

Alternative considered: use ad hoc styles per widget. Faster initially, but harder to make the app feel like one product.

### Prefer restrained professional light mode first

The primary redesign target is a professional light-mode desktop trading UI with controlled contrast, warm-neutral chart background, dark text, blue focus/primary accents, and clear long/short colors. Dark mode can be prepared by token structure but does not need to ship in this change unless already trivial.

Rationale: BarByBar currently works in a light Qt environment, and the priority is a polished default experience.

Alternative considered: switch to a dark trading-terminal theme. That may look more dramatic, but it is a larger accessibility and chart-color migration problem.

### Validate visually, not only structurally

Existing Qt tests will continue to verify behavior and state. This change also needs screenshot/manual smoke acceptance:

- Standard desktop width.
- Narrow but supported desktop width.
- Empty startup.
- Active session with trades.
- Active drawing/order-preview mode.
- Trade history sidebar and full dialog.
- Settings/data/session/log/update/error dialogs.

Rationale: a UI redesign can pass unit tests while still looking bad.

Alternative considered: rely only on widget state tests. That misses spacing, hierarchy, overlap, and visual quality.

## Risks / Trade-offs

- Visual redesign becomes subjective -> Define concrete acceptance criteria: hierarchy, alignment, text fit, state clarity, no overlap, chart dominance, and screenshot review.
- Broad UI change regresses behavior -> Keep trading/domain code out of scope and run full regression tests after each implementation pass.
- Sidebar redesign hides existing controls -> Inventory current actions before redesign and map each old action to a new visible or discoverable location.
- Qt styling limitations slow polish -> Work within reusable theme helpers, object names, and small custom widgets instead of fighting every native control individually.
- Screenshot tests may be brittle -> Use screenshots for manual/approval review and structural tests for automated regression, not pixel-perfect assertions.
- Offscreen font rendering can mislead review -> Use real packaged-app screenshots for final release acceptance.
- Large tasks can drift back into polish -> Split implementation into fine-grained workbench, visual system, chart, sidebar, trade-history, dialogs, and validation passes.
