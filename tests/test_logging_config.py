import shutil
from pathlib import Path
from uuid import uuid4

from loguru import logger
from PySide6.QtCore import qWarning

from barbybar.logging_config import setup_logging


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
        logger.complete()

        assert (log_path / "app.log").exists()
        assert (log_path / "error.log").exists()
        assert "hello loguru" in (log_path / "app.log").read_text(encoding="utf-8")
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
