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

Next task: add export selection UI, background execution, success feedback, empty-session behavior, and write-failure handling.
