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


class OrderLineType(StrEnum):
    ENTRY_LONG = "entry_long"
    ENTRY_SHORT = "entry_short"
    EXIT = "exit"
    REVERSE = "reverse"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    AVERAGE_PRICE = "average_price"


class OrderStatus(StrEnum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"


class OrderTriggerMode(StrEnum):
    TOUCH = "touch"
    BUY_STOP = "buy_stop"
    BUY_LIMIT = "buy_limit"
    SELL_STOP = "sell_stop"
    SELL_LIMIT = "sell_limit"


class DrawingToolType(StrEnum):
    TREND_LINE = "trend_line"
    RAY = "ray"
    EXTENDED_LINE = "extended_line"
    FIB_RETRACEMENT = "fib_retracement"
    HORIZONTAL_LINE = "horizontal_line"
    HORIZONTAL_RAY = "horizontal_ray"
    VERTICAL_LINE = "vertical_line"
    PARALLEL_CHANNEL = "parallel_channel"
    RECTANGLE = "rectangle"
    PRICE_RANGE = "price_range"
    TEXT = "text"


DEFAULT_DRAWING_COLOR = "#ff9f1c"
DEFAULT_DRAWING_FILL_COLOR = "#ff9f1c"
DEFAULT_DRAWING_STYLE: dict[str, Any] = {
    "color": DEFAULT_DRAWING_COLOR,
    "width": 1,
    "line_style": "solid",
    "extend_left": False,
    "extend_right": False,
    "fill_color": DEFAULT_DRAWING_FILL_COLOR,
    "fill_opacity": 0.15,
    "show_price_label": False,
    "fib_levels": [0.0, 0.5, 1.0, 2.0],
    "show_level_labels": True,
    "show_price_labels": True,
    "text": "",
    "font_size": 12,
    "text_color": DEFAULT_DRAWING_COLOR,
    "anchor_mode": "free",
}


def normalize_drawing_style(tool_type: DrawingToolType, style: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(DEFAULT_DRAWING_STYLE)
    if style:
        payload.update(style)
    payload["color"] = str(payload.get("color") or DEFAULT_DRAWING_COLOR)
    payload["fill_color"] = str(payload.get("fill_color") or payload["color"] or DEFAULT_DRAWING_FILL_COLOR)
    payload["width"] = max(1, int(payload.get("width", DEFAULT_DRAWING_STYLE["width"])))
    line_style = str(payload.get("line_style") or "solid").lower()
    payload["line_style"] = line_style if line_style in {"solid", "dash", "dot"} else "solid"
    payload["extend_left"] = bool(payload.get("extend_left", False))
    payload["extend_right"] = bool(payload.get("extend_right", False))
    payload["fill_opacity"] = min(max(float(payload.get("fill_opacity", DEFAULT_DRAWING_STYLE["fill_opacity"])), 0.0), 1.0)
    payload["show_price_label"] = bool(payload.get("show_price_label", False))
    fib_levels = payload.get("fib_levels", DEFAULT_DRAWING_STYLE["fib_levels"])
    if isinstance(fib_levels, list):
        payload["fib_levels"] = [float(item) for item in fib_levels]
    else:
        payload["fib_levels"] = list(DEFAULT_DRAWING_STYLE["fib_levels"])
    payload["show_level_labels"] = bool(payload.get("show_level_labels", True))
    payload["show_price_labels"] = bool(payload.get("show_price_labels", True))
    payload["text"] = str(payload.get("text", ""))
    payload["font_size"] = max(8, int(payload.get("font_size", 12)))
    payload["text_color"] = str(payload.get("text_color") or payload["color"])
    payload["anchor_mode"] = str(payload.get("anchor_mode") or "free")
    if tool_type is DrawingToolType.RAY:
        payload["extend_left"] = False
        payload["extend_right"] = True
    elif tool_type is DrawingToolType.EXTENDED_LINE:
        payload["extend_left"] = True
        payload["extend_right"] = True
    elif tool_type is DrawingToolType.HORIZONTAL_RAY:
        payload["extend_left"] = False
        payload["extend_right"] = True
    elif tool_type not in {DrawingToolType.TREND_LINE, DrawingToolType.RAY, DrawingToolType.EXTENDED_LINE}:
        payload["extend_left"] = False
        payload["extend_right"] = False
    if tool_type not in {DrawingToolType.RECTANGLE, DrawingToolType.PRICE_RANGE}:
        payload["fill_opacity"] = 0.0
    if tool_type is DrawingToolType.FIB_RETRACEMENT:
        payload["extend_left"] = False
        payload["extend_right"] = False
        payload["show_price_label"] = False
    if tool_type is DrawingToolType.TEXT:
        payload["extend_left"] = False
        payload["extend_right"] = False
        payload["fill_opacity"] = 0.0
        payload["show_price_label"] = False
    return payload


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
class WindowBars:
    bars: list[Bar]
    global_start_index: int
    global_end_index: int
    anchor_global_index: int
    total_count: int


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
class OrderLine:
    order_type: OrderLineType
    price: float
    quantity: float
    created_bar_index: int
    active_from_bar_index: int
    created_at: datetime
    trigger_mode: OrderTriggerMode = OrderTriggerMode.TOUCH
    reference_price_at_creation: float | None = None
    status: OrderStatus = OrderStatus.ACTIVE
    triggered_bar_index: int | None = None
    triggered_at: datetime | None = None
    note: str = ""
    id: int | None = None
    session_id: int | None = None

    @property
    def is_active(self) -> bool:
        return self.status is OrderStatus.ACTIVE

    @property
    def is_entry(self) -> bool:
        return self.order_type in {OrderLineType.ENTRY_LONG, OrderLineType.ENTRY_SHORT}

    @property
    def is_flattening(self) -> bool:
        return self.order_type in {OrderLineType.EXIT, OrderLineType.REVERSE}

    @property
    def is_protective(self) -> bool:
        return self.order_type in {OrderLineType.STOP_LOSS, OrderLineType.TAKE_PROFIT}

    @property
    def is_reference(self) -> bool:
        return self.order_type is OrderLineType.AVERAGE_PRICE


@dataclass(slots=True)
class DrawingAnchor:
    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        return {"x": float(self.x), "y": float(self.y)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DrawingAnchor":
        return cls(x=float(payload["x"]), y=float(payload["y"]))


@dataclass(slots=True)
class ChartDrawing:
    tool_type: DrawingToolType
    anchors: list[DrawingAnchor]
    style: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    session_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_type": self.tool_type.value,
            "anchors": [anchor.to_dict() for anchor in self.anchors],
            "style": normalize_drawing_style(self.tool_type, self.style),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ChartDrawing":
        tool_type = DrawingToolType(payload["tool_type"])
        return cls(
            tool_type=tool_type,
            anchors=[DrawingAnchor.from_dict(item) for item in payload.get("anchors", [])],
            style=normalize_drawing_style(tool_type, dict(payload.get("style", {}))),
        )


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
    average_win: float = 0.0
    average_loss: float = 0.0
    payoff_ratio: float = 0.0
    expectancy: float = 0.0
    long_trades: int = 0
    short_trades: int = 0
    long_pnl: float = 0.0
    short_pnl: float = 0.0
    avg_holding_bars: float = 0.0
    max_win_streak: int = 0
    max_loss_streak: int = 0
    trades_with_stop_rate: float = 0.0
    manual_trades: int = 0
    auto_trades: int = 0
    planned_trades: int = 0

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
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "payoff_ratio": self.payoff_ratio,
            "expectancy": self.expectancy,
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
            "long_pnl": self.long_pnl,
            "short_pnl": self.short_pnl,
            "avg_holding_bars": self.avg_holding_bars,
            "max_win_streak": self.max_win_streak,
            "max_loss_streak": self.max_loss_streak,
            "trades_with_stop_rate": self.trades_with_stop_rate,
            "manual_trades": self.manual_trades,
            "auto_trades": self.auto_trades,
            "planned_trades": self.planned_trades,
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
            average_win=float(payload.get("average_win", 0.0)),
            average_loss=float(payload.get("average_loss", 0.0)),
            payoff_ratio=float(payload.get("payoff_ratio", 0.0)),
            expectancy=float(payload.get("expectancy", 0.0)),
            long_trades=int(payload.get("long_trades", 0)),
            short_trades=int(payload.get("short_trades", 0)),
            long_pnl=float(payload.get("long_pnl", 0.0)),
            short_pnl=float(payload.get("short_pnl", 0.0)),
            avg_holding_bars=float(payload.get("avg_holding_bars", 0.0)),
            max_win_streak=int(payload.get("max_win_streak", 0)),
            max_loss_streak=int(payload.get("max_loss_streak", 0)),
            trades_with_stop_rate=float(payload.get("trades_with_stop_rate", 0.0)),
            manual_trades=int(payload.get("manual_trades", 0)),
            auto_trades=int(payload.get("auto_trades", 0)),
            planned_trades=int(payload.get("planned_trades", 0)),
        )


@dataclass(slots=True)
class TradeReviewItem:
    trade_number: int
    entry_time: datetime
    exit_time: datetime
    direction: str
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


@dataclass(slots=True)
class ReviewSession:
    id: int | None
    dataset_id: int
    symbol: str
    timeframe: str
    chart_timeframe: str
    start_index: int
    current_index: int
    current_bar_time: datetime | None = None
    tick_size: float = 1.0
    status: SessionStatus = SessionStatus.ACTIVE
    title: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    position: PositionState = field(default_factory=PositionState)
    stats: SessionStats = field(default_factory=SessionStats)
    created_at: datetime | None = None
    updated_at: datetime | None = None
