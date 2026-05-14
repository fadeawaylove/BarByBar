# Review Workflow UX Inventory

This document completes the first implementation pass for `reframe-review-workflow-ux`. It builds on the existing professional workbench redesign instead of replacing it.

## Current Control Inventory by Workflow Mode

| Current control / surface | Current location | Mode classification | Notes |
| --- | --- | --- | --- |
| Dataset manager (`数据集`) | top nav | app-level | Keep accessible in case header/workspace actions. |
| Session library (`案例库`) | top nav | app-level | Keep accessible in case header/workspace actions. |
| Settings (`设置`) | top nav | app-level | Keep accessible but quiet. |
| Log viewer (`查看日志`) | top nav/settings | diagnostic | Keep in diagnostics area or settings diagnostics. |
| Update check (`检查更新`) | top nav | diagnostic | Keep quiet; not part of active review flow. |
| Timeframe buttons | top nav | Replay | Keep compact and selected; visible during active session. |
| Previous / next bar | replay strip | Replay | Primary replay controls. |
| Jump target / reset view | replay strip | Replay | Chart navigation support. |
| Progress label / current bar | replay strip/status | Replay | Move toward status feedback and Replay state center. |
| `不过夜` | chart strip/right panel/settings | Replay | Training behavior toggle; keep visible but not primary. |
| Direct buy/sell/close/reverse buttons | right training panel | Replay | Critical primary actions; must stay stable across modes. |
| Quantity / price direct-trade inputs | right training panel | Replay | Critical context for direct actions. |
| Entry/exit/reverse line buttons | right training panel | Plan | Start order-preview workflow and switch active workflow to Plan. |
| Stop-loss / take-profit / protective line gestures | chart/right panel | Plan | Active line type, price context, confirmation, and cancel feedback needed. |
| Draw-order quantity / tick size inputs | right training panel | Plan | Plan support controls; keep secondary. |
| Drawing templates | top nav | Annotate | Keep near drawing tools; activate Annotate mode when used. |
| Drawing tool buttons | top nav | Annotate | Existing tool buttons already map cleanly to Annotate. |
| Drawing properties / style dialog | chart context/dialog | Annotate | Preserve behavior; expose selected drawing style context later. |
| Bar labels toggle | chart strip/right panel/settings | display support | Quiet display control, mostly Replay/Annotate support. |
| Hide drawings toggle | chart strip/right panel/settings | display support | Quiet display control, mostly Annotate support. |
| Trade marker/link toggles | right panel/settings | Review/display support | Quiet display control; more relevant in Review. |
| Position readout | right panel | stable state center | Always visible across all modes. |
| Training stats | right panel | Replay/Review | Replay summary and Review context. |
| Save session / mark complete | right panel | app-level/session utility | Keep available but visually below active training controls. |
| Trade history tab | right sidebar | Review | Switches state center to Review. |
| Compact trade cards | right sidebar | Review | Primary compact review surface. |
| Previous/next trade | right sidebar/dialog | Review | Review navigation. |
| Entry/exit focus controls | right sidebar/dialog | Review | Review focus mode, chart jump feedback. |
| Entry thought / review summary editors | right sidebar/dialog | Review | Preserve action-note persistence semantics. |
| Trade filters/sort/full dialog | dialog | Review | Full review workspace; keep table/filter utility but emphasize list/detail. |

## Old-to-New Control Map

| Existing area | Keep / move / demote | New UX role |
| --- | --- | --- |
| Mixed top nav | keep but reinterpret | Case header plus mode-aware toolbar. |
| Timeframe group | keep | Replay toolbar group. |
| Drawing template group | keep | Annotate toolbar group. |
| Drawing tool group | keep | Annotate toolbar group with active-mode feedback. |
| Dataset/session/settings/log/update actions | keep and demote | Case header workspace/diagnostic actions. |
| Chart widget | keep and enlarge visually | Chart-first work surface. |
| Replay strip below chart | keep, later refine | Feedback/replay control band. |
| Right `训练` tab | keep as foundation | State center with stable position/trade actions. |
| Right `历史交易` tab | keep as foundation | Review mode state center. |
| Trade history full dialog | keep as foundation | Full review workspace; evolve from table/detail to list/detail. |
| Settings/data/session/log/update dialogs | keep | Supporting product-family surfaces; no behavior change in this pass. |

## Low-Fidelity Structure Sketches

### Active Session Shell

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Case Header: session / dataset / save state        Data Session Settings   │
├────────────────────────────────────────────────────────────────────────────┤
│ Mode Toolbar: Replay Plan Annotate Review | timeframe | tool summary       │
├──────────────────────────────────────────────────────────┬─────────────────┤
│                                                          │ Position        │
│                                                          │ Primary Trade   │
│                    Chart Workspace                       │ Mode Section    │
│                                                          │ Stats / Review  │
├──────────────────────────────────────────────────────────┴─────────────────┤
│ Feedback: bar index / timestamp / timeframe / worker-save state / hint     │
└────────────────────────────────────────────────────────────────────────────┘
```

### Empty Startup

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Case Header: BarByBar                                  Data Session Settings│
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Start workspace                                                           │
│  ┌ Import CSV ┐  ┌ Open session library ┐  ┌ Dataset manager ┐             │
│                                                                            │
│  Recent sessions / last opened cases                                       │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Replay Mode

```text
Toolbar: [Replay active] timeframe | previous | next | jump | reset
Chart: revealed bars, hover readout, progress context
State center: Position -> Quick Trade -> Progress/Stats -> Display -> Utilities
```

### Plan Mode

```text
Toolbar: [Plan active] active line type | quantity | cancel
Chart: dashed order preview / draggable lines / price context
State center: Position -> Quick Trade -> Order Lines -> Plan status -> Clear/cancel
```

### Annotate Mode

```text
Toolbar: [Annotate active] drawing tools | templates | active tool | cancel
Chart: drawing preview / snap feedback / selected drawing handles
State center: Position -> Quick Trade -> Drawing tools/templates -> Style context
```

### Review Mode

```text
Toolbar: [Review active] selected trade | entry/exit focus | previous/next
Chart: selected trade marker/link emphasis
State center: Position -> Quick Trade -> Trade cards -> Notes -> Focus controls
```

## Trade Review Sketches

### Compact Trade Card

```text
┌──────────────────────────────┐
│ #12  多  +580.00      盈利   │
│ 入 09:45 -> 出 10:30 · 9 bars│
│ 止盈 / 有止损 / 已写复盘     │
└──────────────────────────────┘
```

States: default, hover, selected, selected-entry-focus, selected-exit-focus, filtered-out empty, no-trade empty.

### Full Review Workspace

```text
┌────────────────────────────┬─────────────────────────────────────────────┐
│ Filters / Sort              │ Selected Trade Summary                      │
│ ┌ #12 Long +580 ┐           │ Entry detail / Exit detail / PnL / duration │
│ ┌ #11 Short -240┐           │ Entry thought editor                        │
│ ┌ #10 Long +120 ┐           │ Review summary editor                       │
│                            │ Focus entry | Focus exit | Save status       │
└────────────────────────────┴─────────────────────────────────────────────┘
```

## UX Acceptance Criteria

- Chart dominance: active session screenshots show the chart as the largest, strongest work surface.
- Mode clarity: any state that changes chart click/drag behavior names the active mode and provides a cancellation path.
- State center stability: position snapshot and primary trade actions stay reachable in Replay, Plan, Annotate, and Review.
- Trade review flow: users can scan trades, select one, focus entry/exit, edit notes, and return to chart context without losing selection.
- Text fit: Chinese labels, PnL values, timestamps, symbols, and exit reasons do not clip at 1280 x 720 and 1440 x 900.
- No overlap: chart overlays, toolbar controls, side-panel cards, and dialogs do not cover each other incoherently.
- Action discoverability: low-frequency app actions remain reachable but visually yield to replay/trade/review actions.
- Behavior preservation: existing engine, repository, chart aggregation, drawing persistence, order-line, and note persistence tests remain green.

## Reuse Review

Reuse from `redesign-professional-review-workbench`:

- Existing app header/top toolbar split and object names such as `topNavBar`, `workspaceTools`, and `workspaceActions`.
- Existing right sidebar stack with `训练` and `历史交易` tabs.
- Existing `TradeReviewController` and `TradeHistoryTableModel` for selection, focus, sorting, and filtering.
- Existing `ChartWidget.InteractionMode` foundation for browse/drawing/order-preview feedback.
- Existing settings, dataset manager, session library, log viewer, update dialogs, busy overlay, and unified dialog styling.
- Existing theme role system in `AppTheme` and stylesheet helpers.

Avoid rebuilding:

- Trading engine, persistence layer, session loading/saving, CSV import, chart aggregation, update service, or release workflow.
- Trade-history note semantics, which intentionally store notes through entry/exit action notes and trade review snapshots.
- Core chart drawing/order-preview mechanics, which already provide stable behavior and tests.

Next implementation pass:

1. Add a UI-level four-mode enum/state on top of the existing chart interaction modes.
2. Wire drawing activation to Annotate, order preview to Plan, trade selection/sidebar to Review, and stepping/direct chart browsing to Replay.
3. Add small visible mode readouts first, then refine visual system and layout.
