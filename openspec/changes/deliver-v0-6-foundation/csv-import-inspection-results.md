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

## Structured quality detection slice

Inspection now returns deterministic `CsvQualityFinding` entries with stable codes, total occurrence counts, and up to five bounded row-level examples per category. It detects unmapped required fields, datetime or numeric parse failures, no importable data, duplicate timestamps, reversed source ordering, invalid OHLCV relationships, and abnormal positive intervals.

The interval rule uses the median of at least three positive source intervals as a robust local baseline and flags gaps greater than three times that value. This intentionally identifies candidates only; task 4.3 assigns blocking or confirmable severity.

Invalid rows no longer stop inspection at the first error. Valid rows continue to contribute to the importable count and time range, while the strict persistence parser retains its existing fail-fast behavior.

Verification:

```text
Focused CSV importer and quality tests: 27 passed
Complete automated suite: 737 passed
OpenSpec strict validation: passed
```

## Severity and confirmation slice

Every quality finding now has an explicit `blocking` or `warning` severity. Missing mappings, parse failures, empty data, and invalid OHLCV relationships block import confirmation because the current persistence parser cannot safely import them. Duplicate timestamps, reversed source ordering, and abnormal intervals are confirmable warnings because the existing importer deterministically deduplicates and sorts those rows without inventing market values.

`CsvInspectionResult` exposes blocking and warning collections plus `can_confirm_import`, giving the review interface one tested decision boundary instead of duplicating quality rules in UI code.

Verification:

```text
Focused parser and quality-rule tests: 27 passed
Complete automated suite: 737 passed
OpenSpec strict validation: passed
```

Next task: build the import review dialog for mapping, samples, summary, findings, and blocked confirmation in task 4.4.
