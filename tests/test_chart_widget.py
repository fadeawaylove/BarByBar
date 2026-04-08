from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from barbybar.domain.models import ActionType, Bar, ChartDrawing, DrawingAnchor, DrawingToolType, OrderLine, OrderLineType, SessionAction
from barbybar.ui.chart_widget import BrowseMode, ChartWidget, DOWN_CANDLE_COLOR, HoverTargetType, InteractionMode, UP_CANDLE_COLOR


def _bars(count: int = 240) -> list[Bar]:
    start = datetime(2025, 1, 1, 9, 0)
    bars: list[Bar] = []
    for idx in range(count):
        close = 100 + (idx % 17) - idx * 0.02
        bars.append(
            Bar(
                timestamp=start + timedelta(minutes=idx),
                open=close - 0.8,
                high=close + 1.2,
                low=close - 1.5,
                close=close,
                volume=1000 + idx,
            )
        )
    return bars


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


@pytest.fixture(scope="module")
def app() -> QApplication:
    return _app()


@pytest.fixture()
def widget(app: QApplication) -> ChartWidget:
    chart = ChartWidget()
    yield chart
    chart.close()
    chart.deleteLater()
    app.processEvents()


def test_zoom_and_anchor_stability(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(199)
    old_bars = widget.viewport_state.bars_in_view
    old_right = widget.viewport_state.right_edge_index
    old_left = old_right - old_bars
    latest_x = 199
    old_anchor_ratio = (latest_x - old_left) / old_bars

    widget.zoom_x(anchor_x=50, scale=0.5)

    assert widget.viewport_state.bars_in_view < old_bars
    new_left = widget.viewport_state.right_edge_index - widget.viewport_state.bars_in_view
    new_anchor_ratio = (latest_x - new_left) / widget.viewport_state.bars_in_view
    assert abs(new_anchor_ratio - old_anchor_ratio) < 0.05


def test_pan_disables_follow_latest_and_cursor_update_keeps_view(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    old_right = widget.viewport_state.right_edge_index

    widget.pan_x(-30)

    assert widget.viewport_state.follow_latest is False
    panned_right = widget.viewport_state.right_edge_index
    assert panned_right < old_right

    widget.set_cursor(151)

    assert widget.viewport_state.right_edge_index == panned_right


def test_reset_viewport_restores_follow_latest(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(120)
    widget.pan_x(-20)

    widget.reset_viewport(follow_latest=True)

    assert widget.viewport_state.follow_latest is True
    assert widget.viewport_state.right_edge_index == 121


def test_early_cursor_keeps_fixed_window_width(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(30)

    left, right = widget.current_x_range()

    assert right - left > 120
    assert widget.viewport_state.bars_in_view == 120


def test_future_bars_stay_hidden_while_window_can_extend(widget: ChartWidget) -> None:
    bars = _bars()
    widget.set_full_data(bars)
    widget.set_cursor(50)
    widget.reset_viewport(follow_latest=True)

    x_data, _ = widget._ema_curve.getData()

    assert max(x_data) == 50
    assert widget.viewport_state.right_edge_index == 51


def test_pan_allows_blank_space_when_revealed_bars_are_fewer_than_window(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(50)
    widget.pan_x(-30)

    assert widget.viewport_state.follow_latest is False
    assert widget.viewport_state.right_edge_index == 21.0


def test_pan_allows_right_blank_space_beyond_latest_bar(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(50)
    old_right = widget.viewport_state.right_edge_index

    widget.pan_x(40)

    assert widget.viewport_state.follow_latest is False
    assert widget.viewport_state.right_edge_index > old_right


def test_revealed_window_bars_can_be_empty_in_blank_space(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(50)
    widget.pan_x(-400)

    left = widget.viewport_state.right_edge_index - widget.viewport_state.bars_in_view
    assert widget._revealed_window_bars(left, widget.viewport_state.right_edge_index) == []


def test_hover_target_is_none_when_viewport_is_in_blank_space(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(50)
    widget.pan_x(-400)
    app.processEvents()

    left, _right = widget.current_x_range()
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(left + 10.0, 100.0))
    widget._handle_mouse_moved((scene_pos,))

    assert widget._hover_target.target_type is HoverTargetType.NONE
    assert widget._hover_card.isHidden() is True


def test_candle_color_constants_match_red_up_green_down() -> None:
    assert UP_CANDLE_COLOR == "#d84a4a"
    assert DOWN_CANDLE_COLOR == "#1f8b24"


def test_chart_background_grid_is_disabled(widget: ChartWidget) -> None:
    assert widget.price_plot.ctrl.xGridCheck.isChecked() is False
    assert widget.price_plot.ctrl.yGridCheck.isChecked() is False


def test_session_open_markers_render_for_0900_and_2100(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 30), open=1, high=2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 10, 0), open=1, high=2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 10, 30), open=1, high=2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 21, 30), open=1, high=2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 22, 0), open=1, high=2, low=0.5, close=1.5, volume=1),
    ]

    widget.set_window_data(bars, cursor=4, total_count=5, global_start_index=0)

    markers = [item for item in widget.price_plot.items if getattr(item, "_barbybar_session_marker", False)]

    line_markers = [item for item in markers if hasattr(item, "value")]
    label_markers = [item for item in markers if hasattr(item, "toPlainText")]

    assert len(line_markers) == 2
    assert sorted(round(marker.value(), 2) for marker in line_markers) == [-0.5, 2.5]
    assert sorted(item.toPlainText() for item in label_markers) == ["夜盘", "日盘"]


def test_hover_bar_returns_none_for_future_blank_space(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(20)

    assert widget._hover_bar_at(30.0) is None


def test_hover_info_contains_ohlc_and_mouse_price(widget: ChartWidget) -> None:
    bars = _bars()
    widget.set_full_data(bars)
    widget.set_cursor(10)
    widget.set_tick_size(0.2)

    widget._update_hover_info(bars[5], 123.45)

    assert not widget._hover_card.isHidden()
    assert widget._hover_time_label.text() == "2025-01-01 09:05"
    assert widget._hover_open_label.text() == "开 104.1"
    assert widget._hover_high_label.text() == "高 106.1"
    assert widget._hover_low_label.text() == "低 103.4"
    assert widget._hover_close_label.text() == "收 104.9"


def test_hover_info_highlights_extreme_by_direction(widget: ChartWidget) -> None:
    bullish = Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=10, high=12, low=9, close=11, volume=1)
    bearish = Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=11, high=12, low=8, close=9, volume=1)

    widget._update_hover_info(bullish, 11)
    assert "#d84a4a" in widget._hover_high_label.styleSheet()
    assert "#1f8b24" not in widget._hover_low_label.styleSheet()

    widget._update_hover_info(bearish, 9)
    assert "#1f8b24" in widget._hover_low_label.styleSheet()
    assert "#d84a4a" not in widget._hover_high_label.styleSheet()


def test_hide_crosshair_hides_hover_popup(widget: ChartWidget) -> None:
    bars = _bars()
    widget.set_full_data(bars)
    widget.set_cursor(10)
    widget._update_hover_info(bars[5], 123.45)

    widget._hide_crosshair()

    assert widget._hover_card.isHidden()


def test_order_preview_uses_tick_size_for_preview_line(widget: ChartWidget) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_tick_size(0.2)
    widget._last_hover_price = 101.23

    widget.begin_order_preview("entry_long", 3.0)

    assert widget._preview_line.isVisible()
    assert widget._preview_line.value() == 101.2


def test_order_preview_becomes_active_and_shows_preview_line(widget: ChartWidget) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)

    widget.begin_order_preview("entry_long", 2.0)

    assert widget.is_order_preview_active is True
    assert widget.interaction_mode is InteractionMode.ORDER_PREVIEW
    assert widget._preview_line.isVisible()


def test_trade_actions_render_marker_items(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_trade_actions(
        [
            SessionAction(ActionType.OPEN_LONG, 5, datetime(2025, 1, 1, 9, 5), price=101.0, quantity=1),
            SessionAction(ActionType.CLOSE, 8, datetime(2025, 1, 1, 9, 8), price=103.0, quantity=1),
        ]
    )
    widget._apply_viewport()

    trade_items = [item for item in widget.price_plot.items if getattr(item, "_barbybar_trade_marker", False)]

    assert trade_items
    assert len(widget._trade_markers) == 2
    assert len(widget._trade_links) == 1
    assert widget._trade_markers[0].symbol == "o"
    assert widget._trade_markers[0].brush == "#d84a4a"


def test_trade_marker_hover_returns_action_details(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_trade_actions([SessionAction(ActionType.OPEN_LONG, 5, datetime(2025, 1, 1, 9, 5), price=101.0, quantity=1)])
    app.processEvents()
    marker = widget._trade_markers[0]
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(marker.x, marker.y))

    widget._handle_mouse_moved((scene_pos,))

    assert widget._hover_card.isHidden() is False
    assert "开多" in widget._hover_time_label.text()


def test_multiple_trade_actions_same_bar_are_staggered(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_trade_actions(
        [
            SessionAction(ActionType.OPEN_LONG, 5, datetime(2025, 1, 1, 9, 5), price=101.0, quantity=1),
            SessionAction(ActionType.ADD, 5, datetime(2025, 1, 1, 9, 5), price=101.2, quantity=1),
        ]
    )

    assert len(widget._trade_markers) == 2
    assert widget._trade_markers[0].x != widget._trade_markers[1].x
    assert widget._trade_markers[0].y == 101.0
    assert widget._trade_markers[1].y == 101.2


def test_trade_marker_uses_execution_price_for_vertical_position(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_trade_actions([SessionAction(ActionType.OPEN_LONG, 5, datetime(2025, 1, 1, 9, 5), price=101.35, quantity=1)])

    assert len(widget._trade_markers) == 1
    assert widget._trade_markers[0].y == 101.35


def test_price_label_is_positioned_on_right_axis_side(widget: ChartWidget) -> None:
    bars = _bars()
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(bars)
    widget.set_cursor(20)

    widget._update_crosshair(10, 123.4)

    assert widget._axis_price_label.isVisible()
    assert widget._axis_price_label.x() >= widget.width() - widget._axis_price_label.width() - 8


class _FakeSceneClick:
    def __init__(self, scene_pos: QPointF, button: Qt.MouseButton = Qt.MouseButton.LeftButton) -> None:
        self._scene_pos = scene_pos
        self._button = button
        self.accepted = False

    def button(self):
        return self._button

    def scenePos(self):
        return self._scene_pos

    def accept(self) -> None:
        self.accepted = True


class _FakeDragEvent:
    def __init__(
        self,
        scene_pos: QPointF,
        last_scene_pos: QPointF,
        *,
        is_start: bool = False,
        is_finish: bool = False,
        button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    ) -> None:
        self._scene_pos = scene_pos
        self._last_scene_pos = last_scene_pos
        self._is_start = is_start
        self._is_finish = is_finish
        self._button = button
        self.accepted = False
        self.ignored = False

    def button(self):
        return self._button

    def scenePos(self):
        return self._scene_pos

    def lastScenePos(self):
        return self._last_scene_pos

    def isStart(self):
        return self._is_start

    def isFinish(self):
        return self._is_finish

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


def test_widget_starts_in_browse_mode(widget: ChartWidget) -> None:
    assert widget.interaction_mode is InteractionMode.BROWSE
    assert widget._hover_card.isHidden()
    assert widget._axis_price_label.isHidden()


def test_mouse_move_enters_hover_without_click(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    app.processEvents()
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(10, 100))

    widget._handle_mouse_moved((scene_pos,))

    assert widget.interaction_mode is InteractionMode.BROWSE
    assert widget._hover_card.isHidden() is False
    assert widget._axis_price_label.isHidden() is False
    assert widget._hover_target.target_type is HoverTargetType.BAR


def test_order_preview_hover_info_does_not_depend_on_browse_mode(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.begin_order_preview("entry_long", 1.0)
    app.processEvents()

    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(10, 100))
    widget._handle_mouse_moved((scene_pos,))

    assert widget.interaction_mode is InteractionMode.ORDER_PREVIEW
    assert widget._hover_card.isHidden() is False
    assert widget._preview_line.isVisible()


def test_left_drag_pans_chart_temporarily(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    app.processEvents()
    old_right = widget.viewport_state.right_edge_index

    start = widget.price_plot.vb.mapViewToScene(QPointF(100, 100))
    move = widget.price_plot.vb.mapViewToScene(QPointF(80, 100))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert widget.is_dragging is False
    assert widget.viewport_state.right_edge_index != old_right
    assert widget.interaction_mode is InteractionMode.BROWSE
    assert widget._suppress_next_left_click is True


def test_left_drag_pans_while_browse_hover_is_active(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    app.processEvents()
    old_right = widget.viewport_state.right_edge_index

    widget._handle_mouse_moved((widget.price_plot.vb.mapViewToScene(QPointF(100, 100)),))
    start = widget.price_plot.vb.mapViewToScene(QPointF(100, 100))
    move = widget.price_plot.vb.mapViewToScene(QPointF(80, 100))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert widget.viewport_state.right_edge_index != old_right
    assert widget.interaction_mode is InteractionMode.BROWSE


def test_drag_end_next_mouse_move_restores_hover(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(100, 100))
    move = widget.price_plot.vb.mapViewToScene(QPointF(80, 100))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    widget._handle_mouse_moved((widget.price_plot.vb.mapViewToScene(QPointF(90, 102)),))

    assert widget._hover_card.isHidden() is False
    assert widget._axis_price_label.isHidden() is False


def test_single_click_does_not_toggle_browse_mode_while_drawing(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    app.processEvents()
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(10, 100))

    click = _FakeSceneClick(scene_pos)
    widget._handle_scene_click(click)

    assert widget.interaction_mode is InteractionMode.DRAWING


def test_trend_line_tool_creates_drawing_after_two_clicks(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    app.processEvents()

    first = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100)))
    second = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(15, 110)))
    widget._handle_scene_click(first)
    widget._handle_scene_click(second)

    drawings = widget.drawings()
    assert len(drawings) == 1
    assert drawings[0].tool_type is DrawingToolType.TREND_LINE
    assert len(drawings[0].anchors) == 2
    assert widget.active_drawing_tool is None


def test_ctrl_click_snaps_drawing_anchor_to_nearest_ohlc(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    click = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10.4, 110.7)))
    widget._handle_scene_click(click)

    anchor = widget._pending_drawing_anchors[0]
    bar = widget._bars[10]

    assert anchor.x == 10.0
    assert anchor.y == bar.high


def test_ctrl_preview_anchor_uses_same_snap_rule(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    widget._handle_mouse_moved((widget.price_plot.vb.mapViewToScene(QPointF(11.3, 111.7)),))

    anchor = widget._drawing_preview_anchor
    assert anchor is not None
    assert anchor.x == 11.0
    assert anchor.y == widget._bars[11].high


def test_anchor_remains_free_without_ctrl(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.NoModifier)
    app.processEvents()

    click = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10.4, 105.85)))
    widget._handle_scene_click(click)

    anchor = widget._pending_drawing_anchors[0]
    assert round(anchor.x, 1) == 10.4
    assert round(anchor.y, 2) == 105.85
    assert widget.interaction_mode is InteractionMode.DRAWING


def test_horizontal_line_tool_creates_drawing_after_single_click(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.HORIZONTAL_LINE)
    app.processEvents()

    click = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 105)))
    widget._handle_scene_click(click)

    drawings = widget.drawings()
    assert len(drawings) == 1
    assert drawings[0].tool_type is DrawingToolType.HORIZONTAL_LINE
    assert len(drawings[0].anchors) == 1
    assert widget.active_drawing_tool is None
    assert widget.interaction_mode is InteractionMode.BROWSE


def test_parallel_channel_preview_and_creation(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.PARALLEL_CHANNEL)
    app.processEvents()

    first = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100)))
    second = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(15, 105)))
    third = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(12, 102)))
    widget._handle_scene_click(first)
    widget._handle_scene_click(second)
    widget._handle_mouse_moved((widget.price_plot.vb.mapViewToScene(QPointF(12, 102)),))
    preview_items = [item for item in widget.price_plot.items if getattr(item, "_barbybar_line", False)]
    widget._handle_scene_click(third)

    drawings = widget.drawings()
    assert preview_items
    assert len(drawings) == 1
    assert drawings[0].tool_type is DrawingToolType.PARALLEL_CHANNEL
    assert len(drawings[0].anchors) == 3
    assert widget.active_drawing_tool is None
    assert widget.interaction_mode is InteractionMode.BROWSE


def test_rectangle_persists_after_window_refresh(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.RECTANGLE)
    app.processEvents()

    first = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100)))
    second = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(15, 110)))
    widget._handle_scene_click(first)
    widget._handle_scene_click(second)
    saved = widget.drawings()

    widget.set_window_data(_bars(), cursor=30, total_count=240, global_start_index=0, preserve_viewport=True)
    widget.set_drawings(saved)

    drawings = widget.drawings()
    assert len(drawings) == 1
    assert drawings[0].tool_type is DrawingToolType.RECTANGLE
    assert widget.interaction_mode is InteractionMode.BROWSE


def test_ray_tool_creates_drawing_after_two_clicks(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.RAY)
    app.processEvents()

    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100))))
    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(15, 104))))

    drawing = widget.drawings()[0]
    assert drawing.tool_type is DrawingToolType.RAY
    assert drawing.style["extend_right"] is True


def test_horizontal_ray_tool_creates_drawing_after_single_click(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.HORIZONTAL_RAY)
    app.processEvents()

    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 105))))

    drawing = widget.drawings()[0]
    assert drawing.tool_type is DrawingToolType.HORIZONTAL_RAY
    assert len(drawing.anchors) == 1


def test_vertical_line_tool_creates_drawing_after_single_click(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.VERTICAL_LINE)
    app.processEvents()

    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 105))))

    drawing = widget.drawings()[0]
    assert drawing.tool_type is DrawingToolType.VERTICAL_LINE
    assert len(drawing.anchors) == 1


def test_extended_line_tool_creates_drawing_after_two_clicks(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.EXTENDED_LINE)
    app.processEvents()

    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100))))
    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(15, 104))))

    drawing = widget.drawings()[0]
    assert drawing.tool_type is DrawingToolType.EXTENDED_LINE
    assert drawing.style["extend_left"] is True
    assert drawing.style["extend_right"] is True


def test_price_range_tool_creates_drawing_after_two_clicks(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.PRICE_RANGE)
    app.processEvents()

    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100))))
    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(15, 104))))

    drawing = widget.drawings()[0]
    assert drawing.tool_type is DrawingToolType.PRICE_RANGE
    assert drawing.style["fill_opacity"] > 0


def test_fib_tool_creates_drawing_after_two_clicks(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_tick_size(0.2)
    widget.set_active_drawing_tool(DrawingToolType.FIB_RETRACEMENT)
    app.processEvents()

    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100))))
    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(15, 104))))

    drawing = widget.drawings()[0]
    assert drawing.tool_type is DrawingToolType.FIB_RETRACEMENT
    assert drawing.style["fib_levels"] == [0.0, 0.5, 1.0, 2.0]
    assert drawing.style["show_level_labels"] is True
    assert drawing.style["show_price_labels"] is True


def test_fib_drawing_renders_level_labels(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_tick_size(0.2)
    widget.set_drawings(
        [
            ChartDrawing(
                tool_type=DrawingToolType.FIB_RETRACEMENT,
                anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 104.0)],
                style={"fib_levels": [0.0, 0.5, 1.0, 2.0], "show_level_labels": True, "show_price_labels": True},
            )
        ]
    )
    app.processEvents()

    label_items = [item for item in widget.price_plot.items if getattr(item, "_barbybar_drawing_tool", "") == DrawingToolType.FIB_RETRACEMENT.value and hasattr(item, "toPlainText")]

    assert len(label_items) == 4
    assert any("0.5" in item.toPlainText() for item in label_items)


def test_text_tool_creates_placeholder_after_single_click(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TEXT)
    app.processEvents()

    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100))))

    drawing = widget.drawings()[0]
    assert drawing.tool_type is DrawingToolType.TEXT
    assert len(drawing.anchors) == 1
    assert drawing.style["text"] == ""


def test_escape_cancels_pending_drawing_without_removing_finished(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    app.processEvents()

    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100))))
    widget.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    assert widget.drawings() == []
    assert widget.interaction_mode is InteractionMode.BROWSE

    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100))))
    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(15, 110))))
    widget.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))

    assert len(widget.drawings()) == 1
    assert widget.active_drawing_tool is None
    assert widget.interaction_mode is InteractionMode.BROWSE


def test_cancel_order_preview_hides_preview_line(widget: ChartWidget) -> None:
    widget.begin_order_preview("entry_short", 1.0)

    widget.cancel_order_preview()

    assert widget._preview_line.isVisible() is False
    assert widget.is_order_preview_active is False
    assert widget.interaction_mode is InteractionMode.BROWSE


def test_escape_cancels_order_preview_and_returns_to_hover(widget: ChartWidget) -> None:
    widget.begin_order_preview("entry_short", 1.0)

    widget.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))

    assert widget.is_order_preview_active is False
    assert widget.interaction_mode is InteractionMode.BROWSE


def test_drag_then_activate_drawing_tool_first_click_starts_drawing(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(100, 100))
    move = widget.price_plot.vb.mapViewToScene(QPointF(80, 100))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))
    assert widget._suppress_next_left_click is True

    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    click = _FakeSceneClick(widget.price_plot.sceneBoundingRect().center())
    widget._handle_scene_click(click)

    assert click.accepted is True
    assert len(widget._pending_drawing_anchors) == 1
    assert widget.drawings() == []
    assert widget._suppress_next_left_click is False


def test_drag_then_begin_order_preview_first_click_confirms_order(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(100, 100))
    move = widget.price_plot.vb.mapViewToScene(QPointF(80, 100))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))
    assert widget._suppress_next_left_click is True

    captured: list[tuple[str, float, float]] = []
    widget.orderPreviewConfirmed.connect(lambda order_type, price, quantity: captured.append((order_type, price, quantity)))
    widget.begin_order_preview("entry_long", 2.0)
    click = _FakeSceneClick(widget.price_plot.sceneBoundingRect().center())
    widget._handle_scene_click(click)

    assert click.accepted is True
    assert len(captured) == 1
    assert captured[0][0] == "entry_long"
    assert widget.is_order_preview_active is False
    assert widget._suppress_next_left_click is False


def test_dragging_drawing_anchor_updates_only_target_anchor(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TREND_LINE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 105.0)])])
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(12.0, 101.0))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    drawing = widget.drawings()[0]
    assert drawing.anchors[0].x == 12.0
    assert drawing.anchors[0].y == 101.0
    assert drawing.anchors[1].x == 15.0
    assert drawing.anchors[1].y == 105.0


def test_dragging_rectangle_body_translates_all_anchors(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.RECTANGLE, anchors=[DrawingAnchor(20.0, 99.0), DrawingAnchor(24.0, 103.0)])])
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(22.0, 101.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(25.0, 104.0))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    drawing = widget.drawings()[0]
    assert drawing.anchors[0].x == 23.0
    assert drawing.anchors[0].y == 102.0
    assert drawing.anchors[1].x == 27.0
    assert drawing.anchors[1].y == 106.0


def test_dragging_text_drawing_moves_anchor(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TEXT, anchors=[DrawingAnchor(18.0, 100.0)], style={"text": "A"})])
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(18.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(20.0, 102.0))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    drawing = widget.drawings()[0]
    assert drawing.anchors[0].x == 20.0
    assert drawing.anchors[0].y == 102.0


def test_dragging_drawing_does_not_pan_chart(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TREND_LINE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 105.0)])])
    app.processEvents()
    old_right = widget.viewport_state.right_edge_index

    start = widget.price_plot.vb.mapViewToScene(QPointF(12.0, 102.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(16.0, 106.0))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert widget.viewport_state.right_edge_index == old_right


def test_dragging_drawing_emits_drawings_changed_once_on_finish(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.HORIZONTAL_LINE, anchors=[DrawingAnchor(20.0, 100.0)])])
    app.processEvents()
    changes: list[str] = []
    widget.drawingsChanged.connect(lambda: changes.append("changed"))

    start = widget.price_plot.vb.mapViewToScene(QPointF(20.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(20.0, 102.0))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert changes == ["changed"]


def test_log_interaction_includes_state_fields(widget: ChartWidget, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeBoundLogger:
        def debug(self, message: str, **kwargs) -> None:
            captured["message"] = message
            captured.update(kwargs)

    def fake_bind(**kwargs):
        captured.update(kwargs)
        return _FakeBoundLogger()

    monkeypatch.setattr("barbybar.ui.chart_widget.logger.bind", fake_bind)

    widget._log_interaction("test_event", custom_flag=True)

    assert captured["component"] == "chart_interaction"
    assert captured["interaction_mode"] == widget.interaction_mode.value
    assert captured["suppress_next_left_click"] == widget._suppress_next_left_click
    assert captured["event"] == "test_event"


def test_hover_card_is_positioned_top_right(widget: ChartWidget) -> None:
    widget.resize(900, 600)
    widget._position_hover_card()

    assert widget._hover_card.x() + widget._hover_card.width() <= widget.width() - 8
    assert widget._hover_card.y() <= 16


def test_hover_card_becomes_visible_when_widget_is_shown(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(10)

    widget._update_hover_info(widget._bars[5], 123.45)
    app.processEvents()

    assert widget._hover_card.isVisible()


def test_hover_card_grows_after_text_update(widget: ChartWidget) -> None:
    bars = _bars()
    widget.set_full_data(bars)
    widget.set_cursor(10)
    initial_height = widget._hover_card.height()

    widget._update_hover_info(bars[5], 123.45)

    assert widget._hover_card.height() > initial_height


def test_hover_time_uses_bar_close_time(widget: ChartWidget) -> None:
    bars = _bars()
    widget.set_full_data(bars)
    widget.set_cursor(10)

    widget._update_hover_info(bars[5], 123.45)

    assert widget._hover_time_label.text() == "2025-01-01 09:05"


def test_editable_order_id_at_scene_pos_returns_nearest_line(widget: ChartWidget) -> None:
    widget._order_line_scene_positions = {11: 120.0, 12: 180.0}

    assert widget._editable_order_id_at_scene_pos(124.0) == 11
    assert widget._editable_order_id_at_scene_pos(174.0) == 12
    assert widget._editable_order_id_at_scene_pos(250.0) is None


def test_drawing_hit_test_returns_targeted_drawing(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TREND_LINE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 105.0)])])
    app.processEvents()

    hit = widget._drawing_at_scene_pos(widget.price_plot.vb.mapViewToScene(QPointF(12.0, 102.0)))

    assert hit is not None
    assert hit[0] == 0
    assert hit[1].tool_type is DrawingToolType.TREND_LINE


def test_right_click_on_drawing_opens_drawing_context_menu(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TREND_LINE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 105.0)])])
    app.processEvents()
    captured: list[int] = []
    monkeypatch.setattr(widget, "_show_drawing_context_menu", lambda drawing_index, scene_pos: captured.append(drawing_index))

    click = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(12.0, 102.0)), Qt.MouseButton.RightButton)
    widget._handle_scene_click(click)

    assert click.accepted is True
    assert captured == [0]


def test_hover_target_prioritizes_order_line_over_bar(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_tick_size(0.2)
    widget.set_order_lines(
        [
            OrderLine(
                order_type=OrderLineType.STOP_LOSS,
                price=98.0,
                quantity=1,
                created_bar_index=0,
                active_from_bar_index=1,
                created_at=datetime(2025, 1, 1, 9, 0),
                id=12,
            )
        ]
    )
    app.processEvents()

    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 98.0))
    widget._handle_mouse_moved((scene_pos,))

    assert widget._hover_target.target_type is HoverTargetType.ORDER_LINE
    assert widget._hover_target.order_line_id == 12


def test_hover_target_identifies_drawing_anchor(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TREND_LINE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 105.0)])])
    app.processEvents()

    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    widget._handle_mouse_moved((scene_pos,))

    assert widget._hover_target.target_type is HoverTargetType.DRAWING_ANCHOR
    assert widget._hover_target.drawing_index == 0
    assert widget._hover_target.anchor_index == 0


def test_delete_drawing_removes_only_target(widget: ChartWidget) -> None:
    widget.set_drawings(
        [
            ChartDrawing(tool_type=DrawingToolType.TREND_LINE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 105.0)]),
            ChartDrawing(tool_type=DrawingToolType.RECTANGLE, anchors=[DrawingAnchor(20.0, 99.0), DrawingAnchor(24.0, 103.0)]),
        ]
    )

    widget.delete_drawing(None, 0)

    drawings = widget.drawings()
    assert len(drawings) == 1
    assert drawings[0].tool_type is DrawingToolType.RECTANGLE


def test_update_drawing_style_persists_normalized_style(widget: ChartWidget) -> None:
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.RECTANGLE, anchors=[DrawingAnchor(20.0, 99.0), DrawingAnchor(24.0, 103.0)])])

    widget.update_drawing_style(None, {"color": "#3366ff", "width": 3, "line_style": "dash", "fill_opacity": 0.35}, 0)

    style = widget.drawings()[0].style
    assert style["color"] == "#3366ff"
    assert style["width"] == 3
    assert style["line_style"] == "dash"
    assert style["fill_opacity"] == 0.35


def test_set_drawings_normalizes_legacy_empty_style(widget: ChartWidget) -> None:
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.HORIZONTAL_LINE, anchors=[DrawingAnchor(10.0, 100.0)], style={})])

    style = widget.drawings()[0].style
    assert style["color"] == "#ff9f1c"
    assert style["width"] == 1
    assert style["line_style"] == "solid"


def test_set_drawings_normalizes_text_defaults(widget: ChartWidget) -> None:
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TEXT, anchors=[DrawingAnchor(10.0, 100.0)], style={})])

    style = widget.drawings()[0].style
    assert style["text"] == ""
    assert style["font_size"] == 12
    assert style["text_color"] == "#ff9f1c"


def test_order_line_label_includes_type_quantity_and_price() -> None:
    widget = ChartWidget()
    widget.set_tick_size(1)
    line = OrderLine(
        order_type=OrderLineType.ENTRY_LONG,
        price=5914.0,
        quantity=2,
        created_bar_index=0,
        active_from_bar_index=1,
        created_at=datetime(2025, 1, 1, 9, 0),
    )

    assert widget._order_line_label(line) == "买 2手 5914"
    widget.close()
    widget.deleteLater()


def test_protective_order_label_includes_difference_from_average_price() -> None:
    widget = ChartWidget()
    widget.set_tick_size(1)
    widget.set_order_lines(
        [
            OrderLine(
                order_type=OrderLineType.AVERAGE_PRICE,
                price=7679.0,
                quantity=1,
                created_bar_index=0,
                active_from_bar_index=0,
                created_at=datetime(2025, 1, 1, 9, 0),
            ),
            OrderLine(
                order_type=OrderLineType.STOP_LOSS,
                price=7675.0,
                quantity=1,
                created_bar_index=0,
                active_from_bar_index=1,
                created_at=datetime(2025, 1, 1, 9, 0),
                id=7,
            ),
        ]
    )

    assert widget._order_line_label(widget._order_lines[1]) == "止损 1手 7675 (-4)"
    widget.close()
    widget.deleteLater()


def test_protective_order_label_falls_back_to_reference_price() -> None:
    widget = ChartWidget()
    widget.set_tick_size(0.2)
    line = OrderLine(
        order_type=OrderLineType.TAKE_PROFIT,
        price=102.4,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=1,
        created_at=datetime(2025, 1, 1, 9, 0),
        reference_price_at_creation=100.0,
        id=8,
    )

    assert widget._order_line_label(line) == "止盈 1手 102.4 (+2.4)"
    widget.close()
    widget.deleteLater()


def test_crosshair_price_label_follows_tick_precision(widget: ChartWidget) -> None:
    widget.set_tick_size(0.2)

    widget._update_crosshair(10, 5914.23)

    assert widget._axis_price_label.text() == "5914.2"


def test_native_order_line_drag_updates_axis_price_label(widget: ChartWidget) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_tick_size(0.2)

    widget._handle_native_order_line_dragged(5914.23)

    assert widget._axis_price_label.isVisible()
    assert widget._axis_price_label.text() == "5914.2"


def test_native_order_line_drag_keeps_axis_price_label_visible_during_mouse_move(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_tick_size(0.2)
    app.processEvents()

    widget._handle_native_order_line_dragged(5914.23)
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    widget._handle_mouse_moved((scene_pos,))

    assert widget._axis_price_label.isVisible()
    assert widget._axis_price_label.text() == "5914.2"


def test_hovering_editable_order_line_marks_it_selected(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_tick_size(0.2)
    line = OrderLine(
        order_type=OrderLineType.STOP_LOSS,
        price=98.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=1,
        created_at=datetime(2025, 1, 1, 9, 0),
        id=12,
    )
    widget.set_order_lines([line])
    app.processEvents()

    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 98.0))
    widget._handle_mouse_moved((scene_pos,))

    assert widget._hovered_order_line_id == 12
    assert widget.cursor().shape() == Qt.CursorShape.SizeVerCursor
    assert widget._order_line_items[12].pen.widthF() == 2.0


def test_average_price_drag_emits_take_profit_for_long_above_average(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_tick_size(0.2)
    widget.set_position_direction("long")
    widget.set_order_lines(
        [
            OrderLine(
                order_type=OrderLineType.AVERAGE_PRICE,
                price=100.0,
                quantity=1,
                created_bar_index=0,
                active_from_bar_index=0,
                created_at=datetime(2025, 1, 1, 9, 0),
            )
        ]
    )
    captured: list[tuple[str, float]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price: captured.append((order_type, price)))
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 102.3))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))

    assert widget._axis_price_label.isVisible()
    assert widget._axis_price_label.text() == "102.2"

    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert captured == [(OrderLineType.TAKE_PROFIT.value, 102.2)]


def test_average_price_drag_emits_stop_loss_for_long_below_average(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_tick_size(0.2)
    widget.set_position_direction("long")
    widget.set_order_lines(
        [
            OrderLine(
                order_type=OrderLineType.AVERAGE_PRICE,
                price=100.0,
                quantity=1,
                created_bar_index=0,
                active_from_bar_index=0,
                created_at=datetime(2025, 1, 1, 9, 0),
            )
        ]
    )
    captured: list[tuple[str, float]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price: captured.append((order_type, price)))
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 98.1))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert captured == [(OrderLineType.STOP_LOSS.value, 98.0)]


def test_average_price_drag_reverses_for_short_position(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_tick_size(0.2)
    widget.set_position_direction("short")
    widget.set_order_lines(
        [
            OrderLine(
                order_type=OrderLineType.AVERAGE_PRICE,
                price=100.0,
                quantity=1,
                created_bar_index=0,
                active_from_bar_index=0,
                created_at=datetime(2025, 1, 1, 9, 0),
            )
        ]
    )
    captured: list[tuple[str, float]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price: captured.append((order_type, price)))
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 102.1))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert captured == [(OrderLineType.STOP_LOSS.value, 102.0)]


def test_average_price_drag_small_move_does_not_emit_order(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_tick_size(0.2)
    widget.set_position_direction("long")
    widget.set_order_lines(
        [
            OrderLine(
                order_type=OrderLineType.AVERAGE_PRICE,
                price=100.0,
                quantity=1,
                created_bar_index=0,
                active_from_bar_index=0,
                created_at=datetime(2025, 1, 1, 9, 0),
            )
        ]
    )
    captured: list[tuple[str, float]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price: captured.append((order_type, price)))
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.05))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert captured == []


def test_hovered_non_average_order_line_drag_is_intercepted_by_custom_handler(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_tick_size(0.2)
    line = OrderLine(
        order_type=OrderLineType.STOP_LOSS,
        price=98.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=1,
        created_at=datetime(2025, 1, 1, 9, 0),
        id=12,
    )
    widget.set_order_lines([line])
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 98.0))
    widget._handle_mouse_moved((start,))

    assert widget.handle_order_line_drag_event(_FakeDragEvent(start, start, is_start=True)) is True
    assert widget.is_dragging is True
    assert widget._drag_order_label.isVisible() is True
    assert widget._axis_price_label.isVisible() is True


def test_editable_order_line_wins_over_average_price_drag_when_lines_are_close(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(40)
    widget.set_tick_size(0.2)
    widget.set_position_direction("long")
    widget.set_order_lines(
        [
            OrderLine(
                order_type=OrderLineType.AVERAGE_PRICE,
                price=100.0,
                quantity=1,
                created_bar_index=0,
                active_from_bar_index=0,
                created_at=datetime(2025, 1, 1, 9, 0),
            ),
            OrderLine(
                order_type=OrderLineType.STOP_LOSS,
                price=100.2,
                quantity=1,
                created_bar_index=0,
                active_from_bar_index=1,
                created_at=datetime(2025, 1, 1, 9, 0),
                id=12,
            ),
        ]
    )
    app.processEvents()

    stop_scene = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.2))
    widget._handle_mouse_moved((stop_scene,))

    assert widget.handle_order_line_drag_event(_FakeDragEvent(stop_scene, stop_scene, is_start=True)) is True


def test_hovered_editable_order_line_drag_moves_line_instead_of_panning_chart(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    widget.set_tick_size(0.2)
    line = OrderLine(
        order_type=OrderLineType.STOP_LOSS,
        price=98.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=1,
        created_at=datetime(2025, 1, 1, 9, 0),
        id=12,
    )
    widget.set_order_lines([line])
    app.processEvents()
    captured: list[tuple[int, float]] = []
    widget.orderLineMoved.connect(lambda order_id, price: captured.append((order_id, price)))
    old_right = widget.viewport_state.right_edge_index

    start = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 98.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 98.13))
    widget._handle_mouse_moved((start,))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))

    assert widget.viewport_state.right_edge_index == old_right
    assert widget._axis_price_label.text() == "98.2"
    assert widget.is_dragging is True
    assert widget._drag_order_label.isVisible() is True
    assert widget._drag_order_label.toPlainText() == "止损 1手 98.2"
    assert 12 not in widget._order_line_labels

    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert captured == [(12, 98.2)]
    assert widget.is_dragging is False
    assert widget._hovered_order_line_id == 12
    assert widget._drag_order_label.isVisible() is False
    assert 12 in widget._order_line_labels


def test_hovered_editable_order_line_small_drag_does_not_emit_update(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    widget.set_tick_size(0.2)
    line = OrderLine(
        order_type=OrderLineType.TAKE_PROFIT,
        price=102.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=1,
        created_at=datetime(2025, 1, 1, 9, 0),
        id=18,
    )
    widget.set_order_lines([line])
    app.processEvents()
    captured: list[tuple[int, float]] = []
    widget.orderLineMoved.connect(lambda order_id, price: captured.append((order_id, price)))

    start = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 102.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 102.05))
    widget._handle_mouse_moved((start,))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert captured == []
    assert widget._preview_line.isHidden()
    assert widget._drag_order_label.isVisible() is False
    assert widget._order_lines[0].price == 102.0


def test_hovered_transient_stop_loss_line_drag_emits_protective_upsert(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    widget.set_tick_size(0.2)
    line = OrderLine(
        order_type=OrderLineType.STOP_LOSS,
        price=98.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=1,
        created_at=datetime(2025, 1, 1, 9, 0),
        id=None,
    )
    widget.set_order_lines([line])
    app.processEvents()
    captured: list[tuple[str, float]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price: captured.append((order_type, price)))

    start = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 98.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 98.13))
    widget._handle_mouse_moved((start,))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))

    assert widget.is_dragging is True
    assert widget._axis_price_label.text() == "98.2"
    assert widget._drag_order_label.isVisible() is True
    assert widget._drag_order_label.toPlainText() == "止损 1手 98.2"

    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert captured == [(OrderLineType.STOP_LOSS.value, 98.2)]
    assert widget.is_dragging is False
    assert widget._hover_target.target_type is HoverTargetType.ORDER_LINE
    assert widget._hover_target.order_line_type is OrderLineType.STOP_LOSS
    assert widget._drag_order_label.isVisible() is False


def test_hovered_transient_take_profit_line_small_drag_does_not_emit_update(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    widget.set_tick_size(0.2)
    line = OrderLine(
        order_type=OrderLineType.TAKE_PROFIT,
        price=102.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=1,
        created_at=datetime(2025, 1, 1, 9, 0),
        id=None,
    )
    widget.set_order_lines([line])
    app.processEvents()
    captured: list[tuple[str, float]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price: captured.append((order_type, price)))

    start = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 102.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 102.05))
    widget._handle_mouse_moved((start,))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert captured == []
    assert widget._preview_line.isHidden()
    assert widget._drag_order_label.isVisible() is False
    assert widget._hover_target.target_type is HoverTargetType.ORDER_LINE
    assert widget._hover_target.order_line_type is OrderLineType.TAKE_PROFIT
