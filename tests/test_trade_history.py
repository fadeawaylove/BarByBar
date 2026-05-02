from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import Qt

from barbybar.domain.models import TradeReviewItem
from barbybar.ui.trade_history import (
    TRADE_HISTORY_COLUMNS,
    TradeHistoryFilters,
    TradeHistoryTableModel,
    TradeReviewController,
    format_exit_reason,
)


def _trade(
    trade_number: int,
    *,
    direction: str = "long",
    pnl: float = 1.0,
    exit_reason: str = "手动平仓",
    holding_bars: int = 3,
    stop: bool = False,
    adverse_add: bool = False,
    planned: bool = False,
) -> TradeReviewItem:
    entry_time = datetime(2025, 1, 1, 9, 0) + timedelta(minutes=trade_number)
    return TradeReviewItem(
        trade_number=trade_number,
        entry_time=entry_time,
        exit_time=entry_time + timedelta(minutes=holding_bars),
        direction=direction,
        quantity=1,
        entry_price=100 + trade_number,
        exit_price=100 + trade_number + pnl,
        pnl=pnl,
        entry_bar_index=trade_number,
        exit_bar_index=trade_number + holding_bars,
        holding_bars=holding_bars,
        exit_reason=exit_reason,
        is_manual=True,
        had_stop_protection=stop,
        had_adverse_add=adverse_add,
        is_planned=planned,
        entry_note="入场计划",
        review_note="复盘记录",
    )


def test_trade_history_model_normalizes_rows_for_table_and_detail() -> None:
    model = TradeHistoryTableModel([
        _trade(1, direction="short", pnl=-2.5, stop=True, planned=True),
    ])

    assert model.rowCount() == 1
    assert model.columnCount() == len(TRADE_HISTORY_COLUMNS)
    assert model.data(model.index(0, 0)) == "1"
    assert model.data(model.index(0, 1)) == "空"
    assert model.data(model.index(0, 6)) == "-2.50"
    assert model.data(model.index(0, 0), Qt.ItemDataRole.UserRole) == 1

    detail = model.rows()[0].detail_text
    assert "交易 #1" in detail
    assert "亏损" in detail
    assert "止损" in detail
    assert "执行概览" in detail
    assert model.rows()[0].entry_note == "入场计划"
    assert model.rows()[0].review_note == "复盘记录"


def test_trade_history_model_returns_item_for_clicked_index() -> None:
    first = _trade(1)
    second = _trade(2)
    model = TradeHistoryTableModel([first, second])

    item = model.trade_item_at(model.index(0, 0))

    assert item is second
    assert item.exit_bar_index == second.exit_bar_index
    assert model.trade_item_at(model.index(-1, 0)) is None


def test_trade_history_exit_reason_formats_engine_codes_as_chinese() -> None:
    model = TradeHistoryTableModel([
        _trade(1, exit_reason="stop_loss"),
    ])

    assert format_exit_reason("manual_close") == "手动平仓"
    assert format_exit_reason("stop_loss") == "止损触发"
    assert model.data(model.index(0, 7)) == "止损触发"
    assert "出场原因：止损触发" in model.rows()[0].detail_text


def test_trade_history_model_sorts_by_supported_keys() -> None:
    model = TradeHistoryTableModel([
        _trade(1, pnl=2.0, holding_bars=5),
        _trade(3, pnl=-1.0, holding_bars=2),
        _trade(2, pnl=5.0, holding_bars=8),
    ])

    assert model.trade_numbers() == [3, 2, 1]

    model.set_sort_key("pnl_desc")
    assert model.trade_numbers() == [2, 1, 3]

    model.set_sort_key("holding_asc")
    assert model.trade_numbers() == [3, 1, 2]


def test_trade_history_model_filters_and_clears_filters() -> None:
    model = TradeHistoryTableModel([
        _trade(1, direction="long", pnl=-2.0, exit_reason="止损", stop=True, planned=False),
        _trade(2, direction="short", pnl=4.0, exit_reason="目标", stop=False, planned=True),
        _trade(3, direction="long", pnl=0.0, exit_reason="手动", adverse_add=True, planned=True),
    ])

    model.set_filters(TradeHistoryFilters(direction="long", outcome="loss", exit_reason="止损", had_stop_protection=True))
    assert model.trade_numbers() == [1]

    model.set_filters(TradeHistoryFilters(is_planned=True, min_pnl=0.0))
    assert model.trade_numbers() == [3, 2]

    model.clear_filters()
    assert model.trade_numbers() == [3, 2, 1]


def test_trade_history_controller_preserves_or_resets_selection_deterministically() -> None:
    controller = TradeReviewController()

    controller.select_trade(2, focus_mode="entry")
    assert controller.refresh_selection([3, 2, 1], [1, 2, 3]) == 2
    assert controller.focus_mode == "entry"

    assert controller.refresh_selection([3, 1], [1, 2, 3]) == 2
    assert controller.selected_trade_number == 2

    assert controller.refresh_selection([3, 1], [1, 3]) == 3
    assert controller.selected_trade_number == 3

    assert controller.toggle_entry_exit() == "exit"
    controller.set_focus_mode("entry")
    assert controller.focus_mode == "entry"
