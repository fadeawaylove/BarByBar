from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from barbybar.domain.models import DataSet, ReviewSession, TradeEntryLeg, TradeReviewItem


TRADE_EXPORT_SCHEMA_VERSION = "1.0"
CSV_EXPORT_FIELDS = (
    "schema_version",
    "case_id",
    "dataset_id",
    "dataset_name",
    "title",
    "symbol",
    "source_timeframe",
    "chart_timeframe",
    "status",
    "dataset_start_time",
    "dataset_end_time",
    "start_bar_index",
    "current_bar_index",
    "current_bar_time",
    "created_at",
    "updated_at",
    "session_notes",
    "tags",
    "total_trades",
    "wins",
    "losses",
    "win_rate",
    "total_pnl",
    "average_pnl",
    "profit_factor",
    "max_drawdown",
    "expectancy",
    "long_trades",
    "short_trades",
    "average_holding_bars",
    "trade_number",
    "direction",
    "entry_time",
    "exit_time",
    "quantity",
    "entry_price",
    "exit_price",
    "pnl",
    "entry_bar_index",
    "exit_bar_index",
    "holding_bars",
    "exit_reason",
    "is_manual",
    "had_stop_protection",
    "had_adverse_add",
    "is_planned",
    "entry_note",
    "review_note",
    "entry_legs",
)


class TradeExportError(RuntimeError):
    """Raised when a stable trade export cannot be published."""


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value is not None else None


@dataclass(frozen=True, slots=True)
class SessionExportSummary:
    case_id: int
    dataset_id: int
    dataset_name: str
    title: str
    symbol: str
    source_timeframe: str
    chart_timeframe: str
    status: str
    dataset_start_time: datetime
    dataset_end_time: datetime
    start_bar_index: int
    current_bar_index: int
    current_bar_time: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    notes: str
    tags: tuple[str, ...]
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    average_pnl: float
    profit_factor: float
    max_drawdown: float
    expectancy: float
    long_trades: int
    short_trades: int
    average_holding_bars: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            "title": self.title,
            "symbol": self.symbol,
            "source_timeframe": self.source_timeframe,
            "chart_timeframe": self.chart_timeframe,
            "status": self.status,
            "dataset_start_time": _iso(self.dataset_start_time),
            "dataset_end_time": _iso(self.dataset_end_time),
            "start_bar_index": self.start_bar_index,
            "current_bar_index": self.current_bar_index,
            "current_bar_time": _iso(self.current_bar_time),
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
            "notes": self.notes,
            "tags": list(self.tags),
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "average_pnl": self.average_pnl,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "expectancy": self.expectancy,
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
            "average_holding_bars": self.average_holding_bars,
        }


@dataclass(frozen=True, slots=True)
class TradeEntryLegExport:
    leg_number: int
    bar_index: int
    timestamp: datetime
    price: float
    quantity: float
    action_index: int | None
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "leg_number": self.leg_number,
            "bar_index": self.bar_index,
            "timestamp": _iso(self.timestamp),
            "price": self.price,
            "quantity": self.quantity,
            "action_index": self.action_index,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class TradeExportRecord:
    case_id: int
    trade_number: int
    direction: str
    entry_time: datetime
    exit_time: datetime
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    entry_bar_index: int
    exit_bar_index: int
    holding_bars: int
    exit_reason: str
    is_manual: bool
    had_stop_protection: bool
    had_adverse_add: bool
    is_planned: bool
    entry_note: str
    review_note: str
    entry_legs: tuple[TradeEntryLegExport, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "trade_number": self.trade_number,
            "direction": self.direction,
            "entry_time": _iso(self.entry_time),
            "exit_time": _iso(self.exit_time),
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "entry_bar_index": self.entry_bar_index,
            "exit_bar_index": self.exit_bar_index,
            "holding_bars": self.holding_bars,
            "exit_reason": self.exit_reason,
            "is_manual": self.is_manual,
            "had_stop_protection": self.had_stop_protection,
            "had_adverse_add": self.had_adverse_add,
            "is_planned": self.is_planned,
            "entry_note": self.entry_note,
            "review_note": self.review_note,
            "entry_legs": [leg.to_dict() for leg in self.entry_legs],
        }


@dataclass(frozen=True, slots=True)
class SessionTradeExport:
    schema_version: str
    session: SessionExportSummary
    trades: tuple[TradeExportRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session": self.session.to_dict(),
            "trades": [trade.to_dict() for trade in self.trades],
        }


@dataclass(frozen=True, slots=True)
class TradeExportFileResult:
    path: Path
    format: str
    case_id: int
    trade_count: int
    size_bytes: int


def _entry_leg_export(leg: TradeEntryLeg, leg_number: int) -> TradeEntryLegExport:
    return TradeEntryLegExport(
        leg_number=leg_number,
        bar_index=leg.bar_index,
        timestamp=leg.timestamp,
        price=leg.price,
        quantity=leg.quantity,
        action_index=leg.action_index,
        note=leg.note,
    )


def build_session_trade_export(
    session: ReviewSession,
    dataset: DataSet,
    trades: list[TradeReviewItem],
) -> SessionTradeExport:
    if session.id is None:
        raise ValueError("A persisted case id is required for export.")
    if dataset.id is None:
        raise ValueError("A persisted dataset id is required for export.")
    if session.dataset_id != dataset.id:
        raise ValueError("The export dataset does not belong to the selected case.")

    summary = SessionExportSummary(
        case_id=session.id,
        dataset_id=dataset.id,
        dataset_name=dataset.display_name,
        title=session.title,
        symbol=session.symbol,
        source_timeframe=dataset.timeframe,
        chart_timeframe=session.chart_timeframe,
        status=session.status.value,
        dataset_start_time=dataset.start_time,
        dataset_end_time=dataset.end_time,
        start_bar_index=session.start_index,
        current_bar_index=session.current_index,
        current_bar_time=session.current_bar_time,
        created_at=session.created_at,
        updated_at=session.updated_at,
        notes=session.notes,
        tags=tuple(session.tags),
        total_trades=session.stats.total_trades,
        wins=session.stats.wins,
        losses=session.stats.losses,
        win_rate=session.stats.win_rate,
        total_pnl=session.stats.total_pnl,
        average_pnl=session.stats.average_pnl,
        profit_factor=session.stats.profit_factor,
        max_drawdown=session.stats.max_drawdown,
        expectancy=session.stats.expectancy,
        long_trades=session.stats.long_trades,
        short_trades=session.stats.short_trades,
        average_holding_bars=session.stats.avg_holding_bars,
    )
    records = tuple(
        TradeExportRecord(
            case_id=session.id,
            trade_number=trade.trade_number,
            direction=trade.direction,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            quantity=trade.quantity,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            pnl=trade.pnl,
            entry_bar_index=trade.entry_bar_index,
            exit_bar_index=trade.exit_bar_index,
            holding_bars=trade.holding_bars,
            exit_reason=trade.exit_reason,
            is_manual=trade.is_manual,
            had_stop_protection=trade.had_stop_protection,
            had_adverse_add=trade.had_adverse_add,
            is_planned=trade.is_planned,
            entry_note=trade.entry_note,
            review_note=trade.review_note,
            entry_legs=tuple(
                _entry_leg_export(leg, leg_number)
                for leg_number, leg in enumerate(trade.entry_legs, start=1)
            ),
        )
        for trade in sorted(trades, key=lambda item: item.trade_number)
    )
    return SessionTradeExport(
        schema_version=TRADE_EXPORT_SCHEMA_VERSION,
        session=summary,
        trades=records,
    )


def _csv_value(value: Any) -> str | int:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".15g")
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def _csv_rows(export: SessionTradeExport) -> list[dict[str, str | int]]:
    session = export.session.to_dict()
    session_values: dict[str, Any] = {
        "schema_version": export.schema_version,
        **session,
        "session_notes": session["notes"],
    }
    session_values.pop("notes", None)
    trade_payloads = [trade.to_dict() for trade in export.trades] or [{}]
    return [
        {
            field: _csv_value(
                session_values[field]
                if field in session_values
                else trade.get(field)
            )
            for field in CSV_EXPORT_FIELDS
        }
        for trade in trade_payloads
    ]


def _json_bytes(export: SessionTradeExport) -> bytes:
    text = json.dumps(export.to_dict(), ensure_ascii=False, indent=2) + "\n"
    return text.encode("utf-8")


def _csv_bytes(export: SessionTradeExport) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_EXPORT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(_csv_rows(export))
    return stream.getvalue().encode("utf-8-sig")


def export_session_trade_data(
    export: SessionTradeExport,
    target_path: str | Path,
    *,
    format: str,
) -> TradeExportFileResult:
    normalized_format = format.strip().lower()
    if normalized_format not in {"csv", "json"}:
        raise TradeExportError(f"Unsupported trade export format: {format}")
    target = Path(target_path).expanduser().resolve()
    temporary: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / f".{target.name}.{uuid4().hex}.partial"
        payload = _csv_bytes(export) if normalized_format == "csv" else _json_bytes(export)
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
        return TradeExportFileResult(
            path=target,
            format=normalized_format,
            case_id=export.session.case_id,
            trade_count=len(export.trades),
            size_bytes=target.stat().st_size,
        )
    except TradeExportError:
        raise
    except Exception as exc:
        raise TradeExportError(f"Could not export case {export.session.case_id} to {target}: {exc}") from exc
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
