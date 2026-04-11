from __future__ import annotations

from pathlib import Path

from barbybar import paths


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
