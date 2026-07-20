from __future__ import annotations

from pathlib import Path

from barbybar import desktop_app
from barbybar.paths import DataLocationError


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

    monkeypatch.setattr(desktop_app, "initialize_data_location", lambda: events.append("location"))
    monkeypatch.setattr(desktop_app, "setup_logging", lambda: _FakeLogger())
    monkeypatch.setattr(desktop_app, "default_db_path", lambda: database_path)
    monkeypatch.setattr(desktop_app, "apply_pending_restore", fake_apply_pending_restore)
    monkeypatch.setattr(desktop_app, "QApplication", FakeApplication)
    monkeypatch.setattr(desktop_app, "Repository", FakeRepository)
    monkeypatch.setattr(desktop_app, "MainWindow", FakeWindow)
    monkeypatch.setattr(desktop_app, "QIcon", lambda _path: object())

    assert desktop_app.main() == 0
    assert events == ["application", "location", "restore", "repository"]


def test_main_stops_before_logging_and_repository_when_data_location_is_unsafe(monkeypatch) -> None:
    events: list[str] = []
    messages: list[tuple[str, str]] = []

    class FakeApplication:
        def __init__(self, _args) -> None:  # noqa: ANN001
            events.append("application")

        def setApplicationName(self, _name: str) -> None:
            return None

    def fail_data_location() -> None:
        events.append("location")
        raise DataLocationError("发现多个数据库")

    monkeypatch.setattr(desktop_app, "QApplication", FakeApplication)
    monkeypatch.setattr(desktop_app, "initialize_data_location", fail_data_location)
    monkeypatch.setattr(
        desktop_app.QMessageBox,
        "critical",
        lambda _parent, title, message: messages.append((title, message)),
    )
    monkeypatch.setattr(desktop_app, "setup_logging", lambda: events.append("logging"))
    monkeypatch.setattr(desktop_app, "Repository", lambda: events.append("repository"))

    assert desktop_app.main() == 2
    assert events == ["application", "location"]
    assert messages and messages[0][0] == "无法确定数据目录"
    assert "没有创建、移动或覆盖任何数据库" in messages[0][1]
