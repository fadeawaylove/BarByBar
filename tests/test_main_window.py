from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QGroupBox, QMessageBox, QPushButton, QVBoxLayout

from barbybar.data.csv_importer import MissingColumnsError
from barbybar.data.tick_size import default_tick_size_for_symbol, format_price, price_decimals_for_tick
from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import ActionType, Bar, ChartDrawing, DrawingAnchor, DrawingToolType, OrderLineType, PositionState, ReviewSession, SessionStats, SessionStatus, WindowBars
from barbybar.storage.repository import Repository
from barbybar.ui.chart_widget import InteractionMode
from barbybar.ui.main_window import DataSetManagerDialog, DrawingPropertiesDialog, MainWindow, SessionLibraryDialog


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


@pytest.fixture(scope="module")
def app() -> QApplication:
    return _app()


@pytest.fixture()
def window(app: QApplication) -> MainWindow:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    repo = Repository(case_dir / "barbybar.db")
    start = datetime(2025, 1, 1, 9, 0)
    csv_path = case_dir / "sample.csv"
    lines = ["datetime,open,high,low,close,volume"]
    for index in range(180):
        ts = start + timedelta(minutes=index)
        price = 100 + index * 0.1
        lines.append(f"{ts:%Y-%m-%d %H:%M:%S},{price:.2f},{price + 1:.2f},{price - 1:.2f},{price + 0.2:.2f},{1000 + index}")
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    repo.import_csv(csv_path, "IF", "1m")
    main_window = MainWindow(repo)
    yield main_window
    main_window.close()
    main_window.deleteLater()
    app.processEvents()


def _seed_engine(window: MainWindow) -> None:
    bars = [
        Bar(
            timestamp=datetime(2025, 1, 1, 9, index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100.5 + index,
            volume=1000 + index,
        )
        for index in range(60)
    ]
    session = ReviewSession(
        id=1,
        dataset_id=1,
        symbol="IF",
        timeframe="1m",
        chart_timeframe="1m",
        start_index=0,
        current_index=25,
        current_bar_time=bars[25].timestamp,
        status=SessionStatus.ACTIVE,
        title="Test session",
        notes="",
        tags=[],
        position=PositionState(),
        stats=SessionStats(),
        created_at=bars[0].timestamp,
        updated_at=bars[0].timestamp,
    )
    window.engine = ReviewEngine(session, bars, window_start_index=0, total_count=len(bars))
    window.current_session_id = 1


def _wait_for_loaded_session(app: QApplication, window: MainWindow, timeout_s: float = 5.0) -> None:
    started = perf_counter()
    while perf_counter() - started < timeout_s:
        app.processEvents()
        if window.engine is not None and window.current_session_id is not None:
            return
    raise AssertionError("session did not load in time")


def test_main_window_uses_timeframe_shortcut_buttons(window: MainWindow) -> None:
    assert set(window.timeframe_buttons) == {"1m", "5m", "15m", "30m", "60m"}


def test_main_window_exposes_drawing_toolbar_buttons(window: MainWindow) -> None:
    assert set(window._drawing_tool_buttons) == {
        DrawingToolType.TREND_LINE,
        DrawingToolType.RAY,
        DrawingToolType.FIB_RETRACEMENT,
        DrawingToolType.HORIZONTAL_LINE,
        DrawingToolType.RECTANGLE,
        DrawingToolType.TEXT,
    }
    for button in window._drawing_tool_buttons.values():
        assert button.icon().isNull() is False
        assert button.text() == ""
        assert button.minimumWidth() >= 48 or button.width() >= 48
        assert button.minimumHeight() >= 36 or button.height() >= 36


def test_main_window_has_no_autoplay_controls(window: MainWindow) -> None:
    button_texts = {button.text() for button in window.findChildren(QPushButton)}
    assert "自动播放" not in button_texts
    assert not hasattr(window, "play_button")
    assert not hasattr(window, "speed_combo")


def test_main_window_uses_manager_buttons_instead_of_left_lists(window: MainWindow) -> None:
    button_texts = {button.text() for button in window.findChildren(QPushButton)}

    assert "导入 CSV" not in button_texts
    assert "数据集" in button_texts
    assert "案例库" in button_texts
    assert not hasattr(window, "dataset_list")
    assert not hasattr(window, "session_list")


def test_manager_dialogs_include_delete_actions(window: MainWindow) -> None:
    dataset_dialog = DataSetManagerDialog(window.repo, window)
    session_dialog = SessionLibraryDialog(window.repo, window)
    try:
        dataset_buttons = {button.text() for button in dataset_dialog.findChildren(QPushButton)}
        session_buttons = {button.text() for button in session_dialog.findChildren(QPushButton)}

        assert "删除所选数据集" in dataset_buttons
        assert "导入单个 CSV" in dataset_buttons
        assert "导入文件夹" in dataset_buttons
        assert "删除所选案例" in session_buttons
    finally:
        dataset_dialog.close()
        dataset_dialog.deleteLater()
        session_dialog.close()
        session_dialog.deleteLater()


def test_main_window_removes_session_info_panel(window: MainWindow) -> None:
    group_titles = {group.title() for group in window.findChildren(QGroupBox)}
    assert "会话信息" not in group_titles
    assert "交易" in group_titles
    assert "训练统计" in group_titles
    assert "历史交易" not in group_titles


def test_main_window_uses_single_draw_order_entry(window: MainWindow) -> None:
    button_texts = {button.text() for button in window.findChildren(QPushButton)}

    assert "画线模式" not in button_texts
    assert "买" in button_texts
    assert "卖" in button_texts
    assert "平" in button_texts
    assert "反" in button_texts
    assert "取消画线下单" in button_texts
    drawing_tooltips = {button.toolTip() for button in window._drawing_tool_buttons.values()}
    assert drawing_tooltips == {"线段", "箭头线", "斐波那契", "水平线", "矩形", "文字"}
    for button in window._drawing_tool_buttons.values():
        assert button.text() == ""
        assert button.icon().isNull() is False
    assert "图上开多线" not in button_texts
    assert "图上开空线" not in button_texts
    assert "加仓" not in button_texts
    assert "减仓" not in button_texts


def test_right_panel_uses_compact_trade_layout(window: MainWindow) -> None:
    assert window.splitter.count() == 2
    assert window.splitter.sizes()[1] <= 260
    assert window.stats_label.text().startswith("方向 ")


def test_right_panel_uses_vertical_trade_layout(window: MainWindow) -> None:
    trade_group = next(group for group in window.findChildren(QGroupBox) if group.title() == "交易")
    trade_layout = trade_group.layout()

    assert isinstance(trade_layout, QVBoxLayout)
    assert window.splitter.widget(1).maximumWidth() <= 260

    button_texts = [button.text() for button in trade_group.findChildren(QPushButton)]
    for label in ["开多", "开空", "立即平仓", "买", "卖", "平", "反", "取消画线下单"]:
        assert label in button_texts


def test_timeframe_buttons_render_above_chart(window: MainWindow) -> None:
    center_panel = window.splitter.widget(0)
    layout = center_panel.layout()

    assert layout.itemAt(0).layout() is not None
    assert layout.itemAt(1).widget() is window.chart_widget


def test_toolbar_separates_timeframes_from_drawing_buttons(window: MainWindow) -> None:
    center_panel = window.splitter.widget(0)
    toolbar = center_panel.layout().itemAt(0).layout()

    assert toolbar is not None
    assert toolbar.count() == 3
    assert toolbar.itemAt(0).layout() is not None
    assert toolbar.itemAt(1).spacerItem() is not None
    assert toolbar.itemAt(2).layout() is not None


def test_main_window_autoloads_most_recent_session(app: QApplication) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    repo = Repository(case_dir / "barbybar.db")
    start = datetime(2025, 1, 1, 9, 0)
    csv_path = case_dir / "sample.csv"
    lines = ["datetime,open,high,low,close,volume"]
    for index in range(180):
        ts = start + timedelta(minutes=index)
        price = 100 + index * 0.1
        lines.append(f"{ts:%Y-%m-%d %H:%M:%S},{price:.2f},{price + 1:.2f},{price - 1:.2f},{price + 0.2:.2f},{1000 + index}")
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    dataset = repo.import_csv(csv_path, "IF", "1m")
    session = repo.create_session(dataset.id or 0, start_index=10)
    session.current_index = 12
    session.current_bar_time = start + timedelta(minutes=12)
    repo.save_session(session, [], [])

    main_window = MainWindow(repo)
    try:
        _wait_for_loaded_session(app, main_window)
        assert main_window.current_session_id == session.id
        assert main_window.engine is not None
        assert main_window.engine.session.current_index == 12
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()


def test_draw_order_controls_sync_position_state(window: MainWindow) -> None:
    _seed_engine(window)

    window._sync_draw_order_controls()

    assert window._draw_order_buttons[OrderLineType.EXIT].isEnabled() is False
    assert window._draw_order_buttons[OrderLineType.REVERSE].isEnabled() is False

    window.engine.record_action(ActionType.OPEN_LONG, quantity=1, price=101)
    window._sync_draw_order_controls()

    assert window._draw_order_buttons[OrderLineType.EXIT].isEnabled() is True
    assert window._draw_order_buttons[OrderLineType.REVERSE].isEnabled() is True


def test_update_ui_from_engine_syncs_trade_markers(window: MainWindow) -> None:
    _seed_engine(window)
    window.chart_widget.set_window_data(
        window.engine.bars,
        window.engine.session.current_index,
        window.engine.total_count,
        window.engine.window_start_index,
    )
    window.engine.record_action(ActionType.OPEN_LONG, quantity=1, price=101)
    window.engine.record_action(ActionType.CLOSE, quantity=1, price=103)

    window._update_ui_from_engine()

    assert len(window.chart_widget._trade_markers) == 2
    assert len(window.chart_widget._trade_links) == 1


def test_trade_marker_visibility_toggle_updates_chart_widget(window: MainWindow) -> None:
    _seed_engine(window)

    window.show_trade_markers_check.setChecked(False)
    window.show_trade_links_check.setChecked(False)

    assert window.chart_widget._trade_markers_visible is False
    assert window.chart_widget._trade_links_visible is False


def test_order_preview_confirmed_uses_selected_quantity(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    captured: list[tuple[object, float, float]] = []

    def fake_place(order_type, price, quantity):
        captured.append((order_type, price, quantity))

    monkeypatch.setattr(window, "_place_order_line_with_quantity", fake_place)

    window._handle_order_preview_confirmed("entry_long", 102.5, 3.0)

    assert captured == [(OrderLineType.ENTRY_LONG, 102.5, 3.0)]


def test_clicking_drawing_tool_updates_chart_widget(window: MainWindow) -> None:
    window._toggle_drawing_tool(DrawingToolType.HORIZONTAL_LINE, True)

    assert window.chart_widget.active_drawing_tool is DrawingToolType.HORIZONTAL_LINE
    assert window._drawing_tool_buttons[DrawingToolType.HORIZONTAL_LINE].isChecked() is True
    assert window.chart_widget.interaction_mode is InteractionMode.DRAWING


def test_completed_drawing_unchecks_toolbar_button(window: MainWindow) -> None:
    window._toggle_drawing_tool(DrawingToolType.HORIZONTAL_LINE, True)

    window.chart_widget._consume_drawing_click(DrawingAnchor(10.0, 100.0))

    assert window.chart_widget.active_drawing_tool is None
    assert window._drawing_tool_buttons[DrawingToolType.HORIZONTAL_LINE].isChecked() is False
    assert window.chart_widget.interaction_mode is InteractionMode.BROWSE


def test_clear_lines_schedules_auto_save(window: MainWindow) -> None:
    _seed_engine(window)
    window.chart_widget.set_drawings([])
    window.chart_widget.set_active_drawing_tool(DrawingToolType.HORIZONTAL_LINE)
    window.chart_widget._consume_drawing_click(DrawingAnchor(10.0, 100.0))
    window._session_dirty = False
    window._auto_save_timer.stop()

    window.chart_widget.clear_lines()

    assert window._session_dirty is True
    assert window._auto_save_timer.isActive()
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_confirm_clear_drawings_cancels_without_side_effect(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    window.chart_widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.HORIZONTAL_LINE, anchors=[DrawingAnchor(10.0, 100.0)])])
    monkeypatch.setattr("barbybar.ui.main_window.QMessageBox.warning", lambda *args, **kwargs: QMessageBox.StandardButton.No)
    window._session_dirty = False
    window._auto_save_timer.stop()

    window.confirm_clear_drawings()

    assert len(window.chart_widget.drawings()) == 1
    assert window._session_dirty is False
    assert window._auto_save_timer.isActive() is False


def test_confirm_clear_drawings_confirms_and_clears(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    window.chart_widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.HORIZONTAL_LINE, anchors=[DrawingAnchor(10.0, 100.0)])])
    monkeypatch.setattr("barbybar.ui.main_window.QMessageBox.warning", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    window._session_dirty = False
    window._auto_save_timer.stop()

    window.confirm_clear_drawings()

    assert window.chart_widget.drawings() == []
    assert window._session_dirty is True
    assert window._auto_save_timer.isActive() is True
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_order_preview_cancel_resets_button_state(window: MainWindow) -> None:
    _seed_engine(window)

    window._toggle_draw_order_preview(OrderLineType.ENTRY_LONG, True)
    assert window._draw_order_buttons[OrderLineType.ENTRY_LONG].isChecked() is True

    window.chart_widget.cancel_order_preview()

    assert window._draw_order_buttons[OrderLineType.ENTRY_LONG].isChecked() is False
    assert window.chart_widget.interaction_mode is InteractionMode.BROWSE


def test_order_preview_activation_clears_active_drawing_tool(window: MainWindow) -> None:
    _seed_engine(window)
    window._toggle_drawing_tool(DrawingToolType.TREND_LINE, True)

    window._toggle_draw_order_preview(OrderLineType.ENTRY_LONG, True)

    assert window.chart_widget.active_drawing_tool is None
    assert window._drawing_tool_buttons[DrawingToolType.TREND_LINE].isChecked() is False
    assert window.chart_widget.interaction_mode is InteractionMode.ORDER_PREVIEW


def test_drawing_properties_request_updates_style_and_marks_session_dirty(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    window.chart_widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TREND_LINE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(12.0, 101.0)])])
    window._session_dirty = False
    window._auto_save_timer.stop()

    class _FakeDialog:
        def __init__(self, drawing, parent):
            self.drawing = drawing

        def exec(self):
            return QDialog.DialogCode.Accepted

        def style_payload(self):
            return {"color": "#3366ff", "width": 3, "line_style": "dash"}

    monkeypatch.setattr("barbybar.ui.main_window.DrawingPropertiesDialog", _FakeDialog)

    window._handle_drawing_properties_requested(window.chart_widget.drawings()[0], 0)

    assert window.chart_widget.drawings()[0].style["color"] == "#3366ff"
    assert window.chart_widget.drawings()[0].style["width"] == 3
    assert window._session_dirty is True
    assert window._auto_save_timer.isActive() is True
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_text_drawing_cancel_with_empty_text_deletes_placeholder(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    window.chart_widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TEXT, anchors=[DrawingAnchor(10.0, 100.0)], style={"text": ""})])
    window._session_dirty = False
    window._auto_save_timer.stop()

    class _FakeDialog:
        def __init__(self, drawing, parent):
            self.drawing = drawing

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("barbybar.ui.main_window.DrawingPropertiesDialog", _FakeDialog)

    window._handle_drawing_properties_requested(window.chart_widget.drawings()[0], 0)

    assert window.chart_widget.drawings() == []
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_text_drawing_dialog_focuses_text_input(app: QApplication) -> None:
    dialog = DrawingPropertiesDialog(
        ChartDrawing(tool_type=DrawingToolType.TEXT, anchors=[DrawingAnchor(10.0, 100.0)], style={"text": ""})
    )
    dialog.show()
    app.processEvents()

    assert dialog.text_edit.hasFocus() is True

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_clear_current_session_resets_to_browse_mode(window: MainWindow) -> None:
    window._toggle_drawing_tool(DrawingToolType.TREND_LINE, True)

    window._clear_current_session()

    assert window.chart_widget.interaction_mode is InteractionMode.BROWSE
    assert all(button.isChecked() is False for button in window._drawing_tool_buttons.values())
    assert all(button.isChecked() is False for button in window._draw_order_buttons.values())


def test_tick_size_defaults_from_symbol(window: MainWindow) -> None:
    _seed_engine(window)
    window.engine.session.symbol = "IF"
    window.engine.session.tick_size = default_tick_size_for_symbol("IF")

    window._update_ui_from_engine()

    assert window.tick_size_spin.value() == 0.2


def test_trade_action_price_defaults_to_latest_close(window: MainWindow) -> None:
    _seed_engine(window)

    window._update_ui_from_engine()

    assert window.price_spin.value() == 126.0


def test_update_ui_populates_training_stats_and_trade_history(window: MainWindow) -> None:
    _seed_engine(window)
    window.chart_widget.set_window_data(
        window.engine.bars,
        window.engine.session.current_index,
        window.engine.total_count,
        window.engine.window_start_index,
    )
    window.engine.record_action(ActionType.OPEN_LONG, quantity=1, price=125.5)
    window.engine.record_action(ActionType.SET_STOP_LOSS, price=124.5)
    window.engine.step_forward()
    window.engine.step_forward()
    window.engine.record_action(ActionType.CLOSE, quantity=1, price=128.5)

    window._update_ui_from_engine()

    assert "Expectancy" in window.training_stats_label.text()
    assert window.open_trade_history_button.isEnabled() is True

    window.open_trade_history_dialog()

    assert window._trade_history_dialog is not None
    assert window._trade_history_dialog.trade_history_list.count() == 1
    assert window._trade_history_dialog.trade_history_list.item(0).data(Qt.ItemDataRole.UserRole) == 1


def test_trade_history_click_and_toggle_jump_between_entry_and_exit(window: MainWindow) -> None:
    _seed_engine(window)
    window.chart_widget.set_window_data(
        window.engine.bars,
        window.engine.session.current_index,
        window.engine.total_count,
        window.engine.window_start_index,
    )
    entry_index = window.engine.session.current_index
    window.engine.record_action(ActionType.OPEN_LONG, quantity=1, price=125.5)
    window.engine.record_action(ActionType.SET_STOP_LOSS, price=124.5)
    window.engine.step_forward()
    window.engine.step_forward()
    exit_index = window.engine.session.current_index
    window.engine.record_action(ActionType.CLOSE, quantity=1, price=128.5)
    window._update_ui_from_engine()
    window.open_trade_history_dialog()

    assert window._trade_history_dialog is not None
    item = window._trade_history_dialog.trade_history_list.item(0)
    window._trade_history_dialog._handle_item_clicked(item)

    assert window.chart_widget._cursor == entry_index
    assert window.chart_widget._focused_trade_points is None
    assert window._trade_history_dialog.trade_history_toggle_button.text() == "切换到出场"

    window._trade_history_dialog._toggle_selected_trade_focus()

    assert window.chart_widget._cursor == exit_index
    assert window._trade_history_dialog.trade_history_toggle_button.text() == "切换到入场"


def test_tick_size_change_snaps_price_input(window: MainWindow) -> None:
    _seed_engine(window)
    window.price_spin.setValue(5914.62)

    window._handle_tick_size_changed(1.0)

    assert window.price_spin.value() == 126.0
    assert window.price_spin.decimals() == 0
    window._session_dirty = False
    window._auto_save_timer.stop()


def test_tick_size_decimals_follow_tick_size(window: MainWindow) -> None:
    _seed_engine(window)

    window._handle_tick_size_changed(0.2)
    assert window.price_spin.decimals() == 1

    window._handle_tick_size_changed(0.02)
    assert window.price_spin.decimals() == 2
    window._session_dirty = False
    window._auto_save_timer.stop()


def test_tick_format_helpers_cap_at_two_decimals() -> None:
    assert price_decimals_for_tick(1) == 0
    assert price_decimals_for_tick(0.2) == 1
    assert price_decimals_for_tick(0.02) == 2
    assert format_price(5915, 1) == "5915"
    assert format_price(5914.2, 0.2) == "5914.2"
    assert format_price(5914.02, 0.02) == "5914.02"


def test_busy_overlay_show_and_hide(window: MainWindow) -> None:
    window.show_busy_overlay("正在加载案例...", "正在读取数据并构建图表")

    assert window._busy_overlay is not None
    assert not window._busy_overlay.isHidden()
    assert window._busy_overlay.title_label.text() == "正在加载案例..."
    assert QApplication.overrideCursor() is not None

    window.hide_busy_overlay()

    assert window._busy_overlay.isHidden()
    assert QApplication.overrideCursor() is None


def test_navigation_schedules_auto_save(window: MainWindow) -> None:
    _seed_engine(window)

    window.step_forward()

    assert window._session_dirty is True
    assert window._auto_save_timer.isActive()
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_flush_pending_auto_save_persists_session(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    calls: list[str] = []

    def fake_save_session(*, trigger: str = "manual") -> None:
        calls.append(trigger)
        window._session_dirty = False
        window._auto_save_timer.stop()

    monkeypatch.setattr(window, "save_session", fake_save_session)
    window._session_dirty = True
    window._auto_save_timer.start(5000)

    window._flush_pending_auto_save("change_chart_timeframe")

    assert calls == ["auto_flush:change_chart_timeframe"]
    assert not window._auto_save_timer.isActive()


def test_order_line_context_price_edit_snaps_value(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    line = window.engine.place_order_line(OrderLineType.ENTRY_LONG, price=100.5, quantity=1)
    line.id = 101
    window.engine.session.tick_size = 0.2
    monkeypatch.setattr(window, "save_session", lambda **kwargs: None)

    monkeypatch.setattr("barbybar.ui.main_window.QInputDialog.getDouble", lambda *args, **kwargs: (100.73, True))

    window._handle_order_line_action_requested(101, "edit_price")

    updated = next(item for item in window.engine.active_order_lines if item.id == 101)
    assert updated.price == 100.8


def test_order_line_context_quantity_edit_uses_integer(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    line = window.engine.place_order_line(OrderLineType.ENTRY_LONG, price=100.5, quantity=1)
    line.id = 202
    monkeypatch.setattr(window, "save_session", lambda **kwargs: None)

    monkeypatch.setattr("barbybar.ui.main_window.QInputDialog.getInt", lambda *args, **kwargs: (3, True))

    window._handle_order_line_action_requested(202, "edit_quantity")

    updated = next(item for item in window.engine.active_order_lines if item.id == 202)
    assert updated.quantity == 3


def test_order_line_context_delete_cancels_line(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    line = window.engine.place_order_line(OrderLineType.ENTRY_LONG, price=100.5, quantity=1)
    line.id = 303
    monkeypatch.setattr(window, "save_session", lambda **kwargs: None)

    window._handle_order_line_action_requested(303, "delete")

    assert all(item.id != 303 or item.is_active is False for item in window.engine.order_lines)


def test_handle_chart_protective_order_created_places_protective_line(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    window.engine.record_action(ActionType.OPEN_LONG, quantity=1, price=101)
    captured: list[tuple[OrderLineType, float]] = []
    monkeypatch.setattr(window, "_place_order_line", lambda order_type, price: captured.append((order_type, price)))

    window._handle_chart_protective_order_created(OrderLineType.TAKE_PROFIT.value, 104.2)

    assert captured == [(OrderLineType.TAKE_PROFIT, 104.2)]


def test_place_order_line_saves_before_refreshing_chart(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    window.quantity_spin.setValue(1)
    call_order: list[str] = []
    order_ids_seen_by_chart: list[list[int | None]] = []

    def fake_save_session(*, trigger: str = "manual") -> None:
        call_order.append(f"save:{trigger}")
        for index, line in enumerate(window.engine.order_lines, start=1):
            if line.id is None and line.order_type is not OrderLineType.AVERAGE_PRICE:
                line.id = index

    def fake_update_ui_from_engine() -> None:
        call_order.append("update_ui")
        order_ids_seen_by_chart.append([line.id for line in window.engine.display_order_lines()])

    monkeypatch.setattr(window, "save_session", fake_save_session)
    monkeypatch.setattr(window, "_update_ui_from_engine", fake_update_ui_from_engine)

    window._place_order_line_with_quantity(OrderLineType.ENTRY_LONG, 100.5, 1)

    assert call_order == ["save:place_order_line:entry_long", "update_ui"]
    assert order_ids_seen_by_chart == [[1]]


def test_busy_overlay_becomes_visible_when_window_is_shown(window: MainWindow, app: QApplication) -> None:
    window.show()
    window.show_busy_overlay("正在加载案例...", "正在读取数据并构建图表")
    app.processEvents()

    assert window._busy_overlay is not None
    assert window._busy_overlay.isVisible()


def test_busy_overlay_covers_entire_main_workspace(window: MainWindow) -> None:
    window.resize(1400, 900)
    window.show_busy_overlay("正在加载案例...", "正在读取数据并构建图表")

    assert window._busy_overlay is not None
    assert window._busy_overlay.geometry() == window.centralWidget().rect()


def test_set_timeframe_choices_does_not_trigger_replay_bar_loading(window: MainWindow, monkeypatch) -> None:
    def fail_get_replay_bars(*args, **kwargs):
        raise AssertionError("get_replay_bars should not be called when only updating button states")

    monkeypatch.setattr(window.repo, "get_replay_bars", fail_get_replay_bars)

    window._set_timeframe_choices("1m", "5m")

    assert window.timeframe_buttons["1m"].isEnabled()
    assert window.timeframe_buttons["5m"].isChecked()


def test_import_csv_folder_imports_valid_files_and_skips_duplicate_by_display_name(monkeypatch, app: QApplication) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    folder = case_dir / "batch"
    folder.mkdir()
    valid_a = folder / "AG9999.XSGE_2025_1_1_2025_4_30_1min.csv"
    valid_b = folder / "sample.csv"
    content = "\n".join(
        [
            "datetime,open,high,low,close,volume",
            "2025-01-01 09:00:00,100,101,99,100.5,1000",
            "2025-01-01 09:01:00,100.5,101.5,100,101,1100",
        ]
    )
    for path in [valid_a, valid_b]:
        path.write_text(content, encoding="utf-8")
    repo = Repository(case_dir / "import.db")
    repo.import_csv(valid_a, "AG9999", "1m", display_name=valid_a.name)
    window = MainWindow(repo)
    captured: list[str] = []
    monkeypatch.setattr("barbybar.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(folder))
    monkeypatch.setattr("barbybar.ui.main_window.QMessageBox.information", lambda *args: captured.append(args[2]))

    window.import_csv_folder()

    datasets = repo.list_datasets()
    assert [dataset.display_name for dataset in datasets] == ["sample.csv", valid_a.name]
    assert len(captured) == 1
    assert "成功导入 1 个数据集" in captured[0]
    assert f"已导入: {valid_b.name}" in captured[0]
    assert f"重复跳过: {valid_a.name}" in captured[0]
    window.close()
    window.deleteLater()
    app.processEvents()


def test_import_csv_folder_uses_mapping_for_missing_columns(monkeypatch, app: QApplication) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    folder = case_dir / "batch"
    folder.mkdir()
    csv_path = folder / "date_based.csv"
    csv_path.write_text(
        "\n".join(
            [
                "date,open,high,low,close,size",
                "2025-01-01 09:00:00,100,101,99,100.5,1000",
                "2025-01-01 09:01:00,100.5,101.5,100,101,1100",
            ]
        ),
        encoding="utf-8",
    )
    repo = Repository(case_dir / "import.db")
    window = MainWindow(repo)

    class FakeDialog:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_field_map(self):
            return {
                "datetime": "date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "size",
            }

    monkeypatch.setattr("barbybar.ui.main_window.ColumnMappingDialog", FakeDialog)

    dataset = window._import_csv_with_mapping(str(csv_path), "DATE", "1m", display_name=csv_path.name)

    assert dataset is not None
    assert dataset.display_name == csv_path.name
    assert repo.list_datasets()[0].display_name == csv_path.name
    window.close()
    window.deleteLater()
    app.processEvents()


def test_import_csv_folder_cancel_mapping_does_not_write_dataset(monkeypatch, app: QApplication) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    repo = Repository(case_dir / "import.db")
    window = MainWindow(repo)

    class FakeDialog:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def exec(self):
            return QDialog.DialogCode.Rejected

        def get_field_map(self):
            return {}

    def fake_import_csv(path, symbol, timeframe, field_map=None, *, display_name=None):
        if field_map is None:
            raise MissingColumnsError(
                available_headers=["date", "open", "high", "low", "close", "size"],
                missing_fields=["datetime", "volume"],
                detected_field_map={"open": "open", "high": "high", "low": "low", "close": "close"},
            )
        raise AssertionError("manual mapping should not run after cancel")

    monkeypatch.setattr("barbybar.ui.main_window.ColumnMappingDialog", FakeDialog)
    monkeypatch.setattr(repo, "import_csv", fake_import_csv)

    result = window._import_csv_with_mapping("dummy.csv", "IF", "1m", display_name="dummy.csv")

    assert result is None
    assert repo.list_datasets() == []
    window.close()
    window.deleteLater()
    app.processEvents()


def test_dataset_manager_filters_by_display_name_and_symbol(window: MainWindow) -> None:
    csv_a = Path("C:/code/BarByBar/.pytest-temp") / f"{uuid4().hex}-ag.csv"
    csv_b = Path("C:/code/BarByBar/.pytest-temp") / f"{uuid4().hex}-if.csv"
    csv_a.write_text("datetime,open,high,low,close,volume\n2025-01-01 09:00:00,1,2,0.5,1.5,10\n", encoding="utf-8")
    csv_b.write_text("datetime,open,high,low,close,volume\n2025-01-01 09:00:00,2,3,1.5,2.5,20\n", encoding="utf-8")
    window.repo.import_csv(csv_a, "AG9999", "1m", display_name="silver-contract.csv")
    window.repo.import_csv(csv_b, "IF", "1m", display_name="index-contract.csv")

    dataset_dialog = DataSetManagerDialog(window.repo, window)
    try:
        assert dataset_dialog.dataset_list.count() == 3

        dataset_dialog.dataset_filter.setText("silver")
        assert dataset_dialog.dataset_list.count() == 1
        assert "silver-contract.csv" in dataset_dialog.dataset_list.item(0).text()

        dataset_dialog.dataset_filter.setText("ag9999")
        assert dataset_dialog.dataset_list.count() == 1
        assert "silver-contract.csv" in dataset_dialog.dataset_list.item(0).text()

        dataset_dialog.dataset_filter.setText("")
        assert dataset_dialog.dataset_list.count() == 3
    finally:
        dataset_dialog.close()
        dataset_dialog.deleteLater()


def test_import_csv_imports_single_file_and_uses_busy_overlay(monkeypatch, app: QApplication) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    csv_path = case_dir / "AG9999.single.csv"
    csv_path.write_text(
        "\n".join(
            [
                "datetime,open,high,low,close,volume",
                "2025-01-01 09:00:00,100,101,99,100.5,1000",
                "2025-01-01 09:01:00,100.5,101.5,100,101,1100",
            ]
        ),
        encoding="utf-8",
    )
    repo = Repository(case_dir / "import.db")
    window = MainWindow(repo)
    shown: list[tuple[str, str]] = []
    hidden: list[bool] = []
    monkeypatch.setattr("barbybar.ui.main_window.QFileDialog.getOpenFileName", lambda *args, **kwargs: (str(csv_path), "CSV Files (*.csv)"))
    monkeypatch.setattr(window, "show_busy_overlay", lambda title, detail="": shown.append((title, detail)))
    monkeypatch.setattr(window, "hide_busy_overlay", lambda: hidden.append(True))

    window.import_csv()

    datasets = repo.list_datasets()
    assert len(datasets) == 1
    assert datasets[0].display_name == "AG9999.single.csv"
    assert shown == [("正在导入 CSV...", "正在读取并校验数据")]
    assert hidden == [True]
    window.close()
    window.deleteLater()
    app.processEvents()


def test_import_csv_skips_duplicate_display_name(monkeypatch, app: QApplication) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    csv_path = case_dir / "dup.csv"
    csv_path.write_text(
        "\n".join(
            [
                "datetime,open,high,low,close,volume",
                "2025-01-01 09:00:00,100,101,99,100.5,1000",
            ]
        ),
        encoding="utf-8",
    )
    repo = Repository(case_dir / "import.db")
    repo.import_csv(csv_path, "DUP", "1m", display_name="dup.csv")
    window = MainWindow(repo)
    messages: list[str] = []
    shown: list[tuple[str, str]] = []
    hidden: list[bool] = []
    monkeypatch.setattr("barbybar.ui.main_window.QFileDialog.getOpenFileName", lambda *args, **kwargs: (str(csv_path), "CSV Files (*.csv)"))
    monkeypatch.setattr("barbybar.ui.main_window.QMessageBox.information", lambda *args: messages.append(args[2]))
    monkeypatch.setattr(window, "show_busy_overlay", lambda title, detail="": shown.append((title, detail)))
    monkeypatch.setattr(window, "hide_busy_overlay", lambda: hidden.append(True))

    window.import_csv()

    assert repo.list_datasets()[0].display_name == "dup.csv"
    assert messages == ["同名文件已存在: dup.csv"]
    assert shown == []
    assert hidden == []
    window.close()
    window.deleteLater()
    app.processEvents()


def test_import_csv_folder_uses_busy_overlay(monkeypatch, app: QApplication) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    folder = case_dir / "batch"
    folder.mkdir()
    csv_path = folder / "sample.csv"
    csv_path.write_text(
        "\n".join(
            [
                "datetime,open,high,low,close,volume",
                "2025-01-01 09:00:00,100,101,99,100.5,1000",
                "2025-01-01 09:01:00,100.5,101.5,100,101,1100",
            ]
        ),
        encoding="utf-8",
    )
    repo = Repository(case_dir / "import.db")
    window = MainWindow(repo)
    shown: list[tuple[str, str]] = []
    hidden: list[bool] = []
    monkeypatch.setattr("barbybar.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(folder))
    monkeypatch.setattr("barbybar.ui.main_window.QMessageBox.information", lambda *args, **kwargs: None)
    monkeypatch.setattr(window, "show_busy_overlay", lambda title, detail="": shown.append((title, detail)))
    monkeypatch.setattr(window, "hide_busy_overlay", lambda: hidden.append(True))

    window.import_csv_folder()

    assert shown == [("正在批量导入...", "正在逐个读取 CSV，请稍候")]
    assert hidden == [True]
    window.close()
    window.deleteLater()
    app.processEvents()
