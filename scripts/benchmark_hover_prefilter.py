from __future__ import annotations

import argparse
import os
from datetime import datetime
from statistics import median
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from barbybar.domain.models import ActionType, ChartDrawing, DrawingAnchor, DrawingToolType, SessionAction
from barbybar.ui.chart_widget import ChartWidget, TradeLink, TradeMarker
from benchmark_candlestick_cache import build_bars, percentile


def describe(label: str, samples: list[float]) -> None:
    print(
        f"{label} samples={len(samples)} median_ms={median(samples):.3f} "
        f"p95_ms={percentile(samples, 0.95):.3f} max_ms={max(samples):.3f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare cached and forced hover viewport prefiltering.")
    parser.add_argument("--objects", type=int, default=10_000)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=5)
    args = parser.parse_args()
    if args.objects < 1:
        parser.error("--objects must be positive")

    app = QApplication.instance() or QApplication([])
    widget = ChartWidget()
    widget.resize(900, 600)
    widget.show()
    bars = build_bars(240)
    widget.set_full_data(bars)
    widget.set_cursor(180)
    app.processEvents()

    far_drawings = [
        ChartDrawing(
            tool_type=DrawingToolType.RECTANGLE,
            anchors=[DrawingAnchor(1000.0 + index * 3.0, 99.0), DrawingAnchor(1002.0 + index * 3.0, 103.0)],
        )
        for index in range(args.objects)
    ]
    visible_drawing = ChartDrawing(
        tool_type=DrawingToolType.RECTANGLE,
        anchors=[DrawingAnchor(120.0, 99.0), DrawingAnchor(124.0, 103.0)],
    )
    action = SessionAction(ActionType.OPEN_LONG, 0, datetime(2025, 1, 1, 9, 0), price=101.0, quantity=1)
    widget._drawings = [*far_drawings, visible_drawing]
    widget._trade_markers = [
        TradeMarker(action, None, "entry", "long", "pending", 1000.0 + index * 3.0, 101.0, "t", "#000000", 8.0, [])
        for index in range(args.objects)
    ]
    widget._trade_links = [
        TradeLink(None, "long", "pending", 1000.0 + index * 3.0, 100.0, 1002.0 + index * 3.0, 102.0, 0.0, [])
        for index in range(args.objects)
    ]
    widget._invalidate_hover_hit_test_candidates()
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(122.0, 101.0))
    widget._hover_hit_test_candidates()

    cached_samples: list[float] = []
    forced_samples: list[float] = []
    iterations = max(1, args.warmup + args.samples)
    for index in range(iterations):
        started = perf_counter()
        cached_hit = widget._drawing_at_scene_pos(scene_pos)
        cached_elapsed = (perf_counter() - started) * 1000

        widget._hover_hit_test_signature = None
        widget._hover_hit_test_candidates_cache = None
        started = perf_counter()
        forced_hit = widget._drawing_at_scene_pos(scene_pos)
        forced_elapsed = (perf_counter() - started) * 1000
        if cached_hit is None or forced_hit is None:
            raise RuntimeError("visible drawing was not selected")
        if index >= args.warmup:
            cached_samples.append(cached_elapsed)
            forced_samples.append(forced_elapsed)

    candidates = widget._hover_hit_test_candidates_cache
    print(
        f"source=synthetic drawings={len(widget._drawings)} markers={len(widget._trade_markers)} "
        f"links={len(widget._trade_links)} candidate_drawings={len(candidates.drawings) if candidates else -1}"
    )
    describe("cached_hit_test", cached_samples)
    describe("forced_prefilter_hit_test", forced_samples)
    widget.close()
    widget.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    main()
