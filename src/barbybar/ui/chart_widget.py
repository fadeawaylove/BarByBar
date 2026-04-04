from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor

import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPicture
from PySide6.QtWidgets import QVBoxLayout, QWidget

from barbybar.domain.models import Bar

UP_CANDLE_COLOR = "#d84a4a"
DOWN_CANDLE_COLOR = "#2e9f5b"


@dataclass(slots=True)
class DrawnLine:
    start: QPointF
    end: QPointF


@dataclass(slots=True)
class ViewportState:
    bars_in_view: int = 120
    min_bars_in_view: int = 20
    max_bars_in_view: int = 200
    right_edge_index: float = 0.0
    follow_latest: bool = True


class CandlestickItem(pg.GraphicsObject):
    def __init__(self) -> None:
        super().__init__()
        self._bars: list[Bar] = []
        self._cursor = -1
        self._picture = QPicture()
        self._bounding_rect = pg.QtCore.QRectF()

    def set_data(self, bars: list[Bar], cursor: int) -> None:
        self.prepareGeometryChange()
        self._bars = bars
        self._cursor = cursor
        self._rebuild_picture()
        self.update()

    def _rebuild_picture(self) -> None:
        picture = QPicture()
        painter = QPainter(picture)
        wick_pen = pg.mkPen("#d5d7db")
        width = 0.35
        min_price = None
        max_price = None
        stop = min(len(self._bars), self._cursor + 1)
        for index in range(stop):
            bar = self._bars[index]
            bullish = bar.close >= bar.open
            brush = pg.mkBrush(UP_CANDLE_COLOR if bullish else DOWN_CANDLE_COLOR)
            painter.setPen(wick_pen)
            painter.drawLine(pg.QtCore.QPointF(index, bar.low), pg.QtCore.QPointF(index, bar.high))
            painter.setBrush(brush)
            painter.drawRect(
                pg.QtCore.QRectF(
                    index - width,
                    min(bar.open, bar.close),
                    width * 2,
                    max(abs(bar.close - bar.open), 0.001),
                )
            )
            min_price = bar.low if min_price is None else min(min_price, bar.low)
            max_price = bar.high if max_price is None else max(max_price, bar.high)
        painter.end()
        self._picture = picture
        if self._bars:
            low = min_price if min_price is not None else 0.0
            high = max_price if max_price is not None else 1.0
            self._bounding_rect = pg.QtCore.QRectF(-2.0, low, len(self._bars) + 4.0, max(high - low, 1.0))
        else:
            self._bounding_rect = pg.QtCore.QRectF()

    def paint(self, painter: QPainter, *args) -> None:
        painter.drawPicture(0, 0, self._picture)

    def boundingRect(self):
        return self._bounding_rect


class CandleViewBox(pg.ViewBox):
    def __init__(self, chart: "ChartWidget") -> None:
        super().__init__(enableMenu=False)
        self.chart = chart
        self.setMouseEnabled(x=False, y=False)

    def wheelEvent(self, ev, axis=None) -> None:  # noqa: ANN001
        if self.chart.draw_mode:
            ev.ignore()
            return
        delta = ev.delta() if hasattr(ev, "delta") else ev.angleDelta().y()
        if delta == 0:
            ev.ignore()
            return
        anchor = self.mapSceneToView(ev.scenePos()).x()
        scale = 0.85 if delta > 0 else 1.18
        self.chart.zoom_x(anchor_x=anchor, scale=scale)
        ev.accept()

    def mouseDragEvent(self, ev, axis=None) -> None:  # noqa: ANN001
        if self.chart.draw_mode:
            ev.ignore()
            return
        if ev.button() != Qt.MouseButton.LeftButton:
            super().mouseDragEvent(ev, axis=axis)
            return
        ev.accept()
        if ev.isFinish():
            return
        current = self.mapSceneToView(ev.scenePos())
        last = self.mapSceneToView(ev.lastScenePos())
        self.chart.pan_x(last.x() - current.x())

    def mouseDoubleClickEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.chart.reset_viewport(follow_latest=True)
            ev.accept()
            return
        super().mouseDoubleClickEvent(ev)


class ChartWidget(QWidget):
    lineAdded = Signal()
    viewportChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._bars: list[Bar] = []
        self._cursor = -1
        self._draw_mode = False
        self._line_start: QPointF | None = None
        self._drawn_lines: list[DrawnLine] = []
        self._viewport = ViewportState()
        self._right_padding = 3.0
        self._left_padding = 3.0
        self._is_applying_viewport = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.graphics = pg.GraphicsLayoutWidget()
        self.view_box = CandleViewBox(self)
        self.price_plot = self.graphics.addPlot(row=0, col=0, viewBox=self.view_box)
        self.price_plot.showGrid(x=True, y=True, alpha=0.2)
        self.price_plot.setMenuEnabled(False)
        self.price_plot.setLabel("left", "Price")
        self.price_plot.setLabel("bottom", "Bar")
        self.price_plot.getAxis("bottom").setStyle(showValues=False)
        self.price_plot.hideButtons()
        self.view_box.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=False)
        self.price_plot.enableAutoRange(axis="xy", enable=False)

        self._candles = CandlestickItem()
        self._ema_curve = pg.PlotDataItem([], [], connect="finite", pen=pg.mkPen("#f4c95d", width=2))
        self.price_plot.addItem(self._candles)
        self.price_plot.addItem(self._ema_curve)

        layout.addWidget(self.graphics)
        self.graphics.scene().sigMouseClicked.connect(self._handle_scene_click)

    @property
    def draw_mode(self) -> bool:
        return self._draw_mode

    @property
    def viewport_state(self) -> ViewportState:
        return self._viewport

    def set_draw_mode(self, enabled: bool) -> None:
        self._draw_mode = enabled
        self._line_start = None

    def set_full_data(self, bars: list[Bar]) -> None:
        self._bars = list(bars)
        self._cursor = len(self._bars) - 1 if self._bars else -1
        self._viewport.max_bars_in_view = max(200, len(self._bars))
        self._viewport.bars_in_view = min(max(120, self._viewport.min_bars_in_view), self._viewport.max_bars_in_view)
        self._drawn_lines.clear()
        self._sync_plot_data()
        self.reset_viewport(follow_latest=True)

    def set_cursor(self, index: int) -> None:
        if not self._bars:
            self._cursor = -1
            self._sync_plot_data()
            return
        self._cursor = max(0, min(index, len(self._bars) - 1))
        self._sync_plot_data()
        if self._viewport.follow_latest:
            self._viewport.right_edge_index = self._cursor + 1
        self._apply_viewport()

    def reset_viewport(self, follow_latest: bool = True) -> None:
        self._viewport.follow_latest = follow_latest
        self._viewport.bars_in_view = min(max(120, self._viewport.min_bars_in_view), self._viewport.max_bars_in_view)
        self._viewport.right_edge_index = self._cursor + 1 if self._cursor >= 0 else 0.0
        self._apply_viewport()

    def zoom_x(self, anchor_x: float, scale: float) -> None:
        if self._cursor < 0:
            return
        old_bars = self._viewport.bars_in_view
        new_bars = int(round(old_bars * scale))
        new_bars = max(self._viewport.min_bars_in_view, min(new_bars, self._viewport.max_bars_in_view))
        if new_bars == old_bars:
            return
        old_left = self._viewport.right_edge_index - old_bars
        ratio = 0.0 if old_bars == 0 else (anchor_x - old_left) / old_bars
        ratio = min(max(ratio, 0.0), 1.0)
        new_left = anchor_x - ratio * new_bars
        self._viewport.bars_in_view = new_bars
        self._viewport.right_edge_index = new_left + new_bars
        self._viewport.follow_latest = self._is_near_latest(self._viewport.right_edge_index)
        self._apply_viewport()

    def pan_x(self, delta_bars: float) -> None:
        if self._cursor < 0:
            return
        self._viewport.right_edge_index += delta_bars
        self._viewport.follow_latest = self._is_near_latest(self._viewport.right_edge_index)
        self._apply_viewport()

    def clear_lines(self) -> None:
        self._drawn_lines.clear()
        self._sync_plot_data()
        self._apply_viewport()

    def current_x_range(self) -> tuple[float, float]:
        return self.price_plot.viewRange()[0]

    def _sync_plot_data(self) -> None:
        self._candles.set_data(self._bars, self._cursor)
        x_values = []
        ema_values = []
        closes = [bar.close for bar in self._bars[: self._cursor + 1]]
        ema_prefix = self._ema(closes, period=20)
        for index in range(self._cursor + 1):
            x_values.append(index)
            ema_values.append(ema_prefix[index])
        self._ema_curve.setData(x=x_values, y=ema_values)
        self._rebuild_line_items()

    def _rebuild_line_items(self) -> None:
        for item in list(self.price_plot.items):
            if getattr(item, "_barbybar_line", False):
                self.price_plot.removeItem(item)
        for line in self._drawn_lines:
            item = pg.PlotCurveItem(
                [line.start.x(), line.end.x()],
                [line.start.y(), line.end.y()],
                pen=pg.mkPen("#ff9f1c", width=2),
            )
            item._barbybar_line = True
            self.price_plot.addItem(item)

    def _apply_viewport(self) -> None:
        if not self._bars or self._is_applying_viewport:
            return
        self._is_applying_viewport = True
        try:
            if self._viewport.follow_latest:
                self._viewport.right_edge_index = self._cursor + 1
            self._clamp_viewport()
            left = self._viewport.right_edge_index - self._viewport.bars_in_view
            right = self._viewport.right_edge_index + self._right_padding
            self.price_plot.setXRange(left, right, padding=0)
            self._apply_y_range(left, self._viewport.right_edge_index)
        finally:
            self._is_applying_viewport = False
        self.viewportChanged.emit()

    def _clamp_viewport(self) -> None:
        min_right = self._viewport.bars_in_view - self._left_padding
        max_right = max(self._cursor + 1, 0) if self._viewport.follow_latest else (len(self._bars) - 1 + self._right_padding)
        self._viewport.right_edge_index = min(max(self._viewport.right_edge_index, min_right), max_right)

    def _apply_y_range(self, left: float, right_edge: float) -> None:
        window = self._revealed_window_bars(left, right_edge)
        if not window:
            return
        low = min(bar.low for _, bar in window)
        high = max(bar.high for _, bar in window)
        height = max(high - low, max(abs(high) * 0.01, 1.0))
        padding = max(height * 0.06, 0.5)
        self.price_plot.setYRange(low - padding, high + padding, padding=0)

    def _revealed_window_bars(self, left: float, right_edge: float) -> list[tuple[int, Bar]]:
        if self._cursor < 0:
            return []
        start = max(0, int(floor(left)))
        stop = min(self._cursor + 1, int(ceil(right_edge)))
        if start >= stop:
            start = max(0, min(self._cursor, int(floor(right_edge)) - 1))
            stop = min(self._cursor + 1, start + 1)
        return [(index, self._bars[index]) for index in range(start, stop)]

    def _handle_scene_click(self, event) -> None:  # noqa: ANN001
        if not self._draw_mode or self._cursor < 0:
            return
        pos = event.scenePos()
        if not self.price_plot.sceneBoundingRect().contains(pos):
            return
        point = self.price_plot.vb.mapSceneToView(pos)
        if self._line_start is None:
            self._line_start = point
            return
        self._drawn_lines.append(DrawnLine(start=self._line_start, end=point))
        self._line_start = None
        self._sync_plot_data()
        self._apply_viewport()
        self.lineAdded.emit()

    def _is_near_latest(self, right_edge_index: float) -> bool:
        return abs((self._cursor + 1) - right_edge_index) <= max(1.0, self._right_padding)

    @staticmethod
    def _ema(values: list[float], period: int) -> list[float]:
        if not values:
            return []
        multiplier = 2 / (period + 1)
        ema_values = [values[0]]
        for price in values[1:]:
            ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
        return ema_values
