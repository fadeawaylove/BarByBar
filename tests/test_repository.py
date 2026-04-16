from pathlib import Path
import sqlite3
from datetime import datetime, timedelta
import shutil
from uuid import uuid4

from barbybar.data.tick_size import default_tick_size_for_symbol
from barbybar.data.timeframe import aggregate_bars, find_bar_index_for_timestamp, normalize_timeframe, supported_replay_timeframes
from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import ActionType, Bar, ChartDrawing, DrawingAnchor, DrawingToolType, OrderLineType, SessionStatus
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
        drawings = [
            ChartDrawing(
                tool_type=DrawingToolType.RAY,
                anchors=[DrawingAnchor(1.0, bars[0].close), DrawingAnchor(3.0, bars[1].close)],
                style={"color": "#3366ff", "width": 3, "line_style": "dash"},
            )
        ]
        repo.save_session(engine.session, engine.actions, engine.order_lines, drawings)

        saved = repo.get_session(session.id or 0)
        actions = repo.get_session_actions(session.id or 0)
        order_lines = repo.get_order_lines(session.id or 0)
        loaded_drawings = repo.get_drawings(session.id or 0)
        assert saved.notes.startswith("Breakout")
        assert saved.chart_timeframe == "5m"
        assert saved.tick_size == default_tick_size_for_symbol("IF")
        assert saved.stats.total_trades == 1
        assert len(actions) == 2
        assert len(order_lines) == 1
        assert len(loaded_drawings) == 1
        assert dataset.display_name == "if_sample.csv"
        assert loaded_drawings[0].tool_type is DrawingToolType.RAY
        assert loaded_drawings[0].style["color"] == "#3366ff"
        assert loaded_drawings[0].style["width"] == 3
        assert order_lines[0].order_type is OrderLineType.STOP_LOSS
        assert order_lines[0].active_from_bar_index == 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_find_dataset_by_symbol_returns_latest_match() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        repo.import_csv(Path("sample_data/if_sample.csv"), "AG9999", "1m")

        found = repo.find_dataset_by_symbol("ag9999")

        assert found is not None
        assert found.symbol == "AG9999"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_find_dataset_by_display_name_returns_latest_match() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        repo.import_csv(Path("sample_data/if_sample.csv"), "AG9999", "1m", display_name="AG9999.csv")

        found = repo.find_dataset_by_display_name("AG9999.csv")

        assert found is not None
        assert found.display_name == "AG9999.csv"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_repository_migrates_legacy_sessions_without_last_opened_at() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "legacy.db"
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL DEFAULT '',
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                source_path TEXT NOT NULL,
                total_bars INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                replay_timeframe TEXT NOT NULL DEFAULT '1m',
                chart_timeframe TEXT NOT NULL DEFAULT '1m',
                title TEXT NOT NULL,
                start_index INTEGER NOT NULL,
                current_index INTEGER NOT NULL,
                current_bar_time TEXT,
                tick_size REAL NOT NULL DEFAULT 1.0,
                status TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                drawing_style_presets_json TEXT NOT NULL DEFAULT '{}',
                position_json TEXT NOT NULL DEFAULT '{}',
                stats_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            INSERT INTO datasets(id, display_name, symbol, timeframe, source_path, total_bars, start_time, end_time, created_at)
            VALUES (1, 'legacy.csv', 'IF', '1m', 'legacy.csv', 10, '2025-01-01T09:00:00', '2025-01-01T09:09:00', '2025-01-01T09:00:00');

            INSERT INTO sessions(
                id, dataset_id, symbol, timeframe, replay_timeframe, chart_timeframe, title,
                start_index, current_index, current_bar_time, tick_size, status, notes, tags_json,
                drawing_style_presets_json, position_json, stats_json, created_at, updated_at
            )
            VALUES (
                1, 1, 'IF', '1m', '1m', '1m', 'legacy session',
                0, 0, '2025-01-01T09:00:00', 1.0, 'active', '', '[]',
                '{}', '{}', '{}', '2025-01-01T09:00:00', '2025-01-02T10:00:00'
            );
            """
        )
        conn.commit()
        conn.close()

        repo = Repository(db_path)
        session = repo.get_session(1)

        assert session.last_opened_at is not None
        assert session.last_opened_at == datetime(2025, 1, 2, 10, 0)
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
    assert normalize_timeframe("2") == "2m"
    assert normalize_timeframe("2min") == "2m"
    assert normalize_timeframe("5") == "5m"


def test_supported_replay_timeframes_excludes_1d() -> None:
    assert supported_replay_timeframes("1m") == ["1m", "2m", "5m", "15m", "30m", "60m"]


def test_supported_replay_timeframes_for_2m_only_include_integer_multiples() -> None:
    assert supported_replay_timeframes("2m") == ["2m", "30m", "60m"]


def test_aggregate_bars_supports_2m_timeframe() -> None:
    start = datetime(2025, 1, 1, 9, 0)
    source = [
        Bar(
            timestamp=start + timedelta(minutes=idx),
            open=100 + idx,
            high=101 + idx,
            low=99 + idx,
            close=100.5 + idx,
            volume=10 + idx,
        )
        for idx in range(4)
    ]

    aggregated = aggregate_bars(source, "1m", "2m")

    assert len(aggregated) == 2
    assert aggregated[0].timestamp == start + timedelta(minutes=1)
    assert aggregated[0].open == 100
    assert aggregated[0].close == 101.5
    assert aggregated[0].high == 102
    assert aggregated[0].low == 99
    assert aggregated[0].volume == 21


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


def test_repository_roundtrip_fib_and_text_styles() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        session = repo.create_session(dataset.id or 0, start_index=1)
        drawings = [
            ChartDrawing(
                tool_type=DrawingToolType.FIB_RETRACEMENT,
                anchors=[DrawingAnchor(1.0, 100.0), DrawingAnchor(3.0, 110.0)],
                style={"fib_levels": [0.0, 0.382, 0.5, 0.618, 1.0, 2.0], "show_level_labels": True, "show_price_labels": True},
            ),
            ChartDrawing(
                tool_type=DrawingToolType.TEXT,
                anchors=[DrawingAnchor(2.0, 105.0)],
                style={"text": "观察回撤", "font_size": 14, "text_color": "#3366ff"},
            ),
        ]
        repo.save_session(session, [], [], drawings)

        loaded = repo.get_drawings(session.id or 0)

        assert loaded[0].tool_type is DrawingToolType.FIB_RETRACEMENT
        assert loaded[0].style["fib_levels"] == [0.0, 0.382, 0.5, 0.618, 1.0, 2.0]
        assert loaded[1].tool_type is DrawingToolType.TEXT
        assert loaded[1].style["text"] == "观察回撤"
        assert loaded[1].style["font_size"] == 14
        assert loaded[1].style["text_color"] == "#3366ff"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_get_drawings_normalizes_legacy_empty_style_json() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        session = repo.create_session(dataset.id or 0, start_index=1)
        repo.conn.execute(
            "INSERT INTO drawings(session_id, tool_type, anchors_json, style_json) VALUES (?, ?, ?, ?)",
            (session.id, DrawingToolType.HORIZONTAL_LINE.value, '[{\"x\": 2.0, \"y\": 100.0}]', "{}"),
        )
        repo.conn.commit()

        drawings = repo.get_drawings(session.id or 0)

        assert drawings[0].style["color"] == "#ff9f1c"
        assert drawings[0].style["line_style"] == "solid"
        assert drawings[0].style["width"] == 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_delete_session_removes_actions_and_order_lines() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        session = repo.create_session(dataset.id or 0, start_index=1)
        bars = repo.get_chart_bars(session.id or 0, "1m")
        engine = ReviewEngine(session, bars)
        engine.record_action(ActionType.OPEN_LONG, quantity=1)
        engine.place_order_line(OrderLineType.ENTRY_LONG, price=bars[2].close, quantity=1)
        repo.save_session(
            engine.session,
            engine.actions,
            engine.order_lines,
            [ChartDrawing(tool_type=DrawingToolType.HORIZONTAL_LINE, anchors=[DrawingAnchor(2.0, bars[2].close)])],
        )

        repo.delete_session(session.id or 0)

        assert repo.list_sessions() == []
        assert repo.conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0] == 0
        assert repo.conn.execute("SELECT COUNT(*) FROM order_lines").fetchone()[0] == 0
        assert repo.conn.execute("SELECT COUNT(*) FROM drawings").fetchone()[0] == 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_delete_dataset_cascades_sessions_actions_and_order_lines() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        session = repo.create_session(dataset.id or 0, start_index=1)
        bars = repo.get_chart_bars(session.id or 0, "1m")
        engine = ReviewEngine(session, bars)
        engine.record_action(ActionType.OPEN_LONG, quantity=1)
        engine.place_order_line(OrderLineType.ENTRY_LONG, price=bars[2].close, quantity=1)
        repo.save_session(
            engine.session,
            engine.actions,
            engine.order_lines,
            [ChartDrawing(tool_type=DrawingToolType.RECTANGLE, anchors=[DrawingAnchor(1.0, 100.0), DrawingAnchor(3.0, 110.0)])],
        )

        repo.delete_dataset(dataset.id or 0)

        assert repo.list_datasets() == []
        assert repo.list_sessions() == []
        assert repo.conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0] == 0
        assert repo.conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0] == 0
        assert repo.conn.execute("SELECT COUNT(*) FROM order_lines").fetchone()[0] == 0
        assert repo.conn.execute("SELECT COUNT(*) FROM drawings").fetchone()[0] == 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_save_session_persists_drawings_by_session() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        first = repo.create_session(dataset.id or 0, start_index=1)
        second = repo.create_session(dataset.id or 0, start_index=2)

        first_drawings = [
            ChartDrawing(
                tool_type=DrawingToolType.PARALLEL_CHANNEL,
                anchors=[DrawingAnchor(1.0, 100.0), DrawingAnchor(4.0, 103.0), DrawingAnchor(2.0, 98.0)],
            ),
            ChartDrawing(
                tool_type=DrawingToolType.RECTANGLE,
                anchors=[DrawingAnchor(5.0, 99.0), DrawingAnchor(8.0, 110.0)],
            ),
        ]
        second_drawings = [
            ChartDrawing(
                tool_type=DrawingToolType.HORIZONTAL_LINE,
                anchors=[DrawingAnchor(3.0, 105.0)],
            )
        ]

        repo.save_session(first, [], [], first_drawings)
        repo.save_session(second, [], [], second_drawings)

        loaded_first = repo.get_drawings(first.id or 0)
        loaded_second = repo.get_drawings(second.id or 0)

        assert [drawing.tool_type for drawing in loaded_first] == [
            DrawingToolType.PARALLEL_CHANNEL,
            DrawingToolType.RECTANGLE,
        ]
        assert len(loaded_first[0].anchors) == 3
        assert loaded_first[1].anchors[1].y == 110.0
        assert [drawing.tool_type for drawing in loaded_second] == [DrawingToolType.HORIZONTAL_LINE]
        assert len(loaded_second[0].anchors) == 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_touch_session_opened_updates_recently_opened_order_without_saving() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        first = repo.create_session(dataset.id or 0, start_index=1, title="先打开的案例")
        second = repo.create_session(dataset.id or 0, start_index=2, title="后打开的案例")

        repo.conn.execute(
            "UPDATE sessions SET last_opened_at = '2025-01-01 00:00:00' WHERE id IN (?, ?)",
            (first.id, second.id),
        )
        repo.conn.commit()
        repo.touch_session_opened(first.id or 0)

        recent = repo.list_recently_opened_sessions()

        assert recent[0].id == first.id
        assert recent[1].id == second.id
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_list_sessions_query_matches_title_symbol_and_tags() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset_if = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        dataset_ag = repo.import_csv(Path("sample_data/if_sample.csv"), "AG9999", "1m")

        breakout = repo.create_session(dataset_if.id or 0, start_index=1, title="螺纹突破复盘")
        balance = repo.create_session(dataset_ag.id or 0, start_index=2, title="白银震荡观察")

        breakout.tags = ["breakout", "morning"]
        breakout.status = SessionStatus.COMPLETED
        balance.tags = ["range", "afternoon"]
        repo.save_session(breakout, [], [])
        repo.save_session(balance, [], [])

        assert [session.id for session in repo.list_sessions(query="突破")] == [breakout.id]
        assert [session.id for session in repo.list_sessions(query="ag99")] == [balance.id]
        assert [session.id for session in repo.list_sessions(query="MORNING")] == [breakout.id]
        assert [session.id for session in repo.list_sessions(query="突破", status=breakout.status)] == [breakout.id]
        assert {session.id for session in repo.list_sessions(query="")} == {breakout.id, balance.id}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_save_session_persists_drawing_style_presets() -> None:
    temp_dir = Path(".test_tmp") / f"repo-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        db_path = temp_dir / "barbybar.db"
        repo = Repository(db_path)
        dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
        session = repo.create_session(dataset.id or 0, start_index=1)
        session.drawing_style_presets = {
            DrawingToolType.TREND_LINE.value: {"color": "#3366ff", "width": 3, "line_style": "dash"},
            DrawingToolType.TEXT.value: {"text": "", "font_size": 18, "text_color": "#3366ff", "color": "#3366ff"},
        }

        repo.save_session(session, [], [])
        loaded = repo.get_session(session.id or 0)

        assert loaded.drawing_style_presets[DrawingToolType.TREND_LINE.value]["color"] == "#3366ff"
        assert loaded.drawing_style_presets[DrawingToolType.TREND_LINE.value]["width"] == 3
        assert loaded.drawing_style_presets[DrawingToolType.TEXT.value]["text"] == ""
        assert loaded.drawing_style_presets[DrawingToolType.TEXT.value]["font_size"] == 18
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
