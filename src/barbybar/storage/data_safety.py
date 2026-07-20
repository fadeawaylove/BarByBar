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

from barbybar.paths import default_backup_dir, default_db_path, default_pending_restore_manifest_path


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


@dataclass(frozen=True, slots=True)
class PendingRestoreManifest:
    manifest_path: Path
    staged_database_path: Path
    staged_at: datetime
    source_name: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class DatabaseRestoreResult:
    database_path: Path
    safety_backup_path: Path | None
    applied_at: datetime
    cleanup_warning: str | None = None


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


def read_pending_restore_manifest(
    manifest_path: str | Path | None = None,
) -> PendingRestoreManifest | None:
    manifest = Path(manifest_path or default_pending_restore_manifest_path()).expanduser().resolve()
    if not manifest.exists():
        return None
    if not manifest.is_file():
        raise PendingRestoreError(f"Pending restore manifest is not a file: {manifest}")
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PendingRestoreError(f"Could not read pending restore manifest {manifest}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PendingRestoreError("Pending restore manifest must contain a JSON object.")
    manifest_version = payload.get("manifest_version")
    if type(manifest_version) is not int or manifest_version != PENDING_RESTORE_MANIFEST_VERSION:
        raise PendingRestoreError("Pending restore manifest version is not supported.")

    staged_name = payload.get("staged_database")
    if (
        not isinstance(staged_name, str)
        or not staged_name.startswith("pending-restore-")
        or not staged_name.endswith(".db")
        or Path(staged_name).name != staged_name
        or "/" in staged_name
        or "\\" in staged_name
    ):
        raise PendingRestoreError("Pending restore manifest contains an unsafe staged database name.")
    staged_database = (manifest.parent / staged_name).resolve()
    if staged_database.parent != manifest.parent.resolve():
        raise PendingRestoreError("Pending restore database must remain beside its manifest.")

    sha256 = payload.get("sha256")
    if (
        not isinstance(sha256, str)
        or len(sha256) != 64
        or any(character not in "0123456789abcdef" for character in sha256.lower())
    ):
        raise PendingRestoreError("Pending restore manifest contains an invalid SHA-256 digest.")
    size_bytes = payload.get("size_bytes")
    if type(size_bytes) is not int or size_bytes < 0:
        raise PendingRestoreError("Pending restore manifest contains an invalid database size.")
    source_name = payload.get("source_name")
    if not isinstance(source_name, str) or not source_name:
        raise PendingRestoreError("Pending restore manifest contains an invalid source name.")
    staged_at_text = payload.get("staged_at")
    try:
        staged_at = datetime.fromisoformat(staged_at_text) if isinstance(staged_at_text, str) else None
    except ValueError as exc:
        raise PendingRestoreError("Pending restore manifest contains an invalid staging time.") from exc
    if staged_at is None or staged_at.tzinfo is None:
        raise PendingRestoreError("Pending restore manifest contains an invalid staging time.")

    try:
        validation = validate_restore_database(staged_database)
    except RestoreValidationError as exc:
        raise PendingRestoreError(f"Pending restore database is invalid: {exc}") from exc
    if validation.size_bytes != size_bytes or validation.sha256 != sha256.lower():
        raise PendingRestoreError("Pending restore database no longer matches its validated manifest.")
    return PendingRestoreManifest(
        manifest_path=manifest,
        staged_database_path=staged_database,
        staged_at=staged_at,
        source_name=source_name,
        size_bytes=size_bytes,
        sha256=sha256.lower(),
    )


def _checkpoint_and_remove_sqlite_sidecars(database_path: Path) -> None:
    with closing(sqlite3.connect(database_path, timeout=30)) as connection:
        checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if checkpoint is not None and int(checkpoint[0]) != 0:
            raise PendingRestoreError("The active database is still busy and cannot be restored safely.")
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{database_path}{suffix}")
        if sidecar.exists():
            sidecar.unlink()


def apply_pending_restore(
    *,
    current_database_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    backup_dir: str | Path | None = None,
) -> DatabaseRestoreResult | None:
    manifest = read_pending_restore_manifest(manifest_path)
    if manifest is None:
        return None

    current = Path(current_database_path or default_db_path()).expanduser().resolve()
    if current == manifest.manifest_path or current == manifest.staged_database_path:
        raise PendingRestoreError("Pending restore paths cannot replace the active database directly.")
    replacement_ready = current.parent / f".{current.name}.{uuid4().hex}.restore-ready"
    safety_backup: Path | None = None
    replacement_published = False
    try:
        current.parent.mkdir(parents=True, exist_ok=True)
        if current.exists():
            if not current.is_file():
                raise PendingRestoreError(f"Active database is not a file: {current}")
            backup_root = Path(backup_dir or default_backup_dir()).expanduser().resolve()
            backup_root.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            safety_backup = backup_root / f"pre-restore-{timestamp}-{uuid4().hex[:8]}.db"
            create_database_backup(current, safety_backup)
            _checkpoint_and_remove_sqlite_sidecars(current)

        create_database_backup(manifest.staged_database_path, replacement_ready)
        validate_restore_database(replacement_ready)
        os.replace(replacement_ready, current)
        replacement_published = True
    except PendingRestoreError:
        raise
    except (DatabaseBackupError, RestoreValidationError, OSError, sqlite3.Error) as exc:
        raise PendingRestoreError(f"Could not apply pending database restore: {exc}") from exc
    finally:
        if not replacement_published and replacement_ready.exists():
            try:
                replacement_ready.unlink()
            except OSError:
                pass

    cleanup_warning: str | None = None
    try:
        manifest.manifest_path.unlink()
    except OSError as exc:
        cleanup_warning = f"Restore completed, but the pending manifest could not be removed: {exc}"
    else:
        try:
            manifest.staged_database_path.unlink()
        except OSError as exc:
            cleanup_warning = f"Restore completed, but the staged database could not be removed: {exc}"
    return DatabaseRestoreResult(
        database_path=current,
        safety_backup_path=safety_backup,
        applied_at=datetime.now(timezone.utc),
        cleanup_warning=cleanup_warning,
    )


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
