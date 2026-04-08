from __future__ import annotations

import sys
import threading
from pathlib import Path
from traceback import format_exception

from loguru import logger
from PySide6.QtCore import QtMsgType, qInstallMessageHandler

from barbybar import __version__
from barbybar.paths import default_db_path, default_log_dir


LOG_ROTATION = "10 MB"
LOG_RETENTION = "14 days"
LOG_COMPRESSION = "zip"
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "{process.id}:{thread.id} | {name}:{function}:{line} | {message}"
)


def _console_sink():
    for stream in (sys.stderr, sys.stdout):
        if stream is not None:
            return stream
    return None


def app_root_dir() -> Path:
    return default_db_path().parent


def log_dir() -> Path:
    return default_log_dir()


def setup_logging(base_log_dir: str | Path | None = None):
    target_dir = Path(base_log_dir) if base_log_dir else log_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    console_sink = _console_sink()
    if console_sink is not None:
        logger.add(
            console_sink,
            level="DEBUG",
            format=CONSOLE_FORMAT,
            enqueue=False,
            backtrace=False,
            diagnose=False,
        )
    logger.add(
        target_dir / "app.log",
        level="DEBUG",
        format=FILE_FORMAT,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression=LOG_COMPRESSION,
        enqueue=False,
        backtrace=True,
        diagnose=False,
        encoding="utf-8",
    )
    logger.add(
        target_dir / "error.log",
        level="ERROR",
        format=FILE_FORMAT,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression=LOG_COMPRESSION,
        enqueue=False,
        backtrace=True,
        diagnose=False,
        encoding="utf-8",
    )

    _install_exception_hooks()

    logger.bind(event="app_start").info(
        "BarByBar starting version={} python={} db_path={} log_dir={}",
        __version__,
        sys.version.split()[0],
        default_db_path(),
        target_dir,
    )
    return logger


def _install_exception_hooks() -> None:
    def _qt_message_handler(message_type, context, message) -> None:  # noqa: ANN001
        file_name = getattr(context, "file", "") or ""
        line = getattr(context, "line", 0) or 0
        function = getattr(context, "function", "") or ""
        qt_logger = logger.bind(component="qt", qt_file=file_name, qt_line=line, qt_function=function)
        if message_type == QtMsgType.QtDebugMsg:
            qt_logger.debug("Qt message: {}", message)
        elif message_type == QtMsgType.QtInfoMsg:
            qt_logger.info("Qt message: {}", message)
        elif message_type == QtMsgType.QtWarningMsg:
            qt_logger.warning("Qt message: {}", message)
        elif message_type == QtMsgType.QtCriticalMsg:
            qt_logger.error("Qt message: {}", message)
        elif message_type == QtMsgType.QtFatalMsg:
            qt_logger.critical("Qt message: {}", message)
        else:
            qt_logger.warning("Qt message: {}", message)

    def _sys_excepthook(exc_type, exc_value, exc_traceback) -> None:  # noqa: ANN001
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical("Uncaught exception on main thread")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    def _thread_excepthook(args) -> None:  # noqa: ANN001
        if issubclass(args.exc_type, KeyboardInterrupt):
            return
        logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).critical(
            "Uncaught exception on worker thread name={}",
            args.thread.name,
        )

    sys.excepthook = _sys_excepthook
    threading.excepthook = _thread_excepthook
    qInstallMessageHandler(_qt_message_handler)


def log_exception_message(exc: BaseException) -> str:
    return "".join(format_exception(type(exc), exc, exc.__traceback__)).strip()
