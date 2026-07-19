# Data Safety Results

Measurement date: 2026-07-19

## Consistent backup slice

`barbybar.storage.data_safety.create_database_backup` creates a SQLite-consistent snapshot through the SQLite backup API using a separate read connection. The snapshot is written to a unique partial file in the destination directory, checked with `PRAGMA quick_check`, flushed, and atomically published with `os.replace` only after validation succeeds.

Safety behavior:

- The source must already exist and cannot also be the target.
- An active application connection does not need to be closed for committed data to be captured consistently.
- Existing target files remain untouched until validation succeeds.
- Validation and target-path failures remove the new partial file and preserve the source database.
- The result reports the resolved path, UTC completion time, and final byte size.

Verification:

```text
Focused backup tests: 5 passed
Backup plus repository tests: 47 passed
Complete automated suite: 694 passed
```

Covered failure cases include an invalid target parent, source/target identity, forced validation failure after the partial database exists, preservation of an existing target, partial-file cleanup, and source-data preservation.

Next task: validate restore candidates and create a pending-restore manifest without replacing the active database.
