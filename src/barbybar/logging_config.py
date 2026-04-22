from __future__ import annotations

import sys
import threading
import weakref
from pathlib import Path
from traceback import format_exception

from loguru import logger
from PySide6.QtCore import QObject, QtMsgType, Signal, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

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
_fatal_error_handler_ref: weakref.ReferenceType | None = None
_fatal_error_dialog_active = False
_fatal_error_lock = threading.Lock()
_fatal_error_bridge: "_FatalErrorBridge | None" = None


def _console_sink():
    for stream in (sys.stderr, sys.stdout):
        if stream is not None:
            return stream
    return None


def app_root_dir() -> Path:
    return default_db_path().parent


def log_dir() -> Path:
    return default_log_dir()


class _FatalErrorBridge(QObject):
    fatal_error = Signal(str, str, str, str)

    def __init__(self) -> None:
        super().__init__()
        self.fatal_error.connect(_dispatch_fatal_error_to_ui)


def register_fatal_error_handler(handler) -> None:
    global _fatal_error_handler_ref
    if hasattr(handler, "__self__") and hasattr(handler, "__func__"):
        _fatal_error_handler_ref = weakref.WeakMethod(handler)
    else:
        _fatal_error_handler_ref = weakref.ref(handler)
    _ensure_fatal_error_bridge()


def unregister_fatal_error_handler(handler) -> None:
    global _fatal_error_handler_ref
    current = _resolve_fatal_error_handler()
    if current is None:
        return
    if current is handler:
        _fatal_error_handler_ref = None
        return
    if (
        hasattr(current, "__self__")
        and hasattr(current, "__func__")
        and hasattr(handler, "__self__")
        and hasattr(handler, "__func__")
        and current.__self__ is handler.__self__
        and current.__func__ is handler.__func__
    ):
        _fatal_error_handler_ref = None


def _resolve_fatal_error_handler():
    if _fatal_error_handler_ref is None:
        return None
    return _fatal_error_handler_ref()


def _ensure_fatal_error_bridge() -> _FatalErrorBridge | None:
    global _fatal_error_bridge
    app = QApplication.instance()
    if app is None:
        return None
    if _fatal_error_bridge is None:
        _fatal_error_bridge = _FatalErrorBridge()
        _fatal_error_bridge.moveToThread(app.thread())
    return _fatal_error_bridge


def _fatal_error_summary(source: str) -> str:
    if source == "worker":
        return "后台任务执行失败，刚才的操作未完成。请重试；若持续出现，请反馈问题。"
    return "刚才的操作未完成，请重试；若持续出现，请反馈问题。"


def _notify_unhandled_exception(source: str, exc: BaseException | None, *, thread_name: str = "") -> None:
    bridge = _ensure_fatal_error_bridge()
    if bridge is None:
        return
    exc_name = type(exc).__name__ if exc is not None else "UnknownError"
    exc_message = str(exc).strip() if exc is not None else ""
    heading = "后台任务执行失败" if source == "worker" else "程序出现异常"
    detail_lines = [f"{exc_name}: {exc_message or '未提供异常信息'}"]
    if thread_name:
        detail_lines.append(f"线程：{thread_name}")
    detail_lines.append(f"详情已写入 {log_dir() / 'error.log'}")
    detail_lines.append(f"调试信息见 {log_dir() / 'debug.log'}")
    bridge.fatal_error.emit("程序异常", heading, _fatal_error_summary(source), "\n".join(detail_lines))


def _dispatch_fatal_error_to_ui(title: str, heading: str, summary: str, detail: str) -> None:
    global _fatal_error_dialog_active
    handler = _resolve_fatal_error_handler()
    if handler is None:
        return
    with _fatal_error_lock:
        if _fatal_error_dialog_active:
            return
        _fatal_error_dialog_active = True
    try:
        handler(title, heading, summary, detail)
    except Exception as exc:  # noqa: BLE001
        logger.exception("event=fatal_error_dialog_failed error={}", str(exc))
    finally:
        with _fatal_error_lock:
            _fatal_error_dialog_active = False


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
        level="INFO",
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
        target_dir / "debug.log",
        level="DEBUG",
        format=FILE_FORMAT,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression=LOG_COMPRESSION,
        enqueue=False,
        backtrace=True,
        diagnose=False,
        encoding="utf-8",
        filter=lambda record: record["level"].no < 20,
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
        _notify_unhandled_exception("main", exc_value)
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    def _thread_excepthook(args) -> None:  # noqa: ANN001
        if issubclass(args.exc_type, KeyboardInterrupt):
            return
        logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).critical(
            "Uncaught exception on worker thread name={}",
            args.thread.name,
        )
        _notify_unhandled_exception("worker", args.exc_value, thread_name=args.thread.name)

    sys.excepthook = _sys_excepthook
    threading.excepthook = _thread_excepthook
    qInstallMessageHandler(_qt_message_handler)


def log_exception_message(exc: BaseException) -> str:
    return "".join(format_exception(type(exc), exc, exc.__traceback__)).strip()
