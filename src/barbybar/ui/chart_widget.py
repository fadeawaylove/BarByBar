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
DRAWING_ANCHOR_HIT_DISTANCE_PX = 12.0
TRADE_MARKER_HIT_DISTANCE_PX = 12.0
ORDER_LINE_HIT_DISTANCE_PX = 16.0
TRADE_LINK_WIN_COLOR = "#1f8b24"
TRADE_LINK_LOSS_COLOR = "#d84a4a"
TRADE_CLOSE_MARKER_COLOR = "#5f6b7a"


@dataclass(slots=True)
class TradeMarker:
    action: SessionAction
    trade_number: int | None
    direction: str
    x: float
    y: float
    symbol: str
    brush: str
    size: float
    detail_lines: list[str]


@dataclass(slots=True)
class TradeLink:
    trade_number: int | None
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


class DrawingDragMode(str, Enum):
    ANCHOR = "anchor"
    TRANSLATE = "translate"


class HoverTargetType(str, Enum):
    NONE = "none"
    ORDER_LINE = "order_line"
    DRAWING_ANCHOR = "drawing_anchor"
    DRAWING_BODY = "drawing_body"
    TRADE_MARKER = "trade_marker"
    TRADE_LINK = "trade_link"
    BAR = "bar"


class ActiveDragTargetType(str, Enum):
    NONE = "none"
    ORDER_LINE = "order_line"
    DRAWING_ANCHOR = "drawing_anchor"
    DRAWING_BODY = "drawing_body"


@dataclass(slots=True)
class HoverTarget:
    target_type: HoverTargetType = HoverTargetType.NONE
    order_line_id: int | None = None
    order_line_type: OrderLineType | None = None
    drawing_index: int | None = None
    anchor_index: int | None = None
    trade_marker: TradeMarker | None = None
    trade_link: TradeLink | None = None
    bar_index: int | None = None
    bar: Bar | None = None
    scene_pos: QPointF | None = None
    view_pos: QPointF | None = None
    distance_px: float | None = None


@dataclass(slots=True)
class ActiveDragTarget:
    target_type: ActiveDragTargetType = ActiveDragTargetType.NONE
    order_line_id: int | None = None
    drawing_index: int | None = None
    anchor_index: int | None = None


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
        self.chart._log_interaction(
            "mouse_drag_received",
            button=str(ev.button()),
            is_start=bool(ev.isStart()),
            is_finish=bool(ev.isFinish()),
            scene_x=round(float(ev.scenePos().x()), 3),
            scene_y=round(float(ev.scenePos().y()), 3),
            last_scene_x=round(float(ev.lastScenePos().x()), 3),
            last_scene_y=round(float(ev.lastScenePos().y()), 3),
            hovered_order_line_id=self.chart._hovered_order_line_id or -1,
            drawing_drag_mode=self.chart._drawing_drag_mode.value if self.chart._drawing_drag_mode else "",
            protective_drag_line_id=self.chart._protective_drag_line_id or -1,
            protective_drag_from_average=self.chart._protective_drag_from_average,
        )
        if self.chart.interaction_mode in {InteractionMode.DRAWING, InteractionMode.ORDER_PREVIEW}:
            self.chart._log_interaction(
                "mouse_drag_ignored_tool_mode",
                button=str(ev.button()),
                is_start=bool(ev.isStart()),
                is_finish=bool(ev.isFinish()),
            )
            ev.ignore()
            return
        if self.chart.handle_order_line_drag_event(ev):
            return
        if self.chart.handle_drawing_drag_event(ev):
            return
        if ev.button() != Qt.MouseButton.LeftButton:
            super().mouseDragEvent(ev, axis=axis)
            return
        if ev.isStart():
            self.chart._pan_drag_start_scene_pos = ev.buttonDownScenePos() if hasattr(ev, "buttonDownScenePos") else ev.lastScenePos()
            self.chart._log_interaction(
                "mouse_drag_start_anchor",
                anchor_x=round(float(self.chart._pan_drag_start_scene_pos.x()), 3) if self.chart._pan_drag_start_scene_pos is not None else -1.0,
                anchor_y=round(float(self.chart._pan_drag_start_scene_pos.y()), 3) if self.chart._pan_drag_start_scene_pos is not None else -1.0,
            )
        if ev.isFinish():
            if self.chart.is_dragging:
                self.chart._set_dragging(False)
                self.chart._suppress_next_left_click = True
                self.chart._log_interaction("mouse_drag_finished", suppress_next_left_click=True)
            self.chart._pan_drag_start_scene_pos = None
            ev.accept()
            return
        current_pos = ev.scenePos()
        last_pos = ev.lastScenePos()
        delta_x = float(current_pos.x() - last_pos.x())
        delta_y = float(current_pos.y() - last_pos.y())
        if not self.chart.is_dragging:
            anchor_pos = self.chart._pan_drag_start_scene_pos or last_pos
            distance = hypot(float(current_pos.x() - anchor_pos.x()), float(current_pos.y() - anchor_pos.y()))
            if distance < self.chart._drag_threshold_px:
                self.chart._log_interaction(
                    "mouse_drag_below_threshold",
                    distance=round(distance, 3),
                    threshold=self.chart._drag_threshold_px,
                    anchor_x=round(float(anchor_pos.x()), 3),
                    anchor_y=round(float(anchor_pos.y()), 3),
                )
                ev.ignore()
                return
            self.chart._set_dragging(True)
            self.chart._log_interaction(
                "mouse_drag_started",
                distance=round(distance, 3),
                delta_x=round(delta_x, 3),
                delta_y=round(delta_y, 3),
                anchor_x=round(float(anchor_pos.x()), 3),
                anchor_y=round(float(anchor_pos.y()), 3),
            )
        ev.accept()
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
    protectiveOrderCreated = Signal(str, float)
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
        self._order_line_items: dict[int, pg.InfiniteLine] = {}
        self._order_line_labels: dict[int, pg.TextItem] = {}
        self._trade_actions: list[SessionAction] = []
        self._trade_links: list[TradeLink] = []
        self._trade_markers: list[TradeMarker] = []
        self._trade_markers_visible = True
        self._trade_links_visible = True
        self._focused_trade_number: int | None = None
        self._focused_trade_points: tuple[int, float, int, float] | None = None
        self._preview_order_type: str | None = None
        self._preview_quantity = 1.0
        self._tick_size = 1.0
        self._position_direction: str | None = None
        self._interaction_mode = InteractionMode.BROWSE
        self._is_dragging = False
        self._drag_threshold_px = 4.0
        self._pan_drag_start_scene_pos: QPointF | None = None
        self._suppress_next_left_click = False
        self._drawing_drag_mode: DrawingDragMode | None = None
        self._drag_drawing_index: int | None = None
        self._drag_anchor_index: int | None = None
        self._drag_start_view_pos: DrawingAnchor | None = None
        self._drag_start_anchors: list[DrawingAnchor] = []
        self._drag_drawing_changed = False
        self._hovered_drawing_index: int | None = None
        self._hovered_anchor_index: int | None = None
        self._hovered_order_line_type: OrderLineType | None = None
        self._protective_drag_order_type: OrderLineType | None = None
        self._protective_drag_start_price: float | None = None
        self._protective_drag_preview_price: float | None = None
        self._protective_drag_line_id: int | None = None
        self._protective_drag_from_average = False
        self._native_order_drag_active = False
        self._hovered_order_line_id: int | None = None
        self._hover_target = HoverTarget()
        self._active_drag_target = ActiveDragTarget()

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
        self._clear_drawing_drag_state()
        self._active_drag_target = ActiveDragTarget()
        self._apply_hover_target(self._empty_hover_target())
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
        self._active_drag_target = ActiveDragTarget()
        self._apply_hover_target(self._empty_hover_target())
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

    def set_position_direction(self, direction: str | None) -> None:
        self._position_direction = direction

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
        self._active_drag_target = ActiveDragTarget()
        self._clear_protective_drag_state()
        self._preview_line.hide()
        if self._interaction_mode is InteractionMode.ORDER_PREVIEW:
            self._set_interaction_mode(InteractionMode.BROWSE)
        self._log_interaction("cancel_order_preview_done")

    def set_order_lines(self, order_lines: list[OrderLine]) -> None:
        self._order_lines = list(order_lines)
        valid_ids = {line.id for line in self._order_lines if line.id is not None and self._is_order_line_movable(line)}
        if self._hovered_order_line_id not in valid_ids:
            self._apply_hover_target(self._empty_hover_target())
        self._rebuild_order_line_items()
        self._sync_cursor()

    def set_trade_actions(self, actions: list[SessionAction], trades: list[Trade] | None = None) -> None:
        self._trade_actions = list(actions)
        self._rebuild_trade_geometry(trades)
        self._rebuild_trade_marker_items()

    def set_trade_focus(self, trade_number: int | None, points: tuple[int, float, int, float] | None = None) -> None:
        # Historical trade navigation no longer adds a persistent highlight overlay.
        self._focused_trade_number = None
        self._focused_trade_points = None
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
            self._apply_hover_target(self._empty_hover_target())
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
        previous_right = float(self._viewport.right_edge_index)
        previous_follow_latest = bool(self._viewport.follow_latest)
        self._viewport.right_edge_index += delta_bars
        # Manual panning must break "follow latest"; otherwise _apply_viewport()
        # immediately snaps the view back to the cursor edge.
        self._viewport.follow_latest = False
        self._log_interaction(
            "pan_x_requested",
            delta_bars=round(float(delta_bars), 3),
            previous_right_edge=round(previous_right, 3),
            next_right_edge=round(float(self._viewport.right_edge_index), 3),
            previous_follow_latest=previous_follow_latest,
            next_follow_latest=self._viewport.follow_latest,
        )
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
                is_focused = link.trade_number is not None and link.trade_number == self._focused_trade_number
                item = pg.PlotCurveItem(
                    [link.x1, link.x2],
                    [link.y1, link.y2],
                    pen=pg.mkPen(
                        "#ffd166" if is_focused else (TRADE_LINK_WIN_COLOR if link.pnl >= 0 else TRADE_LINK_LOSS_COLOR),
                        width=3 if is_focused else 1,
                        style=Qt.PenStyle.SolidLine,
                    ),
                )
                item.setOpacity(0.85 if is_focused else 0.55)
                item._barbybar_trade_marker = True
                item.setZValue(15 if is_focused else 13)
                self.price_plot.addItem(item)
        if self._trade_markers_visible:
            for marker in self._trade_markers:
                is_focused = marker.trade_number is not None and marker.trade_number == self._focused_trade_number
                item = pg.ScatterPlotItem(
                    [marker.x],
                    [marker.y],
                    symbol=marker.symbol,
                    size=marker.size + (3.0 if is_focused else 0.0),
                    brush=pg.mkBrush(marker.brush),
                    pen=pg.mkPen("#ffd166" if is_focused else marker.brush, width=2 if is_focused else 1),
                )
                item._barbybar_trade_marker = True
                item.setZValue(16 if is_focused else 14)
                self.price_plot.addItem(item)
        if self._focused_trade_points is not None:
            entry_bar_index, entry_price, exit_bar_index, exit_price = self._focused_trade_points
            in_view = (
                self._global_start_index <= entry_bar_index <= self._cursor
                and self._global_start_index <= exit_bar_index <= self._cursor
            )
            if in_view:
                focus_link = pg.PlotCurveItem(
                    [entry_bar_index, exit_bar_index],
                    [entry_price, exit_price],
                    pen=pg.mkPen("#ffd166", width=3, style=Qt.PenStyle.DashLine),
                )
                focus_link._barbybar_trade_marker = True
                focus_link.setOpacity(0.95)
                focus_link.setZValue(17)
                self.price_plot.addItem(focus_link)
                for x, y in ((entry_bar_index, entry_price), (exit_bar_index, exit_price)):
                    focus_marker = pg.ScatterPlotItem(
                        [x],
                        [y],
                        symbol="o",
                        size=12,
                        brush=pg.mkBrush("#fff3bf"),
                        pen=pg.mkPen("#ffd166", width=2),
                    )
                    focus_marker._barbybar_trade_marker = True
                    focus_marker.setZValue(18)
                    self.price_plot.addItem(focus_marker)

    def _rebuild_order_line_items(self) -> None:
        for item in list(self.price_plot.items):
            if getattr(item, "_barbybar_order_line", False):
                self.price_plot.removeItem(item)
        self._order_line_scene_positions.clear()
        self._order_line_items.clear()
        self._order_line_labels.clear()
        right_edge = self.price_plot.viewRange()[0][1] if self._bars else 0.0
        for line in self._order_lines:
            is_highlighted = self._is_hovered_order_line(line)
            pen, label_color, movable = self._order_line_style(line, highlighted=is_highlighted)
            line_item = pg.InfiniteLine(pos=line.price, angle=0, movable=False, pen=pen)
            line_item._barbybar_order_line = True
            line_item.setZValue(20)
            self.price_plot.addItem(line_item)
            label_fill = pg.mkBrush(255, 243, 191, 245) if is_highlighted else pg.mkBrush(255, 255, 255, 235)
            label = pg.TextItem(self._order_line_label(line), color=label_color, fill=label_fill, anchor=(1, 0.5))
            label._barbybar_order_line = True
            label.setPos(right_edge - 0.4, line.price)
            label.setZValue(21)
            self.price_plot.addItem(label)
            if line.id is not None and movable:
                self._order_line_items[line.id] = line_item
                self._order_line_labels[line.id] = label
                scene_point = self.price_plot.vb.mapViewToScene(QPointF(float(self._global_start_index), float(line.price)))
                self._order_line_scene_positions[line.id] = float(scene_point.y())

    def _apply_viewport(self) -> None:
        if not self._bars or self._is_applying_viewport:
            return
        self._is_applying_viewport = True
        try:
            requested_right_edge = float(self._viewport.right_edge_index)
            requested_follow_latest = bool(self._viewport.follow_latest)
            if self._viewport.follow_latest:
                self._viewport.right_edge_index = self._cursor + 1
            clamp_bounds = self._clamp_viewport()
            left = self._viewport.right_edge_index - self._viewport.bars_in_view
            right = self._viewport.right_edge_index + self._right_padding
            self.price_plot.setXRange(left, right, padding=0)
            visible_window_has_bars = self._apply_y_range(left, self._viewport.right_edge_index)
            self._rebuild_order_line_items()
            self._rebuild_trade_geometry(None)
            self._rebuild_trade_marker_items()
            self._log_interaction(
                "viewport_applied",
                requested_right_edge=round(requested_right_edge, 3),
                applied_right_edge=round(float(self._viewport.right_edge_index), 3),
                left=round(float(left), 3),
                right=round(float(right), 3),
                bars_in_view=int(self._viewport.bars_in_view),
                clamped_right_edge=round(float(self._viewport.right_edge_index), 3),
                min_right_edge=round(float(clamp_bounds[0]), 3),
                max_right_edge=round(float(clamp_bounds[1]), 3),
                cursor=self._cursor,
                right_padding=round(float(self._right_padding), 3),
                follow_latest=requested_follow_latest,
                applied_follow_latest=bool(self._viewport.follow_latest),
                visible_window_has_bars=visible_window_has_bars,
            )
        finally:
            self._is_applying_viewport = False
        self.viewportChanged.emit()

    def _clamp_viewport(self) -> tuple[float, float]:
        blank_buffer = float(max(self._viewport.bars_in_view * 4, self._total_count or len(self._bars), 200))
        min_right = float(self._global_start_index) - blank_buffer
        max_right = (
            max(float(self._cursor + 1), 0.0)
            if self._viewport.follow_latest
            else max(float(max(self._total_count - 1, 0)) + self._right_padding + blank_buffer, min_right)
        )
        self._viewport.right_edge_index = min(max(self._viewport.right_edge_index, min_right), max_right)
        return min_right, max_right

    def _apply_y_range(self, left: float, right_edge: float) -> bool:
        window = self._revealed_window_bars(left, right_edge)
        if not window:
            return False
        low = min(bar.low for _, bar in window)
        high = max(bar.high for _, bar in window)
        height = max(high - low, max(abs(high) * 0.01, 1.0))
        padding = max(height * 0.06, 0.5)
        self.price_plot.setYRange(low - padding, high + padding, padding=0)
        return True

    def _revealed_window_bars(self, left: float, right_edge: float) -> list[tuple[int, Bar]]:
        if self._cursor < 0:
            return []
        start = max(self._global_start_index, int(floor(left)))
        stop = min(self._cursor + 1, int(ceil(right_edge)))
        result: list[tuple[int, Bar]] = []
        for global_index in range(start, stop):
            local_index = global_index - self._global_start_index
            if 0 <= local_index < len(self._bars):
                result.append((global_index, self._bars[local_index]))
        return result

    def _handle_scene_click(self, event) -> None:  # noqa: ANN001
        scene_pos = event.scenePos()
        in_chart = bool(self.price_plot.sceneBoundingRect().contains(scene_pos))
        if in_chart and not self._is_dragging:
            self._apply_hover_target(self._compute_hover_target(scene_pos))
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
                if self._hover_target.target_type in {HoverTargetType.DRAWING_ANCHOR, HoverTargetType.DRAWING_BODY}:
                    drawing_index = self._hover_target.drawing_index
                    if drawing_index is not None:
                        self._log_interaction("scene_click_open_drawing_context_menu", drawing_index=drawing_index)
                        self._show_drawing_context_menu(drawing_index, scene_pos)
                        event.accept()
                        return
                if (
                    self._hover_target.target_type is HoverTargetType.ORDER_LINE
                    and self._hover_target.order_line_id is not None
                ):
                    order_id = self._hover_target.order_line_id
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
        anchor = self._normalized_drawing_anchor(DrawingAnchor(float(point.x()), float(point.y())))
        self._log_interaction(
            "scene_click_consume_drawing",
            mapped_x=round(anchor.x, 3),
            mapped_y=round(anchor.y, 3),
            pending_anchors=len(self._pending_drawing_anchors),
            needed_anchors=self._anchors_required(self._active_drawing_tool),
        )
        self._consume_drawing_click(anchor)
        event.accept()

    def _handle_mouse_moved(self, event) -> None:  # noqa: ANN001
        pos = event[0]
        if self._is_dragging:
            self._log_interaction("mouse_move_skipped_dragging")
        else:
            self._apply_hover_target(self._compute_hover_target(pos))
        if self._active_drawing_tool is not None:
            if self.price_plot.sceneBoundingRect().contains(pos):
                point = self.price_plot.vb.mapSceneToView(pos)
                anchor = self._normalized_drawing_anchor(DrawingAnchor(float(point.x()), float(point.y())))
                self._drawing_preview_anchor = anchor
                self._log_interaction(
                    "mouse_move_drawing_preview",
                    mapped_x=round(anchor.x, 3),
                    mapped_y=round(anchor.y, 3),
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
            or self._interaction_mode is InteractionMode.DRAWING
        ):
            self._hide_crosshair(preserve_axis_label=self._native_order_drag_active)
            return
        if not self.price_plot.sceneBoundingRect().contains(pos):
            self._hide_crosshair(preserve_axis_label=self._native_order_drag_active)
            return
        point = self._hover_target.view_pos or self.price_plot.vb.mapSceneToView(pos)
        self._last_hover_price = self._snap_price(float(point.y()))
        if self._preview_order_type:
            self._log_interaction(
                "mouse_move_order_preview",
                mapped_x=round(float(point.x()), 3),
                mapped_y=round(float(point.y()), 3),
                snapped_price=self._last_hover_price,
            )
            self._preview_line.setPos(self._last_hover_price)
            self._preview_line.show()
        if self._hover_target.target_type is HoverTargetType.TRADE_MARKER and self._hover_target.trade_marker is not None:
            marker = self._hover_target.trade_marker
            hover_price = marker.y
            hover_x = int(round(marker.x))
            self._update_crosshair(hover_x, hover_price)
            self._update_trade_hover_info(marker.detail_lines)
            return
        if self._hover_target.target_type is HoverTargetType.TRADE_LINK and self._hover_target.trade_link is not None:
            link = self._hover_target.trade_link
            hover_price = link.y2
            hover_x = int(round(link.x2))
            self._update_crosshair(hover_x, hover_price)
            self._update_trade_hover_info(link.detail_lines)
            return
        if self._hover_target.target_type is not HoverTargetType.BAR or self._hover_target.bar is None or self._hover_target.bar_index is None:
            self._hide_crosshair(preserve_axis_label=self._native_order_drag_active)
            return
        index, bar = self._hover_target.bar_index, self._hover_target.bar
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
        self._show_axis_price_label(price)

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

    def _hide_crosshair(self, *, preserve_axis_label: bool = False) -> None:
        self._v_line.hide()
        self._h_line.hide()
        if not preserve_axis_label:
            self._axis_price_label.hide()
        self._hover_card.hide()

    def _show_axis_price_label(self, price: float) -> None:
        self._axis_price_label.setText(format_price(price, self._tick_size))
        self._position_axis_price_label(price)
        self._axis_price_label.show()

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

    def _empty_hover_target(self, scene_pos: QPointF | None = None, view_pos: QPointF | None = None) -> HoverTarget:
        return HoverTarget(scene_pos=scene_pos, view_pos=view_pos)

    def _hover_target_matches(self, first: HoverTarget, second: HoverTarget) -> bool:
        return (
            first.target_type == second.target_type
            and first.order_line_id == second.order_line_id
            and first.order_line_type == second.order_line_type
            and first.drawing_index == second.drawing_index
            and first.anchor_index == second.anchor_index
            and first.bar_index == second.bar_index
            and first.trade_marker is second.trade_marker
            and first.trade_link is second.trade_link
        )

    def _apply_hover_target(self, target: HoverTarget) -> None:
        previous = self._hover_target
        if self._hover_target_matches(previous, target):
            self._hover_target = target
            self._sync_cursor()
            return
        self._hover_target = target
        self._hovered_order_line_id = target.order_line_id if target.target_type is HoverTargetType.ORDER_LINE else None
        self._hovered_order_line_type = target.order_line_type if target.target_type is HoverTargetType.ORDER_LINE else None
        if target.target_type is HoverTargetType.DRAWING_ANCHOR:
            self._hovered_drawing_index = target.drawing_index
            self._hovered_anchor_index = target.anchor_index
        elif target.target_type is HoverTargetType.DRAWING_BODY:
            self._hovered_drawing_index = target.drawing_index
            self._hovered_anchor_index = None
        else:
            self._hovered_drawing_index = None
            self._hovered_anchor_index = None
        self._log_interaction(
            "hover_target_changed",
            previous_target=previous.target_type.value,
            target=target.target_type.value,
            order_line_id=target.order_line_id or -1,
            order_line_type=target.order_line_type.value if target.order_line_type else "",
            drawing_index=target.drawing_index if target.drawing_index is not None else -1,
            anchor_index=target.anchor_index if target.anchor_index is not None else -1,
            bar_index=target.bar_index if target.bar_index is not None else -1,
            distance_px=round(float(target.distance_px), 3) if target.distance_px is not None else -1.0,
        )
        self._rebuild_order_line_items()
        self._rebuild_line_items()
        self._sync_cursor()

    def _is_hovered_order_line(self, line: OrderLine) -> bool:
        if self._hover_target.target_type is not HoverTargetType.ORDER_LINE:
            return False
        if line.id is not None and self._hover_target.order_line_id is not None:
            return line.id == self._hover_target.order_line_id
        return line.order_type is self._hover_target.order_line_type

    def _compute_hover_target(self, scene_pos) -> HoverTarget:  # noqa: ANN001
        if self._cursor < 0 or not self.price_plot.sceneBoundingRect().contains(scene_pos):
            return self._empty_hover_target(scene_pos=scene_pos)
        view_pos = self.price_plot.vb.mapSceneToView(scene_pos)
        order_target = self._order_line_hover_target(scene_pos, view_pos)
        if order_target is not None:
            return order_target
        anchor_hit = self._drawing_anchor_at_scene_pos(scene_pos)
        if anchor_hit is not None:
            drawing_index, anchor_index = anchor_hit
            anchor_scene = self.price_plot.vb.mapViewToScene(
                QPointF(self._drawings[drawing_index].anchors[anchor_index].x, self._drawings[drawing_index].anchors[anchor_index].y)
            )
            distance = hypot(float(scene_pos.x()) - float(anchor_scene.x()), float(scene_pos.y()) - float(anchor_scene.y()))
            return HoverTarget(
                target_type=HoverTargetType.DRAWING_ANCHOR,
                drawing_index=drawing_index,
                anchor_index=anchor_index,
                scene_pos=scene_pos,
                view_pos=view_pos,
                distance_px=distance,
            )
        drawing_hit = self._drawing_at_scene_pos(scene_pos)
        if drawing_hit is not None:
            drawing_index, _drawing = drawing_hit
            border_distance, _inside = self._drawing_hit_test(self._drawings[drawing_index], scene_pos)
            return HoverTarget(
                target_type=HoverTargetType.DRAWING_BODY,
                drawing_index=drawing_index,
                scene_pos=scene_pos,
                view_pos=view_pos,
                distance_px=border_distance or 0.0,
            )
        trade_hover = self._trade_marker_at_scene_pos(scene_pos)
        if trade_hover is not None:
            marker, link = trade_hover
            if marker is not None:
                marker_scene = self.price_plot.vb.mapViewToScene(QPointF(marker.x, marker.y))
                distance = hypot(float(scene_pos.x()) - float(marker_scene.x()), float(scene_pos.y()) - float(marker_scene.y()))
                return HoverTarget(
                    target_type=HoverTargetType.TRADE_MARKER,
                    trade_marker=marker,
                    scene_pos=scene_pos,
                    view_pos=view_pos,
                    distance_px=distance,
                )
            return HoverTarget(
                target_type=HoverTargetType.TRADE_LINK,
                trade_link=link,
                scene_pos=scene_pos,
                view_pos=view_pos,
                distance_px=0.0,
            )
        hover = self._hover_bar_at(float(view_pos.x()))
        if hover is None:
            return self._empty_hover_target(scene_pos=scene_pos, view_pos=view_pos)
        bar_index, bar = hover
        return HoverTarget(
            target_type=HoverTargetType.BAR,
            bar_index=bar_index,
            bar=bar,
            scene_pos=scene_pos,
            view_pos=view_pos,
            distance_px=0.0,
        )

    def _order_line_hover_target(self, scene_pos, view_pos: QPointF) -> HoverTarget | None:  # noqa: ANN001
        best_target: HoverTarget | None = None
        best_priority = 99
        best_distance = float("inf")
        for line in self._order_lines:
            scene_point = self.price_plot.vb.mapViewToScene(QPointF(float(self._global_start_index), float(line.price)))
            distance = abs(float(scene_pos.y()) - float(scene_point.y()))
            if distance > ORDER_LINE_HIT_DISTANCE_PX:
                continue
            priority = 0 if self._is_order_line_movable(line) else 1
            if priority < best_priority or (priority == best_priority and distance < best_distance):
                best_priority = priority
                best_distance = distance
                best_target = HoverTarget(
                    target_type=HoverTargetType.ORDER_LINE,
                    order_line_id=line.id,
                    order_line_type=line.order_type,
                    scene_pos=scene_pos,
                    view_pos=view_pos,
                    distance_px=distance,
                )
        return best_target

    def _editable_order_id_at_scene_pos(self, scene_y: float) -> int | None:
        closest_id: int | None = None
        closest_delta = ORDER_LINE_HIT_DISTANCE_PX
        for order_id, order_scene_y in self._order_line_scene_positions.items():
            delta = abs(order_scene_y - scene_y)
            if delta <= closest_delta:
                closest_id = order_id
                closest_delta = delta
        self._log_interaction(
            "editable_order_hit_test",
            scene_y=round(float(scene_y), 3),
            matched_order_id=closest_id or -1,
            matched_delta=round(float(closest_delta), 3) if closest_id is not None else -1.0,
            tracked_order_lines=len(self._order_line_scene_positions),
        )
        return closest_id

    def _editable_order_hit_distance(self, scene_y: float) -> float | None:
        closest_delta: float | None = None
        for order_scene_y in self._order_line_scene_positions.values():
            delta = abs(order_scene_y - scene_y)
            if delta <= ORDER_LINE_HIT_DISTANCE_PX and (closest_delta is None or delta < closest_delta):
                closest_delta = delta
        return closest_delta

    def _update_hovered_order_line_state(self, scene_pos) -> None:  # noqa: ANN001
        self._apply_hover_target(self._compute_hover_target(scene_pos))

    def _set_hovered_order_line_id(self, order_id: int | None) -> None:
        if order_id is None:
            self._apply_hover_target(self._empty_hover_target())
            return
        line = next((item for item in self._order_lines if item.id == order_id), None)
        if line is None:
            self._apply_hover_target(self._empty_hover_target())
            return
        scene_point = self.price_plot.vb.mapViewToScene(QPointF(float(self._global_start_index), float(line.price)))
        self._apply_hover_target(
            HoverTarget(
                target_type=HoverTargetType.ORDER_LINE,
                order_line_id=order_id,
                order_line_type=line.order_type,
                scene_pos=scene_point,
                view_pos=QPointF(float(self._global_start_index), float(line.price)),
                distance_px=0.0,
            )
        )

    def _order_line_at_scene_pos(self, scene_pos) -> OrderLine | None:  # noqa: ANN001
        closest_line: OrderLine | None = None
        closest_delta = ORDER_LINE_HIT_DISTANCE_PX
        for line in self._order_lines:
            scene_point = self.price_plot.vb.mapViewToScene(QPointF(float(self._global_start_index), float(line.price)))
            delta = abs(float(scene_pos.y()) - float(scene_point.y()))
            if delta <= closest_delta:
                closest_line = line
                closest_delta = delta
        return closest_line

    def _average_price_line_match(self, scene_pos) -> tuple[OrderLine, float] | None:  # noqa: ANN001
        average_line = next((line for line in self._order_lines if line.order_type is OrderLineType.AVERAGE_PRICE), None)
        if average_line is None:
            return None
        scene_point = self.price_plot.vb.mapViewToScene(QPointF(float(self._global_start_index), float(average_line.price)))
        delta = abs(float(scene_pos.y()) - float(scene_point.y()))
        if delta > ORDER_LINE_HIT_DISTANCE_PX:
            return None
        return average_line, delta

    def _is_order_line_movable(self, line: OrderLine) -> bool:
        return line.order_type is not OrderLineType.AVERAGE_PRICE and line.id is not None

    def _average_price_drag_direction(self, scene_pos) -> OrderLineType | None:  # noqa: ANN001
        average_line = next((line for line in self._order_lines if line.order_type is OrderLineType.AVERAGE_PRICE), None)
        if average_line is None:
            return None
        point = self.price_plot.vb.mapSceneToView(scene_pos)
        return self._resolve_protective_order_type_from_price(self._snap_price(float(point.y())))

    def _resolve_protective_order_type_from_price(self, price: float) -> OrderLineType | None:
        average_line = next((line for line in self._order_lines if line.order_type is OrderLineType.AVERAGE_PRICE), None)
        if average_line is None:
            return None
        if abs(price - average_line.price) < max(self._tick_size, 0.0001):
            return None
        is_long = self._position_direction != "short"
        above_average = price > average_line.price
        if is_long:
            return OrderLineType.TAKE_PROFIT if above_average else OrderLineType.STOP_LOSS
        return OrderLineType.STOP_LOSS if above_average else OrderLineType.TAKE_PROFIT

    @staticmethod
    def _protective_drag_color(order_type: OrderLineType) -> str:
        return STOP_LOSS_LINE_COLOR if order_type is OrderLineType.STOP_LOSS else TAKE_PROFIT_LINE_COLOR

    def _handle_native_order_line_dragged(self, price: float) -> None:
        self._native_order_drag_active = True
        self._set_dragging(True)
        snapped_price = self._snap_price(float(price))
        self._show_axis_price_label(snapped_price)

    def _handle_native_order_line_drag_finished(self, order_id: int, price: float) -> None:
        self._native_order_drag_active = False
        snapped_price = self._snap_price(float(price))
        line = next((item for item in self._order_lines if item.id == order_id), None)
        if line is not None and abs(snapped_price - self._snap_price(float(line.price))) < max(self._tick_size, 0.0001):
            self._show_axis_price_label(snapped_price)
            self._set_dragging(False)
            return
        self._show_axis_price_label(snapped_price)
        self.orderLineMoved.emit(order_id, snapped_price)
        self._set_dragging(False)

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

    def _drawing_anchor_at_scene_pos(self, scene_pos) -> tuple[int, int] | None:  # noqa: ANN001
        hit: tuple[int, int] | None = None
        closest_distance = float("inf")
        for drawing_index, drawing in enumerate(self._drawings):
            for anchor_index, anchor in enumerate(drawing.anchors):
                anchor_scene = self.price_plot.vb.mapViewToScene(QPointF(anchor.x, anchor.y))
                distance = hypot(float(scene_pos.x()) - float(anchor_scene.x()), float(scene_pos.y()) - float(anchor_scene.y()))
                if distance <= DRAWING_ANCHOR_HIT_DISTANCE_PX and distance < closest_distance:
                    hit = (drawing_index, anchor_index)
                    closest_distance = distance
        return hit

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

    def _resolve_drawing_object_index(self, target: ChartDrawing) -> int | None:
        for index, drawing in enumerate(self._drawings):
            if drawing is target:
                return index
        return None

    def _add_drawing_anchor_items(self, drawing: ChartDrawing, drawing_index: int | None, is_hovered: bool) -> None:
        if drawing_index is None:
            return
        show_handles = is_hovered or self._drag_drawing_index == drawing_index
        if not show_handles:
            return
        for anchor_index, anchor in enumerate(drawing.anchors):
            is_active_anchor = drawing_index == self._hovered_drawing_index and anchor_index == self._hovered_anchor_index
            if self._drag_drawing_index == drawing_index and self._drag_anchor_index == anchor_index:
                is_active_anchor = True
            item = pg.ScatterPlotItem(
                [anchor.x],
                [anchor.y],
                symbol="o",
                size=8 if is_active_anchor else 6,
                brush=pg.mkBrush("#fff3bf" if is_active_anchor else "#ffffff"),
                pen=pg.mkPen("#ffd166" if is_active_anchor else "#5f6b7a", width=2),
            )
            item._barbybar_line = True
            item._barbybar_drawing_id = drawing.id
            item._barbybar_drawing_tool = drawing.tool_type.value
            item.setZValue(20)
            self.price_plot.addItem(item)

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

    def _order_line_style(self, line: OrderLine, *, highlighted: bool = False) -> tuple[pg.QtGui.QPen, str, bool]:
        width = 2 if highlighted else 1
        if line.order_type is OrderLineType.ENTRY_LONG:
            return pg.mkPen(ENTRY_LONG_LINE_COLOR, width=width, style=Qt.PenStyle.DashLine), ENTRY_LONG_LINE_COLOR, True
        if line.order_type is OrderLineType.ENTRY_SHORT:
            return pg.mkPen(ENTRY_SHORT_LINE_COLOR, width=width, style=Qt.PenStyle.DashLine), ENTRY_SHORT_LINE_COLOR, True
        if line.order_type is OrderLineType.EXIT:
            return pg.mkPen("#5f6b7a", width=width, style=Qt.PenStyle.DashLine), "#5f6b7a", True
        if line.order_type is OrderLineType.REVERSE:
            return pg.mkPen("#7a43b6", width=width, style=Qt.PenStyle.DashLine), "#7a43b6", True
        if line.order_type is OrderLineType.STOP_LOSS:
            return pg.mkPen(STOP_LOSS_LINE_COLOR, width=width, style=Qt.PenStyle.DashLine), STOP_LOSS_LINE_COLOR, True
        if line.order_type is OrderLineType.TAKE_PROFIT:
            return pg.mkPen(TAKE_PROFIT_LINE_COLOR, width=width, style=Qt.PenStyle.DashLine), TAKE_PROFIT_LINE_COLOR, True
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
        label = f"{labels[line.order_type]} {quantity}手 {format_price(line.price, self._tick_size)}"
        if not line.is_protective:
            return label
        reference_price = self._protective_reference_price(line)
        if reference_price is None:
            return label
        diff = line.price - reference_price
        if abs(diff) < 0.0001:
            diff_text = "0"
        else:
            diff_text = format_price(abs(diff), self._tick_size)
            diff_text = f"+{diff_text}" if diff > 0 else f"-{diff_text}"
        return f"{label} ({diff_text})"

    def _protective_reference_price(self, line: OrderLine) -> float | None:
        average_line = next((item for item in self._order_lines if item.order_type is OrderLineType.AVERAGE_PRICE), None)
        if average_line is not None:
            return average_line.price
        if line.reference_price_at_creation is not None:
            return float(line.reference_price_at_creation)
        return None

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

    def handle_drawing_drag_event(self, ev) -> bool:  # noqa: ANN001
        if ev.button() != Qt.MouseButton.LeftButton:
            return False
        if self._active_drawing_tool is not None or self._interaction_mode is InteractionMode.ORDER_PREVIEW or self._cursor < 0:
            return False
        if self._active_drag_target.target_type in {ActiveDragTargetType.DRAWING_ANCHOR, ActiveDragTargetType.DRAWING_BODY}:
            if ev.isFinish():
                self._finish_drawing_drag()
                ev.accept()
                return True
            if ev.isStart():
                ev.accept()
                return True
            self._update_drawing_drag(ev.scenePos())
            ev.accept()
            return True
        if self._drawing_drag_mode is None:
            if ev.isFinish():
                return False
            if not self._begin_drawing_drag():
                return False
            ev.accept()
            return True
        return False

    def _begin_drawing_drag(self) -> bool:
        if self._hover_target.target_type is HoverTargetType.DRAWING_ANCHOR:
            if self._hover_target.drawing_index is None or self._hover_target.anchor_index is None:
                return False
            self._drag_drawing_index = self._hover_target.drawing_index
            self._drag_anchor_index = self._hover_target.anchor_index
            self._drawing_drag_mode = DrawingDragMode.ANCHOR
            self._active_drag_target = ActiveDragTarget(
                target_type=ActiveDragTargetType.DRAWING_ANCHOR,
                drawing_index=self._drag_drawing_index,
                anchor_index=self._drag_anchor_index,
            )
        elif self._hover_target.target_type is HoverTargetType.DRAWING_BODY:
            if self._hover_target.drawing_index is None:
                return False
            self._drag_drawing_index = self._hover_target.drawing_index
            self._drag_anchor_index = None
            self._drawing_drag_mode = DrawingDragMode.TRANSLATE
            self._active_drag_target = ActiveDragTarget(
                target_type=ActiveDragTargetType.DRAWING_BODY,
                drawing_index=self._drag_drawing_index,
            )
        else:
            return False
        point = self._hover_target.view_pos
        if point is None:
            return False
        self._drag_start_view_pos = self._stabilize_drawing_anchor(DrawingAnchor(float(point.x()), float(point.y())))
        self._drag_start_anchors = [DrawingAnchor(anchor.x, anchor.y) for anchor in self._drawings[self._drag_drawing_index].anchors]
        self._drag_drawing_changed = False
        self._hovered_drawing_index = self._drag_drawing_index
        self._hovered_anchor_index = self._drag_anchor_index
        self._set_dragging(True)
        self._rebuild_line_items()
        return True

    def _update_drawing_drag(self, scene_pos) -> None:  # noqa: ANN001
        if self._drag_drawing_index is None or self._drawing_drag_mode is None or self._drag_start_view_pos is None:
            return
        point = self.price_plot.vb.mapSceneToView(scene_pos)
        current_anchor = self._stabilize_drawing_anchor(DrawingAnchor(float(point.x()), float(point.y())))
        drawing = self._drawings[self._drag_drawing_index]
        if self._drawing_drag_mode is DrawingDragMode.ANCHOR:
            if self._drag_anchor_index is None:
                return
            drawing.anchors[self._drag_anchor_index] = self._normalized_drawing_anchor(current_anchor)
        else:
            delta_x = current_anchor.x - self._drag_start_view_pos.x
            delta_y = current_anchor.y - self._drag_start_view_pos.y
            drawing.anchors = [
                self._stabilize_drawing_anchor(DrawingAnchor(anchor.x + delta_x, anchor.y + delta_y))
                for anchor in self._drag_start_anchors
            ]
        self._drag_drawing_changed = True
        self._rebuild_line_items()

    def _finish_drawing_drag(self) -> None:
        changed = self._drag_drawing_changed
        self._clear_drawing_drag_state()
        self._active_drag_target = ActiveDragTarget()
        self._pan_drag_start_scene_pos = None
        self._set_dragging(False)
        self._suppress_next_left_click = True
        self._rebuild_line_items()
        if changed:
            self.drawingsChanged.emit()

    def handle_order_line_drag_event(self, ev) -> bool:  # noqa: ANN001
        if ev.button() != Qt.MouseButton.LeftButton or self._active_drawing_tool is not None or self._interaction_mode is InteractionMode.ORDER_PREVIEW:
            return False
        if self._cursor < 0 or not self.price_plot.sceneBoundingRect().contains(ev.scenePos()):
            return False
        if self._active_drag_target.target_type is ActiveDragTargetType.ORDER_LINE:
            if ev.isFinish():
                self._finish_order_line_drag()
                ev.accept()
                return True
            if ev.isStart():
                ev.accept()
                return True
            self._update_order_line_drag(ev.scenePos())
            ev.accept()
            return True
        if self._protective_drag_order_type is None and not self._protective_drag_from_average:
            if ev.isFinish():
                return False
            if not self._begin_order_line_drag():
                return False
            ev.accept()
            return True
        return False

    def _begin_order_line_drag(self) -> bool:
        if self._hover_target.target_type is not HoverTargetType.ORDER_LINE:
            return False
        scene_pos = self._hover_target.scene_pos
        editable_order_id = self._hover_target.order_line_id
        self._log_interaction(
            "begin_order_line_drag_attempt",
            scene_x=round(float(scene_pos.x()), 3) if scene_pos is not None else -1.0,
            scene_y=round(float(scene_pos.y()), 3) if scene_pos is not None else -1.0,
            hovered_order_line_id=self._hovered_order_line_id or -1,
            editable_order_id=editable_order_id or -1,
            hover_target=self._hover_target.target_type.value,
        )
        if editable_order_id is not None:
            line = next((item for item in self._order_lines if item.id == editable_order_id), None)
            if line is None:
                self._log_interaction("begin_order_line_drag_missing_line", order_line_id=editable_order_id)
                return False
            snapped_price = self._snap_price(float(line.price))
            self._protective_drag_order_type = line.order_type
            self._protective_drag_line_id = editable_order_id
            self._protective_drag_start_price = snapped_price
            self._protective_drag_preview_price = snapped_price
            self._protective_drag_from_average = False
            self._preview_line.setPen(pg.mkPen(self._protective_drag_color(line.order_type), width=2, style=Qt.PenStyle.DashLine))
            self._preview_line.setPos(snapped_price)
            self._preview_line.show()
            self._show_axis_price_label(snapped_price)
            self._active_drag_target = ActiveDragTarget(
                target_type=ActiveDragTargetType.ORDER_LINE,
                order_line_id=editable_order_id,
            )
            self._set_dragging(True)
            self._log_interaction(
                "begin_order_line_drag_existing_line",
                order_line_id=editable_order_id,
                order_type=line.order_type.value,
                start_price=snapped_price,
            )
            return True
        if self._hover_target.order_line_type is not OrderLineType.AVERAGE_PRICE:
            self._log_interaction("begin_order_line_drag_no_match")
            return False
        line = next((item for item in self._order_lines if item.order_type is OrderLineType.AVERAGE_PRICE), None)
        if line is None:
            self._log_interaction("begin_order_line_drag_no_match")
            return False
        self._protective_drag_order_type = None
        self._protective_drag_line_id = None
        self._protective_drag_start_price = line.price
        self._protective_drag_preview_price = line.price
        self._protective_drag_from_average = True
        self._preview_line.setPen(pg.mkPen(AVERAGE_PRICE_LINE_COLOR, width=1, style=Qt.PenStyle.DashLine))
        self._preview_line.setPos(line.price)
        self._preview_line.show()
        self._show_axis_price_label(line.price)
        self._active_drag_target = ActiveDragTarget(target_type=ActiveDragTargetType.ORDER_LINE)
        self._set_dragging(True)
        self._log_interaction(
            "begin_order_line_drag_average_line",
            start_price=round(float(line.price), 6),
            average_delta=round(float(self._hover_target.distance_px or 0.0), 3),
        )
        return True

    def _update_order_line_drag(self, scene_pos) -> None:  # noqa: ANN001
        if self._protective_drag_order_type is None and not self._protective_drag_from_average:
            self._log_interaction("update_order_line_drag_skipped_no_active_drag")
            return
        point = self.price_plot.vb.mapSceneToView(scene_pos)
        snapped_price = self._snap_price(float(point.y()))
        self._protective_drag_preview_price = snapped_price
        if self._protective_drag_from_average:
            resolved = self._resolve_protective_order_type_from_price(snapped_price)
            self._protective_drag_order_type = resolved
            if resolved is not None:
                self._protective_drag_order_type = resolved
                self._preview_line.setPen(pg.mkPen(self._protective_drag_color(resolved), width=1, style=Qt.PenStyle.DashLine))
            else:
                self._preview_line.setPen(pg.mkPen(AVERAGE_PRICE_LINE_COLOR, width=1, style=Qt.PenStyle.DashLine))
        self._preview_line.setPos(snapped_price)
        self._show_axis_price_label(snapped_price)
        self._log_interaction(
            "update_order_line_drag",
            scene_x=round(float(scene_pos.x()), 3),
            scene_y=round(float(scene_pos.y()), 3),
            mapped_y=round(float(point.y()), 6),
            snapped_price=round(float(snapped_price), 6),
            order_line_id=self._protective_drag_line_id or -1,
            order_type=self._protective_drag_order_type.value if self._protective_drag_order_type else "",
            from_average=self._protective_drag_from_average,
        )

    def _finish_order_line_drag(self) -> None:
        order_type = self._protective_drag_order_type
        price = self._protective_drag_preview_price
        line_id = self._protective_drag_line_id
        start_price = self._protective_drag_start_price
        self._log_interaction(
            "finish_order_line_drag_start",
            order_line_id=line_id or -1,
            order_type=order_type.value if order_type else "",
            start_price=round(float(start_price), 6) if start_price is not None else -1.0,
            finish_price=round(float(price), 6) if price is not None else -1.0,
            from_average=self._protective_drag_from_average,
        )
        self._set_dragging(False)
        self._preview_line.hide()
        self._suppress_next_left_click = True
        self._pan_drag_start_scene_pos = None
        hovered_target = self._hover_target
        self._active_drag_target = ActiveDragTarget()
        self._clear_protective_drag_state()
        self._apply_hover_target(hovered_target)
        if order_type is None or price is None or start_price is None:
            self._log_interaction("finish_order_line_drag_aborted_incomplete_state")
            return
        if abs(price - start_price) < max(self._tick_size, 0.0001):
            self._log_interaction(
                "finish_order_line_drag_ignored_small_move",
                tick_size=round(float(self._tick_size), 6),
                delta=round(float(abs(price - start_price)), 6),
            )
            return
        if line_id is not None:
            self._log_interaction(
                "finish_order_line_drag_emit_move",
                order_line_id=line_id,
                finish_price=round(float(price), 6),
            )
            self.orderLineMoved.emit(line_id, price)
            return
        self._log_interaction(
            "finish_order_line_drag_emit_protective_create",
            order_type=order_type.value,
            finish_price=round(float(price), 6),
        )
        self.protectiveOrderCreated.emit(order_type.value, price)

    def _clear_protective_drag_state(self) -> None:
        self._protective_drag_order_type = None
        self._protective_drag_start_price = None
        self._protective_drag_preview_price = None
        self._protective_drag_line_id = None
        self._protective_drag_from_average = False

    def _clear_drawing_drag_state(self) -> None:
        self._drawing_drag_mode = None
        self._drag_drawing_index = None
        self._drag_anchor_index = None
        self._drag_start_view_pos = None
        self._drag_start_anchors = []
        self._drag_drawing_changed = False

    def _update_drawing_hover_state(self, scene_pos) -> None:  # noqa: ANN001
        if self._drawing_drag_mode is not None:
            return
        anchor_hit = self._drawing_anchor_at_scene_pos(scene_pos)
        hovered_drawing_index = anchor_hit[0] if anchor_hit is not None else None
        hovered_anchor_index = anchor_hit[1] if anchor_hit is not None else None
        if anchor_hit is None:
            drawing_hit = self._drawing_at_scene_pos(scene_pos)
            hovered_drawing_index = drawing_hit[0] if drawing_hit is not None else None
        if hovered_drawing_index != self._hovered_drawing_index or hovered_anchor_index != self._hovered_anchor_index:
            self._hovered_drawing_index = hovered_drawing_index
            self._hovered_anchor_index = hovered_anchor_index
            self._rebuild_line_items()

    def _normalized_drawing_anchor(self, anchor: DrawingAnchor) -> DrawingAnchor:
        anchor = self._stabilize_drawing_anchor(anchor)
        if not (self._current_keyboard_modifiers() & Qt.KeyboardModifier.ControlModifier):
            return anchor
        hover = self._hover_bar_at(anchor.x)
        if hover is None:
            return anchor
        index, bar = hover
        snapped_price = min((bar.open, bar.high, bar.low, bar.close), key=lambda price: abs(price - anchor.y))
        return DrawingAnchor(float(index), float(snapped_price))

    @staticmethod
    def _stabilize_drawing_anchor(anchor: DrawingAnchor) -> DrawingAnchor:
        return DrawingAnchor(round(float(anchor.x), 6), round(float(anchor.y), 6))

    def _current_keyboard_modifiers(self):
        return QApplication.keyboardModifiers()

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
        drawing_index = None if preview else self._resolve_drawing_object_index(drawing)
        is_hovered = not preview and drawing_index is not None and drawing_index == self._hovered_drawing_index
        if drawing.tool_type is DrawingToolType.TEXT:
            text_item = self._drawing_text_item(drawing, style, preview=preview)
            if text_item is not None:
                text_item._barbybar_line = True
                text_item._barbybar_drawing_id = drawing.id
                text_item._barbybar_drawing_tool = drawing.tool_type.value
                text_item.setZValue(19 if preview else 18)
                self.price_plot.addItem(text_item)
            if not preview:
                self._add_drawing_anchor_items(drawing, drawing_index, is_hovered)
            return
        pen = self._drawing_pen(style, preview=preview, highlighted=is_hovered)
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
        if not preview:
            self._add_drawing_anchor_items(drawing, drawing_index, is_hovered)

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

    def _drawing_pen(self, style: dict[str, object], *, preview: bool, highlighted: bool = False):
        pen_style = {
            "solid": Qt.PenStyle.SolidLine,
            "dash": Qt.PenStyle.DashLine,
            "dot": Qt.PenStyle.DotLine,
        }.get(str(style.get("line_style", "solid")), Qt.PenStyle.SolidLine)
        if preview:
            pen_style = Qt.PenStyle.DashLine
        color = "#ffd166" if highlighted and not preview else str(style.get("color", "#ff9f1c"))
        width = int(style.get("width", 2)) + (1 if highlighted and not preview else 0)
        return pg.mkPen(color, width=width, style=pen_style)

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
                    trade_number=None,
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
                            trade_number=None,
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
            self._sync_cursor()
            return
        self._is_dragging = dragging
        if dragging:
            self._log_interaction("hover_hidden_dragging")
            self._hide_crosshair()
        else:
            self._pan_drag_start_scene_pos = None
            self._hide_crosshair()
            if self._interaction_mode is InteractionMode.BROWSE:
                self._log_interaction("hover_resume_after_drag")
        self._log_interaction("set_dragging", dragging=dragging)
        self._sync_cursor()
        self.interactionModeChanged.emit(self._interaction_mode)

    def _set_interaction_mode(self, mode: InteractionMode) -> None:
        if self._interaction_mode == mode:
            self._sync_cursor()
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
        self._sync_cursor()
        self.interactionModeChanged.emit(mode)

    def _sync_cursor(self) -> None:
        if self._is_dragging:
            cursor = Qt.CursorShape.ClosedHandCursor
        elif self._hover_target.target_type is HoverTargetType.ORDER_LINE:
            cursor = Qt.CursorShape.SizeVerCursor
        elif self._hover_target.target_type in {HoverTargetType.DRAWING_ANCHOR, HoverTargetType.DRAWING_BODY}:
            cursor = Qt.CursorShape.OpenHandCursor
        elif self._crosshair_enabled and self._interaction_mode in {InteractionMode.BROWSE, InteractionMode.ORDER_PREVIEW}:
            cursor = Qt.CursorShape.CrossCursor
        else:
            cursor = Qt.CursorShape.ArrowCursor
        self.setCursor(cursor)
        self.graphics.setCursor(cursor)
        self._log_interaction("sync_cursor", cursor=str(cursor))

    def _log_interaction(self, event: str, **fields) -> None:
        payload = {
            "interaction_mode": self._interaction_mode.value,
            "active_drawing_tool": self._active_drawing_tool.value if self._active_drawing_tool else "",
            "preview_order_type": self._preview_order_type or "",
            "is_dragging": self._is_dragging,
            "suppress_next_left_click": self._suppress_next_left_click,
            "hover_target": self._hover_target.target_type.value,
            "active_drag_target": self._active_drag_target.target_type.value,
        }
        payload.update(fields)
        field_text = " ".join(f"{key}={value}" for key, value in payload.items())
        logger.bind(component="chart_interaction", **payload).debug("event={} {}", event, field_text)

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
