from __future__ import annotations

from pathlib import Path

from barbybar import desktop_app


class _FakeLogger:
    def bind(self, **_context):  # noqa: ANN003, ANN201
        return self

    def info(self, *_args):  # noqa: ANN002, ANN201
        return None

    def warning(self, *_args):  # noqa: ANN002, ANN201
        return None

    def exception(self, *_args):  # noqa: ANN002, ANN201
        return None


def test_main_applies_pending_restore_before_repository_creation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    database_path = tmp_path / "barbybar.db"

    class FakeApplication:
        def __init__(self, _args) -> None:  # noqa: ANN001
            events.append("application")

        def setApplicationName(self, _name: str) -> None:
            return None

        def setWindowIcon(self, _icon) -> None:  # noqa: ANN001
            return None

        def exec(self) -> int:
            return 0

    class FakeRepository:
        def __init__(self) -> None:
            events.append("repository")

    class FakeWindow:
        def __init__(self, _repo) -> None:  # noqa: ANN001
            return None

        def setWindowIcon(self, _icon) -> None:  # noqa: ANN001
            return None

        def resize(self, _width: int, _height: int) -> None:
            return None

        def show(self) -> None:
            return None

    def fake_apply_pending_restore(**kwargs):  # noqa: ANN003, ANN201
        assert kwargs["current_database_path"] == database_path
        events.append("restore")
        return None

    monkeypatch.setattr(desktop_app, "setup_logging", lambda: _FakeLogger())
    monkeypatch.setattr(desktop_app, "default_db_path", lambda: database_path)
    monkeypatch.setattr(desktop_app, "apply_pending_restore", fake_apply_pending_restore)
    monkeypatch.setattr(desktop_app, "QApplication", FakeApplication)
    monkeypatch.setattr(desktop_app, "Repository", FakeRepository)
    monkeypatch.setattr(desktop_app, "MainWindow", FakeWindow)
    monkeypatch.setattr(desktop_app, "QIcon", lambda _path: object())

    assert desktop_app.main() == 0
    assert events == ["restore", "application", "repository"]
