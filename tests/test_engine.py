from datetime import datetime, timedelta

from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import ActionType, Bar, OrderLineType, ReviewSession, TradeReviewItem


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


def test_engine_stamps_new_trade_state_with_chart_timeframe() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="15m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())

    action = engine.record_action(ActionType.OPEN_LONG, quantity=1)
    line = engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)
    average_line = next(item for item in engine.display_order_lines() if item.order_type.value == "average_price")

    assert action.chart_timeframe == "15m"
    assert line.chart_timeframe == "15m"
    assert average_line.chart_timeframe == "15m"


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


def test_trade_review_items_include_entry_exit_action_indices_and_notes() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, note="突破后回踩确认")
    engine.step_forward()
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1, note="止盈后复盘：执行不错")

    review_item = engine.trade_review_items()[0]

    assert review_item.entry_action_index == 0
    assert review_item.exit_action_index == 1
    assert review_item.entry_note == "突破后回踩确认"
    assert review_item.review_note == "止盈后复盘：执行不错"


def test_trade_review_items_include_fifo_entry_legs_for_adds() -> None:
    bars = sample_bars()
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)

    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100, note="首仓计划")
    engine.step_forward()
    engine.record_action(ActionType.ADD, quantity=1, price=102, note="加仓确认")
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=2, price=104, note="整体复盘")

    review_item = engine.trade_review_items()[0]

    assert review_item.entry_note == "首仓计划"
    assert [(leg.bar_index, leg.price, leg.quantity, leg.action_index, leg.note) for leg in review_item.entry_legs] == [
        (0, 100, 1, 0, "首仓计划"),
        (1, 102, 1, 1, "加仓确认"),
    ]


def test_fifo_lot_trade_uses_weighted_entry_price_and_lot_pnl() -> None:
    bars = sample_bars()
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)

    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.step_forward()
    engine.record_action(ActionType.ADD, quantity=1, price=104)
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=2, price=103)

    trade = engine.trades[0]

    assert trade.entry_price == 102
    assert trade.pnl == 2
    assert [(leg.price, leg.quantity) for leg in trade.entry_legs] == [(100, 1), (104, 1)]


def test_trade_review_items_allocate_entry_legs_to_partial_exits_fifo() -> None:
    bars = sample_bars()
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)

    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100, note="首仓")
    engine.step_forward()
    engine.record_action(ActionType.ADD, quantity=2, price=101, note="加仓两手")
    engine.step_forward()
    engine.record_action(ActionType.REDUCE, quantity=1, price=103, note="先止盈一手")
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=2, price=104, note="剩余止盈")

    first, second = engine.trade_review_items()

    assert [(leg.bar_index, leg.price, leg.quantity, leg.note) for leg in first.entry_legs] == [(0, 100, 1, "首仓")]
    assert [(leg.bar_index, leg.price, leg.quantity, leg.note) for leg in second.entry_legs] == [(1, 101, 2, "加仓两手")]
    assert first.entry_action_index == 0
    assert second.entry_action_index == 1


def test_fifo_lot_partial_exit_reprices_remaining_position_average() -> None:
    bars = sample_bars()
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)

    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.step_forward()
    engine.record_action(ActionType.ADD, quantity=2, price=104)
    engine.step_forward()
    engine.record_action(ActionType.REDUCE, quantity=1, price=103)

    assert engine.session.position.quantity == 2
    assert engine.session.position.average_price == 104


def test_trade_review_items_rebuild_legacy_cache_without_entry_legs() -> None:
    bars = sample_bars()
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100, note="首仓")
    engine.step_forward()
    engine.record_action(ActionType.ADD, quantity=1, price=101, note="加仓")
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=2, price=103, note="平仓")
    fresh_item = engine.trade_review_items()[0]
    engine._trade_review_items_cache = [_legacy_review_item_without_entry_legs(fresh_item)]
    engine._trade_review_dirty = False

    rebuilt_item = engine.trade_review_items()[0]

    assert [(leg.bar_index, leg.price, leg.quantity, leg.note) for leg in rebuilt_item.entry_legs] == [
        (0, 100, 1, "首仓"),
        (1, 101, 1, "加仓"),
    ]


def test_step_back_marks_legacy_trade_review_cache_dirty() -> None:
    bars = sample_bars()
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100, note="首仓")
    engine.step_forward()
    engine.record_action(ActionType.ADD, quantity=1, price=101, note="加仓")
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=2, price=103, note="平仓")
    fresh_item = engine.trade_review_items()[0]
    engine._trade_review_items_cache = [_legacy_review_item_without_entry_legs(fresh_item)]
    engine._trade_review_dirty = False

    assert engine.step_forward() is True
    assert engine.step_back() is True
    rebuilt_item = engine.trade_review_items()[0]

    assert [(leg.bar_index, leg.price, leg.quantity, leg.note) for leg in rebuilt_item.entry_legs] == [
        (0, 100, 1, "首仓"),
        (1, 101, 1, "加仓"),
    ]


def _legacy_review_item_without_entry_legs(item: TradeReviewItem) -> TradeReviewItem:
    return TradeReviewItem(
        trade_number=item.trade_number,
        entry_time=item.entry_time,
        exit_time=item.exit_time,
        direction=item.direction,
        quantity=item.quantity,
        entry_price=item.entry_price,
        exit_price=item.exit_price,
        pnl=item.pnl,
        entry_bar_index=item.entry_bar_index,
        exit_bar_index=item.exit_bar_index,
        holding_bars=item.holding_bars,
        exit_reason=item.exit_reason,
        is_manual=item.is_manual,
        had_stop_protection=item.had_stop_protection,
        had_adverse_add=item.had_adverse_add,
        is_planned=item.is_planned,
        entry_action_index=item.entry_action_index,
        exit_action_index=item.exit_action_index,
        entry_note=item.entry_note,
        review_note=item.review_note,
    )


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


def test_same_price_take_profit_lines_merge_quantities() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=3, price=100)

    first = engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=1, note="第一笔止盈")
    second = engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=2, note="第二笔止盈")
    active_take_profit_lines = [line for line in engine.active_order_lines if line.order_type is OrderLineType.TAKE_PROFIT]

    assert first is second
    assert active_take_profit_lines == [first]
    assert first.quantity == 3
    assert first.note == "第一笔止盈\n第二笔止盈"


def test_same_price_order_lines_merge_by_order_type() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=3, price=100)
    merge_cases = [
        (OrderLineType.STOP_LOSS, 99),
        (OrderLineType.ENTRY_LONG, 103),
        (OrderLineType.ENTRY_SHORT, 98),
        (OrderLineType.EXIT, 104),
        (OrderLineType.REVERSE, 105),
    ]

    for order_type, price in merge_cases:
        first = engine.place_order_line(order_type, price=price, quantity=1)
        second = engine.place_order_line(order_type, price=price, quantity=2)
        active_lines = [line for line in engine.active_order_lines if line.order_type is order_type and line.price == price]

        assert first is second
        assert active_lines == [first]
        assert first.quantity == 3


def test_same_price_different_order_types_do_not_merge() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)

    stop = engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)
    exit_line = engine.place_order_line(OrderLineType.EXIT, price=99, quantity=1)

    assert stop is not exit_line
    assert stop.is_active is True
    assert exit_line.is_active is True
    assert len([line for line in engine.active_order_lines if line.price == 99]) == 2


def test_same_order_type_different_price_does_not_merge() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)

    first = engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=1)
    second = engine.place_order_line(OrderLineType.TAKE_PROFIT, price=103, quantity=2)

    assert first is not second
    assert [line.quantity for line in engine.active_order_lines if line.order_type is OrderLineType.TAKE_PROFIT] == [1, 2]


def test_updating_order_line_price_merges_into_existing_same_price_line() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=3, price=100)
    first = engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=1, note="原目标")
    second = engine.place_order_line(OrderLineType.TAKE_PROFIT, price=103, quantity=2, note="移动目标")
    first.id = 1
    second.id = 2

    merged = engine.update_order_line(second.id, 102)
    active_take_profit_lines = [line for line in engine.active_order_lines if line.order_type is OrderLineType.TAKE_PROFIT]

    assert merged is first
    assert active_take_profit_lines == [first]
    assert first.quantity == 3
    assert first.note == "原目标\n移动目标"
    assert second.is_active is False


def test_updating_order_line_quantity_keeps_merged_total() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=4, price=100)
    line = engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=1)
    duplicate = engine.place_order_line(OrderLineType.TAKE_PROFIT, price=103, quantity=1)
    line.id = 1
    duplicate.id = 2
    engine.update_order_line(duplicate.id, 102)

    merged = engine.update_order_line_quantity(line.id, 4)

    assert merged is line
    assert line.quantity == 4
    assert [item for item in engine.active_order_lines if item.order_type is OrderLineType.TAKE_PROFIT] == [line]


def test_nearest_long_stop_loss_triggers_first_when_multiple_lines_are_hit() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=97, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 99


def test_long_stop_loss_gap_down_triggers_at_open_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=97, high=98, low=95, close=96, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 97


def test_long_stop_loss_prefers_gap_open_over_intrabar_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=97, high=101, low=95, close=100, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 97


def test_long_take_profit_gap_up_triggers_at_open_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=105, high=106, low=104, close=105, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 105


def test_long_take_profit_records_single_exit_on_trigger_bar() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=100, high=103, low=99, close=102, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=1)

    engine.step_forward()
    engine.step_forward()

    assert engine.session.position.is_open is False
    assert len(engine.trades) == 1
    assert engine.actions[-1].action_type is ActionType.CLOSE
    assert engine.actions[-1].bar_index == 2
    assert engine.trades[-1].exit_time == bars[2].timestamp


def test_entry_order_line_prefers_gap_open_over_intrabar_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=105, high=106, low=101, close=104, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.place_order_line(OrderLineType.ENTRY_LONG, price=102, quantity=1)

    engine.step_forward()

    assert engine.session.position.direction == "long"
    assert engine.actions[-1].action_type is ActionType.OPEN_LONG
    assert engine.actions[-1].price == 105


def test_short_stop_loss_gap_up_triggers_at_open_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=105, high=106, low=104, close=105, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_SHORT, quantity=1, price=100)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=102, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 105


def test_short_take_profit_gap_down_triggers_at_open_price() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=95, high=96, low=94, close=95, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_SHORT, quantity=1, price=100)
    engine.place_order_line(OrderLineType.TAKE_PROFIT, price=98, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].exit_price == 95


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


def test_stop_loss_line_can_partially_close_position() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)
    engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is True
    assert engine.session.position.quantity == 1
    assert engine.trades[-1].quantity == 1
    assert engine.trades[-1].exit_price == 99


def test_take_profit_line_can_partially_close_position() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=101, high=103, low=100, close=102, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)
    engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is True
    assert engine.session.position.quantity == 1
    assert engine.trades[-1].quantity == 1
    assert engine.trades[-1].exit_price == 102


def test_multiple_take_profit_lines_trigger_on_same_bar_until_position_is_closed() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=101, high=103, low=100, close=102, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)
    first = engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=1)
    second = engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=2)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert first.status.name == "TRIGGERED"
    assert second is first
    assert [trade.quantity for trade in engine.trades] == [2]
    assert [trade.exit_price for trade in engine.trades] == [102]


def test_stop_loss_priority_does_not_mix_take_profit_lines_on_same_bar() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100, high=103, low=98, close=101, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)
    stop = engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)
    take = engine.place_order_line(OrderLineType.TAKE_PROFIT, price=102, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is True
    assert engine.session.position.quantity == 1
    assert stop.status.name == "TRIGGERED"
    assert take.is_active is True
    assert engine.trades[-1].exit_price == 99


def test_partial_protective_trigger_keeps_remaining_protective_lines() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)
    first = engine.place_order_line(OrderLineType.STOP_LOSS, price=99, quantity=1)
    second = engine.place_order_line(OrderLineType.STOP_LOSS, price=97, quantity=1)

    engine.step_forward()

    assert first.status.name == "TRIGGERED"
    assert second.is_active is True
    assert engine.session.position.quantity == 1
    assert engine.session.position.stop_loss == 97


def test_exit_order_line_can_partially_close_position() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)
    engine.place_order_line(OrderLineType.EXIT, price=100.5, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is True
    assert engine.session.position.quantity == 1
    assert engine.trades[-1].quantity == 1


def test_exit_order_line_caps_at_remaining_position_quantity() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)
    engine.place_order_line(OrderLineType.EXIT, price=100.5, quantity=3)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert engine.trades[-1].quantity == 2


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


def test_partial_reverse_line_nets_position_without_dual_sided_holdings() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=2, price=100)
    engine.place_order_line(OrderLineType.REVERSE, price=100.5, quantity=1)

    engine.step_forward()

    assert engine.session.position.is_open is False
    assert len(engine.trades) == 1
    assert engine.trades[-1].quantity == 2
    assert engine.actions[-1].action_type is ActionType.CLOSE
    assert engine.actions[-1].extra["order_type"] == OrderLineType.REVERSE.value


def test_flattening_order_lines_can_be_created_after_pending_entry_line() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.place_order_line(OrderLineType.ENTRY_LONG, price=103, quantity=1)

    exit_line = engine.place_order_line(OrderLineType.EXIT, price=104, quantity=1)
    reverse_line = engine.place_order_line(OrderLineType.REVERSE, price=105, quantity=1)

    assert exit_line.order_type is OrderLineType.EXIT
    assert reverse_line.order_type is OrderLineType.REVERSE


def test_flattening_order_lines_still_require_position_or_pending_entry_line() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())

    for order_type in [OrderLineType.EXIT, OrderLineType.REVERSE]:
        try:
            engine.place_order_line(order_type, price=101, quantity=1)
        except ValueError as exc:
            assert "当前没有持仓或待成交入场条件单" in str(exc)
        else:
            raise AssertionError(f"{order_type.value} should require a position or pending entry line")


def test_flattening_order_line_waits_until_pending_entry_fills() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=100, high=103, low=99, close=102, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 3), open=102, high=105, low=101, close=104, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, bars)
    engine.place_order_line(OrderLineType.ENTRY_LONG, price=102, quantity=1)
    engine.place_order_line(OrderLineType.EXIT, price=104, quantity=1)

    engine.step_forward()
    assert engine.session.position.is_open is False
    assert not any(action.action_type is ActionType.CLOSE for action in engine.actions)

    engine.step_forward()
    assert engine.session.position.direction == "long"

    engine.step_forward()
    assert engine.session.position.is_open is False
    assert engine.actions[-1].action_type is ActionType.CLOSE


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


def test_trade_review_items_uses_cache_until_invalidated() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1, price=101)

    first = engine.trade_review_items()

    def fail_rebuild() -> list[TradeReviewItem]:
        raise AssertionError("trade review cache should have been reused")

    engine._rebuild_trade_review_cache = fail_rebuild  # type: ignore[method-assign]

    second = engine.trade_review_items()

    assert first == second


def test_trade_review_cache_rebuilds_after_new_action() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1, price=101)
    engine.trade_review_items()

    calls = {"count": 0}
    original = engine._rebuild_trade_review_cache

    def wrapped_rebuild() -> list[TradeReviewItem]:
        calls["count"] += 1
        return original()

    engine._rebuild_trade_review_cache = wrapped_rebuild  # type: ignore[method-assign]
    engine.record_action(ActionType.OPEN_SHORT, quantity=1, price=101)
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1, price=99)

    items = engine.trade_review_items()
    cached_items = engine.trade_review_items()

    assert calls["count"] >= 1
    assert len(items) == 2
    assert items == cached_items


def test_step_back_restores_trade_review_cache_and_stats() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1, price=100)
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1, price=101)
    assert len(engine.trade_review_items()) == 1
    assert engine.session.stats.total_trades == 1

    engine.record_action(ActionType.OPEN_SHORT, quantity=1, price=101)
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1, price=99)
    assert len(engine.trade_review_items()) == 2
    assert engine.session.stats.total_trades == 2

    engine.step_back()
    engine.step_back()
    engine.step_back()

    items = engine.trade_review_items()

    assert len(items) == 1
    assert engine.session.stats.total_trades == 1
    assert items[0].direction == "long"


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


def test_entry_order_gap_fill_uses_window_local_previous_bar() -> None:
    bars = [
        Bar(timestamp=datetime(2025, 1, 1, 9, 0), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 1), open=100, high=101, low=99, close=100, volume=1),
        Bar(timestamp=datetime(2025, 1, 1, 9, 2), open=105, high=106, low=104, close=105, volume=1),
    ]
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", chart_timeframe="1m", start_index=1, current_index=1)
    engine = ReviewEngine(session, bars[1:], window_start_index=1, total_count=3)
    engine.place_order_line(OrderLineType.ENTRY_LONG, price=102, quantity=1)

    moved = engine.step_forward()

    assert moved is True
    assert engine.session.current_index == 2
    assert engine.session.position.direction == "long"
    assert engine.actions[-1].action_type is ActionType.OPEN_LONG
    assert engine.actions[-1].price == 105
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
