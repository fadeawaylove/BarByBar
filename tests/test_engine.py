from datetime import datetime, timedelta

from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import ActionType, Bar, ReviewSession


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
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1)
    engine.step_forward()
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1)
    assert engine.session.position.realized_pnl == 3
    assert engine.session.stats.total_trades == 1
    assert engine.session.stats.win_rate == 1.0


def test_stop_loss_auto_close() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_LONG, quantity=1)
    engine.record_action(ActionType.SET_STOP_LOSS, price=99)
    engine.step_forward()
    engine.step_forward()
    engine.step_forward()
    assert engine.session.position.is_open is False
    assert engine.session.stats.total_trades == 1


def test_step_back_restores_state() -> None:
    session = ReviewSession(id=1, dataset_id=1, symbol="IF", timeframe="1m", start_index=0, current_index=0)
    engine = ReviewEngine(session, sample_bars())
    engine.record_action(ActionType.OPEN_SHORT, quantity=1)
    engine.step_forward()
    engine.step_back()
    assert engine.session.current_index == 0
    assert engine.session.position.direction == "short"
