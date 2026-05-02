## Context

The current history review workflow is implemented as a floating `TradeHistoryDialog`. It now contains a rich table, filters, detail panel, entry/exit focus controls, and per-trade notes. The dialog is powerful but spatially wrong for review: it can cover the K-line chart, while the user needs to inspect chart context continuously.

The main window already uses a central layout with the chart as the primary content. This change should add a docked sidebar without introducing new persistence or replacing the trade review model/controller.

## Goals / Non-Goals

**Goals:**

- Keep the chart visible while reviewing historical trades.
- Provide a compact right sidebar for common review work: select trade, jump to entry/exit, edit thoughts.
- Avoid squeezing a wide table into a narrow panel by using compact cards in the sidebar.
- Preserve the full table as an advanced view.
- Reuse current trade review state and note-saving behavior.

**Non-Goals:**

- Do not redesign the full historical trade table in this change.
- Do not add new note storage, tags, screenshots, or AI summaries.
- Do not force the sidebar to be permanently visible.

## Decisions

### Use a docked sidebar as the default review surface

The existing "历史交易" entry point should toggle a right-side sidebar instead of immediately opening the floating dialog. The sidebar sits beside the chart, so it does not obscure candles.

Alternative considered: keep the floating dialog and auto-position it beside the main window. This has lower implementation cost but keeps multi-window friction and can still cover the chart on smaller screens.

### Use compact cards instead of the full table in the sidebar

The sidebar should show each trade as a compact row/card with trade number, direction, PnL, exit reason, and time. The selected card drives the detail area below.

Alternative considered: embed the existing full table directly in the sidebar. This would be too narrow for the current column set and would degrade scanning.

### Keep full table as an advanced action

The sidebar should include a "完整表格" button that opens the existing full table dialog or equivalent wide table view for sorting/filter-heavy workflows.

Alternative considered: remove the dialog entirely. This would lose the wide review mode that is still useful for broad table scanning.

## Risks / Trade-offs

- [Risk] Sidebar reduces chart width. -> Mitigation: make it collapsible and default to a moderate width around 360-420px.
- [Risk] Duplicating dialog logic can drift. -> Mitigation: reuse model/controller and extract shared note/detail widgets where practical.
- [Risk] Existing tests expect the button to open a dialog. -> Mitigation: update tests to assert user-visible entry behavior and add explicit full-table tests.
