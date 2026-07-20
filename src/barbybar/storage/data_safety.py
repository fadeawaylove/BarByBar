from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from barbybar.paths import default_pending_restore_manifest_path


PENDING_RESTORE_MANIFEST_VERSION = 1
REQUIRED_RESTORE_COLUMNS = {
    "datasets": frozenset({"id", "symbol", "timeframe"}),
    "bars": frozenset({"id", "dataset_id", "ts", "open", "high", "low", "close"}),
    "sessions": frozenset({"id", "dataset_id", "status"}),
    "actions": frozenset({"id", "session_id", "action_type"}),
    "order_lines": frozenset({"id", "session_id", "order_type"}),
    "drawings": frozenset({"id", "session_id", "tool_type"}),
    "trades": frozenset({"id", "session_id", "trade_number"}),
    "trade_entry_legs": frozenset({"id", "trade_id", "leg_number"}),
}


class DatabaseBackupError(RuntimeError):
    """Raised when a consistent database backup cannot be published."""


class RestoreValidationError(RuntimeError):
    """Raised when a file is not a safe BarByBar restore candidate."""


class PendingRestoreError(RuntimeError):
    """Raised when a validated restore cannot be staged safely."""


@dataclass(frozen=True, slots=True)
class DatabaseBackupResult:
    path: Path
    created_at: datetime
    size_bytes: int


@dataclass(frozen=True, slots=True)
class RestoreValidationResult:
    path: Path
    validated_at: datetime
    size_bytes: int
    sha256: str
    table_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PendingRestoreResult:
    manifest_path: Path
    staged_database_path: Path
    staged_at: datetime
    size_bytes: int
    sha256: str


def _validate_sqlite_backup(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        result = connection.execute("PRAGMA quick_check").fetchone()
    finally:
        connection.close()
    if result is None or str(result[0]).lower() != "ok":
        detail = str(result[0]) if result is not None else "no validation result"
        raise DatabaseBackupError(f"Backup validation failed: {detail}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_only_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=30)


def validate_restore_database(
    candidate_path: str | Path,
    *,
    current_database_path: str | Path | None = None,
) -> RestoreValidationResult:
    candidate = Path(candidate_path).expanduser().resolve()
    if not candidate.is_file():
        raise RestoreValidationError(f"Restore database does not exist: {candidate}")
    if current_database_path is not None:
        current = Path(current_database_path).expanduser().resolve()
        if candidate == current:
            raise RestoreValidationError("The active database cannot be selected as its own restore source.")

    try:
        with closing(_read_only_connection(candidate)) as connection:
            quick_check = connection.execute("PRAGMA quick_check").fetchone()
            if quick_check is None or str(quick_check[0]).lower() != "ok":
                detail = str(quick_check[0]) if quick_check is not None else "no validation result"
                raise RestoreValidationError(f"Restore database integrity check failed: {detail}")

            table_names = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            missing_tables = sorted(set(REQUIRED_RESTORE_COLUMNS) - table_names)
            if missing_tables:
                raise RestoreValidationError(
                    "Restore database is missing required tables: " + ", ".join(missing_tables)
                )

            for table_name, required_columns in REQUIRED_RESTORE_COLUMNS.items():
                columns = {
                    str(row[1])
                    for row in connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
                }
                missing_columns = sorted(required_columns - columns)
                if missing_columns:
                    raise RestoreValidationError(
                        f"Restore database table {table_name} is missing required columns: "
                        + ", ".join(missing_columns)
                    )
    except RestoreValidationError:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise RestoreValidationError(f"Could not validate restore database {candidate}: {exc}") from exc

    try:
        return RestoreValidationResult(
            path=candidate,
            validated_at=datetime.now(timezone.utc),
            size_bytes=candidate.stat().st_size,
            sha256=_sha256(candidate),
            table_names=tuple(sorted(table_names)),
        )
    except OSError as exc:
        raise RestoreValidationError(f"Could not read restore database {candidate}: {exc}") from exc


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.parent / f".{path.name}.{uuid4().hex}.partial"
    try:
        data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def stage_pending_restore(
    candidate_path: str | Path,
    *,
    current_database_path: str | Path,
    manifest_path: str | Path | None = None,
) -> PendingRestoreResult:
    current = Path(current_database_path).expanduser().resolve()
    manifest = Path(manifest_path or default_pending_restore_manifest_path()).expanduser().resolve()
    staged_database: Path | None = None
    manifest_published = False
    try:
        if manifest == current:
            raise PendingRestoreError("Pending restore manifest cannot replace the active database.")
        validate_restore_database(candidate_path, current_database_path=current)
        manifest.parent.mkdir(parents=True, exist_ok=True)

        staged_database = manifest.parent / f"pending-restore-{uuid4().hex}.db"
        if staged_database.resolve() == current:
            raise PendingRestoreError("Staged restore database cannot replace the active database.")
        create_database_backup(candidate_path, staged_database)
        staged_validation = validate_restore_database(
            staged_database,
            current_database_path=current,
        )
        staged_at = datetime.now(timezone.utc)
        _atomic_write_json(
            manifest,
            {
                "manifest_version": PENDING_RESTORE_MANIFEST_VERSION,
                "sha256": staged_validation.sha256,
                "size_bytes": staged_validation.size_bytes,
                "source_name": Path(candidate_path).name,
                "staged_at": staged_at.isoformat(),
                "staged_database": staged_database.name,
            },
        )
        manifest_published = True
        return PendingRestoreResult(
            manifest_path=manifest,
            staged_database_path=staged_database,
            staged_at=staged_at,
            size_bytes=staged_validation.size_bytes,
            sha256=staged_validation.sha256,
        )
    except (PendingRestoreError, RestoreValidationError):
        raise
    except DatabaseBackupError as exc:
        raise PendingRestoreError(f"Could not stage restore database: {exc}") from exc
    except Exception as exc:
        raise PendingRestoreError(f"Could not publish pending restore manifest at {manifest}: {exc}") from exc
    finally:
        if staged_database is not None and not manifest_published and staged_database.exists():
            staged_database.unlink()


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
        with closing(_read_only_connection(source)) as source_connection, closing(
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
