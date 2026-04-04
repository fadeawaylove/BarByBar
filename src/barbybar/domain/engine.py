from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from barbybar.domain.models import ActionType, Bar, PositionState, ReviewSession, SessionAction, SessionStats, SessionStatus, Trade


@dataclass(slots=True)
class SessionSnapshot:
    current_index: int
    position: PositionState
    trades: list[Trade]
    actions: list[SessionAction]
    notes: str
    tags: list[str]


class ReviewEngine:
    def __init__(self, session: ReviewSession, bars: list[Bar], actions: list[SessionAction] | None = None) -> None:
        if not bars:
            raise ValueError("Session requires at least one bar.")
        self.session = session
        self.bars = bars
        self.actions = list(actions or [])
        self.trades: list[Trade] = []
        self._history: list[SessionSnapshot] = []

    @property
    def current_bar(self) -> Bar:
        return self.bars[self.session.current_index]

    @property
    def visible_bars(self) -> list[Bar]:
        return self.bars[: self.session.current_index + 1]

    def step_forward(self) -> bool:
        if self.session.current_index >= len(self.bars) - 1:
            return False
        self._save_snapshot()
        next_index = self.session.current_index + 1
        next_bar = self.bars[next_index]
        self._apply_protective_orders(next_index, next_bar)
        self.session.current_index = next_index
        self._refresh_stats()
        return True

    def jump_to(self, index: int) -> None:
        index = max(self.session.start_index, min(index, len(self.bars) - 1))
        while self.session.current_index < index:
            if not self.step_forward():
                break
        while self.session.current_index > index and self._history:
            self.step_back()

    def step_back(self) -> bool:
        if not self._history:
            return False
        snap = self._history.pop()
        self.session.current_index = snap.current_index
        self.session.position = deepcopy(snap.position)
        self.trades = deepcopy(snap.trades)
        self.actions = deepcopy(snap.actions)
        self.session.notes = snap.notes
        self.session.tags = list(snap.tags)
        self._refresh_stats()
        return True

    def record_action(
        self,
        action_type: ActionType,
        *,
        quantity: float = 1.0,
        price: float | None = None,
        note: str = "",
        extra: dict | None = None,
    ) -> SessionAction:
        self._save_snapshot()
        bar = self.current_bar
        action_price = bar.close if price is None else price
        action = SessionAction(
            action_type=action_type,
            bar_index=self.session.current_index,
            timestamp=bar.timestamp,
            price=action_price,
            quantity=quantity,
            note=note,
            extra=extra or {},
            session_id=self.session.id,
        )
        self._apply_action(action)
        self.actions.append(action)
        self._refresh_stats()
        return action

    def set_notes(self, notes: str) -> None:
        self.session.notes = notes

    def set_tags(self, tags: list[str]) -> None:
        self.session.tags = [tag.strip() for tag in tags if tag.strip()]

    def complete(self) -> None:
        self.session.status = SessionStatus.COMPLETED
        self._refresh_stats()

    def _apply_action(self, action: SessionAction) -> None:
        position = self.session.position
        price = action.price or self.current_bar.close
        quantity = max(action.quantity, 0.0)
        if action.action_type is ActionType.OPEN_LONG:
            self._open_position("long", quantity, price, action.timestamp)
        elif action.action_type is ActionType.OPEN_SHORT:
            self._open_position("short", quantity, price, action.timestamp)
        elif action.action_type is ActionType.ADD:
            self._add_position(quantity, price)
        elif action.action_type is ActionType.REDUCE:
            self._close_position_partially(quantity, price, action.timestamp)
        elif action.action_type is ActionType.CLOSE:
            self._close_position_partially(position.quantity, price, action.timestamp)
        elif action.action_type is ActionType.SET_STOP_LOSS:
            position.stop_loss = price
        elif action.action_type is ActionType.SET_TAKE_PROFIT:
            position.take_profit = price
        elif action.action_type is ActionType.NOTE and action.note:
            self.session.notes = f"{self.session.notes}\n{action.note}".strip()

    def _open_position(self, direction: str, quantity: float, price: float, timestamp) -> None:
        position = self.session.position
        if position.is_open and position.direction != direction:
            self._close_position_partially(position.quantity, price, timestamp)
        if not position.is_open:
            position.direction = direction
            position.quantity = quantity
            position.average_price = price
            position.open_trade_started_at = timestamp
        else:
            self._add_position(quantity, price)

    def _add_position(self, quantity: float, price: float) -> None:
        position = self.session.position
        if not position.is_open:
            raise ValueError("Cannot add to a position before opening it.")
        new_quantity = position.quantity + quantity
        if new_quantity <= 0:
            raise ValueError("Position quantity must remain positive.")
        position.average_price = ((position.average_price * position.quantity) + (price * quantity)) / new_quantity
        position.quantity = new_quantity

    def _close_position_partially(self, quantity: float, price: float, timestamp) -> None:
        position = self.session.position
        if not position.is_open:
            return
        close_qty = min(quantity, position.quantity)
        direction_sign = 1 if position.direction == "long" else -1
        pnl = (price - position.average_price) * close_qty * direction_sign
        position.realized_pnl += pnl
        trade = Trade(
            entry_time=position.open_trade_started_at or timestamp,
            exit_time=timestamp,
            direction=position.direction or "flat",
            quantity=close_qty,
            entry_price=position.average_price,
            exit_price=price,
            pnl=pnl,
        )
        self.trades.append(trade)
        position.quantity -= close_qty
        if position.quantity <= 0:
            position.direction = None
            position.quantity = 0.0
            position.average_price = 0.0
            position.stop_loss = None
            position.take_profit = None
            position.open_trade_started_at = None

    def _apply_protective_orders(self, index: int, bar: Bar) -> None:
        position = self.session.position
        if not position.is_open:
            return
        exit_price: float | None = None
        if position.direction == "long":
            if position.stop_loss is not None and bar.low <= position.stop_loss:
                exit_price = position.stop_loss
            elif position.take_profit is not None and bar.high >= position.take_profit:
                exit_price = position.take_profit
        else:
            if position.stop_loss is not None and bar.high >= position.stop_loss:
                exit_price = position.stop_loss
            elif position.take_profit is not None and bar.low <= position.take_profit:
                exit_price = position.take_profit
        if exit_price is None:
            self._update_drawdown(bar.close)
            return
        auto_action = SessionAction(
            action_type=ActionType.CLOSE,
            bar_index=index,
            timestamp=bar.timestamp,
            price=exit_price,
            quantity=position.quantity,
            note="Auto close by protective order",
            extra={"auto": True},
            session_id=self.session.id,
        )
        self._apply_action(auto_action)
        self.actions.append(auto_action)
        self._update_drawdown(exit_price)

    def _update_drawdown(self, mark_price: float) -> None:
        position = self.session.position
        if not position.is_open:
            equity = position.realized_pnl
        else:
            direction_sign = 1 if position.direction == "long" else -1
            unrealized = (mark_price - position.average_price) * position.quantity * direction_sign
            equity = position.realized_pnl + unrealized
        position.peak_equity = max(position.peak_equity, equity)
        drawdown = position.peak_equity - equity
        position.max_drawdown = max(position.max_drawdown, drawdown)

    def _refresh_stats(self) -> None:
        total_trades = len(self.trades)
        wins = len([trade for trade in self.trades if trade.pnl > 0])
        losses = len([trade for trade in self.trades if trade.pnl < 0])
        gross_profit = sum(trade.pnl for trade in self.trades if trade.pnl > 0)
        gross_loss = abs(sum(trade.pnl for trade in self.trades if trade.pnl < 0))
        total_pnl = sum(trade.pnl for trade in self.trades)
        self.session.stats = SessionStats(
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            total_pnl=total_pnl,
            average_pnl=total_pnl / total_trades if total_trades else 0.0,
            profit_factor=(gross_profit / gross_loss) if gross_loss else (gross_profit if gross_profit else 0.0),
            max_drawdown=self.session.position.max_drawdown,
        )

    def _save_snapshot(self) -> None:
        self._history.append(
            SessionSnapshot(
                current_index=self.session.current_index,
                position=deepcopy(self.session.position),
                trades=deepcopy(self.trades),
                actions=deepcopy(self.actions),
                notes=self.session.notes,
                tags=list(self.session.tags),
            )
        )
