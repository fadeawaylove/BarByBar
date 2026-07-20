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

## Import review dialog slice

`CsvImportReviewDialog` presents the selected filename and the pre-persistence guarantee, importable row count, parsed time range, blocking and warning totals, all six required field mappings, numbered raw samples, and structured quality findings. Mapping changes trigger a fresh pure inspection and keep the selected mapping visible.

Blocking findings disable confirmation at the widget level and show a Chinese recovery action. Confirmable warnings retain an explicit `确认并导入` action. Severity is communicated through text, counts, table rows, and button state rather than color alone. Internal English parser messages are not exposed in the user-facing review.

Verification:

```text
Focused review-dialog tests: 4 passed
Main-window tests: 265 passed
Complete automated suite: 741 passed
OpenSpec strict validation: passed
```

Visual verification covered warning and blocking states at 980 x 720. The mapping grid, sample table, finding labels, row examples, recovery guidance, and footer actions fit without clipping or horizontal overflow.

## Confirmed single-file import slice

The single-file entry now inspects first, opens the review dialog without creating a dataset, and persists only after explicit confirmation. The exact mapping returned by the reviewed controls is passed to the repository with non-interactive parsing, so persistence cannot silently reopen the legacy mapping dialog or substitute a different mapping.

The workflow rechecks duplicate display names before and after review, preserves the database on cancellation or failure, hides the busy state before presenting errors, and reports every terminal outcome as `成功 / 跳过 / 失败`. Successful warning imports also report the number of quality warnings explicitly confirmed by the user.

Verification:

```text
Focused single-file and folder import tests: 10 passed
Main-window tests: 269 passed
Complete automated suite: 745 passed
OpenSpec strict validation: passed
```

Covered cases include standard reviewed import, exact custom mapping reuse, review cancellation, duplicate skip, persistence failure, and confirmed duplicate/reversed timestamp warnings with deterministic deduplication and ordering.

## Background folder import slice

`BatchImportWorker` now inspects every non-duplicate CSV on its existing background thread before persistence. Clean files import with the inspection's suggested mapping, blocking files fail with categorized Chinese reasons, and warning files are reported as `待确认` without being silently written. Users can review those files through the single-file flow and explicitly confirm the warnings.

Batch progress and final results now distinguish `成功 / 跳过 / 待确认 / 失败`, include bounded examples for duplicate, warning, and failure categories, and preserve the existing non-blocking progress overlay and dataset-manager progress panel. The synchronous folder helper follows the same decision rules for consistency.

Verification:

```text
Focused folder-import and batch-progress tests: 9 passed
Main-window tests: 270 passed
Complete automated suite: 746 passed
OpenSpec strict validation: passed
```

The mixed-folder regression verifies clean import, duplicate skip, warning deferral, blocking failure, actionable summaries, and that all CSV inspection calls execute away from the UI thread.

## Import regression and cleanup slice

The consolidated regression matrix covers clean review, custom remapping, blocked confirmation, confirmed warnings, duplicate dataset handling, background batch progress, review cancellation, persistence failure, and mixed-folder reporting. A repository-level failure injection now verifies cleanup after the dataset row has been inserted but before bar persistence completes.

`Repository.import_csv` wraps dataset and bar insertion in one SQLite transaction. Any exception rolls back both tables and ends the transaction, preventing a later operation from accidentally committing a partial dataset.

Verification:

```text
Repository tests: 43 passed
Focused import workflow tests: 12 passed
Main-window tests: 271 passed
Complete automated suite: 748 passed
OpenSpec strict validation: passed
```

The CSV import quality-review phase (tasks 4.1 through 4.7) is complete. Next task: normalize user-visible position and interaction terminology in task 5.1 while preserving internal enum values.
