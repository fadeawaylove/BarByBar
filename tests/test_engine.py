from datetime import datetime, timedelta

from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import ActionType, Bar, OrderLineType, ReviewSession


def sample_bars() -> list[Bar]:
    start = datetime(2025, 1, 1, 9, 0)
    bars = []
    for idx, close in enumerate([100, 101, 103, 98, 96, 104]):
        bars.append(
            Bar(
                timestamp=start + timedelta(minutes=idx),
                open=close - 1,
                high=close + 1,
                low=close - 2,
                close=close,
                volume=1000 + idx * 100,
            )
        )
    return bars


def test_open_close_and_stats() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1)
    engine.step_forward()
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1)
    assert engine.session.position.realized_pnl == 3
    assert engine.session.stats.total_trades == 1
    assert engine.session.stats.win_rate == 1.0


def test_stop_loss_auto_close() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1)
    engine.record_action(ActionType.SET_STOP_LOSS, price=99)
    engine.step_forward()
    engine.step_forward()
    engine.step_forward()
    assert engine.session.position.is_open is False
    assert engine.session.stats.total_trades == 1


def test_step_back_restores_state() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_SHORT, quantity=1)
    engine.step_forward()
    engine.step_back()
    assert engine.session.current_index == 0
    assert engine.session.position.direction == "short"


def test_entry_order_line_triggers_from_bar_range() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())

    line = engine.place_order_line(OrderLineType.ENTRY_LONG, price=101, quantity=1)

    assert line.active_from_bar_index == 1
    engine.step_forward()

    assert engine.session.position.direction == "long"
    assert engine.session.position.quantity == 1
    assert any(action.action_type is ActionType.OPEN_LONG for action in engine.actions)


def test_new_order_line_does_not_trigger_on_current_bar() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=105, low=99, close=102, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=102, high=103, low=100, close=101, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=101, high=106, low=100, close=105, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)

    engine.place_order_line(OrderLineType.ENTRY_LONG, price=104, quantity=1)

    engine.step_forward()
    assert engine.session.position.is_open is False

    engine.step_forward()
    assert engine.session.position.direction == "long"


def test_stop_loss_line_has_priority_over_take_profit_on_same_bar() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)
    engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 99


def test_exit_order_line_closes_existing_position() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)
    engine.place_order_line(OrderLineType.EXIT, price=100.5, quantity=2)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 100.5
    assert any(action.action_type is ActionType.CLOSE for action in engine.actions)


def test_reverse_order_line_flips_position_direction() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.place_order_line(OrderLineType.REVERSE, price=100.5, quantity=1)

    engine.step_forward()

    assert engine.session.position.direction == "short"
    assert engine.session.position.quantity == 1
    assert engine.actions[-2].action_type is ActionType.CLOSE
    assert engine.actions[-1].action_type is ActionType.OPEN_SHORT
