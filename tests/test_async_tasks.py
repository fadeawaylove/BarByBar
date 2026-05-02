from time import perf_counter

import pytest
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication

from barbybar.ui.async_tasks import AsyncTaskCoordinator


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


@pytest.fixture(scope="module")
def app() -> QApplication:
    return _app()


def _wait_until(app: QApplication, predicate, timeout_s: float = 3.0) -> None:
    started = perf_counter()
    while perf_counter() - started < timeout_s:
        app.processEvents()
        if predicate():
            return
    raise AssertionError("condition did not become true in time")


class _SuccessWorker(QObject):
    finished = Signal(int, object)
    failed = Signal(int, str)

    def run(self) -> None:
        self.finished.emit(1, {"ok": True})


class _FailedWorker(QObject):
    finished = Signal(int, object)
    failed = Signal(int, str)

    def run(self) -> None:
        self.failed.emit(2, "boom")


class _Receiver(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[object] = []
        self.failures: list[str] = []

    @Slot(int, object)
    def handle_finished(self, _token: int, payload: object) -> None:
        self.results.append(payload)

    @Slot(int, str)
    def handle_failed(self, _token: int, message: str) -> None:
        self.failures.append(message)


def test_async_task_coordinator_cleans_up_after_success(app: QApplication) -> None:
    owner = QObject()
    coordinator = AsyncTaskCoordinator(owner, component="test")
    receiver = _Receiver()

    try:
        coordinator.start(
            _SuccessWorker(),
            finished_slot=receiver.handle_finished,
            failed_slot=receiver.handle_failed,
        )
        _wait_until(app, lambda: coordinator.active_thread is None and bool(receiver.results))

        assert receiver.results == [{"ok": True}]
        assert coordinator.active_worker is None
    finally:
        coordinator.shutdown()
        receiver.deleteLater()
        owner.deleteLater()
        app.processEvents()


def test_async_task_coordinator_cleans_up_after_failure(app: QApplication) -> None:
    owner = QObject()
    coordinator = AsyncTaskCoordinator(owner, component="test")
    receiver = _Receiver()

    try:
        coordinator.start(
            _FailedWorker(),
            finished_slot=receiver.handle_finished,
            failed_slot=receiver.handle_failed,
        )
        _wait_until(app, lambda: coordinator.active_thread is None and bool(receiver.failures))

        assert receiver.failures == ["boom"]
        assert coordinator.active_worker is None
    finally:
        coordinator.shutdown()
        receiver.deleteLater()
        owner.deleteLater()
        app.processEvents()


def test_async_task_coordinator_rejects_overlapping_starts(app: QApplication) -> None:
    owner = QObject()
    coordinator = AsyncTaskCoordinator(owner, component="test")

    try:
        coordinator.start(
            _SuccessWorker(),
            finished_slot=lambda *_args: None,
            failed_slot=lambda *_args: None,
        )
        with pytest.raises(RuntimeError):
            coordinator.start(
                _SuccessWorker(),
                finished_slot=lambda *_args: None,
                failed_slot=lambda *_args: None,
            )
        _wait_until(app, lambda: coordinator.active_thread is None)
    finally:
        coordinator.shutdown()
        owner.deleteLater()
        app.processEvents()
