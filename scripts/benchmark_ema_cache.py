from __future__ import annotations

import argparse
import os
from statistics import median
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from barbybar.ui.chart_widget import ChartWidget
from benchmark_candlestick_cache import build_bars, percentile


def describe(label: str, samples: list[float], calculated_values: int) -> None:
    print(
        f"{label} samples={len(samples)} median_ms={median(samples):.2f} "
        f"p95_ms={percentile(samples, 0.95):.2f} max_ms={max(samples):.2f} "
        f"calculated_values={calculated_values}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare incremental and forced-full EMA cursor updates.")
    parser.add_argument("--bars", type=int, default=50_000)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=2)
    args = parser.parse_args()
    if args.bars < 2:
        parser.error("--bars must be at least 2")

    app = QApplication.instance() or QApplication([])
    bars = build_bars(args.bars)
    incremental_samples: list[float] = []
    forced_full_samples: list[float] = []
    incremental_calculated_values = 0
    forced_full_calculated_values = 0
    iterations = max(1, args.warmup + args.samples)
    for index in range(iterations):
        incremental = ChartWidget()
        incremental._bars = bars
        incremental._chart_timeframe = "1m"
        incremental._sync_ema_curve(len(bars) - 2)
        started = perf_counter()
        incremental._sync_ema_curve(len(bars) - 1)
        incremental_elapsed = (perf_counter() - started) * 1000
        incremental_calculated_values = incremental._last_ema_calculated_values

        forced_full = ChartWidget()
        forced_full._bars = bars
        forced_full._chart_timeframe = "1m"
        forced_full._sync_ema_curve(len(bars) - 2)
        forced_full._ema_cache_key = None
        started = perf_counter()
        forced_full._sync_ema_curve(len(bars) - 1)
        forced_full_elapsed = (perf_counter() - started) * 1000
        forced_full_calculated_values = forced_full._last_ema_calculated_values

        if index >= args.warmup:
            incremental_samples.append(incremental_elapsed)
            forced_full_samples.append(forced_full_elapsed)
        incremental.close()
        incremental.deleteLater()
        forced_full.close()
        forced_full.deleteLater()
        app.processEvents()

    print(f"source=synthetic bars={args.bars} cursor_advance=1")
    describe("incremental", incremental_samples, incremental_calculated_values)
    describe("forced_full", forced_full_samples, forced_full_calculated_values)


if __name__ == "__main__":
    main()
