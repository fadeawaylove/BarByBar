## Context

BarByBar's replay workspace uses a fixed right panel for high-frequency training controls. Historical trade review was moved toward this area, but the current page switch is not visually explicit enough: it behaves like a hidden alternate panel rather than a designed navigation model. Users need to see that `训练` and `历史交易` are sibling modes of the same right-side control surface.

The change is UI-only. It must preserve the chart width, existing trade review data model, action notes, selected trade focus behavior, and session persistence.

## Goals / Non-Goals

**Goals:**

- Make right-panel mode switching explicit with top-level `训练` and `历史交易` tabs.
- Keep `训练` as the default mode and preserve current replay controls.
- Keep historical trade review inside the existing right panel without opening a floating history window.
- Keep historical trade selection and entry/exit focus behavior deterministic.
- Fit the existing professional light theme rather than introducing a new visual language.

**Non-Goals:**

- Rebuild the historical trade page as the wide table/filter dialog.
- Change saved session schemas, action note storage, repository APIs, or engine trade-review models.
- Change chart rendering or training execution behavior beyond selected-trade focus.

## Decisions

1. Use a custom segmented tab header over the existing `QStackedWidget`.

   Rationale: the current theme already has compact segmented controls and fixed right-panel density. A custom `QButtonGroup` with two checkable buttons can match the app's visual system better than a native `QTabWidget`, while keeping the implementation simple.

   Alternative considered: `QTabWidget`. It would reduce custom code, but its default styling is more system-like and less consistent with BarByBar's card-based right panel.

2. Keep the right panel fixed at `AppTheme.sidebar_width`.

   Rationale: opening trade history must not steal space from the candlestick chart. The history experience should be compact by design, using cards and detail fields rather than a wide table.

   Alternative considered: expand the sidebar for history. That gives more room to the list but reintroduces chart layout instability.

3. Make the tabs the only visible mode navigation.

   Rationale: duplicated navigation creates the current lack of design intent. The `历史交易` utility button in the display group and the history-page `复盘` / `刷新` buttons should be removed. Existing command methods still route to the history tab for compatibility with tests and internal callers.

   Alternative considered: keep the utility button as a shortcut. That keeps legacy affordances but makes the hierarchy noisier.

4. Keep history refresh automatic on tab entry.

   Rationale: the list is derived from current engine trade review items, so selecting the tab should show current data without a manual refresh control. Refresh still occurs when engine state changes and when note saves invalidate review items.

   Alternative considered: expose a refresh button. It is not needed for the normal workflow and adds clutter in a narrow panel.

## Risks / Trade-offs

- [Risk] Removing the utility button may break tests or callers that assume a visible `open_trade_history_button`. -> Mitigation: keep public methods such as `open_trade_history_dialog()` and `open_full_trade_history_dialog()` as stable entry points, and update UI tests to assert the tab header instead of the old button.
- [Risk] History page controls may feel cramped at 288px. -> Mitigation: keep the compact card list pattern, avoid adding the wide table/filter controls, and use concise labels.
- [Risk] Tab selected state can drift from the stack page if pages are switched programmatically. -> Mitigation: centralize switching in `show_training_sidebar()` and `show_trade_history_sidebar()` helpers that update both stack page and tab checked state.
- [Risk] Historical selection could focus the wrong trade if row positions are reused after sorting/filtering. -> Mitigation: continue using the selected `TradeReviewItem`'s own entry and exit bar indices for chart focus.
