## Why

BarByBar has accumulated enough core review functionality that the next major version should improve confidence, polish, and day-to-day usability rather than add more features. The current opportunity is to make the existing review trainer feel stable, coherent, fast, and visually professional across the main chart, right sidebar, settings, session library, and trade-history workflows.

## What Changes

- Refine the main review workbench layout so chart, top toolbar, right training panel, and trade-history panel feel like one consistent product surface.
- Improve interaction clarity for existing actions: stepping, order entry, chart tools, trade history focus, settings, session/data management, and log/update actions.
- Standardize visual language: spacing, typography, button states, colors, table/card density, empty states, focus states, disabled states, and loading/busy states.
- Tighten stability and responsiveness around existing flows, including session load/save, timeframe switching, chart redraws, trade-history selection, and settings persistence.
- Improve first-run and no-data states without adding new training concepts or data model features.
- Preserve existing core behaviors, database compatibility, trading calculations, review records, and chart drawing/trade workflows.

## Capabilities

### New Capabilities

- `review-workbench-polish`: Covers UI polish, interaction consistency, responsiveness, and stability expectations for the existing BarByBar review workbench.

### Modified Capabilities

None.

## Impact

- Affected UI: main window layout, top toolbar, chart widget presentation, right sidebar, trade-history sidebar/dialog, settings dialog, session/data dialogs, busy/error/empty states.
- Affected tests: main window UI tests, chart widget interaction tests, trade-history tests, settings persistence tests, and focused performance/regression tests.
- Affected docs: README feature wording and any workflow docs that describe trade history or diagnostics if UI text changes.
- No new database schema, no new trading engine behavior, and no new external service dependency.
