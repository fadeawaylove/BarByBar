from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import time, timedelta

from barbybar.data.tick_size import snap_price
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
    TradeReviewItem,
)

PLANNED_STOP_SETUP_MAX_BARS = 3
DAY_SESSION_OPEN = time(hour=9, minute=0)
NIGHT_SESSION_OPEN = time(hour=21, minute=0)
SESSION_END_FLATTEN_ORDER_TYPE = "session_end_flatten"


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

    def step_forward(self, *, flatten_at_session_end: bool = False) -> bool:
        if not self.can_step_forward():
            return self._flatten_terminal_position_if_needed(flatten_at_session_end)
        if self.session.current_index >= self.window_end_index:
            return False
        self._save_snapshot()
        if flatten_at_session_end and self._is_last_bar_of_session(self.current_bar, self.bars[self.local_current_index + 1]):
            self._close_position_for_session_end(self.current_bar)
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

    def jump_to(self, index: int, *, flatten_at_session_end: bool = False) -> None:
        index = max(self.session.start_index, min(index, self.total_count - 1))
        while self.session.current_index < index:
            if not self.step_forward(flatten_at_session_end=flatten_at_session_end):
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
            line = self._create_protective_line(order_type, price, quantity, note)
            self._sync_position_from_lines()
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
        if line.is_protective:
            self._sync_position_from_lines()
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
        if line.is_protective:
            self._sync_position_from_lines()
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

    def trade_review_items(self) -> list[TradeReviewItem]:
        items: list[TradeReviewItem] = []
        position_direction: str | None = None
        position_quantity = 0.0
        average_price = 0.0
        open_trade_started_at = self.actions[0].timestamp if self.actions else self.current_bar.timestamp
        open_trade_started_bar_index = self.session.start_index
        has_stop_protection = False
        stop_set_bar_index: int | None = None
        had_adverse_add = False
        trade_index = 0

        for action in self.actions:
            price = float(action.price if action.price is not None else 0.0)
            quantity = max(float(action.quantity), 0.0)

            if action.action_type in {ActionType.OPEN_LONG, ActionType.OPEN_SHORT}:
                direction = "long" if action.action_type is ActionType.OPEN_LONG else "short"
                if position_quantity <= 0:
                    position_direction = direction
                    position_quantity = quantity
                    average_price = price
                    open_trade_started_at = action.timestamp
                    open_trade_started_bar_index = action.bar_index
                    has_stop_protection = False
                    stop_set_bar_index = None
                    had_adverse_add = False
                elif position_direction == direction:
                    new_quantity = position_quantity + quantity
                    if new_quantity > 0:
                        average_price = ((average_price * position_quantity) + (price * quantity)) / new_quantity
                        position_quantity = new_quantity
                continue

            if action.action_type is ActionType.ADD:
                if position_quantity > 0:
                    is_adverse = (
                        (position_direction == "long" and price < average_price)
                        or (position_direction == "short" and price > average_price)
                    )
                    had_adverse_add = had_adverse_add or is_adverse
                    new_quantity = position_quantity + quantity
                    if new_quantity > 0:
                        average_price = ((average_price * position_quantity) + (price * quantity)) / new_quantity
                        position_quantity = new_quantity
                continue

            if action.action_type is ActionType.SET_STOP_LOSS:
                if position_quantity > 0:
                    has_stop_protection = True
                    if stop_set_bar_index is None:
                        stop_set_bar_index = action.bar_index
                continue

            if action.action_type not in {ActionType.CLOSE, ActionType.REDUCE}:
                continue
            if position_quantity <= 0 or trade_index >= len(self.trades):
                continue

            close_quantity = min(quantity, position_quantity) if quantity > 0 else position_quantity
            remaining_quantity = max(position_quantity - close_quantity, 0.0)
            trade = self.trades[trade_index]
            trade_index += 1
            exit_reason = self._trade_exit_reason(action, remaining_quantity)
            holding_bars = max(action.bar_index - open_trade_started_bar_index, 0)
            is_planned = (
                has_stop_protection
                and stop_set_bar_index is not None
                and stop_set_bar_index - open_trade_started_bar_index <= PLANNED_STOP_SETUP_MAX_BARS
                and not had_adverse_add
                and exit_reason != "unknown"
            )
            items.append(
                TradeReviewItem(
                    trade_number=len(items) + 1,
                    entry_time=trade.entry_time,
                    exit_time=trade.exit_time,
                    direction=trade.direction,
                    quantity=trade.quantity,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    pnl=trade.pnl,
                    entry_bar_index=open_trade_started_bar_index,
                    exit_bar_index=action.bar_index,
                    holding_bars=holding_bars,
                    exit_reason=exit_reason,
                    is_manual=not bool(action.extra.get("auto")),
                    had_stop_protection=has_stop_protection,
                    had_adverse_add=had_adverse_add,
                    is_planned=is_planned,
                )
            )
            position_quantity = remaining_quantity
            if position_quantity <= 0:
                position_direction = None
                average_price = 0.0
                has_stop_protection = False
                stop_set_bar_index = None
                had_adverse_add = False

        return items

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
            self._create_protective_line(OrderLineType.STOP_LOSS, price, position.quantity or quantity, action.note)
            self._sync_position_from_lines()
        elif action.action_type is ActionType.SET_TAKE_PROFIT:
            self._create_protective_line(OrderLineType.TAKE_PROFIT, price, position.quantity or quantity, action.note)
            self._sync_position_from_lines()
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
        stop_line = self._select_triggered_protective_line(OrderLineType.STOP_LOSS, index, bar)
        take_line = self._select_triggered_protective_line(OrderLineType.TAKE_PROFIT, index, bar)
        hit_line: OrderLine | None = None
        fill_price: float | None = None
        if position.direction == "long":
            if stop_line:
                hit_line = stop_line
            elif take_line:
                hit_line = take_line
        else:
            if stop_line:
                hit_line = stop_line
            elif take_line:
                hit_line = take_line
        if hit_line is None:
            self._update_drawdown(bar.close)
            return False
        fill_price = self._resolve_order_fill_price(hit_line, index, bar)
        if fill_price is None:
            self._update_drawdown(bar.close)
            return False
        self._trigger_line(hit_line, index, bar.timestamp)
        auto_action = SessionAction(
            action_type=ActionType.CLOSE,
            bar_index=index,
            timestamp=bar.timestamp,
            price=fill_price,
            quantity=position.quantity,
            note=f"Auto close by {hit_line.order_type.value}",
            extra={"auto": True, "triggered_order_id": hit_line.id, "order_type": hit_line.order_type.value},
            session_id=self.session.id,
        )
        self._apply_action(auto_action)
        self.actions.append(auto_action)
        self._remove_protective_lines()
        self._update_drawdown(fill_price)
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
            if self._resolve_order_fill_price(line, index, bar) is not None:
                hit_line = line
                break
        if hit_line is None:
            self._update_drawdown(bar.close)
            return False
        fill_price = self._resolve_order_fill_price(hit_line, index, bar)
        if fill_price is None:
            self._update_drawdown(bar.close)
            return False
        self._trigger_line(hit_line, index, bar.timestamp)
        action_type = ActionType.OPEN_LONG if hit_line.order_type is OrderLineType.ENTRY_LONG else ActionType.OPEN_SHORT
        auto_action = SessionAction(
            action_type=action_type,
            bar_index=index,
            timestamp=bar.timestamp,
            price=fill_price,
            quantity=hit_line.quantity,
            note=f"Auto entry by {hit_line.order_type.value}",
            extra={"auto": True, "triggered_order_id": hit_line.id, "order_type": hit_line.order_type.value},
            session_id=self.session.id,
        )
        self._apply_action(auto_action)
        self.actions.append(auto_action)
        self._cancel_entry_lines()
        self._update_drawdown(fill_price)
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
            if self._resolve_order_fill_price(line, index, bar) is not None:
                hit_line = line
                break
        if hit_line is None:
            self._update_drawdown(bar.close)
            return False
        fill_price = self._resolve_order_fill_price(hit_line, index, bar)
        if fill_price is None:
            self._update_drawdown(bar.close)
            return False
        self._trigger_line(hit_line, index, bar.timestamp)
        quantity = position.quantity
        direction = position.direction
        close_action = SessionAction(
            action_type=ActionType.CLOSE,
            bar_index=index,
            timestamp=bar.timestamp,
            price=fill_price,
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
                price=fill_price,
                quantity=quantity,
                note="Auto reverse by reverse line",
                extra={"auto": True, "triggered_order_id": hit_line.id, "order_type": hit_line.order_type.value},
                session_id=self.session.id,
            )
            self._apply_action(reverse_action)
            self.actions.append(reverse_action)
        self._cancel_flattening_lines()
        self._update_drawdown(fill_price)
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
        review_items = self.trade_review_items()
        average_win = gross_profit / wins if wins else 0.0
        average_loss = gross_loss / losses if losses else 0.0
        long_trades = len([item for item in review_items if item.direction == "long"])
        short_trades = len([item for item in review_items if item.direction == "short"])
        long_pnl = sum(item.pnl for item in review_items if item.direction == "long")
        short_pnl = sum(item.pnl for item in review_items if item.direction == "short")
        avg_holding_bars = sum(item.holding_bars for item in review_items) / total_trades if total_trades else 0.0
        manual_trades = len([item for item in review_items if item.is_manual])
        auto_trades = total_trades - manual_trades
        planned_trades = len([item for item in review_items if item.is_planned])
        stop_protected_trades = len([item for item in review_items if item.had_stop_protection])
        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0
        for trade in self.trades:
            if trade.pnl > 0:
                current_win_streak += 1
                current_loss_streak = 0
            elif trade.pnl < 0:
                current_loss_streak += 1
                current_win_streak = 0
            else:
                current_win_streak = 0
                current_loss_streak = 0
            max_win_streak = max(max_win_streak, current_win_streak)
            max_loss_streak = max(max_loss_streak, current_loss_streak)
        self.session.stats = SessionStats(
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            total_pnl=total_pnl,
            average_pnl=total_pnl / total_trades if total_trades else 0.0,
            profit_factor=(gross_profit / gross_loss) if gross_loss else (gross_profit if gross_profit else 0.0),
            max_drawdown=self.session.position.max_drawdown,
            average_win=average_win,
            average_loss=average_loss,
            payoff_ratio=(average_win / average_loss) if average_loss else (average_win if average_win else 0.0),
            expectancy=total_pnl / total_trades if total_trades else 0.0,
            long_trades=long_trades,
            short_trades=short_trades,
            long_pnl=long_pnl,
            short_pnl=short_pnl,
            avg_holding_bars=avg_holding_bars,
            max_win_streak=max_win_streak,
            max_loss_streak=max_loss_streak,
            trades_with_stop_rate=(stop_protected_trades / total_trades) if total_trades else 0.0,
            manual_trades=manual_trades,
            auto_trades=auto_trades,
            planned_trades=planned_trades,
        )

    @staticmethod
    def _trade_exit_reason(action: SessionAction, remaining_quantity: float) -> str:
        if action.action_type is ActionType.REDUCE and remaining_quantity <= 0:
            return "reduce_to_flat"
        if not action.extra.get("auto"):
            return "manual_close"
        order_type = str(action.extra.get("order_type", ""))
        if order_type == OrderLineType.STOP_LOSS.value:
            return "stop_loss"
        if order_type == OrderLineType.TAKE_PROFIT.value:
            return "take_profit"
        if order_type == OrderLineType.REVERSE.value:
            return "reverse"
        if order_type == OrderLineType.EXIT.value:
            return "manual_close"
        if order_type == SESSION_END_FLATTEN_ORDER_TYPE:
            return SESSION_END_FLATTEN_ORDER_TYPE
        return "unknown"

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
        stop_line = self._select_display_protective_line(OrderLineType.STOP_LOSS)
        take_line = self._select_display_protective_line(OrderLineType.TAKE_PROFIT)
        self.session.position.stop_loss = stop_line.price if stop_line else None
        self.session.position.take_profit = take_line.price if take_line else None

    def _create_protective_line(self, order_type: OrderLineType, price: float, quantity: float, note: str = "") -> OrderLine:
        position = self.session.position
        if not position.is_open:
            raise ValueError("当前没有持仓，无法设置保护线。")
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
        return line

    def _remove_protective_lines(self) -> None:
        for line in self.order_lines:
            if line.is_active and line.is_protective:
                self._cancel_line(line)
        self._sync_position_from_lines()

    def _cancel_entry_lines(self) -> None:
        for line in self.order_lines:
            if line.is_active and line.is_entry:
                self._cancel_line(line)

    def _cancel_flattening_lines(self) -> None:
        for line in self.order_lines:
            if line.is_active and line.is_flattening:
                self._cancel_line(line)

    def _flatten_terminal_position_if_needed(self, flatten_at_session_end: bool) -> bool:
        if not flatten_at_session_end or not self.session.position.is_open:
            return False
        self._save_snapshot()
        self._close_position_for_session_end(self.current_bar)
        self._refresh_stats()
        return True

    def _close_position_for_session_end(self, bar: Bar) -> None:
        position = self.session.position
        if not position.is_open:
            return
        auto_action = SessionAction(
            action_type=ActionType.CLOSE,
            bar_index=self.session.current_index,
            timestamp=bar.timestamp,
            price=bar.close,
            quantity=position.quantity,
            note="Auto close at session end",
            extra={"auto": True, "order_type": SESSION_END_FLATTEN_ORDER_TYPE},
            session_id=self.session.id,
        )
        self._apply_action(auto_action)
        self.actions.append(auto_action)
        self._cancel_flattening_lines()
        self._update_drawdown(bar.close)

    @staticmethod
    def _is_last_bar_of_session(current_bar: Bar, next_bar: Bar) -> bool:
        return ReviewEngine._session_key(current_bar) != ReviewEngine._session_key(next_bar)

    @staticmethod
    def _session_key(bar: Bar) -> tuple[str, object]:
        bar_time = bar.timestamp.time()
        if bar_time >= NIGHT_SESSION_OPEN:
            return ("night", bar.timestamp.replace(hour=21, minute=0, second=0, microsecond=0))
        if bar_time >= DAY_SESSION_OPEN:
            return ("day", bar.timestamp.replace(hour=9, minute=0, second=0, microsecond=0))
        previous_day = bar.timestamp - timedelta(days=1)
        return ("night", previous_day.replace(hour=21, minute=0, second=0, microsecond=0))

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

    def _active_protective_lines(self, order_type: OrderLineType) -> list[OrderLine]:
        return [
            line
            for line in self.order_lines
            if line.order_type is order_type and line.is_active
        ]

    def _select_display_protective_line(self, order_type: OrderLineType) -> OrderLine | None:
        lines = self._active_protective_lines(order_type)
        if not lines:
            return None
        position = self.session.position
        if position.direction == "long":
            if order_type is OrderLineType.STOP_LOSS:
                return max(lines, key=lambda line: line.price)
            return min(lines, key=lambda line: line.price)
        if order_type is OrderLineType.STOP_LOSS:
            return min(lines, key=lambda line: line.price)
        return max(lines, key=lambda line: line.price)

    def _select_triggered_protective_line(self, order_type: OrderLineType, index: int, bar: Bar) -> OrderLine | None:
        position = self.session.position
        candidates = [
            line
            for line in self._active_protective_lines(order_type)
            if index >= line.active_from_bar_index
        ]
        if not candidates:
            return None
        if position.direction == "long":
            if order_type is OrderLineType.STOP_LOSS:
                hit_lines = [line for line in candidates if self._resolve_order_fill_price(line, index, bar) is not None]
                return max(hit_lines, key=lambda line: line.price, default=None)
            hit_lines = [line for line in candidates if self._resolve_order_fill_price(line, index, bar) is not None]
            return min(hit_lines, key=lambda line: line.price, default=None)
        if order_type is OrderLineType.STOP_LOSS:
            hit_lines = [line for line in candidates if self._resolve_order_fill_price(line, index, bar) is not None]
            return min(hit_lines, key=lambda line: line.price, default=None)
        hit_lines = [line for line in candidates if self._resolve_order_fill_price(line, index, bar) is not None]
        return max(hit_lines, key=lambda line: line.price, default=None)

    def _bar_contains_order_price(self, bar: Bar, order_price: float) -> bool:
        tick_size = max(float(self.session.tick_size), 0.0001)
        low = snap_price(min(float(bar.low), float(bar.high)), tick_size)
        high = snap_price(max(float(bar.low), float(bar.high)), tick_size)
        price = snap_price(float(order_price), tick_size)
        return low <= price <= high

    def _resolve_order_fill_price(self, line: OrderLine, index: int, bar: Bar) -> float | None:
        tick_size = max(float(self.session.tick_size), 0.0001)
        raw_order_price = float(line.price)
        if self._bar_contains_order_price(bar, raw_order_price):
            return raw_order_price
        if index <= 0:
            return None
        order_price = snap_price(raw_order_price, tick_size)
        previous_close = snap_price(float(self.bars[index - 1].close), tick_size)
        current_open = snap_price(float(bar.open), tick_size)
        lower = min(previous_close, current_open)
        upper = max(previous_close, current_open)
        if lower <= order_price <= upper and previous_close != current_open:
            return float(bar.open)
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
