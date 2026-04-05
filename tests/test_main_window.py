from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QGroupBox, QPushButton, QVBoxLayout

from barbybar.data.csv_importer import MissingColumnsError
from barbybar.data.tick_size import default_tick_size_for_symbol, format_price, price_decimals_for_tick
from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import ActionType, Bar, OrderLineType, PositionState, ReviewSession, SessionStats, SessionStatus, WindowBars
from barbybar.storage.repository import Repository
from barbybar.ui.main_window import DataSetManagerDialog, MainWindow, SessionLibraryDialog


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


def test_main_window_has_no_autoplay_controls(window: MainWindow) -> None:
    button_texts = {button.text() for button in window.findChildren(QPushButton)}
    assert "自动播放" not in button_texts
    assert not hasattr(window, "play_button")
    assert not hasattr(window, "speed_combo")


def test_main_window_uses_manager_buttons_instead_of_left_lists(window: MainWindow) -> None:
    button_texts = {button.text() for button in window.findChildren(QPushButton)}

    assert "导入 CSV" in button_texts
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
    assert "交易动作" not in group_titles
    assert "画线下单" not in group_titles
    assert "统计" not in group_titles


def test_main_window_uses_single_draw_order_entry(window: MainWindow) -> None:
    button_texts = {button.text() for button in window.findChildren(QPushButton)}

    assert "画线下单" not in button_texts
    assert "买" in button_texts
    assert "卖" in button_texts
    assert "平" in button_texts
    assert "反" in button_texts
    assert "取消画线下单" in button_texts
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


def test_order_preview_confirmed_uses_selected_quantity(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    captured: list[tuple[object, float, float]] = []

    def fake_place(order_type, price, quantity):
        captured.append((order_type, price, quantity))

    monkeypatch.setattr(window, "_place_order_line_with_quantity", fake_place)

    window._handle_order_preview_confirmed("entry_long", 102.5, 3.0)

    assert captured == [(OrderLineType.ENTRY_LONG, 102.5, 3.0)]


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


def test_import_csv_defaults_to_1m(monkeypatch, app: QApplication) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    csv_path = case_dir / "sample.csv"
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
    monkeypatch.setattr("barbybar.ui.main_window.QFileDialog.getOpenFileName", lambda *args, **kwargs: (str(csv_path), "CSV Files (*.csv)"))
    monkeypatch.setattr("barbybar.ui.main_window.QInputDialog.getText", lambda *args, **kwargs: ("IF", True))

    window.import_csv()

    datasets = repo.list_datasets()
    assert len(datasets) == 1
    assert datasets[0].timeframe == "1m"
    window.close()
    window.deleteLater()
    app.processEvents()


def test_import_csv_opens_mapping_dialog_for_missing_columns(monkeypatch, app: QApplication) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    csv_path = case_dir / "sample.csv"
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

    monkeypatch.setattr("barbybar.ui.main_window.QFileDialog.getOpenFileName", lambda *args, **kwargs: (str(csv_path), "CSV Files (*.csv)"))
    monkeypatch.setattr("barbybar.ui.main_window.QInputDialog.getText", lambda *args, **kwargs: ("IF", True))
    monkeypatch.setattr("barbybar.ui.main_window.ColumnMappingDialog", FakeDialog)

    window.import_csv()

    datasets = repo.list_datasets()
    assert len(datasets) == 1
    assert datasets[0].timeframe == "1m"
    window.close()
    window.deleteLater()
    app.processEvents()


def test_import_csv_cancel_mapping_does_not_write_dataset(monkeypatch, app: QApplication) -> None:
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

    def fake_import_csv(path, symbol, timeframe, field_map=None):
        if field_map is None:
            raise MissingColumnsError(
                available_headers=["date", "open", "high", "low", "close", "size"],
                missing_fields=["datetime", "volume"],
                detected_field_map={"open": "open", "high": "high", "low": "low", "close": "close"},
            )
        raise AssertionError("manual mapping should not run after cancel")

    monkeypatch.setattr("barbybar.ui.main_window.QFileDialog.getOpenFileName", lambda *args, **kwargs: ("dummy.csv", "CSV Files (*.csv)"))
    monkeypatch.setattr("barbybar.ui.main_window.QInputDialog.getText", lambda *args, **kwargs: ("IF", True))
    monkeypatch.setattr("barbybar.ui.main_window.ColumnMappingDialog", FakeDialog)
    monkeypatch.setattr(repo, "import_csv", fake_import_csv)

    window.import_csv()

    assert repo.list_datasets() == []
    window.close()
    window.deleteLater()
    app.processEvents()
