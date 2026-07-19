from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from statistics import median
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from barbybar.domain.models import Bar
from barbybar.ui.chart_widget import CandlestickItem


def percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * ratio))]


def build_bars(count: int) -> list[Bar]:
    start = datetime(2025, 1, 1, 9, 0)
    bars: list[Bar] = []
    for index in range(count):
        base = 100.0 + index * 0.002 + ((index % 80) - 40) * 0.08
        close = base + (0.25 if index % 2 == 0 else -0.2)
        bars.append(
            Bar(
                timestamp=start + timedelta(minutes=index),
                open=base,
                high=max(base, close) + 0.5,
                low=min(base, close) - 0.5,
                close=close,
                volume=1000 + index % 500,
            )
        )
    return bars


def describe(label: str, samples: list[float], rebuilt_chunks: int) -> None:
    print(
        f"{label} samples={len(samples)} median_ms={median(samples):.2f} "
        f"p95_ms={percentile(samples, 0.95):.2f} max_ms={max(samples):.2f} "
        f"rebuilt_chunks={rebuilt_chunks}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare cached and forced-full candlestick window extension.")
    parser.add_argument("--bars", type=int, default=50_000)
    parser.add_argument("--extend-before", type=int, default=256)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=2)
    args = parser.parse_args()
    if args.bars <= args.extend_before or args.extend_before <= 0:
        parser.error("--bars must be greater than --extend-before, and --extend-before must be positive")

    app = QApplication.instance() or QApplication([])
    bars = build_bars(args.bars)
    cached_samples: list[float] = []
    forced_full_samples: list[float] = []
    cached_rebuilt_chunks = 0
    forced_full_rebuilt_chunks = 0
    iterations = max(1, args.warmup + args.samples)
    for index in range(iterations):
        cached = CandlestickItem()
        cached.set_data(
            bars[args.extend_before :],
            cursor=len(bars) - args.extend_before - 1,
            global_start_index=args.extend_before,
        )
        started = perf_counter()
        cached.set_data(bars, cursor=len(bars) - 1, global_start_index=0)
        cached_elapsed = (perf_counter() - started) * 1000
        cached_rebuilt_chunks = len(cached._last_rebuilt_chunk_starts)

        forced_full = CandlestickItem()
        forced_full.set_data(
            bars[args.extend_before :],
            cursor=len(bars) - args.extend_before - 1,
            global_start_index=args.extend_before,
        )
        forced_full._picture_render_signature = None
        started = perf_counter()
        forced_full.set_data(bars, cursor=len(bars) - 1, global_start_index=0)
        forced_full_elapsed = (perf_counter() - started) * 1000
        forced_full_rebuilt_chunks = len(forced_full._last_rebuilt_chunk_starts)

        if index >= args.warmup:
            cached_samples.append(cached_elapsed)
            forced_full_samples.append(forced_full_elapsed)
        cached.deleteLater()
        forced_full.deleteLater()
        app.processEvents()

    print(f"source=synthetic bars={args.bars} extend_before={args.extend_before}")
    describe("cached_extension", cached_samples, cached_rebuilt_chunks)
    describe("forced_full_extension", forced_full_samples, forced_full_rebuilt_chunks)


if __name__ == "__main__":
    main()
