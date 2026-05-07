## 1. Logging Configuration

- [x] 1.1 Change shared file log rotation from 10 MB to 5 MB in the logging configuration.
- [x] 1.2 Change file log retention from 14 days to 5 retained rotated files for every file sink.
- [x] 1.3 Remove file log compression so future rotated logs remain plain text.
- [x] 1.4 Remove the `debug.log` debug-only filter so it records `DEBUG+`.
- [x] 1.5 Keep `app.log` at `INFO+` and `error.log` at `ERROR+`.

## 2. Tests

- [x] 2.1 Update logging file creation tests to assert `app.log` contains info but not debug.
- [x] 2.2 Add coverage that `debug.log` contains debug, info, warning, and error records.
- [x] 2.3 Keep or update exception tests to confirm `error.log` contains exception messages and stack details.
- [x] 2.4 Add focused assertions that configured file sinks use 5 MB rotation, retention count 5, and no compression.
- [x] 2.5 Verify Qt message capture and fatal-error notification tests still pass.

## 3. Validation

- [x] 3.1 Run `uv run pytest -q tests/test_logging_config.py`.
- [x] 3.2 Run `uv run pytest -q`.
- [x] 3.3 Run `openspec validate optimize-logging-retention --strict`.
