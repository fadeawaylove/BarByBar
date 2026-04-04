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
    state = widget.viewport_state
    old_bars = state.bars_in_view
    old_right = state.right_edge_index
    old_left = old_right - old_bars
    anchor = old_right - (old_bars * 0.25)
    old_anchor_ratio = (anchor - old_left) / old_bars

    widget.zoom_x(anchor_x=anchor, scale=0.5)

    assert widget.viewport_state.bars_in_view < old_bars
    new_left = widget.viewport_state.right_edge_index - widget.viewport_state.bars_in_view
    new_anchor_ratio = (anchor - new_left) / widget.viewport_state.bars_in_view
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
    assert DOWN_CANDLE_COLOR == "#2e9f5b"
