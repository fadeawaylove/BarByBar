from pathlib import Path
from datetime import datetime, timedelta
import shutil
from uuid import uuid4

from barbybar.data.tick_size import default_tick_size_for_symbol
from barbybar.data.timeframe import aggregate_bars, find_bar_index_for_timestamp, normalize_timeframe, supported_replay_timeframes
from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import ActionType, Bar, OrderLineType
from barbybar.storage.repository import Repository


def test_repository_roundtrip() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1")
        session = repo.create_session(dataset.id or 0, start_index=1)
        bars = repo.get_chart_bars(session.id or 0, "5m")
        session.chart_timeframe = "5m"
        session.current_index = 0
        session.current_bar_time = bars[0].timestamp
        engine = ReviewEngine(session, bars)
        engine.record_action(ActionType.OPEN_LONG, quantity=1)
        engine.place_order_line(OrderLineType.STOP_LOSS, price=bars[0].close - 10, quantity=1)
        engine.step_forward()
        engine.record_action(ActionType.CLOSE, quantity=1)
        engine.set_notes("Breakout failed after resistance retest")
        engine.set_tags(["breakout", "morning"])
        repo.save_session(engine.session, engine.actions, engine.order_lines)

        saved = repo.get_session(session.id or 0)
        actions = repo.get_session_actions(session.id or 0)
        order_lines = repo.get_order_lines(session.id or 0)
        assert saved.notes.startswith("Breakout")
        assert saved.chart_timeframe == "5m"
        assert saved.tick_size == default_tick_size_for_symbol("IF")
        assert saved.stats.total_trades == 1
        assert len(actions) == 2
        assert len(order_lines) == 1
        assert order_lines[0].order_type is OrderLineType.STOP_LOSS
        assert order_lines[0].active_from_bar_index == 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_aggregate_bars_drops_incomplete_tail() -> None:
    start = datetime(2025, 1, 1, 9, 0)
    source = []
    for idx in range(8):
        source.append(
            Bar(
                timestamp=start + timedelta(minutes=idx),
                open=100 + idx,
                high=101 + idx,
                low=99 + idx,
                close=100.5 + idx,
                volume=10 + idx,
            )
        )

    aggregated = aggregate_bars(source, "1m", "5m")

    assert len(aggregated) == 1
    assert aggregated[0].timestamp == start + timedelta(minutes=4)
    assert aggregated[0].open == 100
    assert aggregated[0].close == 104.5
    assert aggregated[0].high == 105
    assert aggregated[0].low == 99
    assert aggregated[0].volume == sum(10 + idx for idx in range(5))


def test_aggregate_bars_resets_after_session_gap_and_keeps_close_time() -> None:
    start = datetime(2025, 1, 1, 11, 26)
    source = [
        Bar(timestamp=start + timedelta(minutes=idx), open=100 + idx, high=101 + idx, low=99 + idx, close=100.5 + idx, volume=10)
        for idx in range(5)
    ]
    afternoon = datetime(2025, 1, 1, 13, 31)
    source.extend(
        [
            Bar(timestamp=afternoon + timedelta(minutes=idx), open=110 + idx, high=111 + idx, low=109 + idx, close=110.5 + idx, volume=20)
            for idx in range(5)
        ]
    )

    aggregated = aggregate_bars(source, "1m", "5m")

    assert [bar.timestamp for bar in aggregated] == [datetime(2025, 1, 1, 11, 30), datetime(2025, 1, 1, 13, 35)]


def test_normalize_timeframe_accepts_numeric_aliases() -> None:
    assert normalize_timeframe("1") == "1m"
    assert normalize_timeframe("5") == "5m"


def test_supported_replay_timeframes_excludes_1d() -> None:
    assert supported_replay_timeframes("1m") == ["1m", "5m", "15m", "30m", "60m"]


def test_find_bar_index_for_timestamp_aligns_to_containing_bar() -> None:
    start = datetime(2025, 1, 1, 9, 0)
    bars = aggregate_bars(
        [
            Bar(
                timestamp=start + timedelta(minutes=idx),
                open=100,
                high=101,
                low=99,
                close=100,
                volume=10,
            )
            for idx in range(10)
        ],
        "1m",
        "5m",
    )
    assert find_bar_index_for_timestamp(bars, start + timedelta(minutes=3)) == 0
    assert find_bar_index_for_timestamp(bars, start + timedelta(minutes=7)) == 0


def test_get_chart_window_returns_only_local_slice_for_1m() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        session = repo.create_session(dataset.id or 0, start_index=4)

        window = repo.get_chart_window(session.id or 0, "1m", repo.get_bars(dataset.id or 0)[4].timestamp, 4, 3)

        assert len(window.bars) == 8
        assert window.global_start_index == 0
        assert window.global_end_index == 7
        assert window.anchor_global_index == 4
        assert window.total_count == dataset.total_bars
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_get_chart_window_returns_local_aggregate_slice_for_5m() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        session = repo.create_session(dataset.id or 0, start_index=4)
        full_5m = repo.get_chart_bars(session.id or 0, "5m")

        anchor = full_5m[0].timestamp
        window = repo.get_chart_window(session.id or 0, "5m", anchor, 2, 3)

        assert window.anchor_global_index == 0
        assert window.global_start_index == 0
        assert window.global_end_index == len(full_5m) - 1
        assert [bar.timestamp for bar in window.bars] == [bar.timestamp for bar in full_5m[: window.global_end_index + 1]]
        assert [bar.close for bar in window.bars] == [bar.close for bar in full_5m[: window.global_end_index + 1]]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_get_session_falls_back_from_deprecated_1d_chart_timeframe() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        session = repo.create_session(dataset.id or 0, start_index=1)
        repo.conn.execute("UPDATE sessions SET chart_timeframe = '1d' WHERE id = ?", (session.id,))
        repo.conn.commit()

        loaded = repo.get_session(session.id or 0)

        assert loaded.chart_timeframe == "1m"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_session_tick_size_persists_manual_override() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "AG", "1m")
        session = repo.create_session(dataset.id or 0, start_index=1)
        session.tick_size = 0.5
        repo.save_session(session, [], [])

        loaded = repo.get_session(session.id or 0)

        assert loaded.tick_size == 0.5
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_save_session_preserves_existing_order_line_ids() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        session = repo.create_session(dataset.id or 0, start_index=1)
        bars = repo.get_chart_bars(session.id or 0, "1m")
        engine = ReviewEngine(session, bars)
        line = engine.place_order_line(OrderLineType.ENTRY_LONG, price=bars[1].close, quantity=1)
        repo.save_session(engine.session, engine.actions, engine.order_lines)
        first_saved = repo.get_order_lines(session.id or 0)

        assert len(first_saved) == 1
        first_id = first_saved[0].id
        assert first_id is not None

        engine.order_lines = first_saved
        engine.update_order_line(first_id, bars[1].close + 1)
        repo.save_session(engine.session, engine.actions, engine.order_lines)
        second_saved = repo.get_order_lines(session.id or 0)

        assert len(second_saved) == 1
        assert second_saved[0].id == first_id
        assert second_saved[0].price == bars[1].close + 1
        assert second_saved[0].active_from_bar_index == line.active_from_bar_index
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
