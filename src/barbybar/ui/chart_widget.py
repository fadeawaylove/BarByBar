from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from enum import Enum
from math import ceil, floor, hypot

import pyqtgraph as pg
from loguru import logger
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPen, QPicture
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsPathItem, QLabel, QLayout, QMenu, QVBoxLayout, QWidget

from barbybar.data.tick_size import format_price
from barbybar.domain.models import ActionType, Bar, ChartDrawing, DrawingAnchor, DrawingToolType, OrderLine, OrderLineType, SessionAction, Trade, normalize_drawing_style

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
DRAWING_HIT_DISTANCE_PX = 10.0
TRADE_MARKER_HIT_DISTANCE_PX = 12.0
TRADE_LINK_WIN_COLOR = "#1f8b24"
TRADE_LINK_LOSS_COLOR = "#d84a4a"
TRADE_CLOSE_MARKER_COLOR = "#5f6b7a"


@dataclass(slots=True)
class TradeMarker:
    action: SessionAction
    direction: str
    x: float
    y: float
    symbol: str
    brush: str
    size: float
    detail_lines: list[str]


@dataclass(slots=True)
class TradeLink:
    x1: float
    y1: float
    x2: float
    y2: float
    pnl: float
    detail_lines: list[str]


@dataclass(slots=True)
class ViewportState:
    bars_in_view: int = 120
    min_bars_in_view: int = 20
    max_bars_in_view: int = 200
    right_edge_index: float = 0.0
    follow_latest: bool = True


class BrowseMode(str, Enum):
    CROSSHAIR = "crosshair"
    PAN = "pan"


class InteractionMode(str, Enum):
    BROWSE = "browse"
    DRAWING = "drawing"
    ORDER_PREVIEW = "order_preview"


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
        if self.chart.interaction_mode in {InteractionMode.DRAWING, InteractionMode.ORDER_PREVIEW}:
            self.chart._log_interaction(
                "mouse_drag_ignored_tool_mode",
                button=str(ev.button()),
                is_start=bool(ev.isStart()),
                is_finish=bool(ev.isFinish()),
            )
            ev.ignore()
            return
        if ev.button() != Qt.MouseButton.LeftButton:
            super().mouseDragEvent(ev, axis=axis)
            return
        if ev.isFinish():
            if self.chart.is_dragging:
                self.chart._set_dragging(False)
                self.chart._suppress_next_left_click = True
                self.chart._log_interaction("mouse_drag_finished", suppress_next_left_click=True)
            ev.accept()
            return
        current_pos = ev.scenePos()
        last_pos = ev.lastScenePos()
        delta_x = float(current_pos.x() - last_pos.x())
        delta_y = float(current_pos.y() - last_pos.y())
        if not self.chart.is_dragging:
            distance = hypot(delta_x, delta_y)
            if distance < self.chart._drag_threshold_px:
                self.chart._log_interaction(
                    "mouse_drag_below_threshold",
                    distance=round(distance, 3),
                    threshold=self.chart._drag_threshold_px,
                )
                ev.ignore()
                return
            self.chart._set_dragging(True)
            self.chart._log_interaction(
                "mouse_drag_started",
                distance=round(distance, 3),
                delta_x=round(delta_x, 3),
                delta_y=round(delta_y, 3),
            )
        ev.accept()
        if ev.isStart():
            return
        current = self.mapSceneToView(current_pos)
        last = self.mapSceneToView(last_pos)
        self.chart._log_interaction(
            "mouse_drag_pan",
            current_x=round(float(current.x()), 3),
            last_x=round(float(last.x()), 3),
            delta_bars=round(float(last.x() - current.x()), 3),
        )
        self.chart.pan_x(last.x() - current.x())

    def mouseDoubleClickEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.chart.reset_viewport(follow_latest=True)
            ev.accept()
            return
        super().mouseDoubleClickEvent(ev)


class ChartWidget(QWidget):
    lineAdded = Signal()
    drawingsChanged = Signal()
    drawingToolChanged = Signal(object)
    drawingPropertiesRequested = Signal(object, int)
    interactionModeChanged = Signal(object)
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
        self._active_drawing_tool: DrawingToolType | None = None
        self._pending_drawing_anchors: list[DrawingAnchor] = []
        self._drawings: list[ChartDrawing] = []
        self._drawing_preview_anchor: DrawingAnchor | None = None
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
        self._trade_actions: list[SessionAction] = []
        self._trade_links: list[TradeLink] = []
        self._trade_markers: list[TradeMarker] = []
        self._trade_markers_visible = True
        self._trade_links_visible = True
        self._preview_order_type: str | None = None
        self._preview_quantity = 1.0
        self._tick_size = 1.0
        self._interaction_mode = InteractionMode.BROWSE
        self._is_dragging = False
        self._drag_threshold_px = 4.0
        self._suppress_next_left_click = False

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
        self.price_plot.hideAxis("right")
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
        self.price_plot.addItem(self._v_line)
        self.price_plot.addItem(self._h_line)
        self._preview_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen("#5f6b7a", width=1, style=Qt.PenStyle.DashLine),
        )
        self._preview_line.setZValue(19)
        self.price_plot.addItem(self._preview_line)
        self._v_line.hide()
        self._h_line.hide()
        self._preview_line.hide()

        layout.addWidget(self.graphics)
        self._build_hover_card()
        self._build_axis_price_label()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.graphics.scene().sigMouseClicked.connect(self._handle_scene_click)
        self._mouse_proxy = pg.SignalProxy(self.graphics.scene().sigMouseMoved, rateLimit=60, slot=self._handle_mouse_moved)

    @property
    def draw_mode(self) -> bool:
        return self._interaction_mode is InteractionMode.DRAWING

    @property
    def active_drawing_tool(self) -> DrawingToolType | None:
        return self._active_drawing_tool

    @property
    def trade_line_mode(self) -> str | None:
        return self._trade_line_mode

    @property
    def browse_mode(self) -> BrowseMode:
        return BrowseMode.PAN if self._is_dragging else BrowseMode.CROSSHAIR

    @property
    def interaction_mode(self) -> InteractionMode:
        return self._interaction_mode

    @property
    def last_hover_price(self) -> float | None:
        return self._last_hover_price

    @property
    def is_order_preview_active(self) -> bool:
        return self._interaction_mode is InteractionMode.ORDER_PREVIEW and self._preview_order_type is not None

    @property
    def preview_order_type(self) -> str | None:
        return self._preview_order_type

    @property
    def is_dragging(self) -> bool:
        return self._is_dragging

    @property
    def viewport_state(self) -> ViewportState:
        return self._viewport

    def set_crosshair_enabled(self, enabled: bool) -> None:
        self._crosshair_enabled = enabled
        if not enabled:
            self._hide_crosshair()

    def toggle_browse_mode(self) -> None:
        self._set_interaction_mode(InteractionMode.BROWSE)

    def set_draw_mode(self, enabled: bool) -> None:
        self.set_active_drawing_tool(DrawingToolType.TREND_LINE if enabled else None)

    def set_active_drawing_tool(self, tool: DrawingToolType | None) -> None:
        self._log_interaction("set_active_drawing_tool_start", requested_tool=tool.value if tool else None)
        self._active_drawing_tool = tool
        self._pending_drawing_anchors = []
        self._drawing_preview_anchor = None
        self._suppress_next_left_click = False
        if tool is not None:
            self._trade_line_mode = None
            self.cancel_order_preview()
            self._set_dragging(False)
            self._set_interaction_mode(InteractionMode.DRAWING)
        elif self._interaction_mode is InteractionMode.DRAWING:
            self._set_interaction_mode(InteractionMode.BROWSE)
        self._rebuild_line_items()
        self.drawingToolChanged.emit(tool)
        self._log_interaction("set_active_drawing_tool_done", active_tool=tool.value if tool else None)

    def set_drawings(self, drawings: list[ChartDrawing]) -> None:
        self._drawings = [
            ChartDrawing(
                id=drawing.id,
                session_id=drawing.session_id,
                tool_type=drawing.tool_type,
                anchors=[DrawingAnchor(anchor.x, anchor.y) for anchor in drawing.anchors],
                style=normalize_drawing_style(drawing.tool_type, dict(drawing.style)),
            )
            for drawing in drawings
        ]
        self._pending_drawing_anchors = []
        self._drawing_preview_anchor = None
        self._rebuild_line_items()

    def drawings(self) -> list[ChartDrawing]:
        return [
            ChartDrawing(
                id=drawing.id,
                session_id=drawing.session_id,
                tool_type=drawing.tool_type,
                anchors=[DrawingAnchor(anchor.x, anchor.y) for anchor in drawing.anchors],
                style=normalize_drawing_style(drawing.tool_type, dict(drawing.style)),
            )
            for drawing in self._drawings
        ]

    def delete_drawing(self, drawing_id: int | None, fallback_index: int | None = None) -> None:
        index = self._resolve_drawing_index(drawing_id, fallback_index)
        if index is None:
            return
        del self._drawings[index]
        self._rebuild_line_items()
        self.drawingsChanged.emit()

    def update_drawing_style(self, drawing_id: int | None, style: dict[str, object], fallback_index: int | None = None) -> None:
        index = self._resolve_drawing_index(drawing_id, fallback_index)
        if index is None:
            return
        drawing = self._drawings[index]
        drawing.style = normalize_drawing_style(drawing.tool_type, {**drawing.style, **style})
        self._rebuild_line_items()
        self.drawingsChanged.emit()

    def set_trade_line_mode(self, mode: str | None) -> None:
        self._trade_line_mode = mode
        if mode is not None:
            self.set_active_drawing_tool(None)
        else:
            self.cancel_order_preview()

    def set_tick_size(self, tick_size: float) -> None:
        self._tick_size = max(float(tick_size), 0.0001)

    def begin_order_preview(self, order_type: str, quantity: float) -> None:
        self._log_interaction("begin_order_preview_start", order_type=order_type, quantity=quantity)
        self._preview_order_type = order_type
        self._preview_quantity = max(float(quantity), 1.0)
        self.set_active_drawing_tool(None)
        self._trade_line_mode = None
        self._set_dragging(False)
        self._suppress_next_left_click = False
        self._set_interaction_mode(InteractionMode.ORDER_PREVIEW)
        if self._last_hover_price is not None:
            self._preview_line.setPos(self._snap_price(self._last_hover_price))
        self._preview_line.show()
        self._log_interaction("begin_order_preview_done", order_type=order_type, quantity=self._preview_quantity)

    def cancel_order_preview(self) -> None:
        self._log_interaction("cancel_order_preview_start")
        self._preview_order_type = None
        self._preview_line.hide()
        if self._interaction_mode is InteractionMode.ORDER_PREVIEW:
            self._set_interaction_mode(InteractionMode.BROWSE)
        self._log_interaction("cancel_order_preview_done")

    def set_order_lines(self, order_lines: list[OrderLine]) -> None:
        self._order_lines = list(order_lines)
        self._rebuild_order_line_items()

    def set_trade_actions(self, actions: list[SessionAction], trades: list[Trade] | None = None) -> None:
        self._trade_actions = list(actions)
        self._rebuild_trade_geometry(trades)
        self._rebuild_trade_marker_items()

    def set_trade_markers_visible(self, visible: bool) -> None:
        self._trade_markers_visible = bool(visible)
        self._rebuild_trade_marker_items()

    def set_trade_links_visible(self, visible: bool) -> None:
        self._trade_links_visible = bool(visible)
        self._rebuild_trade_marker_items()

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
            self._pending_drawing_anchors = []
            self._drawing_preview_anchor = None
            self._active_drawing_tool = None
            self._trade_line_mode = None
            self._preview_order_type = None
            self._preview_line.hide()
            self._set_dragging(False)
            self._set_interaction_mode(InteractionMode.BROWSE)
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
        self._drawings.clear()
        self._pending_drawing_anchors = []
        self._drawing_preview_anchor = None
        self._active_drawing_tool = None
        self._sync_plot_data()
        self._apply_viewport()
        self.drawingsChanged.emit()
        self.drawingToolChanged.emit(None)

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
            if self._pending_drawing_anchors:
                self._pending_drawing_anchors = []
                self._drawing_preview_anchor = None
                self._rebuild_line_items()
                self.set_active_drawing_tool(None)
                event.accept()
                return
            if self._active_drawing_tool is not None:
                self.set_active_drawing_tool(None)
                event.accept()
                return
            if self._preview_order_type:
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
        y_top = self.price_plot.viewRange()[1][1]
        for index in range(stop):
            bar = self._bars[index]
            session_label = self._session_marker_label(bar.timestamp.time(), timeframe_minutes)
            if session_label is None:
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
            label = pg.TextItem(
                session_label,
                color="#6b7280",
                fill=pg.mkBrush(255, 255, 255, 220),
                anchor=(0.5, 0),
            )
            label._barbybar_session_marker = True
            label.setZValue(5)
            label.setPos(self._global_start_index + index - 0.5, y_top)
            self.price_plot.addItem(label)

    def _rebuild_line_items(self) -> None:
        for item in list(self.price_plot.items):
            if getattr(item, "_barbybar_line", False):
                self.price_plot.removeItem(item)
        for drawing in self._drawings:
            self._add_drawing_items(drawing, preview=False)
        preview = self._current_preview_drawing()
        if preview is not None:
            self._add_drawing_items(preview, preview=True)

    def _rebuild_trade_marker_items(self) -> None:
        for item in list(self.price_plot.items):
            if getattr(item, "_barbybar_trade_marker", False):
                self.price_plot.removeItem(item)
        if not self._bars or self._cursor < 0:
            return
        if self._trade_links_visible:
            for link in self._trade_links:
                item = pg.PlotCurveItem(
                    [link.x1, link.x2],
                    [link.y1, link.y2],
                    pen=pg.mkPen(TRADE_LINK_WIN_COLOR if link.pnl >= 0 else TRADE_LINK_LOSS_COLOR, width=1, style=Qt.PenStyle.SolidLine),
                )
                item.setOpacity(0.55)
                item._barbybar_trade_marker = True
                item.setZValue(13)
                self.price_plot.addItem(item)
        if self._trade_markers_visible:
            for marker in self._trade_markers:
                item = pg.ScatterPlotItem(
                    [marker.x],
                    [marker.y],
                    symbol=marker.symbol,
                    size=marker.size,
                    brush=pg.mkBrush(marker.brush),
                    pen=pg.mkPen(marker.brush, width=1),
                )
                item._barbybar_trade_marker = True
                item.setZValue(14)
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
            self._rebuild_trade_geometry(None)
            self._rebuild_trade_marker_items()
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
        scene_pos = event.scenePos()
        in_chart = bool(self.price_plot.sceneBoundingRect().contains(scene_pos))
        self._log_interaction(
            "scene_click_received",
            button=str(event.button()),
            in_chart=in_chart,
            scene_x=round(float(scene_pos.x()), 3),
            scene_y=round(float(scene_pos.y()), 3),
            pending_anchors=len(self._pending_drawing_anchors),
        )
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._suppress_next_left_click
            and self._interaction_mode is InteractionMode.BROWSE
        ):
            self._log_interaction("scene_click_suppressed")
            self._suppress_next_left_click = False
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            if self._preview_order_type:
                self._log_interaction("scene_click_cancel_order_preview")
                self.cancel_order_preview()
                event.accept()
                return
            if in_chart:
                drawing_hit = self._drawing_at_scene_pos(scene_pos)
                if drawing_hit is not None:
                    self._log_interaction("scene_click_open_drawing_context_menu", drawing_index=drawing_hit[0])
                    self._show_drawing_context_menu(drawing_hit[0], scene_pos)
                    event.accept()
                    return
                order_id = self._editable_order_id_at_scene_pos(float(scene_pos.y()))
                if order_id is not None:
                    self._log_interaction("scene_click_open_order_context_menu", order_id=order_id)
                    self._show_order_line_context_menu(order_id, scene_pos)
                    event.accept()
                    return
        if self._preview_order_type and self._cursor >= 0:
            if not in_chart:
                self._log_interaction("scene_click_order_preview_outside_chart")
                return
            point = self.price_plot.vb.mapSceneToView(scene_pos)
            self._log_interaction(
                "scene_click_order_preview_confirm",
                mapped_x=round(float(point.x()), 3),
                mapped_y=round(float(point.y()), 3),
            )
            self.orderPreviewConfirmed.emit(self._preview_order_type, self._snap_price(float(point.y())), self._preview_quantity)
            self.cancel_order_preview()
            event.accept()
            return
        if self._trade_line_mode and self._cursor >= 0:
            if not in_chart:
                self._log_interaction("scene_click_trade_line_outside_chart")
                return
            point = self.price_plot.vb.mapSceneToView(scene_pos)
            self._log_interaction("scene_click_trade_line_create", trade_line_mode=self._trade_line_mode)
            self.orderLineCreated.emit(self._trade_line_mode, float(point.y()))
            self._trade_line_mode = None
            return
        if self._active_drawing_tool is None or self._cursor < 0:
            return
        if not in_chart:
            self._log_interaction("scene_click_drawing_outside_chart")
            return
        point = self.price_plot.vb.mapSceneToView(scene_pos)
        self._log_interaction(
            "scene_click_consume_drawing",
            mapped_x=round(float(point.x()), 3),
            mapped_y=round(float(point.y()), 3),
            pending_anchors=len(self._pending_drawing_anchors),
            needed_anchors=self._anchors_required(self._active_drawing_tool),
        )
        self._consume_drawing_click(DrawingAnchor(float(point.x()), float(point.y())))
        event.accept()

    def _handle_mouse_moved(self, event) -> None:  # noqa: ANN001
        if (
            not self._crosshair_enabled
            or self._cursor < 0
            or self._is_dragging
            or self._interaction_mode not in {InteractionMode.BROWSE, InteractionMode.ORDER_PREVIEW}
        ):
            self._hide_crosshair()
        pos = event[0]
        if self._active_drawing_tool is not None:
            if self.price_plot.sceneBoundingRect().contains(pos):
                point = self.price_plot.vb.mapSceneToView(pos)
                self._drawing_preview_anchor = DrawingAnchor(float(point.x()), float(point.y()))
                self._log_interaction(
                    "mouse_move_drawing_preview",
                    mapped_x=round(float(point.x()), 3),
                    mapped_y=round(float(point.y()), 3),
                    pending_anchors=len(self._pending_drawing_anchors),
                )
                self._rebuild_line_items()
            else:
                self._log_interaction("mouse_move_drawing_preview_outside_chart")
                self._drawing_preview_anchor = None
                self._rebuild_line_items()
        if (
            not self._crosshair_enabled
            or self._cursor < 0
            or self._is_dragging
            or self._interaction_mode not in {InteractionMode.BROWSE, InteractionMode.ORDER_PREVIEW}
        ):
            return
        if not self.price_plot.sceneBoundingRect().contains(pos):
            self._hide_crosshair()
            return
        point = self.price_plot.vb.mapSceneToView(pos)
        self._last_hover_price = self._snap_price(float(point.y()))
        if self._interaction_mode is InteractionMode.BROWSE:
            trade_hover = self._trade_marker_at_scene_pos(pos)
            if trade_hover is not None:
                marker, link = trade_hover
                hover_price = marker.y if marker is not None else link.y2
                hover_x = int(round(marker.x if marker is not None else link.x2))
                self._update_crosshair(hover_x, hover_price)
                self._update_trade_hover_info(marker.detail_lines if marker is not None else link.detail_lines)
                return
        if self._preview_order_type:
            self._log_interaction(
                "mouse_move_order_preview",
                mapped_x=round(float(point.x()), 3),
                mapped_y=round(float(point.y()), 3),
                snapped_price=self._last_hover_price,
            )
            self._preview_line.setPos(self._last_hover_price)
            self._preview_line.show()
        if self._interaction_mode is InteractionMode.ORDER_PREVIEW:
            self._hide_crosshair()
            return
        hover = self._hover_bar_at(point.x())
        if hover is None:
            self._hide_crosshair()
            return
        index, bar = hover
        self._log_interaction("hover_active", hover_index=index, hover_price=round(float(point.y()), 3))
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
        self._axis_price_label.setText(format_price(price, self._tick_size))
        self._position_axis_price_label(price)
        self._axis_price_label.show()

    def _update_hover_info(self, bar: Bar, price: float) -> None:
        self._hover_time_label.setText(f"{bar.timestamp:%Y-%m-%d %H:%M}")
        self._hover_open_label.setText(f"开 {format_price(bar.open, self._tick_size)}")
        self._hover_high_label.setText(f"高 {format_price(bar.high, self._tick_size)}")
        self._hover_low_label.setText(f"低 {format_price(bar.low, self._tick_size)}")
        self._hover_close_label.setText(f"收 {format_price(bar.close, self._tick_size)}")
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

    def _update_trade_hover_info(self, detail_lines: list[str]) -> None:
        labels = [
            self._hover_time_label,
            self._hover_open_label,
            self._hover_high_label,
            self._hover_low_label,
            self._hover_close_label,
        ]
        for label, text in zip(labels, detail_lines + [""] * max(0, len(labels) - len(detail_lines))):
            label.setText(text)
            label.setStyleSheet("color: #2c2c2c; font-size: 12px;")
        self._hover_card.layout().activate()
        self._hover_card.adjustSize()
        self._position_hover_card()
        self._hover_card.raise_()
        self._hover_card.show()

    def _hide_crosshair(self) -> None:
        self._v_line.hide()
        self._h_line.hide()
        self._axis_price_label.hide()
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

    def _build_axis_price_label(self) -> None:
        self._axis_price_label = QLabel(self)
        self._axis_price_label.setObjectName("axisPriceLabel")
        self._axis_price_label.setStyleSheet(
            "#axisPriceLabel {"
            "background: rgba(255, 255, 255, 238);"
            "border: 1px solid #d9e0e6;"
            "border-radius: 4px;"
            "padding: 2px 6px;"
            "color: #2c2c2c;"
            "font-size: 12px;"
            "}"
        )
        self._axis_price_label.hide()

    def _position_axis_price_label(self, price: float) -> None:
        width = max(self._axis_price_label.sizeHint().width(), 52)
        height = max(self._axis_price_label.sizeHint().height(), 22)
        self._axis_price_label.resize(width, height)
        scene_point = self.price_plot.vb.mapViewToScene(QPointF(self._cursor, price))
        local_point = self.graphics.mapFromScene(scene_point)
        x = self.width() - width - 6
        y = int(local_point.y() - height / 2)
        y = max(4, min(self.height() - height - 4, y))
        self._axis_price_label.move(x, y)

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

    def _show_drawing_context_menu(self, drawing_index: int, scene_pos) -> None:  # noqa: ANN001
        if not (0 <= drawing_index < len(self._drawings)):
            return
        drawing = self._drawings[drawing_index]
        local_pos = self.graphics.mapFromScene(scene_pos)
        menu = QMenu(self)
        properties_action = menu.addAction("属性...")
        delete_action = menu.addAction("删除画线")
        chosen = menu.exec(self.graphics.mapToGlobal(local_pos))
        if chosen is properties_action:
            self.drawingPropertiesRequested.emit(self.drawings()[drawing_index], drawing_index)
        elif chosen is delete_action:
            self.delete_drawing(drawing.id, drawing_index)

    def _drawing_at_scene_pos(self, scene_pos) -> tuple[int, ChartDrawing] | None:  # noqa: ANN001
        hit_index: int | None = None
        hit_priority = 99.0
        hit_distance = float("inf")
        for index, drawing in enumerate(self._drawings):
            border_distance, inside = self._drawing_hit_test(drawing, scene_pos)
            if border_distance is None and not inside:
                continue
            priority = 0.0 if border_distance is not None else 1.0
            distance = border_distance if border_distance is not None else 0.0
            if priority < hit_priority or (priority == hit_priority and distance < hit_distance):
                hit_index = index
                hit_priority = priority
                hit_distance = distance
        if hit_index is None:
            return None
        return hit_index, self._drawings[hit_index]

    def _drawing_hit_test(self, drawing: ChartDrawing, scene_pos) -> tuple[float | None, bool]:
        if drawing.tool_type is DrawingToolType.TEXT and drawing.anchors:
            rect = self._text_scene_rect(drawing)
            return (0.0 if rect.contains(scene_pos) else None), False
        segments = self._drawing_segments(drawing)
        min_distance: float | None = None
        for x_values, y_values in segments:
            for start in range(len(x_values) - 1):
                distance = self._segment_distance_to_scene_pos(
                    DrawingAnchor(x_values[start], y_values[start]),
                    DrawingAnchor(x_values[start + 1], y_values[start + 1]),
                    scene_pos,
                )
                if distance <= DRAWING_HIT_DISTANCE_PX and (min_distance is None or distance < min_distance):
                    min_distance = distance
        inside = False
        if drawing.tool_type in {DrawingToolType.RECTANGLE, DrawingToolType.PRICE_RANGE} and len(drawing.anchors) >= 2:
            first, second = drawing.anchors[:2]
            top_left = self.price_plot.vb.mapViewToScene(QPointF(min(first.x, second.x), max(first.y, second.y)))
            bottom_right = self.price_plot.vb.mapViewToScene(QPointF(max(first.x, second.x), min(first.y, second.y)))
            rect = pg.QtCore.QRectF(top_left, bottom_right).normalized()
            inside = rect.contains(scene_pos)
        return min_distance, inside

    def _text_scene_rect(self, drawing: ChartDrawing):
        style = normalize_drawing_style(drawing.tool_type, drawing.style)
        text = str(style.get("text", "")) or "文字"
        font = QApplication.font()
        font.setPointSize(int(style.get("font_size", 12)))
        metrics = pg.QtGui.QFontMetrics(font)
        lines = text.splitlines() or [text]
        width = max(metrics.horizontalAdvance(line) for line in lines) + 8
        height = metrics.lineSpacing() * max(len(lines), 1) + 6
        scene_top_left = self.price_plot.vb.mapViewToScene(QPointF(drawing.anchors[0].x, drawing.anchors[0].y))
        return pg.QtCore.QRectF(float(scene_top_left.x()), float(scene_top_left.y()), float(width), float(height))

    def _segment_distance_to_scene_pos(self, first: DrawingAnchor, second: DrawingAnchor, scene_pos) -> float:
        start = self.price_plot.vb.mapViewToScene(QPointF(first.x, first.y))
        end = self.price_plot.vb.mapViewToScene(QPointF(second.x, second.y))
        return self._point_to_segment_distance(float(scene_pos.x()), float(scene_pos.y()), float(start.x()), float(start.y()), float(end.x()), float(end.y()))

    @staticmethod
    def _point_to_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        dx = bx - ax
        dy = by - ay
        if abs(dx) <= 0.0001 and abs(dy) <= 0.0001:
            return hypot(px - ax, py - ay)
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = min(max(t, 0.0), 1.0)
        closest_x = ax + dx * t
        closest_y = ay + dy * t
        return hypot(px - closest_x, py - closest_y)

    def _resolve_drawing_index(self, drawing_id: int | None, fallback_index: int | None) -> int | None:
        if drawing_id is not None:
            for index, drawing in enumerate(self._drawings):
                if drawing.id == drawing_id:
                    return index
        if fallback_index is not None and 0 <= fallback_index < len(self._drawings):
            return fallback_index
        return None

    def _trade_marker_at_scene_pos(self, scene_pos) -> tuple[TradeMarker | None, TradeLink | None] | None:  # noqa: ANN001
        if self._trade_markers_visible:
            for marker in self._trade_markers:
                marker_scene = self.price_plot.vb.mapViewToScene(QPointF(marker.x, marker.y))
                if hypot(float(scene_pos.x()) - float(marker_scene.x()), float(scene_pos.y()) - float(marker_scene.y())) <= TRADE_MARKER_HIT_DISTANCE_PX:
                    return marker, None
        if self._trade_links_visible:
            for link in self._trade_links:
                start = self.price_plot.vb.mapViewToScene(QPointF(link.x1, link.y1))
                end = self.price_plot.vb.mapViewToScene(QPointF(link.x2, link.y2))
                distance = self._point_to_segment_distance(
                    float(scene_pos.x()),
                    float(scene_pos.y()),
                    float(start.x()),
                    float(start.y()),
                    float(end.x()),
                    float(end.y()),
                )
                if distance <= TRADE_MARKER_HIT_DISTANCE_PX:
                    return None, link
        return None

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

    def _order_line_label(self, line: OrderLine) -> str:
        labels = {
            OrderLineType.ENTRY_LONG: "买",
            OrderLineType.ENTRY_SHORT: "卖",
            OrderLineType.EXIT: "平",
            OrderLineType.REVERSE: "反",
            OrderLineType.STOP_LOSS: "止损",
            OrderLineType.TAKE_PROFIT: "止盈",
            OrderLineType.AVERAGE_PRICE: "成本",
        }
        quantity = int(round(line.quantity))
        return f"{labels[line.order_type]} {quantity}手 {format_price(line.price, self._tick_size)}"

    def _consume_drawing_click(self, anchor: DrawingAnchor) -> None:
        tool = self._active_drawing_tool
        if tool is None:
            self._log_interaction("consume_drawing_click_ignored_no_tool")
            return
        self._pending_drawing_anchors.append(anchor)
        needed = self._anchors_required(tool)
        self._log_interaction(
            "consume_drawing_click_anchor_added",
            tool=tool.value,
            anchor_x=round(anchor.x, 3),
            anchor_y=round(anchor.y, 3),
            pending_anchors=len(self._pending_drawing_anchors),
            needed_anchors=needed,
        )
        if len(self._pending_drawing_anchors) < needed:
            self._drawing_preview_anchor = anchor
            self._rebuild_line_items()
            return
        drawing = ChartDrawing(
            tool_type=tool,
            anchors=[DrawingAnchor(item.x, item.y) for item in self._pending_drawing_anchors[:needed]],
            style=normalize_drawing_style(tool),
        )
        self._drawings.append(drawing)
        self._pending_drawing_anchors = []
        self._drawing_preview_anchor = None
        self._active_drawing_tool = None
        self._sync_plot_data()
        self._apply_viewport()
        self.lineAdded.emit()
        self.drawingsChanged.emit()
        self.drawingToolChanged.emit(None)
        self._log_interaction("consume_drawing_click_completed", tool=tool.value, anchor_count=needed)
        self._set_interaction_mode(InteractionMode.BROWSE)
        if tool is DrawingToolType.TEXT:
            self.drawingPropertiesRequested.emit(self.drawings()[-1], len(self._drawings) - 1)

    def _current_preview_drawing(self) -> ChartDrawing | None:
        tool = self._active_drawing_tool
        if tool is None or not self._pending_drawing_anchors:
            return None
        preview_anchor = self._drawing_preview_anchor or self._pending_drawing_anchors[-1]
        anchors = [DrawingAnchor(item.x, item.y) for item in self._pending_drawing_anchors]
        needed = self._anchors_required(tool)
        while len(anchors) < needed:
            anchors.append(DrawingAnchor(preview_anchor.x, preview_anchor.y))
        return ChartDrawing(tool_type=tool, anchors=anchors[:needed], style=normalize_drawing_style(tool))

    @staticmethod
    def _anchors_required(tool: DrawingToolType) -> int:
        if tool in {DrawingToolType.HORIZONTAL_LINE, DrawingToolType.HORIZONTAL_RAY, DrawingToolType.VERTICAL_LINE, DrawingToolType.TEXT}:
            return 1
        if tool is DrawingToolType.PARALLEL_CHANNEL:
            return 3
        return 2

    def _add_drawing_items(self, drawing: ChartDrawing, *, preview: bool) -> None:
        style = normalize_drawing_style(drawing.tool_type, drawing.style)
        if drawing.tool_type is DrawingToolType.TEXT:
            text_item = self._drawing_text_item(drawing, style, preview=preview)
            if text_item is not None:
                text_item._barbybar_line = True
                text_item._barbybar_drawing_id = drawing.id
                text_item._barbybar_drawing_tool = drawing.tool_type.value
                text_item.setZValue(19 if preview else 18)
                self.price_plot.addItem(text_item)
            return
        pen = self._drawing_pen(style, preview=preview)
        fill_item = self._drawing_fill_item(drawing, style, preview=preview)
        if fill_item is not None:
            fill_item._barbybar_line = True
            fill_item._barbybar_drawing_id = drawing.id
            fill_item._barbybar_drawing_tool = drawing.tool_type.value
            self.price_plot.addItem(fill_item)
        for x_values, y_values in self._drawing_segments(drawing):
            item = pg.PlotCurveItem(x_values, y_values, pen=pen)
            item._barbybar_line = True
            item._barbybar_drawing_id = drawing.id
            item._barbybar_drawing_tool = drawing.tool_type.value
            item.setZValue(18 if preview else 17)
            self.price_plot.addItem(item)
        if not preview:
            for label_item in self._drawing_label_items(drawing, style):
                label_item._barbybar_line = True
                label_item._barbybar_drawing_id = drawing.id
                label_item._barbybar_drawing_tool = drawing.tool_type.value
                label_item.setZValue(19)
                self.price_plot.addItem(label_item)

    def _drawing_segments(self, drawing: ChartDrawing) -> list[tuple[list[float], list[float]]]:
        anchors = drawing.anchors
        style = normalize_drawing_style(drawing.tool_type, drawing.style)
        if drawing.tool_type in {DrawingToolType.TREND_LINE, DrawingToolType.RAY, DrawingToolType.EXTENDED_LINE} and len(anchors) >= 2:
            return [self._line_points_with_extension(anchors[0], anchors[1], style["extend_left"], style["extend_right"])]
        if drawing.tool_type is DrawingToolType.FIB_RETRACEMENT and len(anchors) >= 2:
            return self._fib_segments(drawing)
        if drawing.tool_type is DrawingToolType.HORIZONTAL_LINE and anchors:
            left = self._global_start_index - self._left_padding
            right = max(self._cursor + 1 + self._right_padding, self.window_end_index + self._right_padding if self._bars else left + 1)
            return [([left, right], [anchors[0].y, anchors[0].y])]
        if drawing.tool_type is DrawingToolType.HORIZONTAL_RAY and anchors:
            right = max(self._cursor + 1 + self._right_padding, self.window_end_index + self._right_padding if self._bars else anchors[0].x + 1)
            return [([anchors[0].x, right], [anchors[0].y, anchors[0].y])]
        if drawing.tool_type is DrawingToolType.VERTICAL_LINE and anchors:
            low, high = self.price_plot.viewRange()[1]
            return [([anchors[0].x, anchors[0].x], [low, high])]
        if drawing.tool_type is DrawingToolType.RECTANGLE and len(anchors) >= 2:
            first = anchors[0]
            second = anchors[1]
            return [(
                [first.x, second.x, second.x, first.x, first.x],
                [first.y, first.y, second.y, second.y, first.y],
            )]
        if drawing.tool_type is DrawingToolType.PRICE_RANGE and len(anchors) >= 2:
            first = anchors[0]
            second = anchors[1]
            left = min(first.x, second.x)
            right = max(first.x, second.x)
            return [([left, right, right, left, left], [first.y, first.y, second.y, second.y, first.y])]
        if drawing.tool_type is DrawingToolType.PARALLEL_CHANNEL and len(anchors) >= 3:
            return self._parallel_channel_segments(anchors[0], anchors[1], anchors[2])
        return []

    def _drawing_label_items(self, drawing: ChartDrawing, style: dict[str, object]) -> list[pg.TextItem]:
        if drawing.tool_type is not DrawingToolType.FIB_RETRACEMENT or len(drawing.anchors) < 2:
            return []
        first, second = drawing.anchors[:2]
        left = min(first.x, second.x)
        right = max(first.x, second.x)
        y_start = first.y
        y_end = second.y
        items: list[pg.TextItem] = []
        for level in style["fib_levels"]:
            level_value = float(level)
            price = y_start + (y_end - y_start) * level_value
            parts: list[str] = []
            if style["show_level_labels"]:
                parts.append(f"{level_value:g}")
            if style["show_price_labels"]:
                parts.append(format_price(self._snap_price(price), self._tick_size))
            if not parts:
                continue
            item = pg.TextItem("  ".join(parts), color=str(style["color"]), fill=pg.mkBrush(255, 255, 255, 220), anchor=(1, 0.5))
            item.setPos(right, price)
            items.append(item)
        return items

    def _drawing_text_item(self, drawing: ChartDrawing, style: dict[str, object], *, preview: bool) -> pg.TextItem | None:
        if not drawing.anchors:
            return None
        text = str(style.get("text", ""))
        if not text and not preview:
            return None
        content = text if text else "文字"
        item = pg.TextItem(content, color=str(style.get("text_color", style.get("color", "#ff9f1c"))), anchor=(0, 0))
        font = item.textItem.font()
        font.setPointSize(int(style.get("font_size", 12)))
        item.textItem.setFont(font)
        item.setPos(drawing.anchors[0].x, drawing.anchors[0].y)
        return item

    def _fib_segments(self, drawing: ChartDrawing) -> list[tuple[list[float], list[float]]]:
        if len(drawing.anchors) < 2:
            return []
        first, second = drawing.anchors[:2]
        left = min(first.x, second.x)
        right = max(first.x, second.x)
        style = normalize_drawing_style(drawing.tool_type, drawing.style)
        start_y = first.y
        end_y = second.y
        segments: list[tuple[list[float], list[float]]] = []
        for level in style["fib_levels"]:
            level_value = float(level)
            price = start_y + (end_y - start_y) * level_value
            segments.append(([left, right], [price, price]))
        return segments

    def _drawing_pen(self, style: dict[str, object], *, preview: bool):
        pen_style = {
            "solid": Qt.PenStyle.SolidLine,
            "dash": Qt.PenStyle.DashLine,
            "dot": Qt.PenStyle.DotLine,
        }.get(str(style.get("line_style", "solid")), Qt.PenStyle.SolidLine)
        if preview:
            pen_style = Qt.PenStyle.DashLine
        return pg.mkPen(str(style.get("color", "#ff9f1c")), width=int(style.get("width", 2)), style=pen_style)

    def _drawing_fill_item(self, drawing: ChartDrawing, style: dict[str, object], *, preview: bool) -> QGraphicsPathItem | None:
        if drawing.tool_type not in {DrawingToolType.RECTANGLE, DrawingToolType.PRICE_RANGE} or len(drawing.anchors) < 2:
            return None
        fill_color = QColor(str(style.get("fill_color", style.get("color", "#ff9f1c"))))
        opacity = float(style.get("fill_opacity", 0.0))
        if opacity <= 0:
            return None
        fill_color.setAlphaF(min(max(opacity * (0.6 if preview else 1.0), 0.0), 1.0))
        first, second = drawing.anchors[:2]
        rect = pg.QtCore.QRectF(
            min(first.x, second.x),
            min(first.y, second.y),
            abs(second.x - first.x),
            abs(second.y - first.y),
        )
        path = QPainterPath()
        path.addRect(rect)
        item = QGraphicsPathItem(path)
        item.setBrush(QBrush(fill_color))
        item.setPen(QPen(Qt.PenStyle.NoPen))
        item.setZValue(16 if not preview else 17)
        return item

    def _line_points_with_extension(
        self,
        first: DrawingAnchor,
        second: DrawingAnchor,
        extend_left: bool,
        extend_right: bool,
    ) -> tuple[list[float], list[float]]:
        left_bound = self._global_start_index - self._left_padding
        right_bound = max(self.window_end_index + self._right_padding, self._cursor + 1 + self._right_padding if self._cursor >= 0 else left_bound + 1)
        x1, y1 = float(first.x), float(first.y)
        x2, y2 = float(second.x), float(second.y)
        if abs(x2 - x1) <= 0.0001:
            low, high = self.price_plot.viewRange()[1]
            return ([x1, x1], [low, high])
        slope = (y2 - y1) / (x2 - x1)
        start_x = left_bound if extend_left else x1
        end_x = right_bound if extend_right else x2
        start_y = y1 + slope * (start_x - x1)
        end_y = y1 + slope * (end_x - x1)
        return ([start_x, end_x], [start_y, end_y])

    def _rebuild_trade_geometry(self, trades: list[Trade] | None) -> None:
        if not self._bars or self._cursor < 0:
            self._trade_markers = []
            self._trade_links = []
            return
        visible_actions = [
            action
            for action in self._trade_actions
            if self._global_start_index <= action.bar_index <= self._cursor
            and action.action_type in {ActionType.OPEN_LONG, ActionType.OPEN_SHORT, ActionType.CLOSE, ActionType.ADD, ActionType.REDUCE}
        ]
        y_min, y_max = self.price_plot.viewRange()[1]
        y_span = max(y_max - y_min, 1.0)
        offset_unit = y_span * 0.018
        marker_offsets: dict[int, int] = {}
        markers: list[TradeMarker] = []
        for action in visible_actions:
            local_index = action.bar_index - self._global_start_index
            if not (0 <= local_index < len(self._bars)):
                continue
            bar = self._bars[local_index]
            stack = marker_offsets.get(action.bar_index, 0)
            marker_offsets[action.bar_index] = stack + 1
            x = self._trade_marker_x(action, stack)
            y = self._trade_marker_y(action, bar)
            symbol, color, size, direction = self._trade_marker_visual(action)
            markers.append(
                TradeMarker(
                    action=action,
                    direction=direction,
                    x=x,
                    y=y,
                    symbol=symbol,
                    brush=color,
                    size=size,
                    detail_lines=self._trade_action_detail_lines(action),
                )
            )
        links = self._trade_link_segments(visible_actions, markers)
        self._trade_markers = markers
        self._trade_links = links

    def _trade_marker_visual(self, action: SessionAction) -> tuple[str, str, float, str]:
        if action.action_type is ActionType.OPEN_LONG:
            return "o", "#d84a4a", 8.0, "long"
        if action.action_type is ActionType.OPEN_SHORT:
            return "o", "#1f8b24", 8.0, "short"
        if action.action_type is ActionType.CLOSE:
            return "d", TRADE_CLOSE_MARKER_COLOR, 9.0, "flat"
        if action.action_type is ActionType.ADD:
            return "o", "#d84a4a", 7.0, "add"
        return "o", "#1f8b24", 7.0, "reduce"

    def _trade_marker_x(self, action: SessionAction, stack: int) -> float:
        if stack == 0:
            return float(action.bar_index)
        direction = -1.0 if stack % 2 else 1.0
        magnitude = 0.12 * ((stack + 1) // 2)
        return float(action.bar_index) + direction * magnitude

    @staticmethod
    def _trade_marker_y(action: SessionAction, bar: Bar) -> float:
        return float(action.price if action.price is not None else bar.close)

    def _trade_action_detail_lines(self, action: SessionAction) -> list[str]:
        action_label = {
            ActionType.OPEN_LONG: "开多",
            ActionType.OPEN_SHORT: "开空",
            ActionType.CLOSE: "平仓",
            ActionType.ADD: "加仓",
            ActionType.REDUCE: "减仓",
        }.get(action.action_type, action.action_type.value)
        quantity = int(action.quantity) if float(action.quantity).is_integer() else round(float(action.quantity), 2)
        return [
            f"{action_label} | {action.timestamp:%Y-%m-%d %H:%M}",
            f"价格 {format_price(float(action.price or 0.0), self._tick_size)}",
            f"手数 {quantity}",
            f"Bar {action.bar_index + 1}",
            "自动触发" if action.extra.get("auto") else "手动成交",
        ]

    def _trade_link_segments(self, actions: list[SessionAction], markers: list[TradeMarker]) -> list[TradeLink]:
        marker_lookup: dict[tuple[int, ActionType, float], list[TradeMarker]] = {}
        for marker in markers:
            marker_lookup.setdefault((marker.action.bar_index, marker.action.action_type, float(marker.action.quantity)), []).append(marker)
        open_lots: list[dict[str, object]] = []
        links: list[TradeLink] = []
        for action in actions:
            price = float(action.price or 0.0)
            if action.action_type is ActionType.OPEN_LONG:
                open_lots.append({"direction": "long", "quantity": float(action.quantity), "bar_index": action.bar_index, "price": price, "timestamp": action.timestamp})
                continue
            if action.action_type is ActionType.OPEN_SHORT:
                open_lots.append({"direction": "short", "quantity": float(action.quantity), "bar_index": action.bar_index, "price": price, "timestamp": action.timestamp})
                continue
            if action.action_type is ActionType.ADD and open_lots:
                direction = str(open_lots[-1]["direction"])
                open_lots.append({"direction": direction, "quantity": float(action.quantity), "bar_index": action.bar_index, "price": price, "timestamp": action.timestamp})
                continue
            if action.action_type not in {ActionType.CLOSE, ActionType.REDUCE}:
                continue
            remaining = float(action.quantity)
            while remaining > 0 and open_lots:
                lot = open_lots[0]
                matched_qty = min(remaining, float(lot["quantity"]))
                remaining -= matched_qty
                lot["quantity"] = float(lot["quantity"]) - matched_qty
                direction = str(lot["direction"])
                entry_price = float(lot["price"])
                pnl = (price - entry_price) * matched_qty * (1 if direction == "long" else -1)
                entry_marker = self._find_trade_marker(markers, int(lot["bar_index"]), entry_price)
                exit_marker = self._find_trade_marker(markers, action.bar_index, price, preferred_action=action.action_type)
                if entry_marker is not None and exit_marker is not None:
                    qty_text = int(matched_qty) if float(matched_qty).is_integer() else round(matched_qty, 2)
                    links.append(
                        TradeLink(
                            x1=entry_marker.x,
                            y1=entry_marker.y,
                            x2=exit_marker.x,
                            y2=exit_marker.y,
                            pnl=pnl,
                            detail_lines=[
                                f"{'多单' if direction == 'long' else '空单'} | {lot['timestamp']:%Y-%m-%d %H:%M} -> {action.timestamp:%Y-%m-%d %H:%M}",
                                f"开 {format_price(entry_price, self._tick_size)} -> 平 {format_price(price, self._tick_size)}",
                                f"手数 {qty_text}",
                                f"PnL {pnl:.2f}",
                                "交易连线",
                            ],
                        )
                    )
                if float(lot["quantity"]) <= 0.0001:
                    open_lots.pop(0)
        return links

    @staticmethod
    def _find_trade_marker(markers: list[TradeMarker], bar_index: int, price: float, preferred_action: ActionType | None = None) -> TradeMarker | None:
        candidates = [
            marker for marker in markers
            if marker.action.bar_index == bar_index and (preferred_action is None or marker.action.action_type is preferred_action)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda item: abs(float(item.action.price or 0.0) - price))

    def _parallel_channel_segments(
        self,
        first: DrawingAnchor,
        second: DrawingAnchor,
        offset_anchor: DrawingAnchor,
    ) -> list[tuple[list[float], list[float]]]:
        dx = second.x - first.x
        dy = second.y - first.y
        length = hypot(dx, dy)
        if length <= 0.0001:
            return [([first.x, offset_anchor.x], [first.y, offset_anchor.y])]
        normal_x = -dy / length
        normal_y = dx / length
        offset = (offset_anchor.x - first.x) * normal_x + (offset_anchor.y - first.y) * normal_y
        shifted_first = DrawingAnchor(first.x + normal_x * offset, first.y + normal_y * offset)
        shifted_second = DrawingAnchor(second.x + normal_x * offset, second.y + normal_y * offset)
        return [
            ([first.x, second.x], [first.y, second.y]),
            ([shifted_first.x, shifted_second.x], [shifted_first.y, shifted_second.y]),
            ([first.x, shifted_first.x], [first.y, shifted_first.y]),
            ([second.x, shifted_second.x], [second.y, shifted_second.y]),
        ]

    def _set_dragging(self, dragging: bool) -> None:
        if self._is_dragging == dragging:
            return
        self._is_dragging = dragging
        if dragging:
            self._log_interaction("hover_hidden_dragging")
            self._hide_crosshair()
        else:
            self._hide_crosshair()
            if self._interaction_mode is InteractionMode.BROWSE:
                self._log_interaction("hover_resume_after_drag")
        self._log_interaction("set_dragging", dragging=dragging)
        self.interactionModeChanged.emit(self._interaction_mode)

    def _set_interaction_mode(self, mode: InteractionMode) -> None:
        if self._interaction_mode == mode:
            return
        previous_mode = self._interaction_mode
        self._interaction_mode = mode
        if mode is not InteractionMode.DRAWING:
            self._drawing_preview_anchor = None
        if mode is InteractionMode.DRAWING:
            self._set_dragging(False)
            self._suppress_next_left_click = False
        if mode is InteractionMode.BROWSE:
            self._hide_crosshair()
        self._log_interaction("set_interaction_mode", previous_mode=previous_mode.value, mode=mode.value)
        self.interactionModeChanged.emit(mode)

    def _log_interaction(self, event: str, **fields) -> None:
        payload = {
            "interaction_mode": self._interaction_mode.value,
            "active_drawing_tool": self._active_drawing_tool.value if self._active_drawing_tool else "",
            "preview_order_type": self._preview_order_type or "",
            "is_dragging": self._is_dragging,
            "suppress_next_left_click": self._suppress_next_left_click,
        }
        payload.update(fields)
        logger.bind(component="chart_interaction", **payload).debug("event={event}", event=event)

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
        return ChartWidget._session_marker_label(bar_time, timeframe_minutes) is not None

    @staticmethod
    def _session_marker_label(bar_time: time, timeframe_minutes: int) -> str | None:
        current_minutes = bar_time.hour * 60 + bar_time.minute
        for session_open, label in zip(SESSION_OPEN_TIMES, ("日盘", "夜盘")):
            open_minutes = session_open.hour * 60 + session_open.minute
            if 0 <= current_minutes - open_minutes <= timeframe_minutes:
                return label
        return None

    @staticmethod
    def _ema(values: list[float], period: int) -> list[float]:
        if not values:
            return []
        multiplier = 2 / (period + 1)
        ema_values = [values[0]]
        for price in values[1:]:
            ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
        return ema_values
