from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from loguru import logger
from PySide6.QtWidgets import QApplication

from barbybar.logging_config import setup_logging
from barbybar.paths import APP_DIR_ENV_VAR
from barbybar.storage.repository import Repository
from barbybar.ui.main_window import MainWindow


def percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * ratio))]


def build_synthetic_session(root: Path, bar_count: int) -> tuple[Path, int]:
    if bar_count < 200:
        raise ValueError("synthetic benchmark requires at least 200 source bars")

    root.mkdir(parents=True, exist_ok=True)
    os.environ[APP_DIR_ENV_VAR] = str(root / "app-data")
    csv_path = root / "synthetic-1m.csv"
    start = datetime(2025, 1, 1, 9, 0)
    lines = ["datetime,open,high,low,close,volume"]
    for index in range(bar_count):
        timestamp = start + timedelta(minutes=index)
        wave = ((index % 80) - 40) * 0.08
        base = 100.0 + index * 0.002 + wave
        close = base + (0.25 if index % 2 == 0 else -0.2)
        lines.append(
            f"{timestamp:%Y-%m-%d %H:%M:%S},{base:.4f},{max(base, close) + 0.5:.4f},"
            f"{min(base, close) - 0.5:.4f},{close:.4f},{1000 + index % 500}"
        )
    csv_path.write_text("\n".join(lines), encoding="utf-8")

    db_path = root / "barbybar-benchmark.db"
    repo = Repository(db_path)
    dataset = repo.import_csv(csv_path, "SYNTH", "1m", display_name=csv_path.name)
    session = repo.create_session(dataset.id or 0, start_index=bar_count // 2, title=f"Synthetic {bar_count}")
    session_id = int(session.id or 0)
    repo.conn.close()
    return db_path, session_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure interactive step-forward latency for an existing session.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--db", type=Path, help="Existing BarByBar database to benchmark.")
    source.add_argument(
        "--synthetic-bars",
        type=int,
        metavar="COUNT",
        help="Build an isolated deterministic 1-minute dataset with COUNT source bars.",
    )
    parser.add_argument("--session", type=int, help="Existing session id; required together with --db.")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()

    temporary_root: TemporaryDirectory[str] | None = None
    if args.db is not None:
        if args.session is None:
            parser.error("--session is required together with --db")
        db_path = args.db
        session_id = args.session
        source_label = f"existing db={db_path} session={session_id}"
    else:
        if args.session is not None:
            parser.error("--session cannot be used together with --synthetic-bars")
        benchmark_parent = Path.cwd() / ".pytest-temp"
        benchmark_parent.mkdir(parents=True, exist_ok=True)
        temporary_root = TemporaryDirectory(prefix="replay-benchmark-", dir=benchmark_parent, ignore_cleanup_errors=True)
        synthetic_bars = int(args.synthetic_bars)
        db_path, session_id = build_synthetic_session(Path(temporary_root.name), synthetic_bars)
        source_label = f"synthetic source_bars={synthetic_bars}"

    setup_logging(db_path.parent / "barbybar-benchmark-logs")
    app = QApplication.instance() or QApplication([])
    repo = Repository(db_path)
    window = MainWindow(repo)
    window.resize(1460, 920)
    window.show()
    deadline = perf_counter() + 10.0
    while window.engine is None and perf_counter() < deadline:
        app.processEvents()
    if window.engine is None:
        raise RuntimeError("session did not load within 10 seconds")
    if window.engine.session.id != session_id:
        window.open_session_by_id(session_id)
        deadline = perf_counter() + 10.0
        while (window.engine is None or window.engine.session.id != session_id) and perf_counter() < deadline:
            app.processEvents()
        if window.engine is None or window.engine.session.id != session_id:
            raise RuntimeError(f"session {session_id} did not load within 10 seconds")

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

    print(f"source={source_label}")
    print(f"samples={len(samples)} median_ms={median(samples):.2f} p95_ms={percentile(samples, 0.95):.2f} max_ms={max(samples):.2f}")
    window.close()
    for _ in range(20):
        app.processEvents()
    window.deleteLater()
    app.processEvents()
    repo.conn.close()
    logger.remove()
    if temporary_root is not None:
        temporary_root.cleanup()


if __name__ == "__main__":
    main()
