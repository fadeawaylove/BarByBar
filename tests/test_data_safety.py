from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from barbybar.storage import data_safety
from barbybar.storage.data_safety import DatabaseBackupError, create_database_backup
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
