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
    apply_pending_restore,
    create_database_backup,
    read_pending_restore_manifest,
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


def _dataset_symbols(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try:
        return [str(row[0]) for row in connection.execute("SELECT symbol FROM datasets ORDER BY id")]
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


def test_read_pending_restore_manifest_rejects_path_traversal(tmp_path: Path) -> None:
    manifest = tmp_path / "restore" / "pending_restore.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "sha256": "0" * 64,
                "size_bytes": 1,
                "source_name": "backup.db",
                "staged_at": "2026-07-20T12:00:00+00:00",
                "staged_database": "../outside.db",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(PendingRestoreError, match="unsafe staged database name"):
        read_pending_restore_manifest(manifest)


def test_apply_pending_restore_replaces_database_and_preserves_safety_backup(tmp_path: Path) -> None:
    current = tmp_path / "data" / "barbybar.db"
    selected = tmp_path / "selected.db"
    manifest = tmp_path / "data" / "restore" / "pending_restore.json"
    backup_dir = tmp_path / "data" / "backups"
    current.parent.mkdir(parents=True)
    active_repo = Repository(current)
    active_repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
    active_repo.conn.close()
    selected_repo = Repository(selected)
    selected_repo.import_csv(Path("sample_data/if_sample.csv"), "IH", "1m")
    selected_repo.conn.close()
    staged = stage_pending_restore(
        selected,
        current_database_path=current,
        manifest_path=manifest,
    )

    result = apply_pending_restore(
        current_database_path=current,
        manifest_path=manifest,
        backup_dir=backup_dir,
    )

    assert result is not None
    assert result.database_path == current.resolve()
    assert result.safety_backup_path is not None
    assert result.safety_backup_path.parent == backup_dir.resolve()
    assert result.cleanup_warning is None
    assert _dataset_symbols(current) == ["IH"]
    assert _dataset_symbols(result.safety_backup_path) == ["IF"]
    assert not manifest.exists()
    assert not staged.staged_database_path.exists()
    assert list(current.parent.glob(".*.restore-ready")) == []


def test_apply_pending_restore_rejects_tampered_staged_database_and_keeps_current(tmp_path: Path) -> None:
    current = tmp_path / "barbybar.db"
    selected = tmp_path / "selected.db"
    manifest = tmp_path / "restore" / "pending_restore.json"
    active_repo = Repository(current)
    active_repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
    active_repo.conn.close()
    selected_repo = Repository(selected)
    selected_repo.import_csv(Path("sample_data/if_sample.csv"), "IH", "1m")
    selected_repo.conn.close()
    staged = stage_pending_restore(
        selected,
        current_database_path=current,
        manifest_path=manifest,
    )
    with staged.staged_database_path.open("ab") as handle:
        handle.write(b"tampered")

    with pytest.raises(PendingRestoreError, match="no longer matches"):
        apply_pending_restore(
            current_database_path=current,
            manifest_path=manifest,
            backup_dir=tmp_path / "backups",
        )

    assert _dataset_symbols(current) == ["IF"]
    assert manifest.exists()
    assert staged.staged_database_path.exists()
    assert list((tmp_path / "backups").glob("*.db")) == []


def test_apply_pending_restore_keeps_current_when_atomic_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = tmp_path / "data" / "barbybar.db"
    selected = tmp_path / "selected.db"
    manifest = tmp_path / "data" / "restore" / "pending_restore.json"
    backup_dir = tmp_path / "data" / "backups"
    current.parent.mkdir(parents=True)
    active_repo = Repository(current)
    active_repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
    active_repo.conn.close()
    selected_repo = Repository(selected)
    selected_repo.import_csv(Path("sample_data/if_sample.csv"), "IH", "1m")
    selected_repo.conn.close()
    staged = stage_pending_restore(
        selected,
        current_database_path=current,
        manifest_path=manifest,
    )
    real_replace = data_safety.os.replace

    def fail_current_replace(source: str | Path, target: str | Path) -> None:
        if Path(target).resolve() == current.resolve():
            raise OSError("forced atomic replace failure")
        real_replace(source, target)

    monkeypatch.setattr(data_safety.os, "replace", fail_current_replace)

    with pytest.raises(PendingRestoreError, match="forced atomic replace failure"):
        apply_pending_restore(
            current_database_path=current,
            manifest_path=manifest,
            backup_dir=backup_dir,
        )

    assert _dataset_symbols(current) == ["IF"]
    assert _dataset_symbols(next(backup_dir.glob("pre-restore-*.db"))) == ["IF"]
    assert manifest.exists()
    assert staged.staged_database_path.exists()
    assert list(current.parent.glob(".*.restore-ready")) == []


def test_apply_pending_restore_keeps_current_when_safety_backup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = tmp_path / "barbybar.db"
    selected = tmp_path / "selected.db"
    manifest = tmp_path / "restore" / "pending_restore.json"
    active_repo = Repository(current)
    active_repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
    active_repo.conn.close()
    selected_repo = Repository(selected)
    selected_repo.import_csv(Path("sample_data/if_sample.csv"), "IH", "1m")
    selected_repo.conn.close()
    staged = stage_pending_restore(
        selected,
        current_database_path=current,
        manifest_path=manifest,
    )
    real_create_backup = data_safety.create_database_backup

    def fail_current_backup(source: str | Path, target: str | Path):  # noqa: ANN202
        if Path(source).resolve() == current.resolve():
            raise DatabaseBackupError("forced safety backup failure")
        return real_create_backup(source, target)

    monkeypatch.setattr(data_safety, "create_database_backup", fail_current_backup)

    with pytest.raises(PendingRestoreError, match="forced safety backup failure"):
        apply_pending_restore(
            current_database_path=current,
            manifest_path=manifest,
            backup_dir=tmp_path / "backups",
        )

    assert _dataset_symbols(current) == ["IF"]
    assert manifest.exists()
    assert staged.staged_database_path.exists()
    assert list(current.parent.glob(".*.restore-ready")) == []


def test_apply_pending_restore_returns_none_without_manifest(tmp_path: Path) -> None:
    assert (
        apply_pending_restore(
            current_database_path=tmp_path / "barbybar.db",
            manifest_path=tmp_path / "missing.json",
            backup_dir=tmp_path / "backups",
        )
        is None
    )
