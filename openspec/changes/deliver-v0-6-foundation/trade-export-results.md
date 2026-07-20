# Trade Export Results

Measurement date: 2026-07-20

## Stable export model slice

`barbybar.trade_export` defines a versioned `SessionTradeExport` boundary assembled only from domain `ReviewSession`, `DataSet`, `SessionStats`, `TradeReviewItem`, and `TradeEntryLeg` objects. Its explicit user-facing keys do not expose SQLite column names or serialized internal fields such as `position_json` and `stats_json`.

The model includes stable case identity and summary fields, dataset and chart context, notes and tags, aggregate performance, deterministic trade ordering, entry/exit values, quantity, PnL, exit reason, execution flags, review notes, and numbered entry legs. Datetimes use second-precision ISO 8601 strings and empty sessions are represented with an empty trade collection.

Verification:

```text
Focused export-model tests: 4 passed
```

Next task: publish this model as deterministic UTF-8 CSV and JSON files.
