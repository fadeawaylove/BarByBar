from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from barbybar.storage import data_safety
from barbybar.storage.data_safety import (
    DatabaseBackupError,
    PendingRestoreError,
    RestoreValidationError,
    create_database_backup,
    stage_pending_restore,
    validate_restore_database,
)
from barbybar.storage.repository import Repository


def _dataset_count(path: Path) -> int:
    connection = sqlite3.connect(path)
    try:
        return int(connection.execute("SELECT COUNT(*) FROM datasets").fetchone()[0])
    finally:
        connection.close()


def test_create_database_backup_captures_committed_data_with_active_connection(tmp_path: Path) -> None:
    source = tmp_path / "barbybar.db"
    target = tmp_path / "backups" / "barbybar-backup.db"
    repo = Repository(source)
    try:
        repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")

        result = create_database_backup(source, target)

        assert result.path == target.resolve()
        assert result.size_bytes == target.stat().st_size
        assert result.size_bytes > 0
        assert result.created_at.tzinfo is not None
        assert _dataset_count(target) == 1
        assert repo.list_datasets()[0].symbol == "IF"
    finally:
        repo.conn.close()


def test_create_database_backup_rejects_source_as_target(tmp_path: Path) -> None:
    source = tmp_path / "barbybar.db"
    repo = Repository(source)
    try:
        with pytest.raises(DatabaseBackupError, match="different from the source"):
            create_database_backup(source, source)
    finally:
        repo.conn.close()


def test_create_database_backup_reports_unwritable_target_without_changing_source(tmp_path: Path) -> None:
    source = tmp_path / "barbybar.db"
    repo = Repository(source)
    repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
    repo.conn.close()
    blocked_parent = tmp_path / "blocked"
    blocked_parent.write_text("not a directory", encoding="utf-8")

    with pytest.raises(DatabaseBackupError, match="Could not create database backup"):
        create_database_backup(source, blocked_parent / "backup.db")

    assert _dataset_count(source) == 1
    assert blocked_parent.read_text(encoding="utf-8") == "not a directory"


def test_create_database_backup_cleans_partial_file_and_preserves_existing_target_on_validation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "barbybar.db"
    target = tmp_path / "backup.db"
    repo = Repository(source)
    repo.conn.close()
    target.write_bytes(b"existing backup")

    def fail_validation(_path: Path) -> None:
        raise DatabaseBackupError("Backup validation failed: forced failure")

    monkeypatch.setattr(data_safety, "_validate_sqlite_backup", fail_validation)

    with pytest.raises(DatabaseBackupError, match="forced failure"):
        create_database_backup(source, target)

    assert target.read_bytes() == b"existing backup"
    assert list(tmp_path.glob(".*.partial")) == []


def test_create_database_backup_replaces_existing_target_only_after_validation(tmp_path: Path) -> None:
    source = tmp_path / "barbybar.db"
    target = tmp_path / "backup.db"
    repo = Repository(source)
    try:
        repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        target.write_bytes(b"old backup")

        create_database_backup(source, target)

        assert target.read_bytes() != b"old backup"
        assert _dataset_count(target) == 1
        assert list(tmp_path.glob(".*.partial")) == []
    finally:
        repo.conn.close()


def test_validate_restore_database_accepts_complete_barbybar_backup(tmp_path: Path) -> None:
    source = tmp_path / "barbybar.db"
    backup = tmp_path / "backup.db"
    repo = Repository(source)
    try:
        repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        create_database_backup(source, backup)
    finally:
        repo.conn.close()

    result = validate_restore_database(backup, current_database_path=source)

    assert result.path == backup.resolve()
    assert result.size_bytes == backup.stat().st_size
    assert len(result.sha256) == 64
    assert {"datasets", "bars", "sessions", "trades"}.issubset(result.table_names)


@pytest.mark.parametrize("invalid_kind", ["text", "missing_tables"])
def test_validate_restore_database_rejects_invalid_file_without_modifying_current_database(
    tmp_path: Path,
    invalid_kind: str,
) -> None:
    current = tmp_path / "barbybar.db"
    repo = Repository(current)
    repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
    repo.conn.close()
    original = current.read_bytes()
    candidate = tmp_path / "invalid.db"
    if invalid_kind == "text":
        candidate.write_text("not sqlite", encoding="utf-8")
    else:
        connection = sqlite3.connect(candidate)
        connection.execute("CREATE TABLE unrelated(id INTEGER PRIMARY KEY)")
        connection.commit()
        connection.close()

    with pytest.raises(RestoreValidationError):
        validate_restore_database(candidate, current_database_path=current)

    assert current.read_bytes() == original
    assert _dataset_count(current) == 1


def test_validate_restore_database_rejects_active_database_as_restore_source(tmp_path: Path) -> None:
    current = tmp_path / "barbybar.db"
    repo = Repository(current)
    try:
        with pytest.raises(RestoreValidationError, match="active database"):
            validate_restore_database(current, current_database_path=current)
    finally:
        repo.conn.close()


def test_stage_pending_restore_publishes_manifest_without_touching_active_database(tmp_path: Path) -> None:
    current = tmp_path / "active" / "barbybar.db"
    candidate = tmp_path / "selected-backup.db"
    manifest = tmp_path / "restore" / "pending_restore.json"
    current.parent.mkdir(parents=True)
    repo = Repository(current)
    try:
        repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        create_database_backup(current, candidate)
        active_before = current.read_bytes()
        candidate_before = candidate.read_bytes()

        result = stage_pending_restore(
            candidate,
            current_database_path=current,
            manifest_path=manifest,
        )

        assert repo.list_datasets()[0].symbol == "IF"
    finally:
        repo.conn.close()

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert result.manifest_path == manifest.resolve()
    assert result.staged_database_path.parent == manifest.parent.resolve()
    assert result.staged_database_path != candidate.resolve()
    assert result.staged_database_path != current.resolve()
    assert payload["manifest_version"] == 1
    assert payload["staged_database"] == result.staged_database_path.name
    assert payload["sha256"] == result.sha256
    assert payload["size_bytes"] == result.size_bytes
    assert "/" not in payload["staged_database"]
    assert "\\" not in payload["staged_database"]
    assert current.read_bytes() == active_before
    assert candidate.read_bytes() == candidate_before
    assert _dataset_count(result.staged_database_path) == 1


def test_stage_pending_restore_preserves_existing_manifest_when_publish_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = tmp_path / "barbybar.db"
    candidate = tmp_path / "backup.db"
    manifest = tmp_path / "restore" / "pending_restore.json"
    repo = Repository(current)
    repo.conn.close()
    create_database_backup(current, candidate)
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"existing": true}\n', encoding="utf-8")
    existing_manifest = manifest.read_bytes()

    def fail_manifest_write(_path: Path, _payload: dict[str, object]) -> None:
        raise OSError("forced manifest failure")

    monkeypatch.setattr(data_safety, "_atomic_write_json", fail_manifest_write)

    with pytest.raises(PendingRestoreError, match="forced manifest failure"):
        stage_pending_restore(
            candidate,
            current_database_path=current,
            manifest_path=manifest,
        )

    assert manifest.read_bytes() == existing_manifest
    assert list(manifest.parent.glob("pending-restore-*.db")) == []
    assert list(manifest.parent.glob(".*.partial")) == []


def test_stage_pending_restore_rejects_manifest_path_that_is_active_database(tmp_path: Path) -> None:
    current = tmp_path / "barbybar.db"
    candidate = tmp_path / "backup.db"
    repo = Repository(current)
    repo.conn.close()
    create_database_backup(current, candidate)
    original = current.read_bytes()

    with pytest.raises(PendingRestoreError, match="manifest cannot replace"):
        stage_pending_restore(
            candidate,
            current_database_path=current,
            manifest_path=current,
        )

    assert current.read_bytes() == original
    assert validate_restore_database(current).path == current.resolve()
