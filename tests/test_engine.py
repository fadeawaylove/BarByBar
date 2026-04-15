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


def session_boundary_bars() -> list[Bar]:
    return [
        Bar(timestamp=datetime(2025, 1, 1, 14, 59), open=100, high=101, low=99, close=100.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 21, 0), open=101, high=102, low=100, close=101.5, volume=1),
        Bar(timestamp=datetime(2025, 1, 2, 9, 0), open=102, high=103, low=101, close=102.5, volume=1),
    ]


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
    review_item = engine.trade_review_items()[0]
    assert review_item.exit_reason == "stop_loss"
    assert review_item.is_manual is False
    assert review_item.had_stop_protection is True


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


def test_multiple_stop_loss_lines_can_coexist() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)

    first = engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)
    second = engine.place_order_line(OrderLineType.STOP_LOSS, price=97, quantity=1)

    active_stop_lines = [line for line in engine.active_order_lines if line.order_type is OrderLineType.STOP_LOSS]

    assert [line.price for line in active_stop_lines] == [99, 97]
    assert engine.session.position.stop_loss == 99
    assert first is not second


def test_nearest_long_stop_loss_triggers_first_when_multiple_lines_are_hit() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=97, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 99


def test_long_stop_loss_gap_down_does_not_trigger_when_bar_range_excludes_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=97, high=98, low=95, close=96, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is True
    assert all(action.action_type is not ActionType.CLOSE for action in engine.actions)


def test_long_take_profit_gap_up_does_not_trigger_when_bar_range_excludes_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=105, high=106, low=104, close=105, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is True
    assert all(action.action_type is not ActionType.CLOSE for action in engine.actions)


def test_short_stop_loss_gap_up_does_not_trigger_when_bar_range_excludes_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=105, high=106, low=104, close=105, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_SHORT, quantity=1, price=100)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=102, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is True
    assert all(action.action_type is not ActionType.CLOSE for action in engine.actions)


def test_short_take_profit_gap_down_does_not_trigger_when_bar_range_excludes_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=95, high=96, low=94, close=95, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_SHORT, quantity=1, price=100)
    engine.place_order_line(OrderLineType.TAKE_PROFIT, price=98, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is True
    assert all(action.action_type is not ActionType.CLOSE for action in engine.actions)


def test_long_stop_loss_triggers_when_display_range_contains_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100.0, high=100.2, low=99.8, close=100.0, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100.0, high=100.2, low=99.91, close=100.0, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0, tick_size=0.2)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100.0)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=100.0, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 100.0


def test_long_take_profit_triggers_when_display_range_contains_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100.0, high=100.2, low=99.8, close=100.0, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100.0, high=100.09, low=99.8, close=100.0, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0, tick_size=0.2)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100.0)
    engine.place_order_line(OrderLineType.TAKE_PROFIT, price=100.0, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 100.0


def test_short_stop_loss_triggers_when_display_range_contains_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100.0, high=100.2, low=99.8, close=100.0, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100.0, high=100.09, low=99.8, close=100.0, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0, tick_size=0.2)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_SHORT, quantity=1, price=100.0)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=100.0, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 100.0


def test_entry_order_line_triggers_when_display_range_contains_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100.0, high=100.2, low=99.8, close=100.0, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100.0, high=100.09, low=99.8, close=100.0, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0, tick_size=0.2)
    engine = ReviewEngine(session, bars)
    engine.place_order_line(OrderLineType.ENTRY_LONG, price=100.0, quantity=1)

    engine.step_forward()

    assert engine.session.position.direction == "long"


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


def test_entry_short_above_price_triggers_when_bar_range_covers_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100, high=100.5, low=95, close=96, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=96, high=103, low=95, close=102, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)

    engine.place_order_line(OrderLineType.ENTRY_SHORT, price=102, quantity=1)
    engine.step_forward()
    assert engine.session.position.is_open is False

    engine.step_forward()
    assert engine.session.position.direction == "short"


def test_updating_order_line_price_restarts_effect_from_next_bar() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=100, high=105, low=99, close=104, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 3), open=104, high=106, low=103, close=105, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    line = engine.place_order_line(OrderLineType.ENTRY_LONG, price=110, quantity=1)
    line.id = 1

    engine.step_forward()
    engine.update_order_line(line.id, 104)

    assert line.active_from_bar_index == 2
    engine.step_forward()
    assert engine.session.position.direction == "long"


def test_updating_order_line_quantity_restarts_effect_from_next_bar() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=100, high=105, low=99, close=104, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 3), open=104, high=106, low=103, close=105, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    line = engine.place_order_line(OrderLineType.ENTRY_LONG, price=104, quantity=1)
    line.id = 1

    engine.step_forward()
    engine.update_order_line_quantity(line.id, 3)

    assert line.active_from_bar_index == 2
    engine.step_forward()
    assert engine.session.position.direction == "long"
    assert engine.session.position.quantity == 3


def test_trade_review_items_include_entry_exit_bars_and_planned_execution() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())

    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.record_action(ActionType.SET_STOP_LOSS, price=97)
    engine.step_forward()
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1, price=103)

    review_item = engine.trade_review_items()[0]

    assert review_item.entry_bar_index == 0
    assert review_item.exit_bar_index == 2
    assert review_item.holding_bars == 2
    assert review_item.exit_reason == "manual_close"
    assert review_item.had_stop_protection is True
    assert review_item.had_adverse_add is False
    assert review_item.is_planned is True


def test_refresh_stats_populates_training_metrics() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())

    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.record_action(ActionType.SET_STOP_LOSS, price=95)
    engine.step_forward()
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1, price=103)

    engine.record_action(ActionType.OPEN_SHORT, quantity=1, price=103)
    engine.record_action(ActionType.SET_STOP_LOSS, price=110)
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1, price=96)

    stats = engine.session.stats

    assert stats.average_win == 5.0
    assert stats.average_loss == 0.0
    assert stats.payoff_ratio == 5.0
    assert stats.expectancy == 5.0
    assert stats.long_trades == 1
    assert stats.short_trades == 1
    assert stats.avg_holding_bars == 1.5
    assert stats.max_win_streak == 2
    assert stats.max_loss_streak == 0
    assert stats.trades_with_stop_rate == 1.0
    assert stats.manual_trades == 2
    assert stats.auto_trades == 0
    assert stats.planned_trades == 2


def test_trade_review_marks_adverse_add_only_when_adding_into_loss() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100, high=100, low=97, close=98, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=98, high=99, low=95, close=96, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)

    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.step_forward()
    engine.record_action(ActionType.ADD, quantity=1, price=98)
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=2, price=96)

    review_item = engine.trade_review_items()[0]

    assert review_item.had_adverse_add is True
    assert review_item.is_planned is False


def test_protective_line_quantity_does_not_expand_after_add() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    line = engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)

    engine.record_action(ActionType.ADD, quantity=1, price=101)

    assert engine.session.position.quantity == 2
    assert line.quantity == 1


def test_protective_line_quantity_does_not_shrink_after_partial_reduce() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)
    line = engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=2)

    engine.record_action(ActionType.REDUCE, quantity=1, price=101)

    assert engine.session.position.quantity == 1
    assert line.quantity == 2


def test_session_end_flatten_closes_position_at_day_session_boundary() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, session_boundary_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)

    moved = engine.step_forward(flatten_at_session_end=True)

    assert moved is True
    assert engine.session.current_index == 1
    assert engine.session.position.is_open is False
    assert engine.actions[-1].action_type is ActionType.CLOSE
    assert engine.actions[-1].price == 100.5
    assert engine.actions[-1].extra["order_type"] == "session_end_flatten"
    assert engine.trade_review_items()[0].exit_reason == "session_end_flatten"


def test_session_end_flatten_closes_position_at_night_session_boundary() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=1, current_index=1)
    engine = ReviewEngine(session, session_boundary_bars()[1:], window_start_index=1, total_count=3)
    engine.record_action(ActionType.OPEN_SHORT, quantity=1, price=101.5)

    moved = engine.step_forward(flatten_at_session_end=True)

    assert moved is True
    assert engine.session.current_index == 2
    assert engine.session.position.is_open is False
    assert engine.actions[-1].price == 101.5
    assert engine.actions[-1].extra["order_type"] == "session_end_flatten"


def test_session_end_flatten_closes_position_on_final_bar_without_advancing() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 14, 58), open=100, high=101, low=99, close=100.0, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 14, 59), open=100, high=101, low=99, close=101.0, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=1, current_index=1)
    engine = ReviewEngine(session, bars[1:], window_start_index=1, total_count=2)
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)

    moved = engine.step_forward(flatten_at_session_end=True)

    assert moved is True
    assert engine.session.current_index == 1
    assert engine.session.position.is_open is False
    assert engine.actions[-1].price == 101.0
    assert engine.can_step_forward() is False


def test_session_end_flatten_can_be_disabled() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, session_boundary_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)

    moved = engine.step_forward(flatten_at_session_end=False)

    assert moved is True
    assert engine.session.current_index == 1
    assert engine.session.position.is_open is True


def test_session_end_flatten_cancels_flattening_lines_and_step_back_restores_them() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, session_boundary_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    flatten_line = engine.place_order_line(OrderLineType.EXIT, price=99.5, quantity=1)

    engine.step_forward(flatten_at_session_end=True)

    assert flatten_line.is_active is False
    assert engine.session.position.is_open is False

    engine.step_back()

    assert engine.session.current_index == 0
    assert engine.session.position.is_open is True
    restored_line = next(line for line in engine.order_lines if line.id == flatten_line.id)
    assert restored_line.is_active is True
