# CSV Import Inspection Results

Measurement date: 2026-07-20

## Pure inspection slice

`barbybar.data.csv_importer.inspect_csv` reads and validates a CSV without opening a repository or writing a database. It returns the source path, detected columns, suggested field mapping, numbered raw sample rows, importable row count after timestamp deduplication, duplicate count, and the parsed start and end times.

Inspection and persistence now share `_read_csv_source` and `_parse_bars`, so the preview uses the same header aliases, explicit mapping overrides, datetime parsing, numeric validation, OHLCV validation, timestamp deduplication, and chronological ordering as the existing import path. The public `load_bars_from_csv` behavior remains unchanged.

Verification:

```text
Focused CSV importer tests: 21 passed
Repository regression tests: 42 passed
Existing single-file and folder import UI tests: 6 passed
Complete automated suite: 731 passed
OpenSpec strict validation: passed
```

Covered inspection cases include standard columns, explicit custom mappings, bounded numbered samples, read-only operation, unordered input, duplicate timestamps, importable row totals, parsed time range, and invalid sample limits.

Next task: add structured row-level quality findings for missing fields, parse errors, empty input, duplicate timestamps, reversed ordering, OHLC inconsistencies, and abnormal intervals in task 4.2.
