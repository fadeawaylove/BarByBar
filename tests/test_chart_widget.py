from datetime import datetime, timedelta

import pyqtgraph as pg
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from barbybar.data.tick_size import format_price
from barbybar.domain.models import ActionType, Bar, ChartDrawing, DrawingAnchor, DrawingToolType, OrderLine, OrderLineType, SessionAction
from barbybar.ui.chart_widget import (
    AVERAGE_PRICE_LINE_COLOR,
    BAR_SLOT_HALF_WIDTH,
    BrowseMode,
    CANDLE_BODY_BORDER_WIDTH,
    CANDLE_WICK_WIDTH,
    ChartWidget,
    DRAWING_SNAP_DISTANCE_PX,
    DOWN_CANDLE_COLOR,
    HoverTargetType,
    InteractionMode,
    STOP_LOSS_LINE_COLOR,
    TRADE_ENTRY_LONG_COLOR,
    TRADE_ENTRY_SHORT_COLOR,
    TRADE_EXIT_MARKER_COLOR,
    TRADE_LINK_FLAT_COLOR,
    TRADE_LINK_LOSS_COLOR,
    TRADE_LINK_WIN_COLOR,
    TAKE_PROFIT_LINE_COLOR,
    UP_CANDLE_COLOR,
)


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
                open_timestamp=start + timedelta(minutes=idx - 1),
            )
        )
    return bars


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


def _snap_preview_guide_items(widget: ChartWidget) -> list[object]:
    return [item for item in widget.price_plot.items if getattr(item, "_barbybar_snap_preview_guide", False)]


def _guide_item_points(item: object) -> tuple[list[float], list[float]]:
    x_data, y_data = item.getData()
    return list(x_data), list(y_data)


def _scene_point_with_y_offset(widget: ChartWidget, x: float, price: float, offset_px: float) -> QPointF:
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(x, price))
    return QPointF(scene_pos.x(), scene_pos.y() + offset_px)


def _scene_point_with_offset(widget: ChartWidget, x: float, price: float, offset_x_px: float = 0.0, offset_y_px: float = 0.0) -> QPointF:
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(x, price))
    return QPointF(scene_pos.x() + offset_x_px, scene_pos.y() + offset_y_px)


def _assert_no_snap_target(widget: ChartWidget, x: float, price: float) -> QPointF:
    for offset_x_px in (0.0, 40.0, 80.0, 120.0):
        for offset_y_px in (-140.0, -100.0, 100.0, 140.0):
            scene_pos = _scene_point_with_offset(widget, x, price, offset_x_px=offset_x_px, offset_y_px=offset_y_px)
            view_pos = widget.price_plot.vb.mapSceneToView(scene_pos)
            if widget._drawing_snap_target(DrawingAnchor(float(view_pos.x()), float(view_pos.y()))) is None:
                return scene_pos
    raise AssertionError("Could not find a point outside the snap radius")


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
    widget.resize(900, 600)
    widget.set_full_data(_bars())
    widget.set_cursor(199)
    widget.pan_x(-30)
    old_bars = widget.viewport_state.bars_in_view
    old_right = widget.viewport_state.right_edge_index
    old_left = old_right - old_bars
    visible_anchor_x = widget._visible_rightmost_bar_x()
    old_anchor_ratio = (visible_anchor_x - old_left) / old_bars

    widget.zoom_x(anchor_x=50, scale=0.5)

    assert widget.viewport_state.bars_in_view < old_bars
    new_left = widget.viewport_state.right_edge_index - widget.viewport_state.bars_in_view
    new_anchor_ratio = (visible_anchor_x - new_left) / widget.viewport_state.bars_in_view
    assert abs(new_anchor_ratio - old_anchor_ratio) < 0.05
    assert widget.viewport_state.follow_latest is False


def test_zoom_uses_rightmost_visible_bar_instead_of_cursor(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(199)
    widget.pan_x(-30)

    old_right = widget.viewport_state.right_edge_index
    expected_anchor_x = widget._visible_rightmost_bar_x()

    widget.zoom_x(anchor_x=20, scale=0.5)

    assert expected_anchor_x == 169.0
    assert widget.viewport_state.right_edge_index != 200.0
    assert widget.viewport_state.right_edge_index < old_right


def test_zoom_out_is_limited_by_dynamic_readable_bar_cap(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(120, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(100)
    app.processEvents()

    for _ in range(20):
        widget.zoom_x(anchor_x=100, scale=1.18)

    assert widget.viewport_state.bars_in_view == widget._max_readable_bars_in_view()


def test_wider_chart_allows_more_bars_than_narrow_chart(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(120, 600)
    widget.show()
    app.processEvents()
    narrow_cap = widget._max_readable_bars_in_view()

    widget.resize(900, 600)
    app.processEvents()

    assert widget._max_readable_bars_in_view() > narrow_cap


def test_reset_viewport_respects_dynamic_readable_bar_cap(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(120, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(100)
    app.processEvents()

    widget.reset_viewport(follow_latest=True)

    assert widget.viewport_state.bars_in_view == widget._max_readable_bars_in_view()


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


def test_set_window_data_preserve_viewport_keeps_user_zoom(widget: ChartWidget) -> None:
    widget.resize(900, 600)
    widget.set_full_data(_bars())
    widget.set_cursor(199)
    widget.zoom_x(anchor_x=50, scale=0.5)
    preserved_bars = widget.viewport_state.bars_in_view

    widget.set_window_data(_bars(180), cursor=170, total_count=240, global_start_index=20, preserve_viewport=True)

    assert widget.viewport_state.bars_in_view == preserved_bars


def test_set_window_data_preserve_viewport_clamps_existing_zoom_instead_of_resetting(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(199)
    widget.viewport_state.bars_in_view = 180
    widget.resize(120, 600)
    app.processEvents()
    readable_cap = widget._max_readable_bars_in_view()

    widget.set_window_data(_bars(180), cursor=170, total_count=240, global_start_index=20, preserve_viewport=True)

    assert widget.viewport_state.bars_in_view == readable_cap
    assert widget.viewport_state.bars_in_view != 120


def test_early_cursor_keeps_fixed_window_width(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(30)

    left, right = widget.current_x_range()

    assert right - left > 120
    assert widget.viewport_state.bars_in_view == 120


def test_viewport_left_edge_aligns_to_whole_bar(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(199)
    widget.pan_x(-30.5)

    left, visible_right = widget._visible_x_window()

    assert left + BAR_SLOT_HALF_WIDTH == pytest.approx(float(int(left + BAR_SLOT_HALF_WIDTH)))
    assert visible_right - BAR_SLOT_HALF_WIDTH == pytest.approx(float(int(visible_right - BAR_SLOT_HALF_WIDTH)))


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


def test_candle_color_constants_match_white_up_black_down_theme() -> None:
    assert UP_CANDLE_COLOR == "#000000"
    assert DOWN_CANDLE_COLOR == "#000000"


def test_candle_line_width_constants_use_integer_hard_edges() -> None:
    assert CANDLE_WICK_WIDTH == 2
    assert CANDLE_BODY_BORDER_WIDTH == 2


def test_chart_background_grid_is_disabled(widget: ChartWidget) -> None:
    assert widget.price_plot.ctrl.xGridCheck.isChecked() is False
    assert widget.price_plot.ctrl.yGridCheck.isChecked() is False


def test_chart_shows_right_price_axis_and_hides_left(widget: ChartWidget) -> None:
    assert widget.price_plot.getAxis("right").isVisible() is True
    assert widget.price_plot.getAxis("left").isVisible() is False


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
    assert sorted(item.toPlainText() for item in label_markers) == ["夜", "日"]
    y_min, y_max = widget.price_plot.viewRange()[1]
    assert all(item.pos().y() < (y_min + y_max) / 2 for item in label_markers)


def test_session_end_markers_render_for_day_and_night_tail_bars(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=1, high=2.0, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 14, 59), open=1, high=2.2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 21, 0), open=1, high=2.1, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 23, 0), open=1, high=2.4, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 2, 9, 0), open=1, high=2.0, low=0.5, close=1.5, volume=1),
    ]

    widget.set_window_data(bars, cursor=4, total_count=5, global_start_index=0)

    markers = [item for item in widget.price_plot.items if getattr(item, "_barbybar_session_end_marker", False)]
    marker_map = {round(item.pos().x(), 2): item for item in markers}

    assert len(markers) == 3
    assert sorted(marker_map) == [1.0, 3.0, 4.0]
    assert marker_map[1.0].pos().y() > bars[1].high
    assert marker_map[3.0].pos().y() > bars[3].high
    assert marker_map[4.0].pos().y() > bars[4].high


def test_session_end_markers_only_appear_after_tail_bar_is_revealed(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=1, high=2.0, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 14, 59), open=1, high=2.2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 21, 0), open=1, high=2.1, low=0.5, close=1.5, volume=1),
    ]

    widget.set_window_data(bars, cursor=0, total_count=3, global_start_index=0)
    assert [item for item in widget.price_plot.items if getattr(item, "_barbybar_session_end_marker", False)] == []

    widget.set_cursor(1)
    markers = [item for item in widget.price_plot.items if getattr(item, "_barbybar_session_end_marker", False)]

    assert len(markers) == 1
    assert round(markers[0].pos().x(), 2) == 1.0


def test_session_end_markers_do_not_accumulate_on_rebuild(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=1, high=2.0, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 14, 59), open=1, high=2.2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 21, 0), open=1, high=2.1, low=0.5, close=1.5, volume=1),
    ]

    widget.set_window_data(bars, cursor=2, total_count=3, global_start_index=0)
    widget._rebuild_session_markers()

    markers = [item for item in widget.price_plot.items if getattr(item, "_barbybar_session_end_marker", False)]

    assert len(markers) == 2


def test_daily_bars_do_not_render_intraday_session_markers(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 2, 14, 59), open=100, high=102, low=99, close=101, volume=1),
        Bar(timestamp=datetime(2025, 1, 3, 14, 59), open=101, high=103, low=100, close=102, volume=1),
    ]

    widget.set_window_data(bars, cursor=1, total_count=2, global_start_index=0, timeframe="1d")

    session_markers = [item for item in widget.price_plot.items if getattr(item, "_barbybar_session_marker", False)]
    session_end_markers = [item for item in widget.price_plot.items if getattr(item, "_barbybar_session_end_marker", False)]

    assert session_markers == []
    assert session_end_markers == []


def test_single_daily_bar_does_not_render_tail_arrow(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 3, 14, 59), open=101, high=103, low=100, close=102, volume=1),
    ]

    widget.set_window_data(bars, cursor=0, total_count=1, global_start_index=0, timeframe="1d")

    session_markers = [item for item in widget.price_plot.items if getattr(item, "_barbybar_session_marker", False)]
    session_end_markers = [item for item in widget.price_plot.items if getattr(item, "_barbybar_session_end_marker", False)]

    assert session_markers == []
    assert session_end_markers == []


def test_explicit_daily_timeframe_suppresses_session_arrows_for_intraday_like_timestamps(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 2, 9, 0), open=100, high=101, low=99, close=100.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 3, 14, 59), open=101, high=103, low=100, close=102, volume=1),
    ]

    widget.set_window_data(bars, cursor=1, total_count=2, global_start_index=0, timeframe="1d")

    session_markers = [item for item in widget.price_plot.items if getattr(item, "_barbybar_session_marker", False)]
    session_end_markers = [item for item in widget.price_plot.items if getattr(item, "_barbybar_session_end_marker", False)]

    assert session_markers == []
    assert session_end_markers == []


def test_bar_count_labels_are_hidden_by_default(widget: ChartWidget) -> None:
    widget.set_window_data(_bars(10), cursor=9, total_count=10, global_start_index=0)

    labels = [item for item in widget.price_plot.items if getattr(item, "_barbybar_bar_count_label", False)]

    assert labels == []


def test_bar_count_labels_render_even_numbers_only_when_enabled(widget: ChartWidget) -> None:
    widget.set_bar_count_labels_visible(True)
    widget.set_window_data(_bars(10), cursor=9, total_count=10, global_start_index=0)

    labels = [item for item in widget.price_plot.items if getattr(item, "_barbybar_bar_count_label", False)]

    assert [item.toPlainText() for item in labels] == ["2", "4", "6", "8", "10"]
    label_map = {int(item.toPlainText()): item for item in labels}
    bars = _bars(10)
    assert label_map[2].pos().y() < bars[1].low
    assert label_map[4].pos().y() < bars[3].low
    assert label_map[2].fill.style() == Qt.BrushStyle.NoBrush
    font_sizes = {item.textItem.font().pointSize() for item in labels}
    assert len(font_sizes) == 1
    assert next(iter(font_sizes)) <= 10


def test_bar_count_labels_reset_between_day_and_night_sessions(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=1, high=2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=1, high=2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=1, high=2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 21, 0), open=1, high=2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 21, 1), open=1, high=2, low=0.5, close=1.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 21, 2), open=1, high=2, low=0.5, close=1.5, volume=1),
    ]

    widget.set_bar_count_labels_visible(True)
    widget.set_window_data(bars, cursor=5, total_count=6, global_start_index=0)

    labels = [item for item in widget.price_plot.items if getattr(item, "_barbybar_bar_count_label", False)]

    assert [item.toPlainText() for item in labels] == ["2", "2"]


def test_bar_count_labels_stay_below_bar_when_low_side_is_close_to_view_bottom(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=104, low=99, close=103, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=103, high=105, low=100, close=104, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=104, high=106, low=99.2, close=99.8, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 3), open=99.2, high=100.5, low=98.0, close=100, volume=1),
    ]
    widget.set_bar_count_labels_visible(True)
    widget.set_window_data(bars, cursor=3, total_count=4, global_start_index=0)

    labels = [item for item in widget.price_plot.items if getattr(item, "_barbybar_bar_count_label", False)]
    label_map = {int(item.toPlainText()): item for item in labels}

    assert label_map[2].pos().y() < bars[1].low
    assert label_map[4].pos().y() < bars[3].low
    assert label_map[4].pos().y() >= widget.price_plot.viewRange()[1][0]


def test_bar_count_label_offset_scales_with_visible_y_range(widget: ChartWidget) -> None:
    bars = _bars(12)
    widget.set_bar_count_labels_visible(True)
    widget.set_window_data(bars, cursor=11, total_count=12, global_start_index=0)

    labels = [item for item in widget.price_plot.items if getattr(item, "_barbybar_bar_count_label", False)]
    label_map = {int(item.toPlainText()): item for item in labels}
    initial_y_range = widget.price_plot.viewRange()[1]
    initial_gap = bars[1].low - label_map[2].pos().y()

    widget.price_plot.setYRange(initial_y_range[0] - 50.0, initial_y_range[1] + 50.0, padding=0)
    widget._rebuild_session_markers()

    labels = [item for item in widget.price_plot.items if getattr(item, "_barbybar_bar_count_label", False)]
    label_map = {int(item.toPlainText()): item for item in labels}
    expanded_y_range = widget.price_plot.viewRange()[1]
    expanded_gap = bars[1].low - label_map[2].pos().y()

    assert expanded_gap > initial_gap
    assert label_map[2].pos().y() < bars[1].low
    assert expanded_y_range[0] < initial_y_range[0]


def test_bar_count_labels_use_recent_six_bar_average_range_for_offset(widget: ChartWidget) -> None:
    bars_with_small_history = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100.0, high=100.2, low=99.9, close=100.1, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100.1, high=100.3, low=100.0, close=100.2, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=100.2, high=100.4, low=100.1, close=100.3, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 3), open=100.3, high=100.5, low=100.2, close=100.4, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 4), open=100.4, high=100.6, low=100.3, close=100.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 5), open=100.5, high=100.7, low=100.4, close=100.6, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 6), open=101.0, high=101.2, low=100.8, close=101.1, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 7), open=101.1, high=101.3, low=100.9, close=101.2, volume=1),
    ]
    bars_with_large_history = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100.0, high=102.0, low=99.0, close=101.0, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=101.0, high=103.0, low=100.0, close=102.0, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=102.0, high=104.0, low=101.0, close=103.0, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 3), open=103.0, high=105.0, low=102.0, close=104.0, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 4), open=104.0, high=106.0, low=103.0, close=105.0, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 5), open=105.0, high=107.0, low=104.0, close=106.0, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 6), open=101.0, high=101.2, low=100.8, close=101.1, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 7), open=101.1, high=101.3, low=100.9, close=101.2, volume=1),
    ]
    widget.set_bar_count_labels_visible(True)
    widget.set_window_data(bars_with_small_history, cursor=7, total_count=8, global_start_index=0)
    widget.price_plot.setYRange(95.0, 110.0, padding=0)
    widget._rebuild_session_markers()
    small_gap = bars_with_small_history[7].low - widget._bar_count_label_y(7)

    widget.set_window_data(bars_with_large_history, cursor=7, total_count=8, global_start_index=0)
    widget.price_plot.setYRange(95.0, 110.0, padding=0)
    widget._rebuild_session_markers()
    large_gap = bars_with_large_history[7].low - widget._bar_count_label_y(7)

    assert large_gap > small_gap


def test_bar_count_label_offset_uses_available_bars_when_fewer_than_six(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100.0, high=101.0, low=99.5, close=100.4, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100.4, high=101.6, low=99.8, close=101.1, volume=1),
    ]
    widget.set_bar_count_labels_visible(True)
    widget.set_window_data(bars, cursor=1, total_count=2, global_start_index=0)
    widget.price_plot.setYRange(95.0, 110.0, padding=0)
    widget._rebuild_session_markers()

    labels = [item for item in widget.price_plot.items if getattr(item, "_barbybar_bar_count_label", False)]

    assert len(labels) == 1
    gap = bars[1].low - labels[0].pos().y()
    average_range = ((bars[0].high - bars[0].low) + (bars[1].high - bars[1].low)) / 2
    assert gap == pytest.approx(max((110.0 - 95.0) * 0.03, average_range * 0.72))


def test_bar_count_labels_keep_minimum_gap_for_small_range_bar(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100.0, high=100.05, low=99.98, close=100.01, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100.01, high=100.04, low=99.99, close=100.02, volume=1),
    ]
    widget.set_bar_count_labels_visible(True)
    widget.set_window_data(bars, cursor=1, total_count=2, global_start_index=0)

    labels = [item for item in widget.price_plot.items if getattr(item, "_barbybar_bar_count_label", False)]

    assert len(labels) == 1
    assert labels[0].pos().y() < bars[1].low
    assert (bars[1].low - labels[0].pos().y()) > 0.01


def test_bar_count_labels_use_larger_gap_than_previous_formula(widget: ChartWidget) -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100.0, high=101.0, low=99.5, close=100.4, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100.4, high=101.6, low=99.8, close=101.1, volume=1),
    ]
    widget.set_bar_count_labels_visible(True)
    widget.set_window_data(bars, cursor=1, total_count=2, global_start_index=0)
    widget.price_plot.setYRange(95.0, 110.0, padding=0)
    widget._rebuild_session_markers()

    new_gap = bars[1].low - widget._bar_count_label_y(1)
    average_range = ((bars[0].high - bars[0].low) + (bars[1].high - bars[1].low)) / 2
    old_gap = max((110.0 - 95.0) * 0.022, average_range * 0.55)

    assert new_gap > old_gap


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
    assert widget._hover_time_label.text() == "开 2025-01-01 09:04 | 收 2025-01-01 09:05"
    assert widget._hover_open_label.text() == "开 104.1"
    assert widget._hover_high_label.text() == "高 106.1"
    assert widget._hover_low_label.text() == "低 103.4"
    assert widget._hover_close_label.text() == "收 104.9"
    assert widget._hover_range_label.text() == "幅 2.7"


def test_hover_info_always_colors_high_red_and_low_green(widget: ChartWidget) -> None:
    bullish = Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=10, high=12, low=9, close=11, volume=1)
    bearish = Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=11, high=12, low=8, close=9, volume=1)

    widget._update_hover_info(bullish, 11)
    assert "#d84a4a" in widget._hover_high_label.styleSheet()
    assert "#1f8b24" in widget._hover_low_label.styleSheet()

    widget._update_hover_info(bearish, 9)
    assert "#1f8b24" in widget._hover_low_label.styleSheet()
    assert "#d84a4a" in widget._hover_high_label.styleSheet()


def test_trade_hover_clears_range_line_from_bar_hover(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_tick_size(0.2)
    widget._update_hover_info(widget._bars[5], 123.45)
    assert widget._hover_range_label.text() == "幅 2.7"

    widget.set_trade_actions([SessionAction(ActionType.OPEN_LONG, 5, datetime(2025, 1, 1, 9, 5), price=101.0, quantity=1)])
    app.processEvents()
    marker = widget._trade_markers[0]
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(marker.x, marker.y))

    widget._handle_mouse_moved((scene_pos,))

    assert widget._hover_card.isHidden() is False
    assert widget._hover_range_label.text() == ""


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
    assert widget._trade_markers[0].role == "entry"
    assert widget._trade_markers[0].direction == "long"
    assert widget._trade_markers[0].symbol == "t1"
    assert widget._trade_markers[0].brush == TRADE_ENTRY_LONG_COLOR
    assert widget._trade_markers[0].size == pytest.approx(widget._scaled_trade_triangle_size())
    assert widget._trade_markers[1].role == "exit"
    assert widget._trade_markers[1].outcome == "win"
    assert widget._trade_markers[1].symbol == "t"
    assert widget._trade_markers[1].brush == TRADE_ENTRY_SHORT_COLOR
    assert widget._trade_markers[1].size == pytest.approx(widget._scaled_trade_triangle_size())
    assert widget._trade_links[0].direction == "long"
    assert widget._trade_links[0].outcome == "win"


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
    assert "多单" in widget._hover_time_label.text()


def test_trade_link_hover_uses_open_hand_cursor(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_trade_actions(
        [
            SessionAction(ActionType.OPEN_LONG, 5, datetime(2025, 1, 1, 9, 5), price=101.0, quantity=1),
            SessionAction(ActionType.CLOSE, 8, datetime(2025, 1, 1, 9, 8), price=103.0, quantity=1),
        ]
    )
    app.processEvents()
    link = widget._trade_links[0]
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF((link.x1 + link.x2) / 2, (link.y1 + link.y2) / 2))

    widget._handle_mouse_moved((scene_pos,))
    highlighted_link_items = [
        item
        for item in widget.price_plot.items
        if getattr(item, "_barbybar_trade_marker", False) and item.__class__.__name__ == "PlotCurveItem"
    ]

    assert widget._hover_target.target_type is HoverTargetType.TRADE_LINK
    assert widget.cursor().shape() == Qt.CursorShape.OpenHandCursor
    assert widget._v_line.isVisible() is True
    assert widget._h_line.isVisible() is True
    assert widget._hover_card.isHidden() is False
    assert "多单盈利" in widget._hover_time_label.text()
    assert "09:05" in widget._hover_time_label.text()
    assert "09:08" in widget._hover_time_label.text()
    assert highlighted_link_items
    assert any(item.opts["pen"].widthF() == 3.0 for item in highlighted_link_items)


def test_short_trade_link_uses_loss_color(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_trade_actions(
        [
            SessionAction(ActionType.OPEN_SHORT, 5, datetime(2025, 1, 1, 9, 5), price=101.0, quantity=1),
            SessionAction(ActionType.CLOSE, 8, datetime(2025, 1, 1, 9, 8), price=103.0, quantity=1),
        ]
    )
    widget._apply_viewport()

    assert widget._trade_markers[0].symbol == "t"
    assert widget._trade_markers[0].brush == TRADE_ENTRY_SHORT_COLOR
    assert widget._trade_markers[0].size == pytest.approx(widget._scaled_trade_triangle_size())
    assert widget._trade_markers[1].outcome == "loss"
    assert widget._trade_markers[1].symbol == "t1"
    assert widget._trade_markers[1].brush == TRADE_ENTRY_LONG_COLOR
    assert widget._trade_markers[1].size == pytest.approx(widget._scaled_trade_triangle_size())
    assert widget._trade_links[0].direction == "short"
    assert widget._trade_links[0].outcome == "loss"

    link_items = [
        item
        for item in widget.price_plot.items
        if getattr(item, "_barbybar_trade_marker", False) and item.__class__.__name__ == "PlotCurveItem"
    ]
    base_link = next(item for item in link_items if item.opts["pen"].widthF() == 1.0)
    assert base_link.opts["pen"].color().name() == TRADE_LINK_LOSS_COLOR
    assert base_link.opts["pen"].style() == Qt.PenStyle.SolidLine


def test_flat_trade_exit_marker_and_link_use_neutral_color(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_trade_actions(
        [
            SessionAction(ActionType.OPEN_LONG, 5, datetime(2025, 1, 1, 9, 5), price=101.0, quantity=1),
            SessionAction(ActionType.CLOSE, 8, datetime(2025, 1, 1, 9, 8), price=101.0, quantity=1),
        ]
    )

    assert widget._trade_markers[1].outcome == "flat"
    assert widget._trade_markers[1].symbol == "t"
    assert widget._trade_markers[1].brush == TRADE_ENTRY_SHORT_COLOR
    assert widget._trade_links[0].outcome == "flat"
    assert widget._trade_links[0].pnl == 0.0


def test_trade_link_highlight_preserves_original_color(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_trade_actions(
        [
            SessionAction(ActionType.OPEN_LONG, 5, datetime(2025, 1, 1, 9, 5), price=101.0, quantity=1),
            SessionAction(ActionType.CLOSE, 8, datetime(2025, 1, 1, 9, 8), price=103.0, quantity=1),
        ]
    )
    app.processEvents()
    link = widget._trade_links[0]
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF((link.x1 + link.x2) / 2, (link.y1 + link.y2) / 2))

    widget._handle_mouse_moved((scene_pos,))

    highlighted_link_items = [
        item
        for item in widget.price_plot.items
        if getattr(item, "_barbybar_trade_marker", False)
        and item.__class__.__name__ == "PlotCurveItem"
        and item.opts["pen"].widthF() == 3.0
    ]

    assert highlighted_link_items
    assert all(item.opts["pen"].color().name() == TRADE_LINK_WIN_COLOR for item in highlighted_link_items)


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
    assert widget._trade_markers[1].symbol == "t1"
    assert widget._trade_markers[1].size == pytest.approx(widget._scaled_trade_triangle_size())


def test_trade_triangle_size_scales_with_zoom(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(120)
    widget.set_trade_actions([SessionAction(ActionType.OPEN_LONG, 60, datetime(2025, 1, 1, 10, 0), price=101.0, quantity=1)])
    app.processEvents()

    initial_size = widget._trade_markers[0].size

    widget.zoom_x(anchor_x=60, scale=0.5)
    app.processEvents()
    zoomed_in_size = widget._trade_markers[0].size

    widget.zoom_x(anchor_x=60, scale=2.0)
    app.processEvents()
    zoomed_out_size = widget._trade_markers[0].size

    assert zoomed_in_size > initial_size
    assert zoomed_out_size < zoomed_in_size


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
    def __init__(self, scene_pos: QPointF, button: Qt.MouseButton = Qt.MouseButton.LeftButton, *, double: bool = False) -> None:
        self._scene_pos = scene_pos
        self._button = button
        self._double = double
        self.accepted = False

    def button(self):
        return self._button

    def scenePos(self):
        return self._scene_pos

    def double(self):
        return self._double

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


class _FakeDoubleClickEvent:
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


def _y_axis_drag_scene_pos(widget: ChartWidget, price: float) -> QPointF:
    rect = widget.price_plot.sceneBoundingRect()
    data_rect = widget.view_box.sceneBoundingRect()
    point = widget.price_plot.vb.mapViewToScene(QPointF(widget._cursor, price))
    x = max(float(data_rect.right()) + 4.0, float(rect.right()) - 4.0)
    return QPointF(x, point.y())


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


def test_order_preview_keeps_axis_price_label_visible_in_blank_space(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(50)
    widget.pan_x(-400)
    widget.set_tick_size(0.2)
    widget.begin_order_preview("entry_long", 1.0)
    app.processEvents()

    left, _right = widget.current_x_range()
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(left + 10.0, 101.23))
    widget._handle_mouse_moved((scene_pos,))

    assert widget._hover_target.target_type is HoverTargetType.NONE
    assert widget._preview_line.isVisible()
    assert widget._axis_price_label.isVisible()


def test_browse_mode_keeps_crosshair_visible_in_blank_space(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(50)
    widget.pan_x(-400)
    app.processEvents()

    left, _right = widget.current_x_range()
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(left + 10.0, 101.23))
    widget._handle_mouse_moved((scene_pos,))

    assert widget._hover_target.target_type is HoverTargetType.NONE
    assert widget._v_line.isVisible() is True
    assert widget._h_line.isVisible() is True
    assert widget._axis_price_label.isVisible() is True
    assert widget._hover_card.isHidden() is True


def test_mouse_move_into_y_axis_gutter_exits_hover_mode(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    app.processEvents()

    start = _y_axis_drag_scene_pos(widget, 100.0)
    widget._handle_mouse_moved((start,))

    assert widget._mouse_in_y_axis_gutter is True
    assert widget._hover_target.target_type is HoverTargetType.NONE
    assert widget.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert widget._v_line.isVisible() is False
    assert widget._h_line.isVisible() is False
    assert widget._hover_card.isHidden() is True


def test_mouse_move_into_x_axis_region_exits_hover_mode(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    app.processEvents()

    data_rect = widget.view_box.sceneBoundingRect()
    plot_rect = widget.price_plot.sceneBoundingRect()
    x = (float(data_rect.left()) + float(data_rect.right())) / 2
    y = min(float(plot_rect.bottom()) - 4.0, float(data_rect.bottom()) + 8.0)
    widget._handle_mouse_moved((QPointF(x, y),))

    assert widget._mouse_on_axis is True
    assert widget._mouse_in_y_axis_gutter is False
    assert widget._hover_target.target_type is HoverTargetType.NONE
    assert widget.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert widget._v_line.isVisible() is False
    assert widget._h_line.isVisible() is False


def test_axis_price_label_region_exits_hover_mode(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    app.processEvents()

    plot_pos = widget.price_plot.vb.mapViewToScene(QPointF(10, 100))
    widget._handle_mouse_moved((plot_pos,))
    label_center = widget._axis_price_label.geometry().center()
    widget._sync_axis_hover_state_from_widget_pos(label_center)

    assert widget._mouse_on_axis is True
    assert widget._mouse_in_y_axis_gutter is True
    assert widget.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert widget._hover_target.target_type is HoverTargetType.NONE
    assert widget._v_line.isVisible() is False
    assert widget._h_line.isVisible() is False


def test_mouse_move_leaving_y_axis_gutter_restores_crosshair(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    app.processEvents()

    gutter_pos = _y_axis_drag_scene_pos(widget, 100.0)
    plot_pos = widget.price_plot.vb.mapViewToScene(QPointF(10, 100))
    widget._handle_mouse_moved((gutter_pos,))
    widget._handle_mouse_moved((plot_pos,))

    assert widget._mouse_in_y_axis_gutter is False
    assert widget.cursor().shape() == Qt.CursorShape.CrossCursor
    assert widget._v_line.isVisible() is True
    assert widget._h_line.isVisible() is True


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


def test_dragging_right_side_gutter_pans_y_range(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    app.processEvents()
    old_y_min, old_y_max = widget.price_plot.viewRange()[1]

    start = _y_axis_drag_scene_pos(widget, 100.0)
    move = start + QPointF(0.0, -40.0)
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    new_y_min, new_y_max = widget.price_plot.viewRange()[1]
    assert widget.is_dragging is False
    assert (new_y_max - new_y_min) == pytest.approx(old_y_max - old_y_min)
    assert new_y_min != pytest.approx(old_y_min)
    assert widget._suppress_next_left_click is True


def test_manual_y_offset_is_reapplied_on_apply_viewport(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    app.processEvents()
    auto_y_range = widget.price_plot.viewRange()[1]

    start = _y_axis_drag_scene_pos(widget, 100.0)
    move = start + QPointF(0.0, -40.0)
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    dragged_y_range = widget.price_plot.viewRange()[1]
    offset = dragged_y_range[0] - auto_y_range[0]

    widget._apply_viewport()

    assert dragged_y_range != pytest.approx(auto_y_range)
    assert widget._y_axis_offset == pytest.approx(offset)
    assert widget.price_plot.viewRange()[1] == pytest.approx(dragged_y_range)


def test_reset_viewport_clears_manual_y_range(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    app.processEvents()
    auto_y_range = widget.price_plot.viewRange()[1]

    start = _y_axis_drag_scene_pos(widget, 100.0)
    move = start + QPointF(0.0, -40.0)
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    widget.reset_viewport(follow_latest=True)

    assert widget._y_axis_offset == pytest.approx(0.0)
    assert widget.price_plot.viewRange()[1] == pytest.approx(auto_y_range)


def test_double_click_y_axis_only_clears_y_offset(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    widget.pan_x(-30)
    app.processEvents()
    auto_y_range = widget.price_plot.viewRange()[1]
    old_right = widget.viewport_state.right_edge_index
    old_follow_latest = widget.viewport_state.follow_latest
    old_x_range = widget.current_x_range()

    start = _y_axis_drag_scene_pos(widget, 100.0)
    move = start + QPointF(0.0, -40.0)
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert widget._y_axis_offset != pytest.approx(0.0)

    event = _FakeSceneClick(_y_axis_drag_scene_pos(widget, 100.0), double=True)
    widget._handle_scene_click(event)

    assert event.accepted is True
    assert widget._y_axis_offset == pytest.approx(0.0)
    assert widget.price_plot.viewRange()[1] == pytest.approx(auto_y_range)
    assert widget.viewport_state.right_edge_index == pytest.approx(old_right)
    assert widget.viewport_state.follow_latest is old_follow_latest
    assert widget.current_x_range() == pytest.approx(old_x_range)


def test_set_cursor_preserves_y_offset_and_refits_visible_bars(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    bars = _bars()
    widget.set_full_data(bars)
    widget.set_cursor(60)
    app.processEvents()

    start = _y_axis_drag_scene_pos(widget, 100.0)
    move = start + QPointF(0.0, -40.0)
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))
    preserved_offset = widget._y_axis_offset

    widget.set_cursor(150)

    y_min, y_max = widget.price_plot.viewRange()[1]
    visible = widget._revealed_window_bars(*widget.current_x_range())
    auto_low = min(bar.low for _, bar in visible)
    auto_high = max(bar.high for _, bar in visible)
    height = max(auto_high - auto_low, max(abs(auto_high) * 0.01, 1.0))
    padding = max(height * 0.06, 0.5)
    assert widget._y_axis_offset == pytest.approx(preserved_offset)
    assert y_min == pytest.approx(auto_low - padding + preserved_offset)
    assert y_max == pytest.approx(auto_high + padding + preserved_offset)


def test_pan_x_preserves_y_offset_and_recomputes_auto_range(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    app.processEvents()

    start = _y_axis_drag_scene_pos(widget, 100.0)
    move = start + QPointF(0.0, -40.0)
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))
    preserved_offset = widget._y_axis_offset

    widget.pan_x(-30)

    visible = widget._revealed_window_bars(*widget.current_x_range())
    low = min(bar.low for _, bar in visible)
    high = max(bar.high for _, bar in visible)
    height = max(high - low, max(abs(high) * 0.01, 1.0))
    padding = max(height * 0.06, 0.5)
    y_min, y_max = widget.price_plot.viewRange()[1]
    assert widget._y_axis_offset == pytest.approx(preserved_offset)
    assert y_min == pytest.approx(low - padding + preserved_offset)
    assert y_max == pytest.approx(high + padding + preserved_offset)


def test_visible_rightmost_bar_uses_aligned_visible_window(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(199)
    widget.pan_x(-30.5)

    left, _right = widget.current_x_range()
    visible_right = left + widget.viewport_state.bars_in_view
    visible = widget._revealed_window_bars(left, visible_right)

    assert visible
    assert widget._visible_rightmost_bar_x() == float(visible[-1][0])


def test_revealed_window_bars_excludes_bar_touching_left_midpoint_boundary(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(30)

    visible = widget._revealed_window_bars(3.5, 10.5)

    assert visible
    assert visible[0][0] == 4
    assert all(index >= 4 for index, _bar in visible)


def test_y_range_includes_bars_visible_in_right_padding(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(30)
    app.processEvents()

    left, right = widget.current_x_range()
    visible = widget._revealed_window_bars(left, right)

    assert visible
    y_min, y_max = widget.price_plot.viewRange()[1]
    low = min(bar.low for _, bar in visible)
    high = max(bar.high for _, bar in visible)
    height = max(high - low, max(abs(high) * 0.01, 1.0))
    padding = max(height * 0.06, 0.5)
    assert y_min == pytest.approx(low - padding)
    assert y_max == pytest.approx(high + padding)


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


def test_main_plot_left_drag_still_pans_x_after_y_axis_drag_added(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    app.processEvents()
    old_right = widget.viewport_state.right_edge_index
    old_y_range = widget.price_plot.viewRange()[1]

    start = widget.price_plot.vb.mapViewToScene(QPointF(100, 100))
    move = widget.price_plot.vb.mapViewToScene(QPointF(80, 100))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert widget.viewport_state.right_edge_index != old_right
    assert widget.price_plot.viewRange()[1] != pytest.approx(old_y_range)


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


def test_alt_left_drag_shows_temporary_measurement_without_panning(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    widget.set_tick_size(0.2)
    app.processEvents()
    old_right = widget.viewport_state.right_edge_index
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.AltModifier)

    start = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(105.0, 104.0))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))

    assert widget.viewport_state.right_edge_index == old_right
    assert widget._temporary_measure_active is True
    assert widget._temporary_measure_line.isVisible() is True
    assert widget._temporary_measure_label.isVisible() is True
    assert widget._temporary_measure_label.toPlainText() == "+4.0"

    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert widget._temporary_measure_active is False
    assert widget._temporary_measure_line.isVisible() is False
    assert widget._temporary_measure_label.isVisible() is False
    assert widget.drawings() == []


def test_temporary_measurement_updates_when_tick_size_changes(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    widget.set_tick_size(1.0)
    app.processEvents()
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.AltModifier)

    start = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(105.0, 102.25))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    assert widget._temporary_measure_label.toPlainText() == "+2"

    widget.set_tick_size(0.25)

    assert widget._temporary_measure_label.toPlainText() == "+2.25"


def test_ctrl_snap_applies_to_temporary_measurement(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_tick_size(0.2)
    app.processEvents()
    modifiers = Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ControlModifier
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: modifiers)

    start_bar = widget._bars[10]
    end_bar = widget._bars[11]
    start = _scene_point_with_offset(widget, 10.0, start_bar.high, offset_x_px=4.0, offset_y_px=-4.0)
    move = _scene_point_with_offset(widget, 11.0, end_bar.low, offset_x_px=4.0, offset_y_px=-4.0)
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))

    expected_delta = end_bar.low - start_bar.high
    expected_text = f"{'+' if expected_delta >= 0 else '-'}{format_price(abs(expected_delta), 0.2)}"
    assert widget._temporary_measure_label.toPlainText() == expected_text


def test_temporary_measurement_is_ignored_in_drawing_mode(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    app.processEvents()
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.AltModifier)

    start = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(15.0, 104.0))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))

    assert widget._temporary_measure_active is False
    assert widget._temporary_measure_line.isVisible() is False


def test_escape_cancels_temporary_measurement(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_tick_size(0.2)
    app.processEvents()
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.AltModifier)

    start = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(15.0, 104.0))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))

    assert widget._temporary_measure_active is False
    assert widget._temporary_measure_line.isVisible() is False
    assert widget._temporary_measure_label.isVisible() is False


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

    bar = widget._bars[10]
    click = _FakeSceneClick(_scene_point_with_offset(widget, 10.0, bar.high, offset_x_px=4.0, offset_y_px=-4.0))
    widget._handle_scene_click(click)

    anchor = widget._pending_drawing_anchors[0]

    assert anchor.x == 10.0
    assert anchor.y == bar.high


def test_ctrl_click_snaps_to_nearest_ohlc_across_nearby_bars(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    target_bar = widget._bars[11]
    scene_pos = _scene_point_with_offset(widget, 11.0, target_bar.high, offset_x_px=-8.0, offset_y_px=-6.0)
    widget._handle_scene_click(_FakeSceneClick(scene_pos))

    anchor = widget._pending_drawing_anchors[0]
    assert anchor.x == 11.0
    assert anchor.y == target_bar.high


def test_ctrl_click_does_not_snap_drawing_anchor_when_price_is_far(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    bar = widget._bars[10]
    scene_pos = _assert_no_snap_target(widget, 10.0, bar.high)
    widget._handle_scene_click(_FakeSceneClick(scene_pos))

    anchor = widget._pending_drawing_anchors[0]
    view_pos = widget.price_plot.vb.mapSceneToView(scene_pos)

    assert anchor.x == pytest.approx(view_pos.x())
    assert anchor.y == pytest.approx(view_pos.y())


def test_ctrl_preview_anchor_uses_same_snap_rule(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    bar = widget._bars[11]
    widget._handle_mouse_moved((_scene_point_with_offset(widget, 11.0, bar.high, offset_x_px=4.0, offset_y_px=-4.0),))

    anchor = widget._drawing_preview_anchor
    assert anchor is not None
    assert anchor.x == 11.0
    assert anchor.y == bar.high


def test_ctrl_preview_anchor_remains_free_when_price_is_far(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    bar = widget._bars[11]
    scene_pos = _assert_no_snap_target(widget, 11.0, bar.high)
    widget._handle_mouse_moved((scene_pos,))

    anchor = widget._drawing_preview_anchor
    view_pos = widget.price_plot.vb.mapSceneToView(scene_pos)
    assert anchor is not None
    assert anchor.x == pytest.approx(view_pos.x())
    assert anchor.y == pytest.approx(view_pos.y())


def test_ctrl_preview_does_not_show_snap_highlight_item(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    widget._handle_mouse_moved((_scene_point_with_offset(widget, 11.0, widget._bars[11].high, offset_x_px=4.0, offset_y_px=-4.0),))

    snap_items = [item for item in widget.price_plot.items if getattr(item, "_barbybar_snap_preview", False)]
    assert snap_items == []


def test_ctrl_preview_shows_snap_guide_segment_when_anchor_moves(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    bar = widget._bars[11]
    scene_pos = _scene_point_with_offset(widget, 11.0, bar.high, offset_x_px=4.0, offset_y_px=-4.0)
    widget._handle_mouse_moved((scene_pos,))

    guide_items = _snap_preview_guide_items(widget)
    assert len(guide_items) == 1
    x_data, y_data = _guide_item_points(guide_items[0])
    raw_view_pos = widget.price_plot.vb.mapSceneToView(scene_pos)
    assert x_data == pytest.approx([raw_view_pos.x(), 11.0])
    assert y_data == pytest.approx([raw_view_pos.y(), bar.high])


def test_preview_does_not_show_snap_highlight_without_ctrl(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.NoModifier)
    app.processEvents()

    widget._handle_mouse_moved((_scene_point_with_offset(widget, 11.0, widget._bars[11].high, offset_x_px=4.0, offset_y_px=-4.0),))

    assert _snap_preview_guide_items(widget) == []


def test_ctrl_preview_guide_clears_outside_chart(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    inside = _scene_point_with_offset(widget, 11.0, widget._bars[11].high, offset_x_px=4.0, offset_y_px=-4.0)
    widget._handle_mouse_moved((inside,))
    assert len(_snap_preview_guide_items(widget)) == 1

    outside = widget.price_plot.sceneBoundingRect().topLeft() - QPointF(20.0, 20.0)
    widget._handle_mouse_moved((outside,))

    assert _snap_preview_guide_items(widget) == []


def test_ctrl_preview_does_not_show_snap_guide_when_price_does_not_move(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    snapped_price = widget._bars[11].high
    widget._handle_mouse_moved((widget.price_plot.vb.mapViewToScene(QPointF(11.0, snapped_price)),))

    assert _snap_preview_guide_items(widget) == []


def test_ctrl_preview_guide_ends_at_nearest_snap_target(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    bar = widget._bars[11]
    scene_pos = _scene_point_with_offset(widget, 11.0, bar.high, offset_x_px=12.0, offset_y_px=-6.0)
    widget._handle_mouse_moved((scene_pos,))

    guide_items = _snap_preview_guide_items(widget)
    assert len(guide_items) == 1
    x_data, y_data = _guide_item_points(guide_items[0])
    raw_view_pos = widget.price_plot.vb.mapSceneToView(scene_pos)
    expected_anchor = widget._drawing_snap_target(DrawingAnchor(float(raw_view_pos.x()), float(raw_view_pos.y())))
    assert expected_anchor is not None
    assert x_data == pytest.approx([raw_view_pos.x(), expected_anchor.x])
    assert y_data == pytest.approx([raw_view_pos.y(), expected_anchor.y])


def test_ctrl_preview_hides_snap_feedback_when_price_is_far(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    scene_pos = _assert_no_snap_target(widget, 11.0, widget._bars[11].high)
    widget._handle_mouse_moved((scene_pos,))

    assert _snap_preview_guide_items(widget) == []


def test_ctrl_preview_second_anchor_uses_snap_without_showing_guide(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    first_click = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0)))
    widget._handle_scene_click(first_click)

    bar = widget._bars[11]
    scene_pos = _scene_point_with_offset(widget, 11.0, bar.high, offset_x_px=4.0, offset_y_px=-4.0)
    widget._handle_mouse_moved((scene_pos,))

    assert _snap_preview_guide_items(widget) == []
    assert widget._drawing_preview_anchor is not None
    assert widget._drawing_preview_anchor.x == 11.0
    assert widget._drawing_preview_anchor.y == bar.high


def test_single_anchor_tool_shows_snap_guide_on_first_point(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.HORIZONTAL_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    bar = widget._bars[11]
    scene_pos = _scene_point_with_offset(widget, 11.0, bar.high, offset_x_px=4.0, offset_y_px=-4.0)
    widget._handle_mouse_moved((scene_pos,))

    guide_items = _snap_preview_guide_items(widget)
    assert len(guide_items) == 1


def test_key_release_clears_snap_preview_guide_without_mouse_move(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    modifiers = {"value": Qt.KeyboardModifier.ControlModifier}
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: modifiers["value"])
    app.processEvents()

    widget._handle_mouse_moved((_scene_point_with_offset(widget, 11.0, widget._bars[11].high, offset_x_px=4.0, offset_y_px=-4.0),))
    assert len(_snap_preview_guide_items(widget)) == 1

    modifiers["value"] = Qt.KeyboardModifier.NoModifier
    widget.keyReleaseEvent(QKeyEvent(QKeyEvent.Type.KeyRelease, Qt.Key.Key_Control, Qt.KeyboardModifier.NoModifier))

    assert _snap_preview_guide_items(widget) == []


def test_disabling_drawing_tool_clears_snap_preview_guide(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    monkeypatch.setattr(widget, "_current_keyboard_modifiers", lambda: Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    widget._handle_mouse_moved((_scene_point_with_offset(widget, 11.0, widget._bars[11].high, offset_x_px=4.0, offset_y_px=-4.0),))
    assert len(_snap_preview_guide_items(widget)) == 1

    widget.set_active_drawing_tool(None)

    assert _snap_preview_guide_items(widget) == []


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
    assert drawing.style["extend_right"] is False
    segments = widget._drawing_segments(drawing)
    assert len(segments) == 1
    assert segments[0] == ([10.0, 15.0], [100.0, 104.0])


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


def test_trend_line_vertical_segment_stays_finite(widget: ChartWidget) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    drawing = ChartDrawing(
        tool_type=DrawingToolType.TREND_LINE,
        anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(10.0, 110.0)],
    )

    segments = widget._drawing_segments(drawing)

    assert segments == [([10.0, 10.0], [100.0, 110.0])]


def test_ray_vertical_segment_stays_finite(widget: ChartWidget) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    drawing = ChartDrawing(
        tool_type=DrawingToolType.RAY,
        anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(10.0, 110.0)],
    )

    segments = widget._drawing_segments(drawing)

    assert segments[0] == ([10.0, 10.0], [100.0, 110.0])
    assert len(segments) == 1


def test_ray_draws_solid_arrow_head_item(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawings(
        [ChartDrawing(tool_type=DrawingToolType.RAY, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 104.0)])]
    )
    app.processEvents()

    items = [
        item
        for item in widget.price_plot.items
        if getattr(item, "_barbybar_drawing_tool", "") == DrawingToolType.RAY.value and item.__class__.__name__ == "QGraphicsPathItem"
    ]

    assert len(items) == 1
    assert items[0].brush().style() != Qt.BrushStyle.NoBrush


def test_vertical_line_tool_still_uses_view_height(widget: ChartWidget) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    drawing = ChartDrawing(
        tool_type=DrawingToolType.VERTICAL_LINE,
        anchors=[DrawingAnchor(10.0, 105.0)],
    )

    segments = widget._drawing_segments(drawing)
    low, high = widget.price_plot.viewRange()[1]

    assert segments == [([10.0, 10.0], [low, high])]


def test_horizontal_line_renders_as_infinite_line(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.pan_x(40)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.HORIZONTAL_LINE, anchors=[DrawingAnchor(10.0, 105.0)])])
    app.processEvents()

    line_items = [
        item
        for item in widget.price_plot.items
        if getattr(item, "_barbybar_drawing_tool", "") == DrawingToolType.HORIZONTAL_LINE.value and isinstance(item, pg.InfiniteLine)
    ]

    assert len(line_items) == 1
    assert line_items[0].value() == 105.0


def test_horizontal_line_hit_test_works_away_from_anchor(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.pan_x(40)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.HORIZONTAL_LINE, anchors=[DrawingAnchor(10.0, 105.0)])])
    app.processEvents()

    hit = widget._drawing_at_scene_pos(widget.price_plot.vb.mapViewToScene(QPointF(80.0, 105.0)))

    assert hit is not None
    assert hit[1].tool_type is DrawingToolType.HORIZONTAL_LINE


def test_horizontal_ray_still_extends_from_anchor_only(widget: ChartWidget) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.pan_x(40)
    drawing = ChartDrawing(
        tool_type=DrawingToolType.HORIZONTAL_RAY,
        anchors=[DrawingAnchor(10.0, 105.0)],
    )

    segments = widget._drawing_segments(drawing)

    assert len(segments) == 1
    assert segments[0][0][0] == 10.0
    assert segments[0][0][1] > 10.0
    assert segments[0][1] == [105.0, 105.0]


def test_horizontal_line_stays_infinite_after_resize(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.HORIZONTAL_LINE, anchors=[DrawingAnchor(10.0, 105.0)])])
    app.processEvents()

    widget.resize(500, 600)
    app.processEvents()

    line_items = [
        item
        for item in widget.price_plot.items
        if getattr(item, "_barbybar_drawing_tool", "") == DrawingToolType.HORIZONTAL_LINE.value and isinstance(item, pg.InfiniteLine)
    ]

    assert len(line_items) == 1
    assert line_items[0].value() == 105.0


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
    assert all(item.pos().x() > 15.0 for item in label_items)
    assert all(item.fill.style() == Qt.BrushStyle.NoBrush for item in label_items)


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


def test_hover_time_shows_open_and_close_time(widget: ChartWidget) -> None:
    bars = _bars()
    widget.set_full_data(bars)
    widget.set_cursor(10)

    widget._update_hover_info(bars[5], 123.45)

    assert widget._hover_time_label.text() == "开 2025-01-01 09:04 | 收 2025-01-01 09:05"


def test_hover_time_uses_chart_timeframe_for_open_and_close(widget: ChartWidget) -> None:
    bars = [
        Bar(
            timestamp=datetime(2025, 1, 1, 9, 5),
            open=100,
            high=101,
            low=99,
            close=100.5,
            volume=1,
            open_timestamp=datetime(2025, 1, 1, 9, 0),
        )
    ]
    widget.set_window_data(bars, cursor=0, total_count=1, global_start_index=0, timeframe="5m")

    widget._update_hover_info(bars[0], 123.45)

    assert widget._hover_time_label.text() == "开 2025-01-01 09:00 | 收 2025-01-01 09:05"


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


def test_set_drawings_hidden_hides_rendered_drawing_items(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TREND_LINE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 105.0)])])
    app.processEvents()

    visible_items = [item for item in widget.price_plot.items if getattr(item, "_barbybar_line", False)]
    assert visible_items

    widget.set_drawings_hidden(True)
    app.processEvents()

    hidden_items = [item for item in widget.price_plot.items if getattr(item, "_barbybar_line", False)]
    assert hidden_items == []
    assert len(widget.drawings()) == 1


def test_hidden_drawings_disable_hit_testing_and_anchor_hover(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TREND_LINE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 105.0)])])
    app.processEvents()

    widget.set_drawings_hidden(True)
    scene_pos = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))

    assert widget._drawing_at_scene_pos(scene_pos) is None
    assert widget._drawing_anchor_at_scene_pos(scene_pos) is None

    widget._handle_mouse_moved((scene_pos,))

    assert widget._hover_target.drawing_index is None
    assert widget._hover_target.anchor_index is None


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


def test_hidden_drawings_ignore_right_click_context_menu(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TREND_LINE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 105.0)])])
    widget.set_drawings_hidden(True)
    app.processEvents()
    captured: list[int] = []
    monkeypatch.setattr(widget, "_show_drawing_context_menu", lambda drawing_index, scene_pos: captured.append(drawing_index))

    click = _FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(12.0, 102.0)), Qt.MouseButton.RightButton)
    widget._handle_scene_click(click)

    assert captured == []


def test_drawing_context_menu_includes_save_template_action(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TREND_LINE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 105.0)])])
    app.processEvents()
    menu, _properties_action, _save_template_action, _delete_action = widget._build_drawing_context_menu()

    assert [action.text() for action in menu.actions()] == ["属性...", "加入常用模板...", "删除画线"]


def test_selecting_save_template_action_emits_signal(widget: ChartWidget, app: QApplication, monkeypatch) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.RECTANGLE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(15.0, 105.0)])])
    app.processEvents()
    captured: list[int] = []
    widget.drawingTemplateSaveRequested.connect(lambda _drawing, index: captured.append(index))
    _menu, _properties_action, save_template_action, _delete_action = widget._build_drawing_context_menu()
    monkeypatch.setattr(widget, "_build_drawing_context_menu", lambda: (_menu, _properties_action, save_template_action, _delete_action))
    monkeypatch.setattr(_menu, "exec", lambda *_args, **_kwargs: save_template_action)

    widget._show_drawing_context_menu(0, widget.price_plot.vb.mapViewToScene(QPointF(12.0, 102.0)))

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

    widget.update_drawing_style(None, {"color": "#3366ff", "opacity": 0.4, "width": 3, "line_style": "dash", "fill_opacity": 0.35}, 0)

    style = widget.drawings()[0].style
    assert style["color"] == "#3366ff"
    assert style["opacity"] == 0.4
    assert style["width"] == 3
    assert style["line_style"] == "dash"
    assert style["fill_opacity"] == 0.35


def test_drawing_pen_uses_configured_opacity(widget: ChartWidget) -> None:
    pen = widget._drawing_pen({"color": "#3366ff", "opacity": 0.35, "width": 2, "line_style": "solid"}, preview=False)

    assert pen.color().alphaF() == pytest.approx(0.35, abs=0.01)


def test_set_drawing_style_preset_applies_to_new_drawings(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawing_style_preset(DrawingToolType.RECTANGLE, {"color": "#3366ff", "width": 3, "fill_opacity": 0.35})
    widget.set_active_drawing_tool(DrawingToolType.RECTANGLE)
    app.processEvents()

    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100))))
    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(15, 110))))

    drawing = widget.drawings()[0]
    assert drawing.style["color"] == "#3366ff"
    assert drawing.style["width"] == 3
    assert drawing.style["fill_opacity"] == 0.35


def test_preview_drawing_uses_line_style_preset(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawing_style_preset(DrawingToolType.TREND_LINE, {"color": "#3366ff", "width": 3, "line_style": "dash"})
    widget.set_active_drawing_tool(DrawingToolType.TREND_LINE)
    app.processEvents()

    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100))))
    widget._handle_mouse_moved((widget.price_plot.vb.mapViewToScene(QPointF(15, 110)),))

    preview = widget._current_preview_drawing()
    assert preview is not None
    assert preview.style["color"] == "#3366ff"
    assert preview.style["width"] == 3
    assert preview.style["line_style"] == "dash"


def test_preview_drawing_uses_fill_style_preset(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawing_style_preset(
        DrawingToolType.RECTANGLE,
        {"color": "#3366ff", "width": 3, "fill_color": "#3366ff", "fill_opacity": 0.35},
    )
    widget.set_active_drawing_tool(DrawingToolType.RECTANGLE)
    app.processEvents()

    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100))))
    widget._handle_mouse_moved((widget.price_plot.vb.mapViewToScene(QPointF(15, 110)),))

    preview = widget._current_preview_drawing()
    assert preview is not None
    assert preview.style["color"] == "#3366ff"
    assert preview.style["width"] == 3
    assert preview.style["fill_color"] == "#3366ff"
    assert preview.style["fill_opacity"] == 0.35


def test_text_style_preset_does_not_reuse_previous_text_content(widget: ChartWidget) -> None:
    widget.set_drawing_style_preset(DrawingToolType.TEXT, {"text": "old", "font_size": 18, "text_color": "#3366ff"})

    style = widget.drawing_style_preset(DrawingToolType.TEXT)
    assert style["text"] == ""
    assert style["font_size"] == 18
    assert style["text_color"] == "#3366ff"


def test_text_preview_uses_style_preset_without_reusing_text_content(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(20)
    widget.set_drawing_style_preset(DrawingToolType.TEXT, {"text": "old", "font_size": 18, "text_color": "#3366ff"})
    widget.set_active_drawing_tool(DrawingToolType.TEXT)
    app.processEvents()

    widget._handle_mouse_moved((widget.price_plot.vb.mapViewToScene(QPointF(10, 100)),))
    widget._handle_scene_click(_FakeSceneClick(widget.price_plot.vb.mapViewToScene(QPointF(10, 100))))

    drawing = widget.drawings()[0]
    assert drawing.style["font_size"] == 18
    assert drawing.style["text_color"] == "#3366ff"
    assert drawing.style["text"] == ""


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


def test_average_price_label_includes_current_pnl_for_long(widget: ChartWidget) -> None:
    widget.set_tick_size(0.2)
    widget.set_full_data(_bars())
    widget.set_cursor(10)
    widget.set_position_direction("long")
    line = OrderLine(
        order_type=OrderLineType.AVERAGE_PRICE,
        price=108.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=0,
        created_at=datetime(2025, 1, 1, 9, 0),
    )

    assert widget._order_line_label(line) == "多单 1手 108.0 (+1.8)"


def test_average_price_label_includes_current_pnl_for_long_loss(widget: ChartWidget) -> None:
    widget.set_tick_size(0.2)
    widget.set_full_data(_bars())
    widget.set_cursor(10)
    widget.set_position_direction("long")
    line = OrderLine(
        order_type=OrderLineType.AVERAGE_PRICE,
        price=110.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=0,
        created_at=datetime(2025, 1, 1, 9, 0),
    )

    assert widget._order_line_label(line) == "多单 1手 110.0 (-0.2)"


def test_average_price_label_includes_current_pnl_for_short(widget: ChartWidget) -> None:
    widget.set_tick_size(0.2)
    widget.set_full_data(_bars())
    widget.set_cursor(10)
    widget.set_position_direction("short")
    line = OrderLine(
        order_type=OrderLineType.AVERAGE_PRICE,
        price=112.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=0,
        created_at=datetime(2025, 1, 1, 9, 0),
    )

    assert widget._order_line_label(line) == "空单 1手 112.0 (+2.2)"


def test_average_price_label_shows_zero_when_flat(widget: ChartWidget) -> None:
    widget.set_tick_size(0.2)
    widget.set_full_data(_bars())
    widget.set_cursor(10)
    widget.set_position_direction("long")
    line = OrderLine(
        order_type=OrderLineType.AVERAGE_PRICE,
        price=109.8,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=0,
        created_at=datetime(2025, 1, 1, 9, 0),
    )

    assert widget._order_line_label(line) == "多单 1手 109.8 (0)"


def test_average_price_label_falls_back_without_position_direction(widget: ChartWidget) -> None:
    widget.set_tick_size(1)
    widget.set_full_data(_bars())
    widget.set_cursor(10)
    widget.set_position_direction(None)
    line = OrderLine(
        order_type=OrderLineType.AVERAGE_PRICE,
        price=108.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=0,
        created_at=datetime(2025, 1, 1, 9, 0),
    )

    assert widget._order_line_label(line) == "持仓 1手 108"


def test_average_price_label_falls_back_without_active_bar(widget: ChartWidget) -> None:
    widget.set_tick_size(1)
    widget.set_position_direction("long")
    line = OrderLine(
        order_type=OrderLineType.AVERAGE_PRICE,
        price=108.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=0,
        created_at=datetime(2025, 1, 1, 9, 0),
    )

    assert widget._order_line_label(line) == "多单 1手 108"


def test_order_line_style_uses_expected_colors() -> None:
    widget = ChartWidget()
    average_pen, average_color, average_movable = widget._order_line_style(
        OrderLine(
            order_type=OrderLineType.AVERAGE_PRICE,
            price=100.0,
            quantity=1,
            created_bar_index=0,
            active_from_bar_index=0,
            created_at=datetime(2025, 1, 1, 9, 0),
        )
    )
    stop_pen, stop_color, stop_movable = widget._order_line_style(
        OrderLine(
            order_type=OrderLineType.STOP_LOSS,
            price=99.0,
            quantity=1,
            created_bar_index=0,
            active_from_bar_index=1,
            created_at=datetime(2025, 1, 1, 9, 0),
        )
    )
    take_pen, take_color, take_movable = widget._order_line_style(
        OrderLine(
            order_type=OrderLineType.TAKE_PROFIT,
            price=101.0,
            quantity=1,
            created_bar_index=0,
            active_from_bar_index=1,
            created_at=datetime(2025, 1, 1, 9, 0),
        )
    )

    assert average_color == AVERAGE_PRICE_LINE_COLOR
    assert average_pen.color().name() == AVERAGE_PRICE_LINE_COLOR
    assert average_movable is False
    assert stop_color == STOP_LOSS_LINE_COLOR
    assert stop_pen.color().name() == STOP_LOSS_LINE_COLOR
    assert stop_movable is True
    assert take_color == TAKE_PROFIT_LINE_COLOR
    assert take_pen.color().name() == TAKE_PROFIT_LINE_COLOR
    assert take_movable is True
    widget.close()
    widget.deleteLater()


def test_protective_drag_color_matches_updated_order_line_colors(widget: ChartWidget) -> None:
    assert widget._protective_drag_color(OrderLineType.STOP_LOSS) == STOP_LOSS_LINE_COLOR
    assert widget._protective_drag_color(OrderLineType.TAKE_PROFIT) == TAKE_PROFIT_LINE_COLOR


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
    captured: list[tuple[str, float, bool]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price, from_average: captured.append((order_type, price, from_average)))
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 102.3))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))

    assert widget._axis_price_label.isVisible()
    assert widget._axis_price_label.text() == "102.2"

    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert captured == [(OrderLineType.TAKE_PROFIT.value, 102.2, True)]


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
    captured: list[tuple[str, float, bool]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price, from_average: captured.append((order_type, price, from_average)))
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 98.1))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert captured == [(OrderLineType.STOP_LOSS.value, 98.0, True)]


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
    captured: list[tuple[str, float, bool]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price, from_average: captured.append((order_type, price, from_average)))
    app.processEvents()

    start = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 100.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(10.0, 102.1))
    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert captured == [(OrderLineType.STOP_LOSS.value, 102.0, True)]


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
    captured: list[tuple[str, float, bool]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price, from_average: captured.append((order_type, price, from_average)))
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
    captured: list[tuple[str, float, bool]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price, from_average: captured.append((order_type, price, from_average)))

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

    assert captured == [(OrderLineType.STOP_LOSS.value, 98.2, False)]
    assert widget.is_dragging is False
    assert widget._hover_target.target_type is HoverTargetType.ORDER_LINE
    assert widget._hover_target.order_line_type is OrderLineType.STOP_LOSS
    assert widget._drag_order_label.isVisible() is False


def test_hovered_transient_entry_line_drag_does_not_emit_duplicate_create(widget: ChartWidget, app: QApplication) -> None:
    widget.resize(900, 600)
    widget.show()
    widget.set_full_data(_bars())
    widget.set_cursor(150)
    widget.set_tick_size(0.2)
    line = OrderLine(
        order_type=OrderLineType.ENTRY_LONG,
        price=98.0,
        quantity=1,
        created_bar_index=0,
        active_from_bar_index=1,
        created_at=datetime(2025, 1, 1, 9, 0),
        id=None,
    )
    widget.set_order_lines([line])
    app.processEvents()
    moved: list[tuple[int, float]] = []
    created: list[tuple[str, float, bool]] = []
    widget.orderLineMoved.connect(lambda order_id, price: moved.append((order_id, price)))
    widget.protectiveOrderCreated.connect(lambda order_type, price, from_average: created.append((order_type, price, from_average)))

    start = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 98.0))
    move = widget.price_plot.vb.mapViewToScene(QPointF(100.0, 98.13))
    widget._handle_mouse_moved((start,))

    widget.view_box.mouseDragEvent(_FakeDragEvent(start, start, is_start=True))
    assert widget.is_dragging is False

    widget.view_box.mouseDragEvent(_FakeDragEvent(move, start))
    widget.view_box.mouseDragEvent(_FakeDragEvent(move, move, is_finish=True))

    assert moved == []
    assert created == []
    assert widget._preview_line.isVisible() is False
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
    captured: list[tuple[str, float, bool]] = []
    widget.protectiveOrderCreated.connect(lambda order_type, price, from_average: captured.append((order_type, price, from_average)))

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
