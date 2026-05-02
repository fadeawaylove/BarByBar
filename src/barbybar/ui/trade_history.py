from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from barbybar.domain.models import TradeReviewItem

TradeFocusMode = Literal["entry", "exit"]


@dataclass(frozen=True, slots=True)
class TradeHistoryColumn:
    key: str
    title: str
    alignment: Qt.AlignmentFlag


TRADE_HISTORY_COLUMNS: tuple[TradeHistoryColumn, ...] = (
    TradeHistoryColumn("trade_number", "#", Qt.AlignmentFlag.AlignCenter),
    TradeHistoryColumn("direction", "方向", Qt.AlignmentFlag.AlignCenter),
    TradeHistoryColumn("entry_time", "入场", Qt.AlignmentFlag.AlignLeft),
    TradeHistoryColumn("exit_time", "出场", Qt.AlignmentFlag.AlignLeft),
    TradeHistoryColumn("holding_bars", "持仓", Qt.AlignmentFlag.AlignRight),
    TradeHistoryColumn("quantity", "数量", Qt.AlignmentFlag.AlignRight),
    TradeHistoryColumn("pnl", "PnL", Qt.AlignmentFlag.AlignRight),
    TradeHistoryColumn("exit_reason", "原因", Qt.AlignmentFlag.AlignLeft),
    TradeHistoryColumn("flags", "标记", Qt.AlignmentFlag.AlignLeft),
)

EXIT_REASON_LABELS: dict[str, str] = {
    "manual_close": "手动平仓",
    "reduce_to_flat": "减仓至空仓",
    "stop_loss": "止损触发",
    "take_profit": "止盈触发",
    "reverse": "反手触发",
    "session_end_flatten": "案例结束平仓",
    "unknown": "未知原因",
}


def format_exit_reason(exit_reason: str | None) -> str:
    if not exit_reason:
        return "-"
    return EXIT_REASON_LABELS.get(exit_reason, exit_reason)


@dataclass(frozen=True, slots=True)
class TradeHistoryFilters:
    direction: str = "all"
    outcome: str = "all"
    exit_reason: str = "all"
    had_stop_protection: bool | None = None
    had_adverse_add: bool | None = None
    is_planned: bool | None = None
    min_holding_bars: int | None = None
    max_holding_bars: int | None = None
    min_pnl: float | None = None
    max_pnl: float | None = None

    def is_empty(self) -> bool:
        return self == TradeHistoryFilters()


@dataclass(frozen=True, slots=True)
class TradeHistoryRow:
    item: TradeReviewItem

    @classmethod
    def from_item(cls, item: TradeReviewItem) -> TradeHistoryRow:
        return cls(item=item)

    @property
    def trade_number(self) -> int:
        return self.item.trade_number

    @property
    def direction_text(self) -> str:
        return "多" if self.item.direction == "long" else "空"

    @property
    def outcome(self) -> str:
        if self.item.pnl > 0:
            return "win"
        if self.item.pnl < 0:
            return "loss"
        return "flat"

    @property
    def quantity_text(self) -> str:
        if float(self.item.quantity).is_integer():
            return str(int(self.item.quantity))
        return f"{self.item.quantity:.2f}".rstrip("0").rstrip(".")

    @property
    def flags_text(self) -> str:
        flags: list[str] = []
        if self.item.had_stop_protection:
            flags.append("止损")
        if self.item.had_adverse_add:
            flags.append("亏损加仓")
        if self.item.is_planned:
            flags.append("计划")
        if self.item.is_manual:
            flags.append("手动")
        return " / ".join(flags) if flags else "-"

    @property
    def detail_text(self) -> str:
        return "\n".join(
            [
                f"交易 #{self.item.trade_number} · {self.direction_text} · {self.outcome_text}",
                f"入场 {self.item.entry_time:%Y-%m-%d %H:%M} @ {self.item.entry_price:.2f}",
                f"出场 {self.item.exit_time:%Y-%m-%d %H:%M} @ {self.item.exit_price:.2f}",
                f"PnL {self.item.pnl:.2f} · 数量 {self.quantity_text} 手 · 持仓 {self.item.holding_bars} bars",
                f"出场原因：{format_exit_reason(self.item.exit_reason)}",
                f"执行标记：{self.flags_text}",
                f"执行概览：{self.action_summary}",
            ]
        )

    @property
    def entry_note(self) -> str:
        return self.item.entry_note

    @property
    def review_note(self) -> str:
        return self.item.review_note

    @property
    def outcome_text(self) -> str:
        if self.outcome == "win":
            return "盈利"
        if self.outcome == "loss":
            return "亏损"
        return "持平"

    @property
    def action_summary(self) -> str:
        protection = "有止损保护" if self.item.had_stop_protection else "无止损保护"
        plan = "按计划" if self.item.is_planned else "未标记计划"
        adverse = "出现亏损加仓" if self.item.had_adverse_add else "无亏损加仓"
        return f"{plan}，{protection}，{adverse}"

    def display_value(self, key: str) -> str:
        if key == "trade_number":
            return str(self.item.trade_number)
        if key == "direction":
            return self.direction_text
        if key == "entry_time":
            return self.item.entry_time.strftime("%m-%d %H:%M")
        if key == "exit_time":
            return self.item.exit_time.strftime("%m-%d %H:%M")
        if key == "holding_bars":
            return str(self.item.holding_bars)
        if key == "quantity":
            return self.quantity_text
        if key == "pnl":
            return f"{self.item.pnl:.2f}"
        if key == "exit_reason":
            return format_exit_reason(self.item.exit_reason)
        if key == "flags":
            return self.flags_text
        return ""


class TradeHistoryTableModel(QAbstractTableModel):
    def __init__(self, items: list[TradeReviewItem] | None = None) -> None:
        super().__init__()
        self._all_rows: list[TradeHistoryRow] = []
        self._rows: list[TradeHistoryRow] = []
        self._sort_key = "time_desc"
        self._filters = TradeHistoryFilters()
        if items:
            self.set_items(items)

    @property
    def filters(self) -> TradeHistoryFilters:
        return self._filters

    @property
    def sort_key(self) -> str:
        return self._sort_key

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(TRADE_HISTORY_COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        column = TRADE_HISTORY_COLUMNS[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return row.display_value(column.key)
        if role == Qt.ItemDataRole.UserRole:
            return row.trade_number
        if role == Qt.ItemDataRole.ToolTipRole:
            return row.detail_text
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(column.alignment | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole and column.key == "pnl":
            if row.item.pnl > 0:
                return QColor("#1a7f37")
            if row.item.pnl < 0:
                return QColor("#c62828")
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(TRADE_HISTORY_COLUMNS):
            return TRADE_HISTORY_COLUMNS[section].title
        return str(section + 1)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if not 0 <= column < len(TRADE_HISTORY_COLUMNS):
            return
        key = TRADE_HISTORY_COLUMNS[column].key
        descending = order == Qt.SortOrder.DescendingOrder
        if key in {"entry_time", "exit_time"}:
            self.set_sort_key("time_desc" if descending else "time_asc")
        elif key == "pnl":
            self.set_sort_key("pnl_desc" if descending else "pnl_asc")
        elif key == "direction":
            self.set_sort_key("direction_desc" if descending else "direction")
        elif key == "holding_bars":
            self.set_sort_key("holding_desc" if descending else "holding_asc")
        elif key == "exit_reason":
            self.set_sort_key("reason_desc" if descending else "reason_asc")
        else:
            self.set_sort_key("trade_desc" if descending else "trade_asc")

    def set_items(self, items: list[TradeReviewItem]) -> None:
        self.beginResetModel()
        self._all_rows = [TradeHistoryRow.from_item(item) for item in items]
        self._rows = self._sorted_rows(self._filtered_rows(self._all_rows))
        self.endResetModel()

    def set_sort_key(self, sort_key: str | None) -> None:
        self.beginResetModel()
        self._sort_key = sort_key or "time_desc"
        self._rows = self._sorted_rows(self._filtered_rows(self._all_rows))
        self.endResetModel()

    def set_filters(self, filters: TradeHistoryFilters) -> None:
        self.beginResetModel()
        self._filters = filters
        self._rows = self._sorted_rows(self._filtered_rows(self._all_rows))
        self.endResetModel()

    def clear_filters(self) -> None:
        self.set_filters(TradeHistoryFilters())

    def rows(self) -> list[TradeHistoryRow]:
        return list(self._rows)

    def all_rows(self) -> list[TradeHistoryRow]:
        return list(self._all_rows)

    def exit_reasons(self) -> list[str]:
        return sorted({row.item.exit_reason for row in self._all_rows if row.item.exit_reason})

    def trade_numbers(self) -> list[int]:
        return [row.trade_number for row in self._rows]

    def row_for_trade(self, trade_number: int) -> TradeHistoryRow | None:
        return next((row for row in self._rows if row.trade_number == trade_number), None)

    def row_index_for_trade(self, trade_number: int) -> int | None:
        for index, row in enumerate(self._rows):
            if row.trade_number == trade_number:
                return index
        return None

    def all_row_for_trade(self, trade_number: int) -> TradeHistoryRow | None:
        return next((row for row in self._all_rows if row.trade_number == trade_number), None)

    def trade_number_at(self, row_index: int) -> int | None:
        if not 0 <= row_index < len(self._rows):
            return None
        return self._rows[row_index].trade_number

    def trade_item_at(self, index: QModelIndex) -> TradeReviewItem | None:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()].item

    def _filtered_rows(self, rows: list[TradeHistoryRow]) -> list[TradeHistoryRow]:
        filters = self._filters
        return [row for row in rows if _matches_filters(row, filters)]

    def _sorted_rows(self, rows: list[TradeHistoryRow]) -> list[TradeHistoryRow]:
        return sorted(rows, key=lambda row: _sort_value(row, self._sort_key), reverse=_sort_reverse(self._sort_key))


class TradeReviewController:
    def __init__(self) -> None:
        self.selected_trade_number: int | None = None
        self.focus_mode: TradeFocusMode = "exit"
        self.filters = TradeHistoryFilters()

    def select_trade(self, trade_number: int | None, *, focus_mode: TradeFocusMode | None = None) -> None:
        self.selected_trade_number = trade_number
        if focus_mode is not None:
            self.focus_mode = focus_mode

    def set_focus_mode(self, focus_mode: TradeFocusMode) -> None:
        self.focus_mode = focus_mode

    def toggle_entry_exit(self) -> TradeFocusMode:
        self.focus_mode = "exit" if self.focus_mode == "entry" else "entry"
        return self.focus_mode

    def set_filters(self, filters: TradeHistoryFilters) -> None:
        self.filters = filters

    def refresh_selection(self, visible_trade_numbers: list[int], all_trade_numbers: list[int]) -> int | None:
        if self.selected_trade_number in visible_trade_numbers:
            return self.selected_trade_number
        if self.selected_trade_number in all_trade_numbers:
            return self.selected_trade_number
        self.selected_trade_number = visible_trade_numbers[0] if visible_trade_numbers else None
        return self.selected_trade_number


def _matches_filters(row: TradeHistoryRow, filters: TradeHistoryFilters) -> bool:
    item = row.item
    if filters.direction != "all" and item.direction != filters.direction:
        return False
    if filters.outcome != "all" and row.outcome != filters.outcome:
        return False
    if filters.exit_reason != "all" and item.exit_reason != filters.exit_reason:
        return False
    if filters.had_stop_protection is not None and item.had_stop_protection != filters.had_stop_protection:
        return False
    if filters.had_adverse_add is not None and item.had_adverse_add != filters.had_adverse_add:
        return False
    if filters.is_planned is not None and item.is_planned != filters.is_planned:
        return False
    if filters.min_holding_bars is not None and item.holding_bars < filters.min_holding_bars:
        return False
    if filters.max_holding_bars is not None and item.holding_bars > filters.max_holding_bars:
        return False
    if filters.min_pnl is not None and item.pnl < filters.min_pnl:
        return False
    if filters.max_pnl is not None and item.pnl > filters.max_pnl:
        return False
    return True


def _sort_value(row: TradeHistoryRow, sort_key: str) -> tuple[object, ...]:
    item = row.item
    if sort_key in {"time_asc", "time_desc"}:
        return (_datetime_sort_value(item.entry_time), item.trade_number)
    if sort_key in {"pnl_asc", "pnl_desc"}:
        return (item.pnl, _datetime_sort_value(item.exit_time), item.trade_number)
    if sort_key in {"direction", "direction_desc"}:
        return (item.direction, _datetime_sort_value(item.entry_time), item.trade_number)
    if sort_key in {"holding_asc", "holding_desc"}:
        return (item.holding_bars, _datetime_sort_value(item.exit_time), item.trade_number)
    if sort_key in {"reason_asc", "reason_desc"}:
        return (item.exit_reason or "", _datetime_sort_value(item.exit_time), item.trade_number)
    if sort_key in {"trade_asc", "trade_desc"}:
        return (item.trade_number,)
    return (_datetime_sort_value(item.entry_time), item.trade_number)


def _sort_reverse(sort_key: str) -> bool:
    return sort_key in {"time_desc", "pnl_desc", "direction_desc", "holding_desc", "reason_desc", "trade_desc"}


def _datetime_sort_value(value: datetime) -> float:
    return value.timestamp()
