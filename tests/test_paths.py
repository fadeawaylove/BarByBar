from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from barbybar import paths


@pytest.fixture(autouse=True)
def _reset_data_location() -> None:
    paths.configure_data_location(None)
    yield
    paths.configure_data_location(None)


def _create_legacy_database(root: Path, *, populated: bool) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    database_path = root / "barbybar.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE datasets (id INTEGER PRIMARY KEY);
            CREATE TABLE bars (id INTEGER PRIMARY KEY);
            CREATE TABLE sessions (id INTEGER PRIMARY KEY);
            CREATE TABLE trades (id INTEGER PRIMARY KEY);
            CREATE TABLE order_lines (id INTEGER PRIMARY KEY);
            CREATE TABLE drawings (id INTEGER PRIMARY KEY);
            """
        )
        if populated:
            connection.execute("INSERT INTO datasets (id) VALUES (1)")
    return database_path


def test_default_data_root_uses_project_data_dir(monkeypatch) -> None:
    monkeypatch.delenv(paths.APP_DIR_ENV_VAR, raising=False)

    root = paths.default_data_root()

    assert root == Path("C:/code/BarByBar/data")


def test_default_data_root_honors_env_override(monkeypatch, tmp_path: Path) -> None:
    custom_root = tmp_path / "portable-data"
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(custom_root))

    root = paths.default_data_root()

    assert root == custom_root.resolve()
    assert root.exists()


def test_default_ui_settings_path_uses_data_root(monkeypatch, tmp_path: Path) -> None:
    custom_root = tmp_path / "portable-data"
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(custom_root))

    path = paths.default_ui_settings_path()

    assert path == custom_root.resolve() / "ui_settings.json"


def test_default_pending_restore_manifest_path_uses_dedicated_directory(monkeypatch, tmp_path: Path) -> None:
    custom_root = tmp_path / "portable-data"
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(custom_root))

    path = paths.default_pending_restore_manifest_path()

    assert path == custom_root.resolve() / "restore" / "pending_restore.json"
    assert path.parent.is_dir()


def test_default_backup_dir_uses_data_root(monkeypatch, tmp_path: Path) -> None:
    custom_root = tmp_path / "portable-data"
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(custom_root))

    path = paths.default_backup_dir()

    assert path == custom_root.resolve() / "backups"
    assert path.is_dir()


def test_default_exports_dir_uses_data_root(monkeypatch, tmp_path: Path) -> None:
    custom_root = tmp_path / "portable-data"
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(custom_root))

    path = paths.default_exports_dir()

    assert path == custom_root.resolve() / "exports"
    assert path.is_dir()


def test_packaged_fresh_install_uses_stable_user_data_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(paths.APP_DIR_ENV_VAR, raising=False)
    local_app_data = tmp_path / "LocalAppData"

    location = paths.resolve_data_location(
        frozen_root=tmp_path / "new-install",
        local_app_data=local_app_data,
    )

    assert location.root == (local_app_data / "BarByBar" / "data").resolve()
    assert location.source is paths.DataLocationSource.STABLE
    locator = local_app_data / "BarByBar" / paths.DATA_LOCATION_FILENAME
    assert json.loads(locator.read_text(encoding="utf-8"))["data_root"] == str(location.root)


def test_packaged_install_path_change_keeps_adopted_legacy_database(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(paths.APP_DIR_ENV_VAR, raising=False)
    local_app_data = tmp_path / "LocalAppData"
    old_install = tmp_path / "old-install"
    _create_legacy_database(old_install / "data", populated=True)

    first = paths.resolve_data_location(frozen_root=old_install, local_app_data=local_app_data)
    second = paths.resolve_data_location(frozen_root=tmp_path / "new-install", local_app_data=local_app_data)

    assert first.root == (old_install / "data").resolve()
    assert first.source is paths.DataLocationSource.LEGACY
    assert second.root == first.root
    assert second.source is paths.DataLocationSource.LOCATOR


def test_populated_legacy_database_wins_over_empty_decoy(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(paths.APP_DIR_ENV_VAR, raising=False)
    local_app_data = tmp_path / "LocalAppData"
    temporary_install = tmp_path / "temporary-install"
    canonical_root = local_app_data / "Programs" / "BarByBar" / "data"
    _create_legacy_database(temporary_install / "data", populated=False)
    _create_legacy_database(canonical_root, populated=True)

    location = paths.resolve_data_location(
        frozen_root=temporary_install,
        local_app_data=local_app_data,
    )

    assert location.root == canonical_root.resolve()
    assert location.source is paths.DataLocationSource.LEGACY


def test_invalid_locator_does_not_create_replacement_database(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(paths.APP_DIR_ENV_VAR, raising=False)
    local_app_data = tmp_path / "LocalAppData"
    locator = paths.data_location_file_path(local_app_data)
    locator.parent.mkdir(parents=True)
    locator.write_text('{"version": 1, "data_root": "relative-data"}', encoding="utf-8")

    with pytest.raises(paths.DataLocationError, match="绝对目录"):
        paths.resolve_data_location(
            frozen_root=tmp_path / "install",
            local_app_data=local_app_data,
        )

    assert not (local_app_data / "BarByBar" / "data" / "barbybar.db").exists()


def test_packaged_environment_override_has_highest_priority(monkeypatch, tmp_path: Path) -> None:
    override = tmp_path / "explicit-data"
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(override))
    _create_legacy_database(tmp_path / "install" / "data", populated=True)

    location = paths.resolve_data_location(
        frozen_root=tmp_path / "install",
        local_app_data=tmp_path / "LocalAppData",
    )

    assert location.root == override.resolve()
    assert location.source is paths.DataLocationSource.ENVIRONMENT


def test_multiple_populated_legacy_databases_stop_automatic_selection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(paths.APP_DIR_ENV_VAR, raising=False)
    local_app_data = tmp_path / "LocalAppData"
    install_root = tmp_path / "temporary-install"
    canonical_root = local_app_data / "Programs" / "BarByBar" / "data"
    first = _create_legacy_database(install_root / "data", populated=True)
    second = _create_legacy_database(canonical_root, populated=True)

    with pytest.raises(paths.DataLocationConflictError) as exc_info:
        paths.resolve_data_location(
            frozen_root=install_root,
            local_app_data=local_app_data,
        )

    assert {candidate.database_path for candidate in exc_info.value.candidates} == {
        first.resolve(),
        second.resolve(),
    }
    assert not paths.data_location_file_path(local_app_data).exists()
