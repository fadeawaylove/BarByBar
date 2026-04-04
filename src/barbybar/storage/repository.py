from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from sqlite3 import Connection

from barbybar.data.csv_importer import load_bars_from_csv
from barbybar.domain.models import ActionType, Bar, DataSet, PositionState, ReviewSession, SessionAction, SessionStats, SessionStatus
from barbybar.storage.database import connect


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class Repository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.conn: Connection = connect(db_path)

    def import_csv(self, path: str | Path, symbol: str, timeframe: str, field_map: dict[str, str] | None = None) -> DataSet:
        result = load_bars_from_csv(path, field_map=field_map)
        bars = result.bars
        cursor = self.conn.execute(
            """
            INSERT INTO datasets(symbol, timeframe, source_path, total_bars, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (symbol, timeframe, str(path), len(bars), bars[0].timestamp.isoformat(), bars[-1].timestamp.isoformat()),
        )
        dataset_id = int(cursor.lastrowid)
        self.conn.executemany(
            """
            INSERT INTO bars(dataset_id, ts, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (dataset_id, bar.timestamp.isoformat(), bar.open, bar.high, bar.low, bar.close, bar.volume)
                for bar in bars
            ],
        )
        self.conn.commit()
        return self.get_dataset(dataset_id)

    def list_datasets(self) -> list[DataSet]:
        rows = self.conn.execute("SELECT * FROM datasets ORDER BY created_at DESC, id DESC").fetchall()
        return [self._dataset_from_row(row) for row in rows]

    def get_dataset(self, dataset_id: int) -> DataSet:
        row = self.conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown dataset id: {dataset_id}")
        return self._dataset_from_row(row)

    def get_bars(self, dataset_id: int) -> list[Bar]:
        rows = self.conn.execute(
            "SELECT ts, open, high, low, close, volume FROM bars WHERE dataset_id = ? ORDER BY ts",
            (dataset_id,),
        ).fetchall()
        return [
            Bar(
                timestamp=datetime.fromisoformat(row["ts"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for row in rows
        ]

    def create_session(self, dataset_id: int, start_index: int, title: str | None = None) -> ReviewSession:
        dataset = self.get_dataset(dataset_id)
        session_title = title or f"{dataset.symbol} {dataset.timeframe} {dataset.start_time:%Y-%m-%d %H:%M}"
        cursor = self.conn.execute(
            """
            INSERT INTO sessions(dataset_id, symbol, timeframe, title, start_index, current_index, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (dataset_id, dataset.symbol, dataset.timeframe, session_title, start_index, start_index, SessionStatus.ACTIVE.value),
        )
        self.conn.commit()
        return self.get_session(int(cursor.lastrowid))

    def save_session(self, session: ReviewSession, actions: list[SessionAction]) -> ReviewSession:
        if session.id is None:
            raise ValueError("Session must have an id before it can be saved.")
        self.conn.execute(
            """
            UPDATE sessions
            SET current_index = ?, status = ?, notes = ?, tags_json = ?, position_json = ?, stats_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                session.current_index,
                session.status.value,
                session.notes,
                json.dumps(session.tags, ensure_ascii=False),
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
        self.conn.commit()
        return self.get_session(session.id)

    def get_session(self, session_id: int) -> ReviewSession:
        row = self.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown session id: {session_id}")
        return self._session_from_row(row)

    def list_sessions(self, *, symbol: str = "", tag: str = "", status: SessionStatus | None = None, direction: str = "") -> list[ReviewSession]:
        query = "SELECT * FROM sessions WHERE 1 = 1"
        params: list[object] = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if status:
            query += " AND status = ?"
            params.append(status.value)
        if tag:
            query += " AND tags_json LIKE ?"
            params.append(f"%{tag}%")
        rows = self.conn.execute(query + " ORDER BY updated_at DESC, id DESC", params).fetchall()
        sessions = [self._session_from_row(row) for row in rows]
        if direction:
            sessions = [session for session in sessions if session.position.direction == direction]
        return sessions

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

    def _dataset_from_row(self, row) -> DataSet:
        return DataSet(
            id=row["id"],
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            source_path=row["source_path"],
            total_bars=row["total_bars"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]),
            created_at=_dt(row["created_at"]),
        )

    def _session_from_row(self, row) -> ReviewSession:
        return ReviewSession(
            id=row["id"],
            dataset_id=row["dataset_id"],
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            title=row["title"],
            start_index=row["start_index"],
            current_index=row["current_index"],
            status=SessionStatus(row["status"]),
            notes=row["notes"],
            tags=json.loads(row["tags_json"]),
            position=PositionState.from_dict(json.loads(row["position_json"])),
            stats=SessionStats.from_dict(json.loads(row["stats_json"])),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )
