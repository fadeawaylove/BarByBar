## Why

Current file logs rotate at 10 MB, keep logs by age, and compress rotated files. That makes support handoff less convenient because recent diagnostics can be split across zipped archives, while `debug.log` currently excludes info, warning, and error records that are useful when debugging installed builds.

## What Changes

- Change every file log sink to rotate at 5 MB.
- Keep at most 5 rotated files per log sink instead of retaining logs by age.
- Stop compressing rotated log files.
- Keep `app.log` as the user-facing `INFO+` log.
- Change `debug.log` into the primary diagnostic log by recording `DEBUG+`, including info, warning, and error records.
- Keep `error.log` focused on `ERROR+` records and exception stack traces.
- Preserve existing console logging, Qt message capture, unhandled exception handling, fatal-error UI notification, and diagnostics settings UI.

## Capabilities

### New Capabilities

- `logging-retention-policy`: Covers file log rotation size, retention count, compression behavior, and diagnostic log level coverage.

### Modified Capabilities

None.

## Impact

- Affected code: logging setup in `src/barbybar/logging_config.py`.
- Affected tests: logging configuration tests in `tests/test_logging_config.py`.
- Affected runtime behavior: new rotated log files remain plain text and `debug.log` becomes more complete for troubleshooting.
- No database, release, update, or user data migration is required.
