from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from sqlite3 import Connection

from loguru import logger

from barbybar.data.csv_importer import load_bars_from_csv
from barbybar.data.tick_size import default_tick_size_for_symbol
from barbybar.data.timeframe import (
    aggregate_bars,
    default_chart_timeframe,
    find_timestamp_window,
    normalize_timeframe,
    supported_replay_timeframes,
    timeframe_to_minutes,
)
from barbybar.domain.models import (
    ActionType,
    Bar,
    ChartDrawing,
    DataSet,
    DrawingAnchor,
    DrawingToolType,
    normalize_drawing_style,
    OrderLine,
    OrderLineType,
    OrderStatus,
    OrderTriggerMode,
    PositionState,
    ReviewSession,
    SessionAction,
    SessionStats,
    SessionStatus,
    WindowBars,
)
from barbybar.storage.database import connect


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(slots=True)
class _WindowMeta:
    timestamp: datetime
    source_start_offset: int
    source_end_offset: int


class Repository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else None
        self.conn: Connection = connect(db_path)
        self._window_meta_cache: dict[tuple[int, str], list[_WindowMeta]] = {}

    def import_csv(
        self,
        path: str | Path,
        symbol: str,
        timeframe: str,
        field_map: dict[str, str] | None = None,
        *,
        display_name: str | None = None,
    ) -> DataSet:
        timeframe = normalize_timeframe(timeframe)
        result = load_bars_from_csv(path, field_map=field_map)
        bars = result.bars
        resolved_display_name = (display_name or Path(path).name).strip() or Path(path).name
        cursor = self.conn.execute(
            """
            INSERT INTO datasets(display_name, symbol, timeframe, source_path, total_bars, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_display_name,
                symbol,
                timeframe,
                str(path),
                len(bars),
                self._resolve_open_timestamp(bars[0], timeframe).isoformat(),
                bars[-1].close_timestamp.isoformat(),
            ),
        )
        dataset_id = int(cursor.lastrowid)
        self.conn.executemany(
            """
            INSERT INTO bars(dataset_id, open_ts, close_ts, ts, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    dataset_id,
                    self._resolve_open_timestamp(bar, timeframe).isoformat(),
                    bar.close_timestamp.isoformat(),
                    bar.close_timestamp.isoformat(),
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    bar.volume,
                )
                for bar in bars
            ],
        )
        self.conn.commit()
        return self.get_dataset(dataset_id)

    def find_dataset_by_symbol(self, symbol: str) -> DataSet | None:
        row = self.conn.execute(
            "SELECT * FROM datasets WHERE UPPER(symbol) = UPPER(?) ORDER BY created_at DESC, id DESC LIMIT 1",
            (symbol,),
        ).fetchone()
        if row is None:
            return None
        return self._dataset_from_row(row)

    def find_dataset_by_display_name(self, display_name: str) -> DataSet | None:
        row = self.conn.execute(
            "SELECT * FROM datasets WHERE display_name = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (display_name,),
        ).fetchone()
        if row is None:
            return None
        return self._dataset_from_row(row)

    def list_datasets(self) -> list[DataSet]:
        rows = self.conn.execute("SELECT * FROM datasets ORDER BY created_at DESC, id DESC").fetchall()
        return [self._dataset_from_row(row) for row in rows]

    def delete_dataset(self, dataset_id: int) -> None:
        self.get_dataset(dataset_id)
        self.conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
        self.conn.commit()
        self._window_meta_cache = {
            key: value for key, value in self._window_meta_cache.items() if key[0] != dataset_id
        }

    def get_dataset(self, dataset_id: int) -> DataSet:
        row = self.conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown dataset id: {dataset_id}")
        return self._dataset_from_row(row)

    def get_bars(self, dataset_id: int) -> list[Bar]:
        dataset = self.get_dataset(dataset_id)
        rows = self.conn.execute(
            "SELECT open_ts, close_ts, ts, open, high, low, close, volume FROM bars WHERE dataset_id = ? ORDER BY close_ts",
            (dataset_id,),
        ).fetchall()
        return [
            Bar(
                timestamp=datetime.fromisoformat(row["close_ts"] or row["ts"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                open_timestamp=self._row_open_timestamp(row, dataset.timeframe),
            )
            for row in rows
        ]

    def get_bars_window(self, dataset_id: int, start_index: int, count: int) -> list[Bar]:
        if count <= 0:
            return []
        dataset = self.get_dataset(dataset_id)
        rows = self.conn.execute(
            """
            SELECT open_ts, close_ts, ts, open, high, low, close, volume
            FROM bars
            WHERE dataset_id = ?
            ORDER BY close_ts
            LIMIT ? OFFSET ?
            """,
            (dataset_id, count, max(start_index, 0)),
        ).fetchall()
        return [
            Bar(
                timestamp=datetime.fromisoformat(row["close_ts"] or row["ts"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                open_timestamp=self._row_open_timestamp(row, dataset.timeframe),
            )
            for row in rows
        ]

    def get_chart_window(
        self,
        session_id: int,
        timeframe: str,
        anchor_time: datetime | None,
        before_count: int,
        after_count: int,
    ) -> WindowBars:
        session = self.get_session(session_id)
        dataset = self.get_dataset(session.dataset_id)
        normalized = normalize_timeframe(timeframe)
        meta = self._get_window_meta(dataset.id or 0, dataset.timeframe, normalized)
        total_count = len(meta)
        if not meta:
            return WindowBars([], 0, -1, 0, 0)
        start, end, anchor_index = find_timestamp_window(
            [item.timestamp for item in meta],
            anchor_time,
            before_count,
            after_count,
        )
        source_start = meta[start].source_start_offset
        source_end = meta[end].source_end_offset
        source_bars = self.get_bars_window(dataset.id or 0, source_start, source_end - source_start + 1)
        bars = self._materialize_window_bars(meta[start : end + 1], source_start, source_bars)
        return WindowBars(
            bars=bars,
            global_start_index=start,
            global_end_index=end,
            anchor_global_index=anchor_index,
            total_count=total_count,
        )

    def get_replay_bars(self, dataset_id: int, replay_timeframe: str) -> list[Bar]:
        dataset = self.get_dataset(dataset_id)
        replay_timeframe = normalize_timeframe(replay_timeframe)
        if replay_timeframe == normalize_timeframe(dataset.timeframe):
            return self.get_bars(dataset_id)
        if replay_timeframe not in supported_replay_timeframes(dataset.timeframe):
            raise ValueError(f"{dataset.timeframe} cannot be replayed as {replay_timeframe}.")
        return aggregate_bars(self.get_bars(dataset_id), dataset.timeframe, replay_timeframe)

    def create_session(self, dataset_id: int, start_index: int, title: str | None = None) -> ReviewSession:
        dataset = self.get_dataset(dataset_id)
        chart_timeframe = default_chart_timeframe(dataset.timeframe)
        tick_size = default_tick_size_for_symbol(dataset.symbol)
        source_bars = self.get_bars(dataset_id)
        current_bar_time = source_bars[start_index].timestamp if source_bars else dataset.start_time
        session_title = title or f"{dataset.symbol} {dataset.timeframe} {dataset.start_time:%Y-%m-%d %H:%M}"
        cursor = self.conn.execute(
            """
            INSERT INTO sessions(
                dataset_id, symbol, timeframe, replay_timeframe, chart_timeframe, title,
                start_index, current_index, current_bar_time, tick_size, status, last_opened_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                dataset_id,
                dataset.symbol,
                dataset.timeframe,
                chart_timeframe,
                chart_timeframe,
                session_title,
                start_index,
                start_index,
                current_bar_time.isoformat(),
                tick_size,
                SessionStatus.ACTIVE.value,
            ),
        )
        self.conn.commit()
        return self.get_session(int(cursor.lastrowid))

    def touch_session_opened(self, session_id: int) -> None:
        self.get_session(session_id)
        self.conn.execute(
            """
            UPDATE sessions
            SET last_opened_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (session_id,),
        )
        self.conn.commit()

    def save_session(
        self,
        session: ReviewSession,
        actions: list[SessionAction],
        order_lines: list[OrderLine] | None = None,
        drawings: list[ChartDrawing] | None = None,
    ) -> ReviewSession:
        if session.id is None:
            raise ValueError("Session must have an id before it can be saved.")
        self.conn.execute(
            """
            UPDATE sessions
            SET current_index = ?, chart_timeframe = ?, current_bar_time = ?, tick_size = ?, status = ?, notes = ?, tags_json = ?, drawing_style_presets_json = ?, position_json = ?, stats_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                session.current_index,
                session.chart_timeframe,
                session.current_bar_time.isoformat() if session.current_bar_time else None,
                session.tick_size,
                session.status.value,
                session.notes,
                json.dumps(session.tags, ensure_ascii=False),
                json.dumps(session.drawing_style_presets, ensure_ascii=False),
                json.dumps(session.position.to_dict(), ensure_ascii=False),
                json.dumps(session.stats.to_dict(), ensure_ascii=False),
                session.id,
            ),
        )
        self.conn.execute("DELETE FROM actions WHERE session_id = ?", (session.id,))
        self.conn.executemany(
            """
            INSERT INTO actions(session_id, action_type, bar_index, ts, price, quantity, note, extra_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    session.id,
                    action.action_type.value,
                    action.bar_index,
                    action.timestamp.isoformat(),
                    action.price,
                    action.quantity,
                    action.note,
                    json.dumps(action.extra, ensure_ascii=False),
                )
                for action in actions
            ],
        )
        if order_lines is not None:
            persisted_lines = [line for line in order_lines if line.order_type is not OrderLineType.AVERAGE_PRICE]
            incoming_ids = {line.id for line in persisted_lines if line.id is not None}
            existing_ids = {
                row["id"]
                for row in self.conn.execute("SELECT id FROM order_lines WHERE session_id = ?", (session.id,)).fetchall()
            }
            stale_ids = existing_ids - incoming_ids
            if stale_ids:
                self.conn.executemany("DELETE FROM order_lines WHERE id = ?", [(order_id,) for order_id in stale_ids])

            for order_line in persisted_lines:
                if order_line.id is None:
                    cursor = self.conn.execute(
                        """
                        INSERT INTO order_lines(
                            session_id, order_type, price, quantity, trigger_mode, reference_price_at_creation, status, created_bar_index, created_at,
                            active_from_bar_index, triggered_bar_index, triggered_at, note
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session.id,
                            order_line.order_type.value,
                            order_line.price,
                            order_line.quantity,
                            order_line.trigger_mode.value,
                            order_line.reference_price_at_creation,
                            order_line.status.value,
                            order_line.created_bar_index,
                            order_line.created_at.isoformat(),
                            order_line.active_from_bar_index,
                            order_line.triggered_bar_index,
                            order_line.triggered_at.isoformat() if order_line.triggered_at else None,
                            order_line.note,
                        ),
                    )
                    order_line.id = int(cursor.lastrowid)
                    order_line.session_id = session.id
                    continue
                self.conn.execute(
                    """
                    UPDATE order_lines
                    SET order_type = ?, price = ?, quantity = ?, trigger_mode = ?, reference_price_at_creation = ?, status = ?, created_bar_index = ?, created_at = ?,
                        active_from_bar_index = ?, triggered_bar_index = ?, triggered_at = ?, note = ?
                    WHERE id = ? AND session_id = ?
                    """,
                    (
                        order_line.order_type.value,
                        order_line.price,
                        order_line.quantity,
                        order_line.trigger_mode.value,
                        order_line.reference_price_at_creation,
                        order_line.status.value,
                        order_line.created_bar_index,
                        order_line.created_at.isoformat(),
                        order_line.active_from_bar_index,
                        order_line.triggered_bar_index,
                        order_line.triggered_at.isoformat() if order_line.triggered_at else None,
                        order_line.note,
                        order_line.id,
                        session.id,
                    ),
                )
        if drawings is not None:
            drawing_timeframe = normalize_timeframe(session.chart_timeframe)
            incoming_ids = {drawing.id for drawing in drawings if drawing.id is not None}
            existing_ids = {
                row["id"]
                for row in self.conn.execute(
                    "SELECT id FROM drawings WHERE session_id = ? AND chart_timeframe = ?",
                    (session.id, drawing_timeframe),
                ).fetchall()
            }
            stale_ids = existing_ids - incoming_ids
            if stale_ids:
                self.conn.executemany("DELETE FROM drawings WHERE id = ?", [(drawing_id,) for drawing_id in stale_ids])

            for drawing in drawings:
                anchors_json = json.dumps([anchor.to_dict() for anchor in drawing.anchors], ensure_ascii=False)
                style_json = json.dumps(drawing.style, ensure_ascii=False)
                if drawing.id is None:
                    cursor = self.conn.execute(
                        """
                        INSERT INTO drawings(session_id, chart_timeframe, tool_type, anchors_json, style_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (session.id, drawing_timeframe, drawing.tool_type.value, anchors_json, style_json),
                    )
                    drawing.id = int(cursor.lastrowid)
                    drawing.session_id = session.id
                    continue
                self.conn.execute(
                    """
                    UPDATE drawings
                    SET chart_timeframe = ?, tool_type = ?, anchors_json = ?, style_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND session_id = ? AND chart_timeframe = ?
                    """,
                    (drawing_timeframe, drawing.tool_type.value, anchors_json, style_json, drawing.id, session.id, drawing_timeframe),
                )
        self.conn.commit()
        return self.get_session(session.id)

    def get_session(self, session_id: int) -> ReviewSession:
        row = self.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown session id: {session_id}")
        return self._session_from_row(row)

    def get_session_bars(self, session_id: int) -> list[Bar]:
        session = self.get_session(session_id)
        return self.get_chart_bars(session_id, session.chart_timeframe)

    def get_chart_bars(self, session_id: int, timeframe: str) -> list[Bar]:
        session = self.get_session(session_id)
        return self.get_replay_bars(session.dataset_id, timeframe)

    def get_chart_bar_time(self, session_id: int, timeframe: str, global_index: int) -> datetime:
        session = self.get_session(session_id)
        dataset = self.get_dataset(session.dataset_id)
        meta = self._get_window_meta(dataset.id or 0, dataset.timeframe, timeframe)
        if not meta:
            raise ValueError("当前数据不足以生成目标周期 K 线。")
        index = max(0, min(global_index, len(meta) - 1))
        return meta[index].timestamp

    def list_sessions(
        self,
        *,
        symbol: str = "",
        tag: str = "",
        status: SessionStatus | None = None,
        direction: str = "",
        query: str = "",
    ) -> list[ReviewSession]:
        sql = "SELECT * FROM sessions WHERE 1 = 1"
        params: list[object] = []
        if symbol:
            sql += " AND symbol = ?"
            params.append(symbol)
        if status:
            sql += " AND status = ?"
            params.append(status.value)
        if tag:
            sql += " AND tags_json LIKE ?"
            params.append(f"%{tag}%")
        if query:
            search = f"%{query.strip().lower()}%"
            sql += " AND (LOWER(title) LIKE ? OR LOWER(symbol) LIKE ? OR LOWER(tags_json) LIKE ?)"
            params.extend([search, search, search])
        rows = self.conn.execute(sql + " ORDER BY updated_at DESC, id DESC", params).fetchall()
        sessions = [self._session_from_row(row) for row in rows]
        if direction:
            sessions = [session for session in sessions if session.position.direction == direction]
        return sessions

    def list_recently_opened_sessions(self) -> list[ReviewSession]:
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY last_opened_at DESC, id DESC"
        ).fetchall()
        return [self._session_from_row(row) for row in rows]

    def delete_session(self, session_id: int) -> None:
        self.get_session(session_id)
        self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.conn.commit()

    def get_session_actions(self, session_id: int) -> list[SessionAction]:
        rows = self.conn.execute("SELECT * FROM actions WHERE session_id = ? ORDER BY id", (session_id,)).fetchall()
        return [
            SessionAction(
                id=row["id"],
                session_id=row["session_id"],
                action_type=ActionType(row["action_type"]),
                bar_index=row["bar_index"],
                timestamp=datetime.fromisoformat(row["ts"]),
                price=row["price"],
                quantity=row["quantity"],
                note=row["note"],
                extra=json.loads(row["extra_json"]),
            )
            for row in rows
        ]

    def get_order_lines(self, session_id: int) -> list[OrderLine]:
        rows = self.conn.execute("SELECT * FROM order_lines WHERE session_id = ? ORDER BY id", (session_id,)).fetchall()
        return [
            OrderLine(
                id=row["id"],
                session_id=row["session_id"],
                order_type=OrderLineType(row["order_type"]),
                price=row["price"],
                quantity=row["quantity"],
                trigger_mode=OrderTriggerMode(row["trigger_mode"]) if "trigger_mode" in row.keys() and row["trigger_mode"] else OrderTriggerMode.TOUCH,
                reference_price_at_creation=row["reference_price_at_creation"] if "reference_price_at_creation" in row.keys() else None,
                status=OrderStatus(row["status"]),
                created_bar_index=row["created_bar_index"],
                active_from_bar_index=row["active_from_bar_index"] if "active_from_bar_index" in row.keys() else row["created_bar_index"] + 1,
                created_at=datetime.fromisoformat(row["created_at"]),
                triggered_bar_index=row["triggered_bar_index"],
                triggered_at=_dt(row["triggered_at"]),
                note=row["note"],
            )
            for row in rows
        ]

    def get_drawings(self, session_id: int, chart_timeframe: str) -> list[ChartDrawing]:
        normalized_timeframe = normalize_timeframe(chart_timeframe)
        rows = self.conn.execute(
            """
            SELECT *
            FROM drawings
            WHERE session_id = ?
              AND (chart_timeframe = ? OR chart_timeframe = '1m')
            ORDER BY id
            """,
            (session_id, normalized_timeframe),
        ).fetchall()
        drawings: list[ChartDrawing] = []
        for row in rows:
            try:
                tool_type = DrawingToolType(row["tool_type"])
                anchors = [DrawingAnchor.from_dict(item) for item in json.loads(row["anchors_json"])]
                style = normalize_drawing_style(tool_type, json.loads(row["style_json"]))
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                logger.bind(
                    component="session_repository",
                    session_id=session_id,
                    drawing_id=row["id"],
                    tool_type=row["tool_type"],
                ).warning("event=skip_invalid_drawing error={}", str(exc))
                continue
            drawings.append(
                ChartDrawing(
                    id=row["id"],
                    session_id=row["session_id"],
                    tool_type=tool_type,
                    anchors=anchors,
                    style=style,
                )
            )
        return drawings

    def _dataset_from_row(self, row) -> DataSet:
        return DataSet(
            id=row["id"],
            display_name=(row["display_name"] or row["symbol"]).strip(),
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            source_path=row["source_path"],
            total_bars=row["total_bars"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]),
            created_at=_dt(row["created_at"]),
        )

    def _session_from_row(self, row) -> ReviewSession:
        supported = set(supported_replay_timeframes(row["timeframe"]))
        persisted_timeframe = row["chart_timeframe"] or row["replay_timeframe"] or row["timeframe"]
        chart_timeframe = normalize_timeframe(persisted_timeframe)
        if chart_timeframe not in supported:
            chart_timeframe = default_chart_timeframe(row["timeframe"])
            logger.bind(
                component="session_repository",
                session_id=row["id"],
                dataset_id=row["dataset_id"],
                persisted_timeframe=persisted_timeframe,
                fallback_timeframe=chart_timeframe,
            ).warning("event=deprecated_chart_timeframe_fallback")
        return ReviewSession(
            id=row["id"],
            dataset_id=row["dataset_id"],
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            chart_timeframe=chart_timeframe,
            title=row["title"],
            start_index=row["start_index"],
            current_index=row["current_index"],
            current_bar_time=_dt(row["current_bar_time"]),
            tick_size=float(row["tick_size"]) if "tick_size" in row.keys() else default_tick_size_for_symbol(row["symbol"]),
            status=SessionStatus(row["status"]),
            notes=row["notes"],
            tags=json.loads(row["tags_json"]),
            drawing_style_presets=json.loads(row["drawing_style_presets_json"]) if "drawing_style_presets_json" in row.keys() else {},
            position=PositionState.from_dict(json.loads(row["position_json"])),
            stats=SessionStats.from_dict(json.loads(row["stats_json"])),
            created_at=_dt(row["created_at"]),
            last_opened_at=_dt(row["last_opened_at"]) if "last_opened_at" in row.keys() else _dt(row["updated_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    def _get_window_meta(self, dataset_id: int, source_timeframe: str, target_timeframe: str) -> list[_WindowMeta]:
        normalized = normalize_timeframe(target_timeframe)
        key = (dataset_id, normalized)
        cached = self._window_meta_cache.get(key)
        if cached is not None:
            return cached
        source = normalize_timeframe(source_timeframe)
        timestamps = [
            datetime.fromisoformat(row["ts"])
            for row in self.conn.execute("SELECT ts FROM bars WHERE dataset_id = ? ORDER BY ts", (dataset_id,)).fetchall()
        ]
        if normalized == source:
            meta = [_WindowMeta(timestamp=ts, source_start_offset=index, source_end_offset=index) for index, ts in enumerate(timestamps)]
            self._window_meta_cache[key] = meta
            return meta
        if normalized == "1d":
            bars = self.get_bars(dataset_id)
            aggregated = aggregate_bars(bars, source, normalized)
            meta: list[_WindowMeta] = []
            source_index = 0
            for aggregated_bar in aggregated:
                bucket_start = source_index
                while source_index < len(bars) and bars[source_index].timestamp <= aggregated_bar.timestamp:
                    source_index += 1
                bucket_end = max(bucket_start, source_index - 1)
                meta.append(
                    _WindowMeta(
                        timestamp=aggregated_bar.timestamp,
                        source_start_offset=bucket_start,
                        source_end_offset=bucket_end,
                    )
                )
            self._window_meta_cache[key] = meta
            return meta
        factor = timeframe_to_minutes(normalized) // timeframe_to_minutes(source)
        expected_step_seconds = timeframe_to_minutes(source) * 60
        meta: list[_WindowMeta] = []
        bucket_start: int | None = None
        bucket_count = 0
        previous: datetime | None = None
        for offset, ts in enumerate(timestamps):
            if previous is not None and (ts - previous).total_seconds() != expected_step_seconds:
                bucket_start = None
                bucket_count = 0
            if bucket_start is None:
                bucket_start = offset
                bucket_count = 0
            bucket_count += 1
            previous = ts
            if bucket_count == factor:
                meta.append(_WindowMeta(timestamp=ts, source_start_offset=bucket_start, source_end_offset=offset))
                bucket_start = None
                bucket_count = 0
        self._window_meta_cache[key] = meta
        return meta

    def _materialize_window_bars(self, meta: list[_WindowMeta], source_start: int, source_bars: list[Bar]) -> list[Bar]:
        if not meta:
            return []
        result: list[Bar] = []
        for item in meta:
            start = item.source_start_offset - source_start
            end = item.source_end_offset - source_start + 1
            bucket = source_bars[start:end]
            result.append(
                Bar(
                    timestamp=item.timestamp,
                    open=bucket[0].open,
                    high=max(bar.high for bar in bucket),
                    low=min(bar.low for bar in bucket),
                    close=bucket[-1].close,
                    volume=sum(bar.volume for bar in bucket),
                    open_timestamp=bucket[0].open_timestamp,
                )
            )
        return result

    @staticmethod
    def _resolve_open_timestamp(bar: Bar, timeframe: str) -> datetime:
        if bar.open_timestamp is not None:
            return bar.open_timestamp
        return bar.close_timestamp - timedelta(minutes=max(timeframe_to_minutes(timeframe), 1))

    @staticmethod
    def _row_open_timestamp(row, timeframe: str) -> datetime:
        open_ts = row["open_ts"]
        if open_ts:
            return datetime.fromisoformat(open_ts)
        close_ts = datetime.fromisoformat(row["close_ts"] or row["ts"])
        return close_ts - timedelta(minutes=max(timeframe_to_minutes(timeframe), 1))
