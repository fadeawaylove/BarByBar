from __future__ import annotations

import argparse
import os
from pathlib import Path
from statistics import median
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from barbybar.logging_config import setup_logging
from barbybar.storage.repository import Repository
from barbybar.ui.main_window import MainWindow


def percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * ratio))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure interactive step-forward latency for an existing session.")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--session", type=int, required=True)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()

    setup_logging(args.db.parent / "barbybar-benchmark-logs")
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Repository(args.db))
    window.resize(1460, 920)
    window.show()
    window.open_session_by_id(args.session)
    deadline = perf_counter() + 10.0
    while window.engine is None and perf_counter() < deadline:
        app.processEvents()
    if window.engine is None:
        raise RuntimeError("session did not load within 10 seconds")

    # This benchmark isolates the click-to-render path. Persistence capture is
    # measured independently and is coalesced by the application.
    window._enqueue_step_forward_save = lambda _trigger="step_forward": None  # type: ignore[method-assign]
    samples: list[float] = []
    for index in range(max(1, args.warmup + args.steps)):
        started = perf_counter()
        window.step_forward()
        for _ in range(4):
            app.processEvents()
        elapsed_ms = (perf_counter() - started) * 1000
        if index >= args.warmup:
            samples.append(elapsed_ms)

    print(
        f"samples={len(samples)} median_ms={median(samples):.2f} "
        f"p95_ms={percentile(samples, 0.95):.2f} max_ms={max(samples):.2f}"
    )
    window.close()
    window.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    main()
