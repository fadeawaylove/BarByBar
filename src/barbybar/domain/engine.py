from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from barbybar.domain.models import (
    ActionType,
    Bar,
    OrderLine,
    OrderLineType,
    OrderStatus,
    OrderTriggerMode,
    PositionState,
    ReviewSession,
    SessionAction,
    SessionStats,
    SessionStatus,
    Trade,
)


@dataclass(slots=True)
class SessionSnapshot:
    current_index: int
    position: PositionState
    trades: list[Trade]
    actions: list[SessionAction]
    order_lines: list[OrderLine]
    notes: str
    tags: list[str]


class ReviewEngine:
    def __init__(
        self,
        session: ReviewSession,
        bars: list[Bar],
        actions: list[SessionAction] | None = None,
        order_lines: list[OrderLine] | None = None,
        *,
        window_start_index: int = 0,
        total_count: int | None = None,
    ) -> None:
        if not bars:
            raise ValueError("Session requires at least one bar.")
        self.session = session
        self.bars = bars
        self.actions = list(actions or [])
        self.order_lines = list(order_lines or [])
        self.trades: list[Trade] = []
        self._history: list[SessionSnapshot] = []
        self.window_start_index = max(0, window_start_index)
        self.total_count = max(len(bars), total_count or len(bars))
        self.session.current_index = max(self.window_start_index, min(self.session.current_index, self.window_end_index))
        self.session.current_bar_time = self.current_bar.timestamp
        self._reconcile_state()

    @property
    def current_bar(self) -> Bar:
        return self.bars[self.local_current_index]

    @property
    def visible_bars(self) -> list[Bar]:
        return self.bars[: self.local_current_index + 1]

    @property
    def local_current_index(self) -> int:
        return self.session.current_index - self.window_start_index

    @property
    def window_end_index(self) -> int:
        return self.window_start_index + len(self.bars) - 1

    @property
    def forward_buffer(self) -> int:
        return self.window_end_index - self.session.current_index

    @property
    def backward_buffer(self) -> int:
        return self.session.current_index - self.window_start_index

    @property
    def active_order_lines(self) -> list[OrderLine]:
        return [line for line in self.order_lines if line.is_active and not line.is_reference]

    def display_order_lines(self) -> list[OrderLine]:
        lines = [deepcopy(line) for line in self.order_lines if line.is_active]
        position = self.session.position
        if position.is_open:
            lines.append(
                OrderLine(
                    order_type=OrderLineType.AVERAGE_PRICE,
                    price=position.average_price,
                    quantity=position.quantity,
                    created_bar_index=self.session.current_index,
                    active_from_bar_index=self.session.current_index,
                    created_at=self.current_bar.timestamp,
                    trigger_mode=OrderTriggerMode.TOUCH,
                    reference_price_at_creation=position.average_price,
                    note="成本线",
                    session_id=self.session.id,
                )
            )
        return lines

    def replace_window(self, bars: list[Bar], window_start_index: int, total_count: int) -> None:
        if not bars:
            raise ValueError("Window requires at least one bar.")
        self.bars = bars
        self.window_start_index = window_start_index
        self.total_count = total_count
        self.session.current_index = max(self.window_start_index, min(self.session.current_index, self.window_end_index))
        self.session.current_bar_time = self.current_bar.timestamp

    def can_step_forward(self) -> bool:
        return self.session.current_index < self.total_count - 1

    def can_step_back(self) -> bool:
        return bool(self._history)

    def previous_history_index(self) -> int | None:
        if not self._history:
            return None
        return self._history[-1].current_index

    def step_forward(self) -> bool:
        if not self.can_step_forward():
            return False
        if self.session.current_index >= self.window_end_index:
            return False
        self._save_snapshot()
        next_index = self.session.current_index + 1
        next_bar = self.bars[next_index - self.window_start_index]
        protective_triggered = self._apply_protective_order_lines(next_index, next_bar)
        if not protective_triggered:
            flattening_triggered = self._apply_flattening_order_lines(next_index, next_bar)
            if not flattening_triggered:
                self._apply_entry_order_lines(next_index, next_bar)
        self.session.current_index = next_index
        self.session.current_bar_time = next_bar.timestamp
        self._refresh_stats()
        return True

    def jump_to(self, index: int) -> None:
        index = max(self.session.start_index, min(index, self.total_count - 1))
        while self.session.current_index < index:
            if not self.step_forward():
                break
        while self.session.current_index > index and self._history:
            self.step_back()

    def step_back(self) -> bool:
        if not self._history:
            return False
        snap = self._history.pop()
        if snap.current_index < self.window_start_index or snap.current_index > self.window_end_index:
            return False
        self.session.current_index = snap.current_index
        self.session.current_bar_time = self.bars[snap.current_index - self.window_start_index].timestamp
        self.session.position = deepcopy(snap.position)
        self.trades = deepcopy(snap.trades)
        self.actions = deepcopy(snap.actions)
        self.order_lines = deepcopy(snap.order_lines)
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

    def place_order_line(
        self,
        order_type: OrderLineType,
        *,
        price: float,
        quantity: float = 1.0,
        note: str = "",
    ) -> OrderLine:
        if order_type is OrderLineType.AVERAGE_PRICE:
            raise ValueError("Average price line is derived and cannot be placed manually.")
        self._save_snapshot()
        quantity = max(quantity, 0.1)
        if order_type in {OrderLineType.EXIT, OrderLineType.REVERSE} and not self.session.position.is_open:
            raise ValueError("当前没有持仓，无法创建平仓/反手条件线。")
        if order_type in {OrderLineType.STOP_LOSS, OrderLineType.TAKE_PROFIT}:
            self._upsert_protective_line(order_type, price, quantity, note)
            line = self._get_active_line(order_type)
            assert line is not None
            self._refresh_stats()
            return line
        line = OrderLine(
            order_type=order_type,
            price=price,
            quantity=quantity,
            created_bar_index=self.session.current_index,
            active_from_bar_index=self.session.current_index + 1,
            created_at=self.current_bar.timestamp,
            trigger_mode=OrderTriggerMode.TOUCH,
            reference_price_at_creation=self.current_bar.close,
            note=note,
            session_id=self.session.id,
        )
        self.order_lines.append(line)
        self._refresh_stats()
        return line

    def update_order_line(self, order_id: int, price: float) -> OrderLine:
        line = self._find_order_line(order_id)
        if line is None or not line.is_active:
            raise ValueError("Order line does not exist or is no longer active.")
        if line.is_reference:
            raise ValueError("Average price line cannot be modified.")
        self._save_snapshot()
        line.price = price
        line.active_from_bar_index = self.session.current_index + 1
        if line.is_entry:
            line.reference_price_at_creation = self.current_bar.close
            line.trigger_mode = OrderTriggerMode.TOUCH
        if line.order_type is OrderLineType.STOP_LOSS:
            self.session.position.stop_loss = price
        elif line.order_type is OrderLineType.TAKE_PROFIT:
            self.session.position.take_profit = price
        self._refresh_stats()
        return line

    def update_order_line_quantity(self, order_id: int, quantity: float) -> OrderLine:
        line = self._find_order_line(order_id)
        if line is None or not line.is_active:
            raise ValueError("Order line does not exist or is no longer active.")
        if line.is_reference:
            raise ValueError("Average price line cannot be modified.")
        self._save_snapshot()
        line.quantity = max(float(quantity), 1.0)
        line.active_from_bar_index = self.session.current_index + 1
        if line.is_entry:
            line.reference_price_at_creation = self.current_bar.close
            line.trigger_mode = OrderTriggerMode.TOUCH
        self._refresh_stats()
        return line

    def cancel_order_line(self, order_id: int) -> None:
        line = self._find_order_line(order_id)
        if line is None or not line.is_active or line.is_reference:
            return
        self._save_snapshot()
        self._cancel_line(line)
        self._refresh_stats()

    def cancel_entry_order_lines(self) -> None:
        self._save_snapshot()
        for line in self.order_lines:
            if line.is_active and line.is_entry:
                self._cancel_line(line)
        self._refresh_stats()

    def clear_protective_lines(self) -> None:
        self._save_snapshot()
        self._remove_protective_lines()
        self._refresh_stats()

    def move_stop_to_break_even(self) -> None:
        position = self.session.position
        if not position.is_open:
            raise ValueError("当前没有持仓，无法一键保本。")
        self.place_order_line(
            OrderLineType.STOP_LOSS,
            price=position.average_price,
            quantity=position.quantity,
            note="移动到保本价",
        )

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
            self._upsert_protective_line(OrderLineType.STOP_LOSS, price, position.quantity or quantity, action.note)
        elif action.action_type is ActionType.SET_TAKE_PROFIT:
            self._upsert_protective_line(OrderLineType.TAKE_PROFIT, price, position.quantity or quantity, action.note)
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
        self._cancel_entry_lines()

    def _add_position(self, quantity: float, price: float) -> None:
        position = self.session.position
        if not position.is_open:
            raise ValueError("Cannot add to a position before opening it.")
        new_quantity = position.quantity + quantity
        if new_quantity <= 0:
            raise ValueError("Position quantity must remain positive.")
        position.average_price = ((position.average_price * position.quantity) + (price * quantity)) / new_quantity
        position.quantity = new_quantity
        self._update_protective_quantities(new_quantity)

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
            self._remove_protective_lines()
        else:
            self._update_protective_quantities(position.quantity)

    def _apply_protective_order_lines(self, index: int, bar: Bar) -> bool:
        position = self.session.position
        if not position.is_open:
            return False
        protective_lines = [
            line for line in self.order_lines
            if line.is_active and line.is_protective and index >= line.active_from_bar_index
        ]
        if not protective_lines:
            self._update_drawdown(bar.close)
            return False
        stop_line = self._get_active_line(OrderLineType.STOP_LOSS)
        take_line = self._get_active_line(OrderLineType.TAKE_PROFIT)
        hit_line: OrderLine | None = None
        if position.direction == "long":
            if stop_line and bar.low <= stop_line.price:
                hit_line = stop_line
            elif take_line and bar.high >= take_line.price:
                hit_line = take_line
        else:
            if stop_line and bar.high >= stop_line.price:
                hit_line = stop_line
            elif take_line and bar.low <= take_line.price:
                hit_line = take_line
        if hit_line is None:
            self._update_drawdown(bar.close)
            return False
        self._trigger_line(hit_line, index, bar.timestamp)
        auto_action = SessionAction(
            action_type=ActionType.CLOSE,
            bar_index=index,
            timestamp=bar.timestamp,
            price=hit_line.price,
            quantity=position.quantity,
            note=f"Auto close by {hit_line.order_type.value}",
            extra={"auto": True, "triggered_order_id": hit_line.id, "order_type": hit_line.order_type.value},
            session_id=self.session.id,
        )
        self._apply_action(auto_action)
        self.actions.append(auto_action)
        self._remove_protective_lines()
        self._update_drawdown(hit_line.price)
        return True

    def _apply_entry_order_lines(self, index: int, bar: Bar) -> bool:
        entry_lines = [
            line for line in self.order_lines
            if line.is_active and line.is_entry and index >= line.active_from_bar_index
        ]
        if not entry_lines:
            self._update_drawdown(bar.close)
            return False
        hit_line: OrderLine | None = None
        for line in entry_lines:
            if bar.low <= line.price <= bar.high:
                hit_line = line
                break
        if hit_line is None:
            self._update_drawdown(bar.close)
            return False
        self._trigger_line(hit_line, index, bar.timestamp)
        action_type = ActionType.OPEN_LONG if hit_line.order_type is OrderLineType.ENTRY_LONG else ActionType.OPEN_SHORT
        auto_action = SessionAction(
            action_type=action_type,
            bar_index=index,
            timestamp=bar.timestamp,
            price=hit_line.price,
            quantity=hit_line.quantity,
            note=f"Auto entry by {hit_line.order_type.value}",
            extra={"auto": True, "triggered_order_id": hit_line.id, "order_type": hit_line.order_type.value},
            session_id=self.session.id,
        )
        self._apply_action(auto_action)
        self.actions.append(auto_action)
        self._cancel_entry_lines()
        self._update_drawdown(hit_line.price)
        return True

    def _apply_flattening_order_lines(self, index: int, bar: Bar) -> bool:
        position = self.session.position
        if not position.is_open:
            return False
        flattening_lines = [
            line for line in self.order_lines
            if line.is_active and line.is_flattening and index >= line.active_from_bar_index
        ]
        if not flattening_lines:
            self._update_drawdown(bar.close)
            return False
        hit_line: OrderLine | None = None
        for line in flattening_lines:
            if min(bar.low, bar.high) <= line.price <= max(bar.low, bar.high):
                hit_line = line
                break
        if hit_line is None:
            self._update_drawdown(bar.close)
            return False
        self._trigger_line(hit_line, index, bar.timestamp)
        quantity = position.quantity
        direction = position.direction
        close_action = SessionAction(
            action_type=ActionType.CLOSE,
            bar_index=index,
            timestamp=bar.timestamp,
            price=hit_line.price,
            quantity=quantity,
            note=f"Auto close by {hit_line.order_type.value}",
            extra={"auto": True, "triggered_order_id": hit_line.id, "order_type": hit_line.order_type.value},
            session_id=self.session.id,
        )
        self._apply_action(close_action)
        self.actions.append(close_action)
        if hit_line.order_type is OrderLineType.REVERSE and direction is not None:
            reverse_action = SessionAction(
                action_type=ActionType.OPEN_SHORT if direction == "long" else ActionType.OPEN_LONG,
                bar_index=index,
                timestamp=bar.timestamp,
                price=hit_line.price,
                quantity=quantity,
                note="Auto reverse by reverse line",
                extra={"auto": True, "triggered_order_id": hit_line.id, "order_type": hit_line.order_type.value},
                session_id=self.session.id,
            )
            self._apply_action(reverse_action)
            self.actions.append(reverse_action)
        self._cancel_flattening_lines()
        self._update_drawdown(hit_line.price)
        return True

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
                order_lines=deepcopy(self.order_lines),
                notes=self.session.notes,
                tags=list(self.session.tags),
            )
        )

    def _reconcile_state(self) -> None:
        self._cancel_reference_lines()
        self._sync_position_from_lines()
        self._refresh_stats()

    def _sync_position_from_lines(self) -> None:
        stop_line = self._get_active_line(OrderLineType.STOP_LOSS)
        take_line = self._get_active_line(OrderLineType.TAKE_PROFIT)
        self.session.position.stop_loss = stop_line.price if stop_line else None
        self.session.position.take_profit = take_line.price if take_line else None

    def _upsert_protective_line(self, order_type: OrderLineType, price: float, quantity: float, note: str = "") -> None:
        position = self.session.position
        if not position.is_open:
            raise ValueError("当前没有持仓，无法设置保护线。")
        line = self._get_active_line(order_type)
        if line is None:
            line = OrderLine(
                order_type=order_type,
                price=price,
                quantity=position.quantity if quantity <= 0 else quantity,
                created_bar_index=self.session.current_index,
                active_from_bar_index=self.session.current_index + 1,
                created_at=self.current_bar.timestamp,
                trigger_mode=OrderTriggerMode.TOUCH,
                reference_price_at_creation=self.current_bar.close,
                note=note,
                session_id=self.session.id,
            )
            self.order_lines.append(line)
        else:
            line.price = price
            line.quantity = position.quantity if quantity <= 0 else quantity
            line.active_from_bar_index = self.session.current_index + 1
            if note:
                line.note = note
        if order_type is OrderLineType.STOP_LOSS:
            position.stop_loss = price
        elif order_type is OrderLineType.TAKE_PROFIT:
            position.take_profit = price


    def _remove_protective_lines(self) -> None:
        for line in self.order_lines:
            if line.is_active and line.is_protective:
                self._cancel_line(line)
        self.session.position.stop_loss = None
        self.session.position.take_profit = None

    def _cancel_entry_lines(self) -> None:
        for line in self.order_lines:
            if line.is_active and line.is_entry:
                self._cancel_line(line)

    def _cancel_flattening_lines(self) -> None:
        for line in self.order_lines:
            if line.is_active and line.is_flattening:
                self._cancel_line(line)

    def _cancel_reference_lines(self) -> None:
        self.order_lines = [line for line in self.order_lines if line.order_type is not OrderLineType.AVERAGE_PRICE]

    def _update_protective_quantities(self, quantity: float) -> None:
        for line in self.order_lines:
            if line.is_active and line.is_protective:
                line.quantity = quantity

    def _find_order_line(self, order_id: int) -> OrderLine | None:
        for line in self.order_lines:
            if line.id == order_id:
                return line
        return None

    def _get_active_line(self, order_type: OrderLineType) -> OrderLine | None:
        for line in self.order_lines:
            if line.order_type is order_type and line.is_active:
                return line
        return None

    def _cancel_line(self, line: OrderLine) -> None:
        line.status = OrderStatus.CANCELLED
        if line.order_type is OrderLineType.STOP_LOSS:
            self.session.position.stop_loss = None
        elif line.order_type is OrderLineType.TAKE_PROFIT:
            self.session.position.take_profit = None

    def _trigger_line(self, line: OrderLine, bar_index: int, timestamp) -> None:
        line.status = OrderStatus.TRIGGERED
        line.triggered_bar_index = bar_index
        line.triggered_at = timestamp
