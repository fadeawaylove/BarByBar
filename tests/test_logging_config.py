import shutil
import types
from pathlib import Path
from uuid import uuid4

import barbybar.logging_config as logging_config
from loguru import logger
from PySide6.QtCore import qWarning
from PySide6.QtWidgets import QApplication

from barbybar.logging_config import register_fatal_error_handler, setup_logging, unregister_fatal_error_handler


def _case_dir() -> Path:
    root = Path("C:/code/BarByBar/.pytest-temp")
    root.mkdir(exist_ok=True)
    case_dir = root / uuid4().hex
    case_dir.mkdir()
    return case_dir


def test_setup_logging_creates_log_files() -> None:
    case_dir = _case_dir()
    log_path = case_dir / "logs"

    try:
        setup_logging(log_path)
        logger.info("hello loguru")
        logger.debug("debug only")
        logger.complete()

        assert (log_path / "app.log").exists()
        assert (log_path / "debug.log").exists()
        assert (log_path / "error.log").exists()
        assert "hello loguru" in (log_path / "app.log").read_text(encoding="utf-8")
        assert "debug only" not in (log_path / "app.log").read_text(encoding="utf-8")
        assert "debug only" in (log_path / "debug.log").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_setup_logging_writes_exceptions_to_error_log() -> None:
    case_dir = _case_dir()
    log_path = case_dir / "logs"

    try:
        setup_logging(log_path)
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("captured exception")
        logger.complete()

        error_log = (log_path / "error.log").read_text(encoding="utf-8")
        assert "captured exception" in error_log
        assert "ValueError: boom" in error_log
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_setup_logging_captures_qt_messages() -> None:
    case_dir = _case_dir()
    log_path = case_dir / "logs"

    try:
        setup_logging(log_path)
        qWarning("qt warning from test")
        logger.complete()

        app_log = (log_path / "app.log").read_text(encoding="utf-8")
        assert "Qt message: qt warning from test" in app_log
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_setup_logging_handles_windowed_runtime_without_console(monkeypatch) -> None:
    case_dir = _case_dir()
    log_path = case_dir / "logs"

    try:
        monkeypatch.setattr(logging_config.sys, "stderr", None)
        monkeypatch.setattr(logging_config.sys, "stdout", None)
        setup_logging(log_path)
        logger.info("windowed log")
        logger.complete()

        app_log = (log_path / "app.log").read_text(encoding="utf-8")
        assert "windowed log" in app_log
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_sys_excepthook_notifies_registered_fatal_error_handler(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    calls: list[tuple[str, str, str, str]] = []

    def handler(title: str, heading: str, summary: str, detail: str) -> None:
        calls.append((title, heading, summary, detail))

    register_fatal_error_handler(handler)
    try:
        setup_logging(_case_dir() / "logs")
        monkeypatch.setattr(logging_config.sys, "__excepthook__", lambda *args: None)
        try:
            raise ValueError("boom")
        except ValueError as exc:
            logging_config.sys.excepthook(type(exc), exc, exc.__traceback__)
        app.processEvents()
        assert len(calls) == 1
        assert calls[0][0] == "程序异常"
        assert calls[0][1] == "程序出现异常"
        assert "刚才的操作未完成" in calls[0][2]
        assert "ValueError: boom" in calls[0][3]
    finally:
        unregister_fatal_error_handler(handler)


def test_thread_excepthook_notifies_registered_fatal_error_handler(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    calls: list[tuple[str, str, str, str]] = []

    def handler(title: str, heading: str, summary: str, detail: str) -> None:
        calls.append((title, heading, summary, detail))

    register_fatal_error_handler(handler)
    try:
        setup_logging(_case_dir() / "logs")
        monkeypatch.setattr(logging_config.threading, "excepthook", logging_config.threading.excepthook)
        try:
            raise RuntimeError("worker boom")
        except RuntimeError as exc:
            args = types.SimpleNamespace(
                exc_type=type(exc),
                exc_value=exc,
                exc_traceback=exc.__traceback__,
                thread=types.SimpleNamespace(name="loader-thread"),
            )
            logging_config.threading.excepthook(args)
        app.processEvents()
        assert len(calls) == 1
        assert calls[0][1] == "后台任务执行失败"
        assert "后台任务执行失败" in calls[0][2]
        assert "线程：loader-thread" in calls[0][3]
    finally:
        unregister_fatal_error_handler(handler)


def test_fatal_error_dispatch_is_reentrant_guarded() -> None:
    calls: list[str] = []

    def handler(title: str, heading: str, summary: str, detail: str) -> None:
        calls.append(heading)
        logging_config._dispatch_fatal_error_to_ui("程序异常", "重入异常", "summary", "detail")

    register_fatal_error_handler(handler)
    try:
        logging_config._dispatch_fatal_error_to_ui("程序异常", "程序出现异常", "summary", "detail")
        assert calls == ["程序出现异常"]
    finally:
        unregister_fatal_error_handler(handler)
