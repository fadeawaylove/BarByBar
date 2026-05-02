from __future__ import annotations

from collections.abc import Callable

from loguru import logger
from PySide6.QtCore import QObject, QThread, Qt


class AsyncTaskCoordinator(QObject):
    def __init__(self, owner: QObject, *, component: str, shutdown_timeout_ms: int = 2000) -> None:
        super().__init__(owner)
        self.component = component
        self.shutdown_timeout_ms = shutdown_timeout_ms
        self.active_thread: QThread | None = None
        self.active_worker: QObject | None = None
        self._thread_finished_callback: Callable[[], None] | None = None

    def is_running(self) -> bool:
        return self.active_thread is not None and self.active_thread.isRunning()

    def start(
        self,
        worker: QObject,
        *,
        finished_slot: Callable[..., None],
        failed_slot: Callable[..., None],
        thread_finished_slot: Callable[[], None] | None = None,
    ) -> QThread:
        if self.is_running():
            raise RuntimeError(f"{self.component} task is already running")
        thread = QThread(self.parent())
        worker.moveToThread(thread)
        thread.started.connect(worker.run)  # type: ignore[attr-defined]
        worker.finished.connect(finished_slot, Qt.ConnectionType.QueuedConnection)  # type: ignore[attr-defined]
        worker.failed.connect(failed_slot, Qt.ConnectionType.QueuedConnection)  # type: ignore[attr-defined]
        worker.finished.connect(thread.quit)  # type: ignore[attr-defined]
        worker.failed.connect(thread.quit)  # type: ignore[attr-defined]
        worker.finished.connect(worker.deleteLater)  # type: ignore[attr-defined]
        worker.failed.connect(worker.deleteLater)  # type: ignore[attr-defined]
        thread.finished.connect(lambda thread=thread: self._handle_thread_finished(thread))
        self.active_thread = thread
        self.active_worker = worker
        self._thread_finished_callback = thread_finished_slot
        thread.start()
        return thread

    def shutdown(self) -> None:
        if self.active_thread is None or not self.active_thread.isRunning():
            return
        logger.bind(component=self.component).warning("event=close_waiting_for_async_task")
        self.active_thread.quit()
        self.active_thread.wait(self.shutdown_timeout_ms)

    def _handle_thread_finished(self, thread: QThread) -> None:
        if thread is not self.active_thread:
            logger.bind(component=self.component).debug("event=ignore_stale_async_task_thread_finished")
            return
        self.active_thread = None
        self.active_worker = None
        callback = self._thread_finished_callback
        self._thread_finished_callback = None
        if callback is not None:
            callback()
        thread.deleteLater()
