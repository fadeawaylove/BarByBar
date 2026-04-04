from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ActionType(StrEnum):
    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    ADD = "add"
    REDUCE = "reduce"
    CLOSE = "close"
    SET_STOP_LOSS = "set_stop_loss"
    SET_TAKE_PROFIT = "set_take_profit"
    NOTE = "note"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass(slots=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True)
class DataSet:
    id: int | None
    symbol: str
    timeframe: str
    source_path: str
    total_bars: int
    start_time: datetime
    end_time: datetime
    created_at: datetime | None = None


@dataclass(slots=True)
class SessionAction:
    action_type: ActionType
    bar_index: int
    timestamp: datetime
    price: float | None = None
    quantity: float = 1.0
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    session_id: int | None = None


@dataclass(slots=True)
class Trade:
    entry_time: datetime
    exit_time: datetime
    direction: str
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float


@dataclass(slots=True)
class PositionState:
    direction: str | None = None
    quantity: float = 0.0
    average_price: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    realized_pnl: float = 0.0
    max_drawdown: float = 0.0
    peak_equity: float = 0.0
    open_trade_started_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.direction is not None and self.quantity > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "realized_pnl": self.realized_pnl,
            "max_drawdown": self.max_drawdown,
            "peak_equity": self.peak_equity,
            "open_trade_started_at": self.open_trade_started_at.isoformat() if self.open_trade_started_at else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "PositionState":
        if not payload:
            return cls()
        started_at = payload.get("open_trade_started_at")
        return cls(
            direction=payload.get("direction"),
            quantity=float(payload.get("quantity", 0.0)),
            average_price=float(payload.get("average_price", 0.0)),
            stop_loss=payload.get("stop_loss"),
            take_profit=payload.get("take_profit"),
            realized_pnl=float(payload.get("realized_pnl", 0.0)),
            max_drawdown=float(payload.get("max_drawdown", 0.0)),
            peak_equity=float(payload.get("peak_equity", 0.0)),
            open_trade_started_at=datetime.fromisoformat(started_at) if started_at else None,
        )


@dataclass(slots=True)
class SessionStats:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    average_pnl: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.wins / self.total_trades

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "total_pnl": self.total_pnl,
            "average_pnl": self.average_pnl,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "SessionStats":
        if not payload:
            return cls()
        return cls(
            total_trades=int(payload.get("total_trades", 0)),
            wins=int(payload.get("wins", 0)),
            losses=int(payload.get("losses", 0)),
            total_pnl=float(payload.get("total_pnl", 0.0)),
            average_pnl=float(payload.get("average_pnl", 0.0)),
            profit_factor=float(payload.get("profit_factor", 0.0)),
            max_drawdown=float(payload.get("max_drawdown", 0.0)),
        )


@dataclass(slots=True)
class ReviewSession:
    id: int | None
    dataset_id: int
    symbol: str
    timeframe: str
    start_index: int
    current_index: int
    status: SessionStatus = SessionStatus.ACTIVE
    title: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    position: PositionState = field(default_factory=PositionState)
    stats: SessionStats = field(default_factory=SessionStats)
    created_at: datetime | None = None
    updated_at: datetime | None = None
