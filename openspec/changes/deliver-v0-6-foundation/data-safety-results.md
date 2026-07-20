# Data Safety Results

Measurement date: 2026-07-20

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

## Safe staged restore slice

`validate_restore_database` opens the selected file in SQLite read-only mode, runs `PRAGMA quick_check`, and verifies the required BarByBar tables and identifying columns. It rejects the active database itself, non-SQLite content, incomplete schemas, and unreadable files before any staging work begins.

`stage_pending_restore` then creates a separate SQLite-consistent snapshot under the dedicated restore directory. The pending manifest is flushed and atomically published only after the staged snapshot passes validation again. It stores a manifest version, controlled same-directory filename, byte size, SHA-256 digest, source display name, and UTC staging time; it never points the active application at a replacement database during the running session.

Safety behavior:

- The active database path cannot be used as either the restore source or manifest path.
- The selected source and active database remain byte-for-byte unchanged while staging.
- Invalid content is rejected before a pending manifest is created.
- A manifest write failure preserves any existing manifest and removes the new staged database and partial manifest.
- The default pending manifest lives at `data/restore/pending_restore.json`, including portable data-root overrides.

Verification:

```text
Focused data-safety, path, and repository tests: 58 passed
Complete automated suite: 702 passed
```

## Startup restore application slice

`apply_pending_restore` reads and validates the versioned manifest, rejects unsafe staged paths, and rechecks the staged database size, SHA-256 digest, SQLite integrity, tables, and identifying columns. When a request is valid, it creates a timestamped `pre-restore-*.db` safety backup of the active database before preparing any replacement.

The replacement is rebuilt and validated in the active database directory, SQLite WAL state is checkpointed, stale WAL/SHM sidecars are removed, and `os.replace` performs the final same-directory atomic switch. The application invokes this flow after logging starts but before `QApplication`, `Repository`, windows, or background workers are created.

Failure and recovery behavior:

- A missing manifest is a no-op and normal startup continues.
- A malformed manifest, path traversal, staged-file tampering, validation failure, safety-backup failure, busy database, or atomic-replace failure leaves the active database in place and retains the pending request for diagnosis or retry.
- An atomic-replace failure still leaves the verified pre-restore safety backup available.
- A successful restore removes the manifest first and then the staged snapshot; a cleanup failure does not invalidate the completed restore and is surfaced as a startup log warning.
- Startup logs both successful restore paths and actionable restore failures before opening the repository.

Verification:

```text
Focused data-safety, path, desktop-startup, repository, and logging tests: 75 passed
Complete automated suite: 710 passed
```

Next task: add the settings/data-management UI for manual backup, restore selection, restart guidance, paths, progress, and actionable errors.
