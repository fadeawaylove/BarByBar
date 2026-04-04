from datetime import datetime, timedelta

import pytest
from PySide6.QtWidgets import QApplication

from barbybar.domain.models import Bar
from barbybar.ui.chart_widget import ChartWidget, DOWN_CANDLE_COLOR, UP_CANDLE_COLOR


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

    assert len(markers) == 2
    assert sorted(round(marker.value(), 2) for marker in markers) == [-0.5, 2.5]


def test_hover_bar_returns_none_for_future_blank_space(widget: ChartWidget) -> None:
    widget.set_full_data(_bars())
    widget.set_cursor(20)

    assert widget._hover_bar_at(30.0) is None


def test_hover_info_contains_ohlc_and_mouse_price(widget: ChartWidget) -> None:
    bars = _bars()
    widget.set_full_data(bars)
    widget.set_cursor(10)

    widget._update_hover_info(bars[5], 123.45)

    assert not widget._hover_card.isHidden()
    assert widget._hover_time_label.text() == "2025-01-01 09:05"
    assert widget._hover_open_label.text().startswith("开 ")
    assert widget._hover_high_label.text().startswith("高 ")
    assert widget._hover_low_label.text().startswith("低 ")
    assert widget._hover_close_label.text().startswith("收 ")


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


def test_cancel_order_preview_hides_preview_line(widget: ChartWidget) -> None:
    widget.begin_order_preview("entry_short", 1.0)

    widget.cancel_order_preview()

    assert widget._preview_line.isVisible() is False


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
