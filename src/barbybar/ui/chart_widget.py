from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from math import ceil, floor

import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainter, QPicture
from PySide6.QtWidgets import QFrame, QLabel, QLayout, QMenu, QVBoxLayout, QWidget

from barbybar.domain.models import Bar, OrderLine, OrderLineType

UP_CANDLE_COLOR = "#d84a4a"
DOWN_CANDLE_COLOR = "#1f8b24"
SESSION_MARKER_COLOR = "#d6dde6"
SESSION_OPEN_TIMES = (time(9, 0), time(21, 0))
EMA_LINE_COLOR = "#d84a4a"
ENTRY_LONG_LINE_COLOR = "#2979ff"
ENTRY_SHORT_LINE_COLOR = "#ff9f1c"
STOP_LOSS_LINE_COLOR = "#d84a4a"
TAKE_PROFIT_LINE_COLOR = "#1f8b24"
AVERAGE_PRICE_LINE_COLOR = "#5f6b7a"


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
        self._global_start_index = 0
        self._picture = QPicture()
        self._bounding_rect = pg.QtCore.QRectF()

    def set_data(self, bars: list[Bar], cursor: int, global_start_index: int = 0) -> None:
        self.prepareGeometryChange()
        self._bars = bars
        self._cursor = cursor
        self._global_start_index = global_start_index
        self._rebuild_picture()
        self.update()

    def _rebuild_picture(self) -> None:
        picture = QPicture()
        painter = QPainter(picture)
        width = 0.35
        min_price = None
        max_price = None
        stop = min(len(self._bars), self._cursor + 1)
        for index in range(stop):
            bar = self._bars[index]
            x = self._global_start_index + index
            bullish = bar.close >= bar.open
            candle_color = UP_CANDLE_COLOR if bullish else DOWN_CANDLE_COLOR
            wick_pen = pg.mkPen(candle_color, width=1)
            body_pen = pg.mkPen(candle_color, width=1)
            body_brush = pg.mkBrush(QColor("white") if bullish else QColor(DOWN_CANDLE_COLOR))
            painter.setPen(wick_pen)
            painter.drawLine(pg.QtCore.QPointF(x, bar.low), pg.QtCore.QPointF(x, bar.high))
            painter.setPen(body_pen)
            painter.setBrush(body_brush)
            painter.drawRect(
                pg.QtCore.QRectF(
                    x - width,
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
            self._bounding_rect = pg.QtCore.QRectF(
                self._global_start_index - 2.0,
                low,
                len(self._bars) + 4.0,
                max(high - low, 1.0),
            )
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
        scale = 0.85 if delta > 0 else 1.18
        self.chart.zoom_x(anchor_x=float(self.chart._cursor), scale=scale)
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
    orderLineCreated = Signal(str, float)
    orderLineMoved = Signal(int, float)
    orderPreviewConfirmed = Signal(str, float, float)
    orderLineActionRequested = Signal(int, str)

    def __init__(self) -> None:
        super().__init__()
        self._bars: list[Bar] = []
        self._cursor = -1
        self._total_count = 0
        self._global_start_index = 0
        self._draw_mode = False
        self._line_start: QPointF | None = None
        self._drawn_lines: list[DrawnLine] = []
        self._viewport = ViewportState()
        self._right_padding = 3.0
        self._left_padding = 3.0
        self._is_applying_viewport = False
        self._crosshair_enabled = True
        self._hover_card_margin = 12
        self._trade_line_mode: str | None = None
        self._last_hover_price: float | None = None
        self._order_lines: list[OrderLine] = []
        self._order_line_scene_positions: dict[int, float] = {}
        self._preview_order_type: str | None = None
        self._preview_quantity = 1.0
        self._tick_size = 1.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.graphics = pg.GraphicsLayoutWidget()
        self.graphics.setBackground("w")
        self.view_box = CandleViewBox(self)
        self.price_plot = self.graphics.addPlot(row=0, col=0, viewBox=self.view_box)
        self.price_plot.showGrid(x=False, y=False, alpha=0.0)
        self.price_plot.setMenuEnabled(False)
        self.price_plot.setLabel("left", "Price")
        self.price_plot.setLabel("bottom", "Bar")
        self.price_plot.getAxis("bottom").setStyle(showValues=False)
        self.price_plot.hideButtons()
        self.view_box.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=False)
        self.price_plot.enableAutoRange(axis="xy", enable=False)

        self._candles = CandlestickItem()
        self._ema_curve = pg.PlotDataItem(
            [],
            [],
            connect="finite",
            pen=pg.mkPen(EMA_LINE_COLOR, width=1, style=Qt.PenStyle.DashLine),
        )
        self.price_plot.addItem(self._candles)
        self.price_plot.addItem(self._ema_curve)

        self._v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#9aa1ab", width=1, style=Qt.PenStyle.DashLine))
        self._h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#9aa1ab", width=1, style=Qt.PenStyle.DashLine))
        self._price_label_item = pg.TextItem("", color="#2c2c2c", fill=pg.mkBrush(255, 255, 255, 230), anchor=(0, 0.5))
        self.price_plot.addItem(self._v_line)
        self.price_plot.addItem(self._h_line)
        self.price_plot.addItem(self._price_label_item)
        self._preview_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen("#5f6b7a", width=1, style=Qt.PenStyle.DashLine),
        )
        self._preview_line.setZValue(19)
        self.price_plot.addItem(self._preview_line)
        self._v_line.hide()
        self._h_line.hide()
        self._price_label_item.hide()
        self._preview_line.hide()

        layout.addWidget(self.graphics)
        self._build_hover_card()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.graphics.scene().sigMouseClicked.connect(self._handle_scene_click)
        self._mouse_proxy = pg.SignalProxy(self.graphics.scene().sigMouseMoved, rateLimit=60, slot=self._handle_mouse_moved)

    @property
    def draw_mode(self) -> bool:
        return self._draw_mode

    @property
    def trade_line_mode(self) -> str | None:
        return self._trade_line_mode

    @property
    def last_hover_price(self) -> float | None:
        return self._last_hover_price

    @property
    def viewport_state(self) -> ViewportState:
        return self._viewport

    def set_crosshair_enabled(self, enabled: bool) -> None:
        self._crosshair_enabled = enabled
        if not enabled:
            self._hide_crosshair()

    def set_draw_mode(self, enabled: bool) -> None:
        self._draw_mode = enabled
        self._line_start = None
        if enabled:
            self._trade_line_mode = None
            self.cancel_order_preview()
        if enabled:
            self._hide_crosshair()

    def set_trade_line_mode(self, mode: str | None) -> None:
        self._trade_line_mode = mode
        if mode is not None:
            self._draw_mode = False
        else:
            self.cancel_order_preview()

    def set_tick_size(self, tick_size: float) -> None:
        self._tick_size = max(float(tick_size), 0.0001)

    def begin_order_preview(self, order_type: str, quantity: float) -> None:
        self._preview_order_type = order_type
        self._preview_quantity = max(float(quantity), 1.0)
        self._draw_mode = False
        self._trade_line_mode = None
        if self._last_hover_price is not None:
            self._preview_line.setPos(self._snap_price(self._last_hover_price))
        self._preview_line.show()

    def cancel_order_preview(self) -> None:
        self._preview_order_type = None
        self._preview_line.hide()

    def set_order_lines(self, order_lines: list[OrderLine]) -> None:
        self._order_lines = list(order_lines)
        self._rebuild_order_line_items()

    def set_full_data(self, bars: list[Bar]) -> None:
        self.set_window_data(bars, len(bars) - 1 if bars else -1, len(bars), 0)

    def set_window_data(
        self,
        bars: list[Bar],
        cursor: int,
        total_count: int,
        global_start_index: int,
        *,
        preserve_viewport: bool = False,
    ) -> None:
        self._bars = list(bars)
        self._global_start_index = max(0, global_start_index)
        self._total_count = max(0, total_count)
        self._cursor = cursor if self._bars else -1
        self._viewport.max_bars_in_view = max(200, self._total_count or len(self._bars))
        self._viewport.bars_in_view = min(max(120, self._viewport.min_bars_in_view), self._viewport.max_bars_in_view)
        if not preserve_viewport:
            self._drawn_lines.clear()
        self._sync_plot_data()
        self._rebuild_order_line_items()
        self.cancel_order_preview()
        if preserve_viewport:
            self._apply_viewport()
        else:
            self.reset_viewport(follow_latest=True)
        self._hide_crosshair()

    def set_cursor(self, index: int) -> None:
        if not self._bars:
            self._cursor = -1
            self._sync_plot_data()
            return
        self._cursor = max(self._global_start_index, min(index, self.window_end_index))
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
        anchor_x = float(self._cursor)
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

    @property
    def window_end_index(self) -> int:
        return self._global_start_index + len(self._bars) - 1

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._position_hover_card()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_order_preview()
            event.accept()
            return
        super().keyPressEvent(event)

    def _sync_plot_data(self) -> None:
        local_cursor = self._cursor - self._global_start_index if self._cursor >= 0 else -1
        self._candles.set_data(self._bars, local_cursor, self._global_start_index)
        x_values = []
        ema_values = []
        closes = [bar.close for bar in self._bars[: local_cursor + 1]]
        ema_prefix = self._ema(closes, period=20)
        for index in range(local_cursor + 1):
            x_values.append(self._global_start_index + index)
            ema_values.append(ema_prefix[index])
        self._ema_curve.setData(x=x_values, y=ema_values)
        self._rebuild_session_markers()
        self._rebuild_line_items()

    def _rebuild_session_markers(self) -> None:
        for item in list(self.price_plot.items):
            if getattr(item, "_barbybar_session_marker", False):
                self.price_plot.removeItem(item)
        if not self._bars:
            return
        timeframe_minutes = self._infer_timeframe_minutes()
        local_cursor = self._cursor - self._global_start_index if self._cursor >= 0 else -1
        stop = min(len(self._bars), local_cursor + 1)
        for index in range(stop):
            bar = self._bars[index]
            if not self._is_session_open_marker(bar.timestamp.time(), timeframe_minutes):
                continue
            marker = pg.InfiniteLine(
                pos=self._global_start_index + index - 0.5,
                angle=90,
                movable=False,
                pen=pg.mkPen(SESSION_MARKER_COLOR, width=1, style=Qt.PenStyle.DashLine),
            )
            marker.setZValue(-10)
            marker._barbybar_session_marker = True
            self.price_plot.addItem(marker)

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

    def _rebuild_order_line_items(self) -> None:
        for item in list(self.price_plot.items):
            if getattr(item, "_barbybar_order_line", False):
                self.price_plot.removeItem(item)
        self._order_line_scene_positions.clear()
        right_edge = self.price_plot.viewRange()[0][1] if self._bars else 0.0
        for line in self._order_lines:
            pen, label_color, movable = self._order_line_style(line)
            line_item = pg.InfiniteLine(pos=line.price, angle=0, movable=movable, pen=pen)
            line_item._barbybar_order_line = True
            line_item.setZValue(20)
            if line.id is not None and movable:
                line_item.sigPositionChangeFinished.connect(
                    lambda item=line_item, order_id=line.id: self.orderLineMoved.emit(order_id, float(item.value()))
                )
            self.price_plot.addItem(line_item)
            label = pg.TextItem(self._order_line_label(line), color=label_color, fill=pg.mkBrush(255, 255, 255, 235), anchor=(1, 0.5))
            label._barbybar_order_line = True
            label.setPos(right_edge - 0.4, line.price)
            label.setZValue(21)
            self.price_plot.addItem(label)
            if line.id is not None and movable:
                scene_point = self.price_plot.vb.mapViewToScene(QPointF(float(self._global_start_index), float(line.price)))
                self._order_line_scene_positions[line.id] = float(scene_point.y())

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
            self._rebuild_order_line_items()
        finally:
            self._is_applying_viewport = False
        self.viewportChanged.emit()

    def _clamp_viewport(self) -> None:
        min_right = self._viewport.bars_in_view - self._left_padding
        max_right = max(self._cursor + 1, 0) if self._viewport.follow_latest else (max(self._total_count - 1, 0) + self._right_padding)
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
        start = max(self._global_start_index, int(floor(left)))
        stop = min(self._cursor + 1, int(ceil(right_edge)))
        if start >= stop:
            start = max(self._global_start_index, min(self._cursor, int(floor(right_edge)) - 1))
            stop = min(self._cursor + 1, start + 1)
        result: list[tuple[int, Bar]] = []
        for global_index in range(start, stop):
            local_index = global_index - self._global_start_index
            if 0 <= local_index < len(self._bars):
                result.append((global_index, self._bars[local_index]))
        return result

    def _handle_scene_click(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.RightButton:
            if self._preview_order_type:
                self.cancel_order_preview()
                event.accept()
                return
            pos = event.scenePos()
            if self.price_plot.sceneBoundingRect().contains(pos):
                order_id = self._editable_order_id_at_scene_pos(float(pos.y()))
                if order_id is not None:
                    self._show_order_line_context_menu(order_id, pos)
                    event.accept()
                    return
        if self._preview_order_type and self._cursor >= 0:
            pos = event.scenePos()
            if not self.price_plot.sceneBoundingRect().contains(pos):
                return
            point = self.price_plot.vb.mapSceneToView(pos)
            self.orderPreviewConfirmed.emit(self._preview_order_type, self._snap_price(float(point.y())), self._preview_quantity)
            self.cancel_order_preview()
            event.accept()
            return
        if self._trade_line_mode and self._cursor >= 0:
            pos = event.scenePos()
            if not self.price_plot.sceneBoundingRect().contains(pos):
                return
            point = self.price_plot.vb.mapSceneToView(pos)
            self.orderLineCreated.emit(self._trade_line_mode, float(point.y()))
            self._trade_line_mode = None
            return
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

    def _handle_mouse_moved(self, event) -> None:  # noqa: ANN001
        if not self._crosshair_enabled or self._draw_mode or self._cursor < 0:
            self._hide_crosshair()
            return
        pos = event[0]
        if not self.price_plot.sceneBoundingRect().contains(pos):
            self._hide_crosshair()
            return
        point = self.price_plot.vb.mapSceneToView(pos)
        self._last_hover_price = self._snap_price(float(point.y()))
        if self._preview_order_type:
            self._preview_line.setPos(self._last_hover_price)
            self._preview_line.show()
        hover = self._hover_bar_at(point.x())
        if hover is None:
            self._hide_crosshair()
            return
        index, bar = hover
        self._update_crosshair(index, point.y())
        self._update_hover_info(bar, point.y())

    def _hover_bar_at(self, x: float) -> tuple[int, Bar] | None:
        if self._cursor < 0:
            return None
        index = int(round(x))
        local_index = index - self._global_start_index
        if index < self._global_start_index or index > self._cursor or local_index >= len(self._bars):
            return None
        return index, self._bars[local_index]

    def _update_crosshair(self, x: int, price: float) -> None:
        self._v_line.setPos(x)
        self._h_line.setPos(price)
        self._v_line.show()
        self._h_line.show()
        x_right = self.price_plot.viewRange()[0][1]
        self._price_label_item.setText(f"{price:.2f}")
        self._price_label_item.setPos(x_right - 0.2, price)
        self._price_label_item.show()

    def _update_hover_info(self, bar: Bar, price: float) -> None:
        self._hover_time_label.setText(f"{bar.timestamp:%Y-%m-%d %H:%M}")
        self._hover_open_label.setText(f"开 {bar.open:.2f}")
        self._hover_high_label.setText(f"高 {bar.high:.2f}")
        self._hover_low_label.setText(f"低 {bar.low:.2f}")
        self._hover_close_label.setText(f"收 {bar.close:.2f}")
        neutral_style = "color: #2c2c2c; font-size: 12px;"
        bullish = bar.close >= bar.open
        self._hover_open_label.setStyleSheet(neutral_style)
        self._hover_high_label.setStyleSheet(
            "color: #d84a4a; font-size: 12px; font-weight: 600;" if bullish else neutral_style
        )
        self._hover_low_label.setStyleSheet(
            "color: #1f8b24; font-size: 12px; font-weight: 600;" if not bullish else neutral_style
        )
        self._hover_close_label.setStyleSheet(neutral_style)
        self._hover_card.layout().activate()
        self._hover_card.adjustSize()
        self._position_hover_card()
        self._hover_card.raise_()
        self._hover_card.show()

    def _hide_crosshair(self) -> None:
        self._v_line.hide()
        self._h_line.hide()
        self._price_label_item.hide()
        self._hover_card.hide()

    def _build_hover_card(self) -> None:
        self._hover_card = QFrame(self)
        self._hover_card.setObjectName("hoverCard")
        self._hover_card.setStyleSheet(
            "#hoverCard {"
            "background: rgba(255, 255, 255, 238);"
            "border: 1px solid #d9e0e6;"
            "border-radius: 6px;"
            "}"
        )
        self._hover_card.setFixedWidth(220)
        layout = QVBoxLayout(self._hover_card)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self._hover_time_label = QLabel()
        self._hover_open_label = QLabel()
        self._hover_high_label = QLabel()
        self._hover_low_label = QLabel()
        self._hover_close_label = QLabel()
        for label in [
            self._hover_time_label,
            self._hover_open_label,
            self._hover_high_label,
            self._hover_low_label,
            self._hover_close_label,
        ]:
            label.setStyleSheet("color: #2c2c2c; font-size: 12px;")
            layout.addWidget(label)
        self._hover_card.hide()

    def _position_hover_card(self) -> None:
        if not hasattr(self, "_hover_card"):
            return
        x = max(self._hover_card_margin, self.width() - self._hover_card.width() - self._hover_card_margin)
        y = self._hover_card_margin
        self._hover_card.move(x, y)

    def _editable_order_id_at_scene_pos(self, scene_y: float) -> int | None:
        closest_id: int | None = None
        closest_delta = 9.0
        for order_id, order_scene_y in self._order_line_scene_positions.items():
            delta = abs(order_scene_y - scene_y)
            if delta <= closest_delta:
                closest_id = order_id
                closest_delta = delta
        return closest_id

    def _show_order_line_context_menu(self, order_id: int, scene_pos) -> None:  # noqa: ANN001
        local_pos = self.graphics.mapFromScene(scene_pos)
        menu = QMenu(self)
        edit_price = menu.addAction("修改价格")
        edit_quantity = menu.addAction("修改手数")
        delete_action = menu.addAction("删除条件单")
        chosen = menu.exec(self.graphics.mapToGlobal(local_pos))
        if chosen is edit_price:
            self.orderLineActionRequested.emit(order_id, "edit_price")
        elif chosen is edit_quantity:
            self.orderLineActionRequested.emit(order_id, "edit_quantity")
        elif chosen is delete_action:
            self.orderLineActionRequested.emit(order_id, "delete")

    def _order_line_style(self, line: OrderLine) -> tuple[pg.QtGui.QPen, str, bool]:
        if line.order_type is OrderLineType.ENTRY_LONG:
            return pg.mkPen(ENTRY_LONG_LINE_COLOR, width=1, style=Qt.PenStyle.DashLine), ENTRY_LONG_LINE_COLOR, True
        if line.order_type is OrderLineType.ENTRY_SHORT:
            return pg.mkPen(ENTRY_SHORT_LINE_COLOR, width=1, style=Qt.PenStyle.DashLine), ENTRY_SHORT_LINE_COLOR, True
        if line.order_type is OrderLineType.EXIT:
            return pg.mkPen("#5f6b7a", width=1, style=Qt.PenStyle.DashLine), "#5f6b7a", True
        if line.order_type is OrderLineType.REVERSE:
            return pg.mkPen("#7a43b6", width=1, style=Qt.PenStyle.DashLine), "#7a43b6", True
        if line.order_type is OrderLineType.STOP_LOSS:
            return pg.mkPen(STOP_LOSS_LINE_COLOR, width=1, style=Qt.PenStyle.DashLine), STOP_LOSS_LINE_COLOR, True
        if line.order_type is OrderLineType.TAKE_PROFIT:
            return pg.mkPen(TAKE_PROFIT_LINE_COLOR, width=1, style=Qt.PenStyle.DashLine), TAKE_PROFIT_LINE_COLOR, True
        return pg.mkPen(AVERAGE_PRICE_LINE_COLOR, width=1, style=Qt.PenStyle.DashLine), AVERAGE_PRICE_LINE_COLOR, False

    @staticmethod
    def _order_line_label(line: OrderLine) -> str:
        labels = {
            OrderLineType.ENTRY_LONG: "开多线",
            OrderLineType.ENTRY_SHORT: "开空线",
            OrderLineType.EXIT: "平仓线",
            OrderLineType.REVERSE: "反手线",
            OrderLineType.STOP_LOSS: "止损线",
            OrderLineType.TAKE_PROFIT: "止盈线",
            OrderLineType.AVERAGE_PRICE: "成本线",
        }
        return f"{labels[line.order_type]} {line.price:.2f}"

    def _is_near_latest(self, right_edge_index: float) -> bool:
        return abs((self._cursor + 1) - right_edge_index) <= max(1.0, self._right_padding)

    def _snap_price(self, price: float) -> float:
        tick_size = max(self._tick_size, 0.0001)
        snapped = round(price / tick_size) * tick_size
        tick_text = f"{tick_size:.8f}".rstrip("0").rstrip(".")
        decimals = len(tick_text.split(".")[1]) if "." in tick_text else 0
        return round(snapped, decimals)

    def _infer_timeframe_minutes(self) -> int:
        if len(self._bars) < 2:
            return 1
        diffs = []
        for previous, current in zip(self._bars, self._bars[1:]):
            delta_minutes = int((current.timestamp - previous.timestamp).total_seconds() // 60)
            if delta_minutes > 0:
                diffs.append(delta_minutes)
        return min(diffs) if diffs else 1

    @staticmethod
    def _is_session_open_marker(bar_time: time, timeframe_minutes: int) -> bool:
        current_minutes = bar_time.hour * 60 + bar_time.minute
        for session_open in SESSION_OPEN_TIMES:
            open_minutes = session_open.hour * 60 + session_open.minute
            if 0 <= current_minutes - open_minutes <= timeframe_minutes:
                return True
        return False

    @staticmethod
    def _ema(values: list[float], period: int) -> list[float]:
        if not values:
            return []
        multiplier = 2 / (period + 1)
        ema_values = [values[0]]
        for price in values[1:]:
            ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
        return ema_values
