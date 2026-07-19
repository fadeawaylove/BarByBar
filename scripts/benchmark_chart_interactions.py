from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from statistics import median
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from barbybar.domain.models import (
    ActionType,
    ChartDrawing,
    DrawingAnchor,
    DrawingToolType,
    OrderLine,
    OrderLineType,
    SessionAction,
)
from barbybar.ui.chart_widget import ChartWidget
from benchmark_candlestick_cache import build_bars, percentile


def describe(label: str, samples: list[float]) -> None:
    print(
        f"{label} samples={len(samples)} median_ms={median(samples):.2f} "
        f"p95_ms={percentile(samples, 0.95):.2f} max_ms={max(samples):.2f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure large-case pan, zoom, and overlay-settle latency.")
    parser.add_argument("--source-bars", type=int, default=50_000)
    parser.add_argument("--window-bars", type=int, default=2_000)
    parser.add_argument("--drawings", type=int, default=1_000)
    parser.add_argument("--trade-actions", type=int, default=1_000)
    parser.add_argument("--order-lines", type=int, default=20)
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()
    if args.source_bars < args.window_bars or args.window_bars < 240:
        parser.error("--source-bars must be at least --window-bars, and --window-bars must be at least 240")

    app = QApplication.instance() or QApplication([])
    bars = build_bars(args.window_bars)
    global_start = max(0, args.source_bars // 2 - args.window_bars // 2)
    cursor = global_start + args.window_bars // 2
    widget = ChartWidget()
    widget.resize(1460, 920)
    widget.show()
    widget.set_window_data(
        bars,
        cursor=cursor,
        total_count=args.source_bars,
        global_start_index=global_start,
        timeframe="1m",
    )
    drawings = [
        ChartDrawing(
            tool_type=DrawingToolType.RECTANGLE,
            anchors=[
                DrawingAnchor(float(global_start + (index * 17) % args.window_bars), 98.0 + index % 5),
                DrawingAnchor(float(global_start + (index * 17) % args.window_bars + 4), 102.0 + index % 5),
            ],
        )
        for index in range(args.drawings)
    ]
    widget.set_drawings(drawings)
    action_start = datetime(2025, 1, 1, 9, 0)
    actions = [
        SessionAction(
            ActionType.OPEN_LONG if index % 2 == 0 else ActionType.CLOSE,
            global_start + (index * 13) % (args.window_bars // 2 + 1),
            action_start + timedelta(minutes=(index * 13) % (args.window_bars // 2 + 1)),
            price=100.0 + index % 7,
            quantity=1,
        )
        for index in range(args.trade_actions)
    ]
    widget.set_trade_actions(actions)
    widget.set_order_lines(
        [
            OrderLine(
                id=index + 1,
                order_type=OrderLineType.ENTRY_LONG if index % 2 == 0 else OrderLineType.ENTRY_SHORT,
                price=95.0 + index * 0.5,
                quantity=1,
                created_bar_index=cursor,
                active_from_bar_index=cursor + 1,
                created_at=action_start,
            )
            for index in range(args.order_lines)
        ]
    )
    app.processEvents()

    iterations = max(1, args.warmup + args.samples)
    pan_samples: list[float] = []
    for index in range(iterations):
        started = perf_counter()
        widget.pan_x(-1.0 if index % 2 == 0 else 1.0)
        app.processEvents()
        elapsed = (perf_counter() - started) * 1000
        if index >= args.warmup:
            pan_samples.append(elapsed)

    zoom_samples: list[float] = []
    for index in range(iterations):
        started = perf_counter()
        widget.zoom_x(float(cursor), 0.96 if index % 2 == 0 else 1.04)
        app.processEvents()
        elapsed = (perf_counter() - started) * 1000
        if index >= args.warmup:
            zoom_samples.append(elapsed)

    started = perf_counter()
    widget._finish_interactive_viewport()
    for _ in range(4):
        app.processEvents()
    settle_ms = (perf_counter() - started) * 1000

    print(
        f"source=synthetic source_bars={args.source_bars} window_bars={args.window_bars} "
        f"drawings={len(drawings)} trade_actions={len(actions)} order_lines={args.order_lines}"
    )
    describe("pan", pan_samples)
    describe("zoom", zoom_samples)
    print(f"overlay_settle_ms={settle_ms:.2f}")
    widget.close()
    widget.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    main()
