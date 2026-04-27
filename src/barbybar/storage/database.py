from __future__ import annotations

import sqlite3
from pathlib import Path

from barbybar.paths import default_db_path as resolve_default_db_path


def default_db_path() -> Path:
    return resolve_default_db_path()


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS datasets (
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

CREATE TABLE IF NOT EXISTS bars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL,
    open_ts TEXT NOT NULL,
    close_ts TEXT NOT NULL,
    ts TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    UNIQUE(dataset_id, ts)
);

CREATE TABLE IF NOT EXISTS sessions (
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
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    bar_index INTEGER NOT NULL,
    ts TEXT NOT NULL,
    price REAL,
    quantity REAL NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    extra_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS order_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    order_type TEXT NOT NULL,
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    trigger_mode TEXT NOT NULL DEFAULT 'touch',
    reference_price_at_creation REAL,
    status TEXT NOT NULL,
    created_bar_index INTEGER NOT NULL,
    active_from_bar_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    triggered_bar_index INTEGER,
    triggered_at TEXT,
    note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS drawings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    chart_timeframe TEXT NOT NULL DEFAULT '1m',
    tool_type TEXT NOT NULL,
    anchors_json TEXT NOT NULL DEFAULT '[]',
    style_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
"""


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else default_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    dataset_columns = {row["name"] for row in conn.execute("PRAGMA table_info(datasets)").fetchall()}
    if dataset_columns and "display_name" not in dataset_columns:
        conn.execute("ALTER TABLE datasets ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")
        conn.execute("UPDATE datasets SET display_name = symbol WHERE display_name = ''")
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
    if "replay_timeframe" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN replay_timeframe TEXT NOT NULL DEFAULT '1m'")
        conn.execute("UPDATE sessions SET replay_timeframe = timeframe WHERE replay_timeframe = '1m'")
    if "chart_timeframe" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN chart_timeframe TEXT NOT NULL DEFAULT '1m'")
        source_column = "replay_timeframe" if "replay_timeframe" in columns else "timeframe"
        conn.execute(f"UPDATE sessions SET chart_timeframe = {source_column}")
    if "current_bar_time" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN current_bar_time TEXT")
    if "tick_size" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN tick_size REAL NOT NULL DEFAULT 1.0")
    if "drawing_style_presets_json" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN drawing_style_presets_json TEXT NOT NULL DEFAULT '{}'")
    if "last_opened_at" not in columns:
        # SQLite does not allow adding a column with a non-constant default like CURRENT_TIMESTAMP.
        conn.execute("ALTER TABLE sessions ADD COLUMN last_opened_at TEXT")
        conn.execute("UPDATE sessions SET last_opened_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)")
    order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(order_lines)").fetchall()}
    if order_columns and "note" not in order_columns:
        conn.execute("ALTER TABLE order_lines ADD COLUMN note TEXT NOT NULL DEFAULT ''")
    if order_columns and "active_from_bar_index" not in order_columns:
        conn.execute("ALTER TABLE order_lines ADD COLUMN active_from_bar_index INTEGER NOT NULL DEFAULT 0")
        conn.execute("UPDATE order_lines SET active_from_bar_index = created_bar_index + 1 WHERE active_from_bar_index = 0")
    order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(order_lines)").fetchall()}
    if order_columns and "trigger_mode" not in order_columns:
        conn.execute("ALTER TABLE order_lines ADD COLUMN trigger_mode TEXT NOT NULL DEFAULT 'touch'")
    order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(order_lines)").fetchall()}
    if order_columns and "reference_price_at_creation" not in order_columns:
        conn.execute("ALTER TABLE order_lines ADD COLUMN reference_price_at_creation REAL")
    bar_columns = {row["name"] for row in conn.execute("PRAGMA table_info(bars)").fetchall()}
    if bar_columns and "open_ts" not in bar_columns:
        conn.execute("ALTER TABLE bars ADD COLUMN open_ts TEXT")
    bar_columns = {row["name"] for row in conn.execute("PRAGMA table_info(bars)").fetchall()}
    if bar_columns and "close_ts" not in bar_columns:
        conn.execute("ALTER TABLE bars ADD COLUMN close_ts TEXT")
    drawing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(drawings)").fetchall()}
    if not drawing_columns:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS drawings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                chart_timeframe TEXT NOT NULL DEFAULT '1m',
                tool_type TEXT NOT NULL,
                anchors_json TEXT NOT NULL DEFAULT '[]',
                style_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        drawing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(drawings)").fetchall()}
    if drawing_columns and "chart_timeframe" not in drawing_columns:
        conn.execute("ALTER TABLE drawings ADD COLUMN chart_timeframe TEXT NOT NULL DEFAULT '1m'")
        conn.execute(
            """
            UPDATE drawings
            SET chart_timeframe = COALESCE(
                (
                    SELECT sessions.chart_timeframe
                    FROM sessions
                    WHERE sessions.id = drawings.session_id
                ),
                '1m'
            )
            WHERE chart_timeframe = '1m'
            """
        )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_drawings_session_timeframe ON drawings(session_id, chart_timeframe)")
    conn.execute("UPDATE datasets SET display_name = symbol WHERE display_name = ''")
    conn.commit()
