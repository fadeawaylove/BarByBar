from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class DatabaseBackupError(RuntimeError):
    """Raised when a consistent database backup cannot be published."""


@dataclass(frozen=True, slots=True)
class DatabaseBackupResult:
    path: Path
    created_at: datetime
    size_bytes: int


def _validate_sqlite_backup(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        result = connection.execute("PRAGMA quick_check").fetchone()
    finally:
        connection.close()
    if result is None or str(result[0]).lower() != "ok":
        detail = str(result[0]) if result is not None else "no validation result"
        raise DatabaseBackupError(f"Backup validation failed: {detail}")


def create_database_backup(source_path: str | Path, target_path: str | Path) -> DatabaseBackupResult:
    source = Path(source_path).expanduser().resolve()
    target = Path(target_path).expanduser().resolve()
    if not source.is_file():
        raise DatabaseBackupError(f"Source database does not exist: {source}")
    if source == target:
        raise DatabaseBackupError("Backup target must be different from the source database.")

    temporary: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / f".{target.name}.{uuid4().hex}.partial"
        with closing(sqlite3.connect(source, timeout=30)) as source_connection, closing(
            sqlite3.connect(temporary)
        ) as destination_connection:
            source_connection.execute("PRAGMA query_only = ON")
            source_connection.backup(destination_connection)
            destination_connection.commit()

        _validate_sqlite_backup(temporary)
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
        return DatabaseBackupResult(
            path=target,
            created_at=datetime.now(timezone.utc),
            size_bytes=target.stat().st_size,
        )
    except DatabaseBackupError:
        raise
    except Exception as exc:
        raise DatabaseBackupError(f"Could not create database backup at {target}: {exc}") from exc
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
