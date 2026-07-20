# Trade Export Results

Measurement date: 2026-07-20

## Stable export model slice

`barbybar.trade_export` defines a versioned `SessionTradeExport` boundary assembled only from domain `ReviewSession`, `DataSet`, `SessionStats`, `TradeReviewItem`, and `TradeEntryLeg` objects. Its explicit user-facing keys do not expose SQLite column names or serialized internal fields such as `position_json` and `stats_json`.

The model includes stable case identity and summary fields, dataset and chart context, notes and tags, aggregate performance, deterministic trade ordering, entry/exit values, quantity, PnL, exit reason, execution flags, review notes, and numbered entry legs. Datetimes use second-precision ISO 8601 strings and empty sessions are represented with an empty trade collection.

Verification:

```text
Focused export-model tests: 4 passed
```

## CSV and JSON writer slice

`export_session_trade_data` publishes either indented UTF-8 JSON or Excel-friendly UTF-8-with-BOM CSV through a unique partial file, flush, `fsync`, and atomic replace. Existing targets remain untouched until the complete export is ready, and partial files are removed after write or publish failures.

The JSON structure preserves the versioned `session` and `trades` boundary. CSV uses the explicit `CSV_EXPORT_FIELDS` order, repeats the case context on each trade row, serializes tags and entry legs as compact JSON, formats booleans and numbers deterministically, and writes one summary row with blank trade fields when a case has no trades.

Verification:

```text
Focused export model and writer tests: 9 passed
```

Covered cases include deterministic repeat exports, Chinese text, stable headers, trade ordering, entry-leg encoding, empty-case summaries, unsupported formats, atomic publish failure, preservation of an existing target, and partial-file cleanup.

## Export workflow slice

The full trade-history workspace now provides CSV and JSON export actions for the current case. Export preparation uses the stable view model, and file writing runs through the existing background data-safety coordinator so the window remains responsive and backup, restore, and export operations cannot overlap.

The interface keeps the export scope explicit: every export contains the current case summary and all saved trades, independent of history filters. It shows progress while writing, reports the destination and trade count on success, produces a valid summary-only export for an empty case, and leaves the selected target untouched when writing fails. Failures remain visible in the workspace and include a concrete retry action.

Visual verification used the 1080 x 640 full-history layout. The secondary export actions remain separate from filters and the progress or result message has a dedicated row without reducing the table or review workspace.

Verification:

```text
Focused export workflow tests: 4 passed
Focused export, paths, and main-window tests: 276 passed
Complete automated suite: 727 passed
OpenSpec strict validation: passed
```

Covered workflow cases include no open case, empty-case CSV export, saved-trade JSON export, review-note preservation, background progress, success re-enablement, actionable write failure, and preservation of a blocked target path.

Next task: extract the pure CSV inspection result required by task 4.1 before changing the import interface.
