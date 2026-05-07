## Context

BarByBar uses Loguru to write `app.log`, `debug.log`, and `error.log` under the application data log directory. The current setup rotates files at 10 MB, retains rotated files for 14 days, compresses rotated logs as zip archives, and filters `debug.log` so it only receives records below `INFO`.

The diagnostics UI already exposes the log directory and these three active files. This change should improve the file policy and diagnostic usefulness without changing the log directory, UI entry points, or exception reporting flow.

## Goals / Non-Goals

**Goals:**

- Use one file policy for every file log sink: 5 MB rotation, 5 retained rotated files, no compression.
- Make `debug.log` the primary troubleshooting log by including `DEBUG+` records.
- Preserve `app.log` as an `INFO+` operational log and `error.log` as an `ERROR+` failure log.
- Keep existing Qt message capture and unhandled exception notification behavior.
- Add tests that make the new policy hard to regress.

**Non-Goals:**

- Do not move the log directory or rename log files.
- Do not delete or migrate existing zip-compressed rotated logs.
- Do not add a new log viewer, export workflow, or diagnostics bundle format.
- Do not change database, update service, or release packaging behavior.

## Decisions

### Use Loguru's built-in retention count

Set the shared retention constant to `5` and pass it to all file sinks. This maps directly to the requested "keep at most 5 log files" behavior for rotated files without adding custom cleanup code.

Alternative considered: implement custom cleanup by scanning the log directory. That would be more error-prone and duplicate Loguru behavior.

### Disable compression by omitting the compression option

Remove the shared compression constant from file sink configuration, or set the value to `None` and pass that consistently. The implementation should avoid producing new `.zip` rotated logs after this change.

Alternative considered: keep a named `LOG_COMPRESSION = None` constant. That keeps the policy explicit, but omitting the option is simpler and avoids ambiguity in tests.

### Promote `debug.log` to complete diagnostics

Remove the current `filter=lambda record: record["level"].no < 20` from the `debug.log` sink. With `level="DEBUG"`, the file will include debug, info, warning, error, and critical records.

Alternative considered: keep `debug.log` debug-only and ask users to collect multiple files. That is less useful for installed-build troubleshooting.

## Risks / Trade-offs

- Older zipped logs remain in the directory -> Acceptable because the change only governs new writes; deleting user logs would be surprising.
- `debug.log` grows faster after including `INFO+` -> Mitigated by lower 5 MB rotation and count-based retention.
- Retention count semantics depend on Loguru's rotated-file behavior -> Mitigated by tests against configured sink options and by relying on the library's documented policy.
- Support may need one transition period where old and new rotated naming coexist -> Mitigated by keeping active file names unchanged.
