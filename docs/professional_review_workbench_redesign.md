# Professional Review Workbench Redesign Map

This document supports `openspec/changes/redesign-professional-review-workbench`. It is the implementation map for replacing the accumulated Qt utility layout with a professional chart-first review workbench.

## Product Direction

BarByBar 1.0 should feel like a focused trading review terminal:

- chart-first
- calm and professional
- high-density but readable
- fast for replay and trading
- reflective for trade review
- consistent across workbench, dialogs, errors, logs, and settings

Avoid decorative dashboard tropes: gradients, glass effects, oversized hero sections, large marketing cards, novelty iconography, and one-note dark terminal styling.

## Current Control Inventory

### App-Level Controls

These controls manage data, sessions, configuration, diagnostics, or updates. They belong in the redesigned app header or supporting dialogs, not in the high-frequency training toolbar.

| Current control | Current location | Classification | Redesigned location |
| --- | --- | --- | --- |
| `数据集` | top nav | app-level | app header workspace actions |
| `案例库` | top nav | app-level | app header workspace actions |
| `设置` | top nav | app-level | app header utility actions |
| `查看日志` | top nav/settings | diagnostic | app header diagnostics or settings diagnostics page |
| `检查更新` | top nav | diagnostic | app header diagnostics/update action |
| Dataset manager import/create/delete | dataset dialog | app-level data management | redesigned dataset manager |
| Session library open/delete | session dialog | app-level session management | redesigned session library |
| Settings categories and controls | settings dialog | configuration | redesigned settings dialog |
| Log file selector/refresh/status | log viewer | diagnostic | redesigned log viewer |
| Update, notice, error dialogs | transient dialogs | diagnostic/recovery | unified dialog family |

### Training-Level Controls

These controls directly support replay and chart operation. They belong in the training toolbar or bottom status bar.

| Current control | Current location | Classification | Redesigned location |
| --- | --- | --- | --- |
| Timeframe buttons | top nav | training/chart | training toolbar timeframe group |
| Drawing templates | top nav | chart/tooling | training toolbar chart tools |
| Drawing tool buttons | top nav | chart/tooling | training toolbar chart tools |
| `K线序号` | chart/replay area | display support | quiet display controls or settings |
| `隐藏画线` | chart/replay area | display support | quiet display controls or settings |
| `不过夜` | chart/replay area/settings | training behavior | right panel/session behavior and settings |
| Progress label | replay controls | status | bottom status bar and session stats |
| `上一步` | replay controls | training | training toolbar replay group |
| `下一根` | replay controls | training | training toolbar replay group |
| Jump spin | replay controls | training | training toolbar replay group |
| `重置视图` | replay controls | chart | training toolbar view group |
| `清除画线` | replay controls | chart/destructive utility | training toolbar view group with confirmation |

### Chart-Level Controls and Overlays

| Current surface | Classification | Redesigned treatment |
| --- | --- | --- |
| K-line canvas | primary workspace | largest visual region, minimal chrome |
| Axes, tick labels, grid | chart metadata | subdued but readable |
| Bar numbers/session markers | chart metadata | quiet display layer |
| Hover readout | chart interaction | compact overlay, no important overlap |
| Measurement label | chart interaction | clamped, readable, low visual noise |
| Drawing handles/anchors | chart interaction | clear selected/hover state |
| Order preview lines | chart/order workflow | color-coded by type with active mode hint |
| Trade markers | trade review | readable but not candle-dominant |
| Trade links | trade review | subdued at rest, stronger on hover/selection |
| Trade note editing | trade review | integrated with marker/link focus states |

### Right Sidebar Controls

The current right sidebar mixes direct actions, order tools, chart tools, state, stats, display toggles, and session actions. The redesign turns it into a training state center.

| Current control | Current location | Classification | Redesigned section |
| --- | --- | --- | --- |
| `数量` spin | trade box | quick trade | Quick Trade |
| `价格` spin | trade box | quick trade | Quick Trade |
| `买` | trade box | quick trade | Quick Trade primary action |
| `卖` | trade box | quick trade | Quick Trade primary action |
| `平` | trade box | quick trade | Quick Trade primary action |
| `反` | trade box | quick trade | Quick Trade primary action |
| `手数` draw spin | trade box | line/order tools | Line / Order Tools |
| `最小跳动` spin | trade box | session/chart parameter | Position/Tools support or Settings |
| Entry/exit/stop/take-profit/adverse/reverse line buttons | trade box | line/order tools | Line / Order Tools |
| Drawing/template controls | side/top | chart tools | Training toolbar or secondary chart tools section |
| Position readout | right panel | position state | Position Snapshot |
| Training stats headline/meta/label | right panel | stats | Session Stats |
| Trade markers/links toggles | right panel | display support | Quiet Display Controls |
| Save session | right panel | session utility | Session Utilities or app header save/status |
| Mark complete | right panel | session lifecycle | Session Utilities with primary completion role |

### Trade History Controls

| Current control | Current location | Classification | Redesigned location |
| --- | --- | --- | --- |
| Trade history tab | right sidebar | review navigation | right panel review section/tab |
| Trade card list | sidebar | review scanning | compact trade list |
| Previous/next trade | sidebar/dialog | review navigation | review center navigation |
| Entry/exit focus buttons | sidebar/dialog | chart focus | focus controls in list/detail |
| Trade summary | sidebar/dialog | review detail | detail panel |
| Entry thought editor | sidebar/dialog | note editing | review detail editor |
| Review summary editor | sidebar/dialog | note editing | review detail editor |
| Save thought button/status | sidebar/dialog | note persistence | explicit dirty/saved feedback |
| Sort/filter controls | full dialog | review filtering | compact filter bar |
| Clear filters | full dialog | review filtering | visible only when filters active |
| Empty/no-selection states | sidebar/dialog | review state | designed empty states |

### Supporting Dialog Controls

| Surface | Current responsibilities | Redesigned surface |
| --- | --- | --- |
| Settings | chart display, colors, alpha, default quantity, flatten behavior, logs, performance | multi-section settings with chart/training/diagnostics pages |
| Dataset manager | import single CSV, import folder, filter, create session, delete dataset, batch progress | data management workspace with selected dataset detail |
| Session library | filter, open, delete | session browser with selected session detail and current-session state |
| Log viewer | log file combo, refresh, text, status | diagnostics viewer with missing/read failure states |
| Update dialog | update status, release detail, actions | unified notice/update dialog |
| Busy overlay | import/session/update progress | scoped operation feedback |
| Inline error/notice dialogs | confirmations and failures | unified dialog hierarchy |

## Controls to Demote or Move

| Control or surface | Decision | Reason |
| --- | --- | --- |
| Logs/update buttons | keep visible but demote | diagnostic, not training-critical |
| Settings | keep visible but demote | configuration, low-frequency |
| Dataset/session management | keep visible in app header | important setup flow but not replay flow |
| Bar labels/drawing visibility/trade marker toggles | move to quiet display controls and settings | visual support controls should not compete with trade actions |
| Clear drawings | keep but separate as chart utility/destructive action | useful but dangerous/noisy |
| Tick size | keep available but reduce prominence | important parameter, not every-step action |
| Template buttons | keep but compact or move into chart tool group | chart workflow support |
| Save session | surface save status in app header/status bar; keep manual save as quiet utility | saving is mostly background behavior |

## Old-to-New Information Architecture

```text
OLD
┌──────────────────────────────────────────────────────────────┐
│ Mixed top nav: timeframe + templates + drawing + data/logs   │
├───────────────────────────────────────────────┬──────────────┤
│ Chart + replay strip                           │ mixed sidebar │
│                                                │ trade/stats   │
│                                                │ display/save  │
└───────────────────────────────────────────────┴──────────────┘

NEW
┌──────────────────────────────────────────────────────────────┐
│ App Header: brand/session/save + data/session/settings/logs  │
├──────────────────────────────────────────────────────────────┤
│ Training Toolbar: timeframe/replay/chart tools/active mode   │
├───────────────────────────────────────────────┬──────────────┤
│ Chart Workspace                                │ Position     │
│                                                │ Quick Trade  │
│                                                │ Line Tools   │
│                                                │ Stats/Review │
├───────────────────────────────────────────────┴──────────────┤
│ Status Bar: current bar/timeframe/source/save/context hints   │
└──────────────────────────────────────────────────────────────┘
```

## Target Desktop Sizes

| Target | Size | Purpose |
| --- | --- | --- |
| Narrow supported desktop | 1280 x 720 | Small laptop / constrained window |
| Standard desktop | 1440 x 900 | Primary design target |
| Wide desktop | 1920 x 1080 | High-information trading review |

Minimum viable main-window content target: 1280 x 720. Below this size, the UI may scroll the right panel but must not clip primary trade actions, toolbar controls, or status text.

## Screenshot Acceptance Set

- Empty startup / no active session.
- Active session with no position.
- Active session with long position.
- Active session with short position.
- Completed session.
- Drawing mode active.
- Order-preview mode active.
- Trade-history sidebar with selected trade and entry focus.
- Full trade review center with selected trade.
- Settings dialog.
- Dataset manager: empty, populated, filtered, batch progress.
- Session library: empty, populated, filtered, current session.
- Log viewer: normal log, missing log, failed read where feasible.
- Update available, up-to-date, update failure, and generic error/notice dialogs.
- Busy overlay for import/session load/update.
- Narrow 1280 x 720 layout.
- Wide 1920 x 1080 layout.

## Redesign Acceptance Checklist

- [ ] Chart is visually dominant in active session views.
- [ ] App-level actions are accessible but quieter than training controls.
- [ ] Replay/timeframe/chart-tool controls form a stable training toolbar.
- [ ] Right sidebar scans as Position, Quick Trade, Line Tools, Stats, Review/Utilities.
- [ ] Direct trade buttons are the clearest sidebar actions.
- [ ] Line/order tools are visible but secondary.
- [ ] Trade history reads as review workflow, not just a table.
- [ ] Empty states look intentional and provide clear next actions.
- [ ] Busy states identify the operation and clear after success/failure/cancel.
- [ ] Dialogs share one product family: heading, summary, details, primary/secondary/danger actions.
- [ ] Chinese labels fit without clipping or overlap at 1280 x 720 and 1440 x 900.
- [ ] Hover, focus, selected, disabled, checked, long, short, danger, and loading states are visible.
- [ ] Existing replay, trade, drawing, persistence, and note semantics remain unchanged.
- [ ] Packaged app screenshots render Chinese fonts correctly.

## Implementation Guardrails

- Do not change trading engine behavior.
- Do not change DB schema for this redesign.
- Do not remove existing workflows without a discoverable replacement.
- Prefer shared theme roles and small reusable UI helpers over one-off styles.
- Use structural tests for behavior and screenshot/manual review for visual quality.

## Visual System Roles

The first implementation layer defines reusable roles in `AppTheme` and stylesheet helpers. These names are intentionally semantic so later UI work does not depend on raw colors.

### Surface Roles

- `shell_background`, `shell_background_soft`: outer app shell.
- `header_background`: app header with brand/session/workspace actions.
- `toolbar_background`: training toolbar and compact control strips.
- `chart_surround`: area around the K-line canvas.
- `sidebar_background`: right training panel shell.
- `status_bar_background`: bottom status bar.
- `panel_surface`, `section_surface`, `card_surface`, `dialog_surface`, `input_surface`, `table_surface`, `overlay_surface`, `popover_surface`: shared component surfaces.

### Border Roles

- `border_hairline`: subtle component frame.
- `border_divider`: region divider.
- `border_selected`: selected state.
- `border_focus`: keyboard/input focus.
- `border_danger`, `border_long`, `border_short`: semantic action borders.
- `border_muted`: quiet section borders.

### Text Roles

- `text_title`, `text_subtitle`, `text_section`, `text_body`.
- `text_secondary`, `text_muted`, `text_disabled`.
- `text_numeric`, `text_positive`, `text_negative`.
- `text_warning`, `text_error`, `text_success`.

### Action Roles

- `action_primary`, `action_secondary`, `action_quiet`.
- `action_danger`, `action_long`, `action_short`.
- `action_toggle`, `action_selected`, `action_checked`.
- `action_pressed`, `action_hover`, `action_focus`, `action_disabled`.

### Layout and Typography Roles

- Shell and toolbar dimensions: `shell_margin`, `header_height`, `training_toolbar_height`, `status_bar_height`.
- Dense layout values: `sidebar_section_gap`, `section_padding`, `card_padding`, `dialog_padding`, `form_row_gap`, `table_row_height`.
- Stable controls: `status_chip_height`, `trade_button_width`, `trade_button_height`, `app_action_button_width`.
- Text scale: `font_size_title`, `font_size_session`, `font_size_toolbar`, `font_size_section`, `font_size_body`, `font_size_dense`, `font_size_numeric`, `font_size_button`, `font_size_table`.

### Helper Stylesheets

- `professional_workbench_stylesheet()`: app-level composition used by `MainWindow`.
- `shell_stylesheet()`: app header, training toolbar, chart workspace, right panel, and status bar region roles.
- `panel_stylesheet()`: reusable panel, section, and card surfaces.
- `status_bar_stylesheet()`: status chip styling.

### Anti-Patterns

- Do not add new raw hex colors inside feature widgets unless they become theme roles.
- Do not use heavy borders to create hierarchy; prefer spacing, role, typography, and action priority.
- Do not make diagnostic/app-management buttons visually compete with replay and trade controls.
- Do not add decorative gradients or image-like backgrounds to the training workbench.
- Do not rely on screenshot-only validation for behavior; pair visual checks with structural tests.
