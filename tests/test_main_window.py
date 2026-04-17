import json
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QDialog, QGroupBox, QLabel, QLineEdit, QPushButton, QVBoxLayout

from barbybar import paths
from barbybar.data.csv_importer import MissingColumnsError
from barbybar.data.tick_size import default_tick_size_for_symbol, format_price, price_decimals_for_tick
from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import ActionType, Bar, ChartDrawing, DrawingAnchor, DrawingTemplate, DrawingToolType, OrderLineType, PositionState, ReviewSession, SessionAction, SessionStats, SessionStatus, WindowBars
from barbybar.storage.repository import Repository
from barbybar.ui.chart_widget import InteractionMode
from barbybar.ui.main_window import (
    BatchImportOutcome,
    BatchImportProgress,
    ColumnMappingDialog,
    DataSetManagerDialog,
    DrawingPropertiesDialog,
    DrawingTemplateDialog,
    MainWindow,
    SessionLibraryDialog,
    UpdateActionDialog,
)
from barbybar.update_service import UpdateInfo


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class _FakeSceneClick:
    def __init__(self, scene_pos: QPointF, button: Qt.MouseButton = Qt.MouseButton.LeftButton) -> None:
        self._scene_pos = scene_pos
        self._button = button
        self._accepted = False

    def scenePos(self):
        return self._scene_pos

    def button(self):
        return self._button

    def accept(self) -> None:
        self._accepted = True


@pytest.fixture(scope="module")
def app() -> QApplication:
    return _app()


@pytest.fixture()
def window(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(case_dir / "app-data"))
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


def _wait_for_batch_import(app: QApplication, window: MainWindow, timeout_s: float = 5.0) -> None:
    started = perf_counter()
    while perf_counter() - started < timeout_s:
        app.processEvents()
        thread = window._active_batch_import_thread
        if thread is None or not thread.isRunning():
            return
    raise AssertionError("batch import did not finish in time")


def test_main_window_uses_timeframe_shortcut_buttons(window: MainWindow) -> None:
    assert set(window.timeframe_buttons) == {"5m", "15m", "30m", "60m", "1d"}


def test_main_window_exposes_bar_count_toggle_button(window: MainWindow) -> None:
    assert window.bar_count_toggle_button is not None
    assert window.bar_count_toggle_button.text() == "K线序号"
    assert window.bar_count_toggle_button.isCheckable() is True
    assert window.bar_count_toggle_button.isChecked() is True
    assert window.chart_widget.bar_count_labels_visible is True


def test_main_window_exposes_hide_drawings_toggle_button(window: MainWindow) -> None:
    assert window.hide_drawings_toggle_button is not None
    assert window.hide_drawings_toggle_button.text() == "隐藏画线"
    assert window.hide_drawings_toggle_button.isCheckable() is True
    assert window.hide_drawings_toggle_button.isChecked() is False
    assert window.chart_widget.drawings_hidden is False


def test_main_window_exposes_flatten_at_session_end_toggle_button(window: MainWindow) -> None:
    assert window.flatten_at_session_end_toggle_button is not None
    assert window.flatten_at_session_end_toggle_button.text() == "不过夜"
    assert window.flatten_at_session_end_toggle_button.isCheckable() is True
    assert window.flatten_at_session_end_toggle_button.isChecked() is True


def test_main_window_exposes_six_drawing_template_buttons(window: MainWindow) -> None:
    assert set(window._drawing_template_buttons) == {1, 2, 3, 4, 5, 6}
    assert [window._drawing_template_buttons[index].text() for index in range(1, 7)] == [
        "模板1",
        "模板2",
        "模板3",
        "模板4",
        "模板5",
        "模板6",
    ]
    assert all(window._drawing_template_buttons[index].isEnabled() is False for index in range(1, 7))


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


def test_drawing_toolbar_places_arrow_line_immediately_after_trend_line(window: MainWindow) -> None:
    buttons = list(window._drawing_tool_buttons)
    assert buttons == [
        DrawingToolType.TREND_LINE,
        DrawingToolType.RAY,
        DrawingToolType.FIB_RETRACEMENT,
        DrawingToolType.HORIZONTAL_LINE,
        DrawingToolType.RECTANGLE,
        DrawingToolType.TEXT,
    ]


def test_main_window_has_no_autoplay_controls(window: MainWindow) -> None:
    button_texts = {button.text() for button in window.findChildren(QPushButton)}
    assert "自动播放" not in button_texts
    assert not hasattr(window, "play_button")
    assert not hasattr(window, "speed_combo")


def test_main_window_exposes_check_update_button(window: MainWindow) -> None:
    assert window.check_update_button is not None
    assert window.check_update_button.text() == "检查更新"


def test_main_window_uses_manager_buttons_instead_of_left_lists(window: MainWindow) -> None:
    button_texts = {button.text() for button in window.findChildren(QPushButton)}

    assert "导入 CSV" not in button_texts
    assert "数据集" in button_texts
    assert "案例库" in button_texts
    assert "检查更新" in button_texts
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
    assert toolbar.count() == 4
    assert toolbar.itemAt(0).widget() is window._timeframe_toolbar_group
    assert toolbar.itemAt(1).widget() is window._template_toolbar_group
    assert toolbar.itemAt(2).spacerItem() is not None
    assert toolbar.itemAt(3).widget() is window._drawing_toolbar_group


def test_toolbar_uses_distinct_group_widgets_for_timeframe_template_and_drawing(window: MainWindow) -> None:
    center_panel = window.splitter.widget(0)
    toolbar = center_panel.layout().itemAt(0).layout()

    assert window._timeframe_toolbar_group is not None
    assert window._template_toolbar_group is not None
    assert window._drawing_toolbar_group is not None
    assert toolbar.itemAt(0).widget() is not window._template_toolbar_group
    assert toolbar.itemAt(1).widget() is not window._drawing_toolbar_group


def test_toolbar_groups_do_not_render_title_labels(window: MainWindow) -> None:
    for group in [window._timeframe_toolbar_group, window._template_toolbar_group, window._drawing_toolbar_group]:
        assert group is not None
        assert not any(
            child.property("toolbarGroupTitle") is True
            for child in group.findChildren(QLabel)
        )


def test_bar_count_toggle_button_is_placed_beside_clear_drawings(window: MainWindow) -> None:
    center_panel = window.splitter.widget(0)
    controls = center_panel.layout().itemAt(2).layout()

    assert controls is not None
    clear_index = next(index for index in range(controls.count()) if controls.itemAt(index).widget() is window.clear_lines_button)
    assert controls.itemAt(clear_index + 1).widget() is window.bar_count_toggle_button
    assert controls.itemAt(clear_index + 2).widget() is window.hide_drawings_toggle_button
    assert controls.itemAt(clear_index + 3).widget() is window.flatten_at_session_end_toggle_button


def test_dataset_session_and_update_buttons_are_placed_before_prev_button(window: MainWindow) -> None:
    center_panel = window.splitter.widget(0)
    controls = center_panel.layout().itemAt(2).layout()

    assert controls is not None
    prev_index = next(index for index in range(controls.count()) if controls.itemAt(index).widget() is window.prev_button)
    leading_widgets = [controls.itemAt(index).widget() for index in range(prev_index)]

    assert leading_widgets == [window.dataset_button, window.session_button, window.check_update_button]


def test_main_window_loads_bar_count_toggle_from_global_ui_settings(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(case_dir / "app-data"))
    paths.default_ui_settings_path().write_text('{"bar_count_labels_visible": false}', encoding="utf-8")
    repo = Repository(case_dir / "barbybar.db")
    main_window = MainWindow(repo)
    try:
        assert main_window.bar_count_toggle_button.isChecked() is False
        assert main_window.chart_widget.bar_count_labels_visible is False
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()


def test_main_window_loads_flatten_toggle_from_global_ui_settings(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(case_dir / "app-data"))
    paths.default_ui_settings_path().write_text('{"flatten_at_session_end_enabled": false}', encoding="utf-8")
    repo = Repository(case_dir / "barbybar.db")
    main_window = MainWindow(repo)
    try:
        assert main_window.flatten_at_session_end_toggle_button.isChecked() is False
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()


def test_main_window_loads_hide_drawings_toggle_from_global_ui_settings(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(case_dir / "app-data"))
    paths.default_ui_settings_path().write_text('{"drawings_hidden": true}', encoding="utf-8")
    repo = Repository(case_dir / "barbybar.db")
    main_window = MainWindow(repo)
    try:
        assert main_window.hide_drawings_toggle_button.isChecked() is True
        assert main_window.chart_widget.drawings_hidden is True
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()


def test_main_window_defaults_bar_count_toggle_to_enabled_when_ui_settings_missing(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(case_dir / "app-data"))
    repo = Repository(case_dir / "barbybar.db")
    main_window = MainWindow(repo)
    try:
        assert main_window.bar_count_toggle_button.isChecked() is True
        assert main_window.chart_widget.bar_count_labels_visible is True
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()


def test_main_window_falls_back_to_enabled_when_ui_settings_is_invalid(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(case_dir / "app-data"))
    paths.default_ui_settings_path().write_text("{broken", encoding="utf-8")
    repo = Repository(case_dir / "barbybar.db")
    main_window = MainWindow(repo)
    try:
        assert main_window.bar_count_toggle_button.isChecked() is True
        assert main_window.chart_widget.bar_count_labels_visible is True
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()


def test_toggling_bar_count_button_persists_global_ui_setting(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(case_dir / "app-data"))
    repo = Repository(case_dir / "barbybar.db")
    main_window = MainWindow(repo)
    try:
        main_window.bar_count_toggle_button.click()
        saved = json.loads(paths.default_ui_settings_path().read_text(encoding="utf-8"))
        assert saved["bar_count_labels_visible"] is False
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()

    reloaded_window = MainWindow(repo)
    try:
        assert reloaded_window.bar_count_toggle_button.isChecked() is False
        assert reloaded_window.chart_widget.bar_count_labels_visible is False
    finally:
        reloaded_window.close()
        reloaded_window.deleteLater()
        app.processEvents()


def test_toggling_flatten_toggle_persists_global_ui_setting(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(case_dir / "app-data"))
    repo = Repository(case_dir / "barbybar.db")
    main_window = MainWindow(repo)
    try:
        main_window.flatten_at_session_end_toggle_button.click()
        saved = json.loads(paths.default_ui_settings_path().read_text(encoding="utf-8"))
        assert saved["flatten_at_session_end_enabled"] is False
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()

    reloaded_window = MainWindow(repo)
    try:
        assert reloaded_window.flatten_at_session_end_toggle_button.isChecked() is False
    finally:
        reloaded_window.close()
        reloaded_window.deleteLater()
        app.processEvents()


def test_toggling_hide_drawings_button_persists_global_ui_setting(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(case_dir / "app-data"))
    repo = Repository(case_dir / "barbybar.db")
    main_window = MainWindow(repo)
    try:
        main_window.hide_drawings_toggle_button.click()
        saved = json.loads(paths.default_ui_settings_path().read_text(encoding="utf-8"))
        assert saved["drawings_hidden"] is True
        assert main_window.chart_widget.drawings_hidden is True
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()

    reloaded_window = MainWindow(repo)
    try:
        assert reloaded_window.hide_drawings_toggle_button.isChecked() is True
        assert reloaded_window.chart_widget.drawings_hidden is True
    finally:
        reloaded_window.close()
        reloaded_window.deleteLater()
        app.processEvents()


def test_top_area_does_not_keep_empty_top_bar_spacing(window: MainWindow) -> None:
    center_panel = window.splitter.widget(0)
    layout = center_panel.layout()

    assert layout.contentsMargins().top() <= 2
    assert layout.spacing() <= 4


def test_toolbar_group_margins_are_compact(window: MainWindow) -> None:
    for group in [window._timeframe_toolbar_group, window._template_toolbar_group, window._drawing_toolbar_group]:
        assert group is not None
        margins = group.layout().contentsMargins()
        assert margins.top() <= 4
        assert margins.bottom() <= 4


def test_set_timeframe_choices_supports_1d(window: MainWindow) -> None:
    window._set_timeframe_choices("1m", "1d")

    assert window.timeframe_buttons["1d"].isEnabled()
    assert window.timeframe_buttons["1d"].isChecked()


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
        assert main_window.engine.session.chart_timeframe == "5m"
        assert main_window.engine.session.current_bar_time == start + timedelta(minutes=12)
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()


def test_main_window_reopens_with_last_selected_chart_timeframe(app: QApplication) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    repo = Repository(case_dir / "barbybar.db")
    start = datetime(2025, 1, 1, 9, 0)
    csv_path = case_dir / "sample.csv"
    lines = ["datetime,open,high,low,close,volume"]
    for index in range(480):
        ts = start + timedelta(minutes=index)
        price = 100 + index * 0.1
        lines.append(f"{ts:%Y-%m-%d %H:%M:%S},{price:.2f},{price + 1:.2f},{price - 1:.2f},{price + 0.2:.2f},{1000 + index}")
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    dataset = repo.import_csv(csv_path, "IF", "1m")
    session = repo.create_session(dataset.id or 0, start_index=10)
    repo.save_session(session, [], [])

    first_window = MainWindow(repo)
    try:
        _wait_for_loaded_session(app, first_window)
        assert first_window.engine is not None
        first_window.change_chart_timeframe("60m")
        started = perf_counter()
        while perf_counter() - started < 5.0:
            app.processEvents()
            if first_window.engine is not None and first_window.engine.session.chart_timeframe == "60m":
                break
        assert first_window.engine is not None
        assert first_window.engine.session.chart_timeframe == "60m"
    finally:
        first_window.close()
        first_window.deleteLater()
        app.processEvents()

    reopened_window = MainWindow(repo)
    try:
        _wait_for_loaded_session(app, reopened_window)
        assert reopened_window.engine is not None
        assert reopened_window.engine.session.chart_timeframe == "60m"
        assert reopened_window.timeframe_buttons["60m"].isChecked()
    finally:
        reopened_window.close()
        reopened_window.deleteLater()
        app.processEvents()


def test_main_window_restores_drawing_style_presets_from_saved_session(app: QApplication) -> None:
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
    session.drawing_style_presets = {
        DrawingToolType.RECTANGLE.value: {"color": "#3366ff", "width": 3, "fill_color": "#3366ff", "fill_opacity": 0.35},
        DrawingToolType.TEXT.value: {"text": "", "font_size": 18, "text_color": "#3366ff", "color": "#3366ff"},
    }
    repo.save_session(session, [], [])

    main_window = MainWindow(repo)
    try:
        _wait_for_loaded_session(app, main_window)
        rectangle_style = main_window.chart_widget.drawing_style_preset(DrawingToolType.RECTANGLE)
        text_style = main_window.chart_widget.drawing_style_preset(DrawingToolType.TEXT)
        assert rectangle_style["color"] == "#3366ff"
        assert rectangle_style["width"] == 3
        assert rectangle_style["fill_opacity"] == 0.35
        assert text_style["font_size"] == 18
        assert text_style["text_color"] == "#3366ff"
        assert text_style["text"] == ""
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()


def test_main_window_autoloads_last_opened_session_even_without_new_save(app: QApplication) -> None:
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
    saved_session = repo.create_session(dataset.id or 0, start_index=10, title="已保存案例")
    saved_session.current_index = 12
    saved_session.current_bar_time = start + timedelta(minutes=12)
    repo.save_session(saved_session, [], [])
    opened_session = repo.create_session(dataset.id or 0, start_index=30, title="最后打开案例")
    repo.conn.execute(
        "UPDATE sessions SET last_opened_at = ? WHERE id = ?",
        ("2025-01-01T00:00:00", saved_session.id),
    )
    repo.conn.execute(
        "UPDATE sessions SET last_opened_at = ? WHERE id = ?",
        ("2025-01-01T00:00:00", opened_session.id),
    )
    repo.conn.commit()

    first_window = MainWindow(repo)
    try:
        _wait_for_loaded_session(app, first_window)
        first_window._load_session(opened_session.id or 0)
        _wait_for_loaded_session(app, first_window)
        assert first_window.current_session_id == opened_session.id
    finally:
        first_window.close()
        first_window.deleteLater()
        app.processEvents()

    reopened_window = MainWindow(repo)
    try:
        _wait_for_loaded_session(app, reopened_window)
        assert reopened_window.current_session_id == opened_session.id
        assert reopened_window.engine is not None
        assert reopened_window.engine.session.title == "最后打开案例"
    finally:
        reopened_window.close()
        reopened_window.deleteLater()
        app.processEvents()


def test_main_window_loads_global_drawing_templates_from_store(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(case_dir / "app-data"))
    templates_path = paths.default_drawing_templates_path()
    templates_path.write_text(
        '{"templates":{"2":{"slot":2,"tool_type":"rectangle","note":"阻力区","style":{"color":"#3366ff","width":3,"fill_opacity":0.35}}}}',
        encoding="utf-8",
    )
    repo = Repository(case_dir / "barbybar.db")
    main_window = MainWindow(repo)
    try:
        button = main_window._drawing_template_buttons[2]
        assert button.isEnabled() is True
        assert button.text() == "阻力区"
        assert "矩形" in button.toolTip()
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()


def test_main_window_ignores_invalid_global_drawing_template_store(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = Path("C:/code/BarByBar/.pytest-temp")
    temp_root.mkdir(exist_ok=True)
    case_dir = temp_root / uuid4().hex
    case_dir.mkdir()
    monkeypatch.setenv(paths.APP_DIR_ENV_VAR, str(case_dir / "app-data"))
    paths.default_drawing_templates_path().write_text("{broken", encoding="utf-8")
    repo = Repository(case_dir / "barbybar.db")
    main_window = MainWindow(repo)
    try:
        assert all(button.isEnabled() is False for button in main_window._drawing_template_buttons.values())
    finally:
        main_window.close()
        main_window.deleteLater()
        app.processEvents()


def test_clicking_drawing_template_button_activates_tool_and_style(window: MainWindow) -> None:
    window._drawing_templates[1] = DrawingTemplate(
        slot=1,
        tool_type=DrawingToolType.RECTANGLE,
        note="阻力区",
        style={"color": "#3366ff", "width": 3, "fill_color": "#3366ff", "fill_opacity": 0.35},
    )
    window._refresh_drawing_template_buttons()

    window._drawing_template_buttons[1].click()

    assert window.chart_widget.active_drawing_tool is DrawingToolType.RECTANGLE
    assert window._drawing_template_buttons[1].isChecked() is True
    assert window._drawing_tool_buttons[DrawingToolType.RECTANGLE].isChecked() is False
    preset = window.chart_widget.drawing_style_preset(DrawingToolType.RECTANGLE)
    assert preset["color"] == "#3366ff"
    assert preset["width"] == 3
    assert preset["fill_opacity"] == 0.35


def test_saving_drawing_template_updates_buttons_and_store(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(DrawingTemplateDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(DrawingTemplateDialog, "template_slot", lambda self: 2)
    monkeypatch.setattr(DrawingTemplateDialog, "template_note", lambda self: "阻力区")
    monkeypatch.setattr(DrawingTemplateDialog, "clear_requested", lambda self: False)

    original_save = window._save_global_drawing_templates

    def _capture_save() -> None:
        original_save()
        captured["content"] = window._drawing_templates_path.read_text(encoding="utf-8")

    monkeypatch.setattr(window, "_save_global_drawing_templates", _capture_save)

    drawing = ChartDrawing(
        tool_type=DrawingToolType.RECTANGLE,
        anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(12.0, 103.0)],
        style={"color": "#3366ff", "width": 3, "fill_color": "#3366ff", "fill_opacity": 0.35},
    )

    window._handle_drawing_template_save_requested(drawing, 0)

    assert window._drawing_template_buttons[2].text() == "阻力区"
    assert '"tool_type": "rectangle"' in str(captured["content"])
    assert '"note": "阻力区"' in str(captured["content"])


def test_template_drawing_auto_exits_after_completion(window: MainWindow, app: QApplication) -> None:
    _seed_engine(window)
    window.chart_widget.resize(900, 600)
    window.chart_widget.show()
    window._update_ui_from_engine()
    window._drawing_templates[1] = DrawingTemplate(
        slot=1,
        tool_type=DrawingToolType.RECTANGLE,
        note="阻力区",
        style={"color": "#3366ff", "width": 3, "fill_color": "#3366ff", "fill_opacity": 0.35},
    )
    window._refresh_drawing_template_buttons()
    window._drawing_template_buttons[1].click()
    app.processEvents()

    window.chart_widget._consume_drawing_click(DrawingAnchor(10.0, 100.0))
    window.chart_widget._consume_drawing_click(DrawingAnchor(12.0, 103.0))

    assert window.chart_widget.active_drawing_tool is None
    assert window._drawing_template_buttons[1].isChecked() is False
    drawing = window.chart_widget.drawings()[0]
    assert drawing.tool_type is DrawingToolType.RECTANGLE
    assert drawing.style["color"] == "#3366ff"
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_clicking_normal_drawing_tool_clears_template_button_state(window: MainWindow) -> None:
    window._drawing_templates[1] = DrawingTemplate(
        slot=1,
        tool_type=DrawingToolType.RECTANGLE,
        note="阻力区",
        style={"color": "#3366ff", "width": 3, "fill_color": "#3366ff", "fill_opacity": 0.35},
    )
    window._refresh_drawing_template_buttons()

    window._drawing_template_buttons[1].click()
    window._drawing_tool_buttons[DrawingToolType.HORIZONTAL_LINE].click()

    assert window._drawing_template_buttons[1].isChecked() is False
    assert window._drawing_tool_buttons[DrawingToolType.HORIZONTAL_LINE].isChecked() is True
    assert window.chart_widget.active_drawing_tool is DrawingToolType.HORIZONTAL_LINE


def test_text_template_button_reuses_style_without_reusing_content(window: MainWindow) -> None:
    window._drawing_templates[1] = DrawingTemplate(
        slot=1,
        tool_type=DrawingToolType.TEXT,
        note="标注",
        style={"text": "", "font_size": 18, "text_color": "#3366ff", "color": "#3366ff"},
    )
    window._refresh_drawing_template_buttons()

    window._drawing_template_buttons[1].click()

    preset = window.chart_widget.drawing_style_preset(DrawingToolType.TEXT)
    assert preset["font_size"] == 18
    assert preset["text_color"] == "#3366ff"
    assert preset["text"] == ""


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


def test_step_forward_refits_y_axis_after_manual_vertical_drag(window: MainWindow) -> None:
    _seed_engine(window)
    window.chart_widget.set_window_data(
        window.engine.bars,
        window.engine.session.current_index,
        window.engine.total_count,
        window.engine.window_start_index,
    )
    window.chart_widget.pan_y(10.0)
    preserved_offset = window.chart_widget._y_axis_offset

    window.step_forward()

    visible = window.chart_widget._revealed_window_bars(*window.chart_widget.current_x_range())
    y_min, y_max = window.chart_widget.price_plot.viewRange()[1]
    low = min(bar.low for _, bar in visible)
    high = max(bar.high for _, bar in visible)
    height = max(high - low, max(abs(high) * 0.01, 1.0))
    padding = max(height * 0.06, 0.5)
    assert window.chart_widget._y_axis_offset == pytest.approx(preserved_offset)
    assert y_min == pytest.approx(low - padding + preserved_offset)
    assert y_max == pytest.approx(high + padding + preserved_offset)
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_trade_marker_visibility_toggle_updates_chart_widget(window: MainWindow) -> None:
    _seed_engine(window)

    window.show_trade_markers_check.setChecked(False)
    window.show_trade_links_check.setChecked(False)

    assert window.chart_widget._trade_markers_visible is False
    assert window.chart_widget._trade_links_visible is False


def test_clicking_check_update_button_starts_update_check(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[bool] = []
    monkeypatch.setattr(window, "_start_update_check", lambda: started.append(True))

    window.check_update_button.click()

    assert started == [True]


def test_handle_update_check_finished_shows_latest_message(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}
    window._active_update_check_token = 1

    def fake_notice(_title: str, heading: str, summary: str, detail: str = "") -> None:
        captured["heading"] = heading
        captured["summary"] = summary
        captured["detail"] = detail

    monkeypatch.setattr(window, "_show_update_notice", fake_notice)

    window._handle_update_check_finished(1, None)

    assert captured["heading"] == "当前已是最新版本"
    assert "暂时没有可下载的新版本" in captured["summary"]
    assert captured["detail"] == ""
    assert window.check_update_button.isEnabled() is True


def test_handle_update_check_finished_starts_download_when_confirmed(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    window._active_update_check_token = 1
    update_info = UpdateInfo(
        version="0.3.0",
        tag="v0.3.0",
        release_notes="Bug fixes",
        installer_url="https://example.com/BarByBar-v0.3.0-windows-x64-setup.exe",
        installer_name="BarByBar-v0.3.0-windows-x64-setup.exe",
        asset_size=1024,
    )
    started: list[UpdateInfo] = []
    monkeypatch.setattr(window, "_confirm_update_download", lambda info: True)
    monkeypatch.setattr(window, "_start_update_download", lambda info: started.append(info))

    window._handle_update_check_finished(1, update_info)

    assert started == [update_info]


def test_confirm_update_download_uses_custom_dialog(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    update_info = UpdateInfo(
        version="0.3.0",
        tag="v0.3.0",
        release_notes="Fix A\nFix B",
        installer_url="https://example.com/BarByBar-v0.3.0-windows-x64-setup.exe",
        installer_name="BarByBar-v0.3.0-windows-x64-setup.exe",
    )
    captured: dict[str, str] = {}

    def fake_exec(self) -> int:
        captured["heading"] = self.heading_label.text()
        captured["summary"] = self.summary_label.text()
        captured["detail"] = self.detail_text.toPlainText()
        captured["accept_text"] = self.accept_button.text()
        captured["cancel_text"] = self.cancel_button.text()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(UpdateActionDialog, "exec", fake_exec)

    assert window._confirm_update_download(update_info) is True
    assert captured["heading"] == "BarByBar 0.3.0 已可下载"
    assert "当前版本" in captured["summary"]
    assert "Fix A" in captured["detail"]
    assert captured["accept_text"] == "开始下载"
    assert captured["cancel_text"] == "暂不更新"


def test_handle_update_download_finished_launches_installer_when_confirmed(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    window._active_update_download_token = 1
    update_info = UpdateInfo(
        version="0.3.0",
        tag="v0.3.0",
        release_notes="Bug fixes",
        installer_url="https://example.com/BarByBar-v0.3.0-windows-x64-setup.exe",
        installer_name="BarByBar-v0.3.0-windows-x64-setup.exe",
    )
    window._pending_download_update_info = update_info
    launched: list[str] = []
    closed: list[bool] = []
    monkeypatch.setattr(window, "_confirm_install_downloaded_update", lambda info, path: True)
    monkeypatch.setattr(window, "_launch_installer", lambda path: launched.append(str(path)))
    monkeypatch.setattr(window, "close", lambda: closed.append(True))

    window._handle_update_download_finished(1, "C:/tmp/BarByBar-v0.3.0-windows-x64-setup.exe")

    assert [Path(path) for path in launched] == [Path("C:/tmp/BarByBar-v0.3.0-windows-x64-setup.exe")]
    assert closed == [True]


def test_handle_update_download_finished_does_not_close_when_install_cancelled(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    window._active_update_download_token = 1
    update_info = UpdateInfo(
        version="0.3.0",
        tag="v0.3.0",
        release_notes="Bug fixes",
        installer_url="https://example.com/BarByBar-v0.3.0-windows-x64-setup.exe",
        installer_name="BarByBar-v0.3.0-windows-x64-setup.exe",
    )
    window._pending_download_update_info = update_info
    launched: list[str] = []
    closed: list[bool] = []
    monkeypatch.setattr(window, "_confirm_install_downloaded_update", lambda info, path: False)
    monkeypatch.setattr(window, "_launch_installer", lambda path: launched.append(str(path)))
    monkeypatch.setattr(window, "close", lambda: closed.append(True))

    window._handle_update_download_finished(1, "C:/tmp/BarByBar-v0.3.0-windows-x64-setup.exe")

    assert launched == []
    assert closed == []


def test_update_download_finished_signal_uses_pending_context_to_prompt_install(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    window._active_update_download_token = 1
    update_info = UpdateInfo(
        version="0.3.0",
        tag="v0.3.0",
        release_notes="Bug fixes",
        installer_url="https://example.com/BarByBar-v0.3.0-windows-x64-setup.exe",
        installer_name="BarByBar-v0.3.0-windows-x64-setup.exe",
    )
    window._pending_download_update_info = update_info
    prompted: list[tuple[str, Path]] = []
    monkeypatch.setattr(window, "_confirm_install_downloaded_update", lambda info, path: prompted.append((info.version, path)) or False)

    window._handle_update_download_finished(1, "C:/tmp/BarByBar-v0.3.0-windows-x64-setup.exe")

    assert prompted == [("0.3.0", Path("C:/tmp/BarByBar-v0.3.0-windows-x64-setup.exe"))]


def test_confirm_install_downloaded_update_uses_custom_dialog(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    update_info = UpdateInfo(
        version="0.3.0",
        tag="v0.3.0",
        release_notes="Bug fixes",
        installer_url="https://example.com/BarByBar-v0.3.0-windows-x64-setup.exe",
        installer_name="BarByBar-v0.3.0-windows-x64-setup.exe",
    )
    captured: dict[str, str] = {}

    def fake_exec(self) -> int:
        captured["heading"] = self.heading_label.text()
        captured["summary"] = self.summary_label.text()
        captured["detail"] = self.detail_text.toPlainText()
        captured["accept_text"] = self.accept_button.text()
        captured["cancel_text"] = self.cancel_button.text() if self.cancel_button is not None else ""
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(UpdateActionDialog, "exec", fake_exec)

    assert window._confirm_install_downloaded_update(update_info, Path("C:/tmp/BarByBar-v0.3.0-windows-x64-setup.exe")) is False
    assert captured["heading"] == "0.3.0 已下载完成"
    assert "关闭当前程序后将启动安装器" in captured["summary"]
    assert "安装包：BarByBar-v0.3.0-windows-x64-setup.exe" in captured["detail"]
    assert captured["accept_text"] == "立即安装"
    assert captured["cancel_text"] == "稍后安装"


def test_show_update_notice_uses_single_button_dialog(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_exec(self) -> int:
        captured["heading"] = self.heading_label.text()
        captured["summary"] = self.summary_label.text()
        captured["detail"] = self.detail_text.toPlainText()
        captured["accept_text"] = self.accept_button.text()
        captured["has_cancel"] = "yes" if self.cancel_button is not None else "no"
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(UpdateActionDialog, "exec", fake_exec)

    window._show_update_notice("检查更新失败", "未能完成更新检查", "请检查网络连接后重试。", "timeout")

    assert captured["heading"] == "未能完成更新检查"
    assert captured["summary"] == "请检查网络连接后重试。"
    assert captured["detail"] == "timeout"
    assert captured["accept_text"] == "知道了"
    assert captured["has_cancel"] == "no"


def test_update_download_progress_uses_compact_overlay_copy(window: MainWindow) -> None:
    long_name = "BarByBar-v0.3.0-windows-x64-super-long-installer-name-for-ui-regression-check-setup.exe"
    window.resize(480, 320)
    window.show_busy_overlay("初始", "准备中")
    window._active_update_download_token = 1
    window._pending_download_update_info = UpdateInfo(
        version="0.3.0",
        tag="v0.3.0",
        release_notes="Bug fixes",
        installer_url="https://example.com/BarByBar-v0.3.0-windows-x64-setup.exe",
        installer_name=long_name,
        asset_size=4096,
    )

    window._handle_update_download_progress(1, 1536, 4096)

    assert window._busy_overlay is not None
    assert window._busy_overlay.title_label.text() == "下载更新"
    assert window._busy_overlay.detail_label.text() == "正在下载 v0.3.0"
    assert window._busy_overlay.meta_label.text() == "1.5 KB / 4.0 KB"
    assert window._busy_overlay.progress.maximum() == 4096
    assert window._busy_overlay.progress.value() == 1536
    assert window._busy_overlay.progress_value_label.text() == "37%"
    assert long_name not in window._busy_overlay.detail_label.text()
    assert window._busy_overlay.filename_label.toolTip() == long_name
    assert window._busy_overlay.filename_label.text() != long_name


def test_update_download_progress_handles_indeterminate_total(window: MainWindow) -> None:
    window.show_busy_overlay("初始", "准备中")
    window._active_update_download_token = 1
    window._pending_download_update_info = UpdateInfo(
        version="0.3.0",
        tag="v0.3.0",
        release_notes="Bug fixes",
        installer_url="https://example.com/BarByBar-v0.3.0-windows-x64-setup.exe",
        installer_name="BarByBar-v0.3.0-windows-x64-setup.exe",
    )

    window._handle_update_download_progress(1, 0, 0)

    assert window._busy_overlay is not None
    assert window._busy_overlay.detail_label.text() == "正在下载 v0.3.0"
    assert window._busy_overlay.meta_label.text() == "正在准备下载"
    assert window._busy_overlay.progress.minimum() == 0
    assert window._busy_overlay.progress.maximum() == 0
    assert window._busy_overlay.progress_value_label.isHidden() is True


def test_update_action_dialog_hides_detail_panel_when_empty() -> None:
    dialog = UpdateActionDialog(
        "安装更新",
        "0.3.0 已下载完成",
        "关闭当前程序后将启动安装器。",
        "",
        accept_text="立即安装",
    )
    try:
        assert dialog.heading_label.text() == "0.3.0 已下载完成"
        assert dialog.summary_label.text() == "关闭当前程序后将启动安装器。"
        assert dialog.detail_text.isHidden() is True
    finally:
        dialog.close()


def test_update_action_dialog_can_render_single_button_notice() -> None:
    dialog = UpdateActionDialog(
        "检查更新",
        "当前已是最新版本",
        "你当前使用的是 0.3.0。",
        "",
        accept_text="知道了",
        cancel_text=None,
    )
    try:
        assert dialog.accept_button.text() == "知道了"
        assert dialog.cancel_button is None
    finally:
        dialog.close()


def test_handle_update_download_finished_shows_error_and_stays_open_when_launch_fails(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    window._active_update_download_token = 1
    update_info = UpdateInfo(
        version="0.3.0",
        tag="v0.3.0",
        release_notes="Bug fixes",
        installer_url="https://example.com/BarByBar-v0.3.0-windows-x64-setup.exe",
        installer_name="BarByBar-v0.3.0-windows-x64-setup.exe",
    )
    window._pending_download_update_info = update_info
    warnings: list[tuple[str, str, str]] = []
    closed: list[bool] = []
    monkeypatch.setattr(window, "_confirm_install_downloaded_update", lambda info, path: True)
    monkeypatch.setattr(window, "_launch_installer", lambda path: (_ for _ in ()).throw(OSError("boom")))
    monkeypatch.setattr(window, "close", lambda: closed.append(True))
    monkeypatch.setattr(window, "_show_update_notice", lambda title, heading, summary, detail="": warnings.append((heading, summary, detail)))

    window._handle_update_download_finished(1, "C:/tmp/BarByBar-v0.3.0-windows-x64-setup.exe")

    assert warnings
    assert warnings[0][0] == "安装器未能启动"
    assert "安装包路径" in warnings[0][1]
    assert "boom" in warnings[0][2]
    assert closed == []


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
    monkeypatch.setattr(window, "_confirm_dialog", lambda *args, **kwargs: False)
    window._session_dirty = False
    window._auto_save_timer.stop()

    window.confirm_clear_drawings()

    assert len(window.chart_widget.drawings()) == 1
    assert window._session_dirty is False
    assert window._auto_save_timer.isActive() is False


def test_confirm_clear_drawings_confirms_and_clears(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    window.chart_widget.set_window_data(
        window.engine.bars,
        window.engine.session.current_index,
        window.engine.total_count,
        window.engine.window_start_index,
    )
    window.chart_widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.HORIZONTAL_LINE, anchors=[DrawingAnchor(10.0, 100.0)])])
    monkeypatch.setattr(window, "_confirm_dialog", lambda *args, **kwargs: True)
    captured: list[str] = []

    def _record_save(*, trigger: str = "manual") -> None:
        captured.append(trigger)
        window._auto_save_timer.stop()
        window._session_dirty = False

    monkeypatch.setattr(window, "save_session", _record_save)
    window._session_dirty = False
    window._auto_save_timer.stop()

    window.confirm_clear_drawings()

    assert window.chart_widget.drawings() == []
    assert "clear_drawings" in captured
    assert window._session_dirty is False
    assert window._auto_save_timer.isActive() is False
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
    assert window.chart_widget.drawing_style_preset(DrawingToolType.TREND_LINE)["color"] == "#3366ff"
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_new_drawing_reuses_last_style_for_same_tool(window, app: QApplication, monkeypatch) -> None:
    _seed_engine(window)
    window.chart_widget.set_window_data(
        window.engine.bars,
        window.engine.session.current_index,
        window.engine.total_count,
        window.engine.window_start_index,
    )
    window.chart_widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.RECTANGLE, anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(12.0, 103.0)])])

    class _FakeDialog:
        def __init__(self, drawing, parent):
            self.drawing = drawing

        def exec(self):
            return QDialog.DialogCode.Accepted

        def style_payload(self):
            return {"color": "#3366ff", "width": 3, "fill_color": "#3366ff", "fill_opacity": 0.35}

    monkeypatch.setattr("barbybar.ui.main_window.DrawingPropertiesDialog", _FakeDialog)
    window._handle_drawing_properties_requested(window.chart_widget.drawings()[0], 0)

    window.chart_widget.set_drawings([])
    window._toggle_drawing_tool(DrawingToolType.RECTANGLE, True)
    app.processEvents()
    window.chart_widget._handle_scene_click(_FakeSceneClick(window.chart_widget.price_plot.vb.mapViewToScene(QPointF(14, 101))))
    window.chart_widget._handle_scene_click(_FakeSceneClick(window.chart_widget.price_plot.vb.mapViewToScene(QPointF(16, 104))))

    drawing = window.chart_widget.drawings()[0]
    assert drawing.style["color"] == "#3366ff"
    assert drawing.style["width"] == 3
    assert drawing.style["fill_opacity"] == 0.35
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_text_preset_stores_style_without_reusing_content(window, monkeypatch) -> None:
    _seed_engine(window)
    window.chart_widget.set_window_data(
        window.engine.bars,
        window.engine.session.current_index,
        window.engine.total_count,
        window.engine.window_start_index,
    )
    window.chart_widget.set_drawings([ChartDrawing(tool_type=DrawingToolType.TEXT, anchors=[DrawingAnchor(10.0, 100.0)], style={"text": ""})])

    class _FakeDialog:
        def __init__(self, drawing, parent):
            self.drawing = drawing

        def exec(self):
            return QDialog.DialogCode.Accepted

        def style_payload(self):
            return {"text": "hello", "font_size": 18, "text_color": "#3366ff", "color": "#3366ff"}

    monkeypatch.setattr("barbybar.ui.main_window.DrawingPropertiesDialog", _FakeDialog)
    window._handle_drawing_properties_requested(window.chart_widget.drawings()[0], 0)

    preset = window.chart_widget.drawing_style_preset(DrawingToolType.TEXT)
    assert preset["font_size"] == 18
    assert preset["text_color"] == "#3366ff"
    assert preset["text"] == ""
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


def test_fib_drawing_dialog_exposes_current_levels_and_parses_custom_levels() -> None:
    dialog = DrawingPropertiesDialog(
        ChartDrawing(
            tool_type=DrawingToolType.FIB_RETRACEMENT,
            anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(12.0, 110.0)],
            style={"fib_levels": [0.0, 0.382, 0.5, 0.618, 1.0, 2.0], "show_level_labels": True, "show_price_labels": True},
        )
    )
    dialog.fib_levels_edit.setText("0, 0.382, 0.5, 0.618, 1, 2")

    payload = dialog.style_payload()

    assert dialog.fib_levels_edit.text() == "0, 0.382, 0.5, 0.618, 1, 2"
    assert payload["fib_levels"] == [0.0, 0.382, 0.5, 0.618, 1.0, 2.0]
    dialog.close()
    dialog.deleteLater()


def test_drawing_dialog_exposes_line_opacity_for_line_tools() -> None:
    dialog = DrawingPropertiesDialog(
        ChartDrawing(
            tool_type=DrawingToolType.TREND_LINE,
            anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(12.0, 110.0)],
            style={"opacity": 0.45},
        )
    )

    payload = dialog.style_payload()

    assert dialog.line_opacity_spin.value() == 0.45
    assert payload["opacity"] == 0.45
    dialog.close()
    dialog.deleteLater()


def test_text_drawing_dialog_does_not_expose_line_opacity_control() -> None:
    dialog = DrawingPropertiesDialog(
        ChartDrawing(tool_type=DrawingToolType.TEXT, anchors=[DrawingAnchor(10.0, 100.0)], style={"text": ""})
    )

    labels = [dialog.layout().itemAt(0).layout().labelForField(dialog.line_opacity_spin)]

    assert labels == [None]
    dialog.close()
    dialog.deleteLater()


def test_fib_drawing_dialog_rejects_invalid_levels() -> None:
    dialog = DrawingPropertiesDialog(
        ChartDrawing(
            tool_type=DrawingToolType.FIB_RETRACEMENT,
            anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(12.0, 110.0)],
            style={"fib_levels": [0.0, 0.5, 1.0, 2.0]},
        )
    )
    dialog.fib_levels_edit.setText("0, abc, 1")

    with pytest.raises(ValueError, match="斐波那契档位格式无效"):
        dialog.style_payload()

    dialog.close()
    dialog.deleteLater()


def test_fib_drawing_dialog_shows_inline_error_on_accept() -> None:
    dialog = DrawingPropertiesDialog(
        ChartDrawing(
            tool_type=DrawingToolType.FIB_RETRACEMENT,
            anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(12.0, 110.0)],
            style={"fib_levels": [0.0, 0.5, 1.0, 2.0]},
        )
    )
    try:
        dialog.fib_levels_edit.setText("0, abc, 1")
        dialog.accept()

        assert dialog.result() == 0
        assert dialog.error_label.isHidden() is False
        assert "斐波那契档位格式无效" in dialog.error_label.text()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_column_mapping_dialog_shows_inline_error_for_missing_fields() -> None:
    dialog = ColumnMappingDialog(
        csv_path="sample.csv",
        available_headers=["date", "open", "high", "low", "close"],
        detected_field_map={"open": "open", "high": "high", "low": "low", "close": "close"},
        missing_fields=["datetime", "volume"],
    )
    try:
        dialog.accept()

        assert dialog.result() == 0
        assert dialog.error_label.isHidden() is False
        assert "datetime" in dialog.error_label.text()
        assert "volume" in dialog.error_label.text()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_drawing_template_dialog_shows_inline_error_when_note_is_empty() -> None:
    dialog = DrawingTemplateDialog(templates_by_slot={}, initial_slot=1, initial_note="")
    try:
        dialog.note_edit.setText("")
        dialog.accept()

        assert dialog.result() == 0
        assert dialog.error_label.isHidden() is False
        assert dialog.error_label.text() == "备注不能为空"
    finally:
        dialog.close()
        dialog.deleteLater()


def test_drawing_properties_request_preserves_custom_fib_levels(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    window.chart_widget.set_drawings(
        [
            ChartDrawing(
                tool_type=DrawingToolType.FIB_RETRACEMENT,
                anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(12.0, 110.0)],
                style={"fib_levels": [0.0, 0.5, 1.0, 2.0], "show_level_labels": True, "show_price_labels": True},
            )
        ]
    )
    window._session_dirty = False
    window._auto_save_timer.stop()

    class _FakeDialog:
        def __init__(self, drawing, parent):
            self.drawing = drawing

        def exec(self):
            return QDialog.DialogCode.Accepted

        def style_payload(self):
            return {
                "color": "#ff9f1c",
                "width": 1,
                "line_style": "solid",
                "fib_levels": [0.0, 0.382, 0.5, 0.618, 1.0, 2.0],
                "show_level_labels": True,
                "show_price_labels": True,
            }

    monkeypatch.setattr("barbybar.ui.main_window.DrawingPropertiesDialog", _FakeDialog)

    window._handle_drawing_properties_requested(window.chart_widget.drawings()[0], 0)

    assert window.chart_widget.drawings()[0].style["fib_levels"] == [0.0, 0.382, 0.5, 0.618, 1.0, 2.0]
    assert window.chart_widget.drawing_style_preset(DrawingToolType.FIB_RETRACEMENT)["fib_levels"] == [
        0.0,
        0.382,
        0.5,
        0.618,
        1.0,
        2.0,
    ]
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_drawing_properties_request_shows_warning_for_invalid_fib_levels(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    window.chart_widget.set_drawings(
        [
            ChartDrawing(
                tool_type=DrawingToolType.FIB_RETRACEMENT,
                anchors=[DrawingAnchor(10.0, 100.0), DrawingAnchor(12.0, 110.0)],
                style={"fib_levels": [0.0, 0.5, 1.0, 2.0]},
            )
        ]
    )
    warnings: list[tuple[str, str, str]] = []

    class _FakeDialog:
        def __init__(self, drawing, parent):
            self.drawing = drawing

        def exec(self):
            return QDialog.DialogCode.Accepted

        def style_payload(self):
            raise ValueError("斐波那契档位格式无效，请使用逗号分隔的数字。")

    monkeypatch.setattr("barbybar.ui.main_window.DrawingPropertiesDialog", _FakeDialog)
    monkeypatch.setattr(window, "_show_error", lambda title, heading, summary="", detail="": warnings.append((title, heading, detail or summary)))

    window._handle_drawing_properties_requested(window.chart_widget.drawings()[0], 0)

    assert warnings == [("属性无效", "画线属性未通过校验", "斐波那契档位格式无效，请使用逗号分隔的数字。")]


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
    assert "总交易 1 笔" in window.training_stats_label.text()
    assert "做多 1 次" in window.training_stats_label.text()
    assert "做空 0 次" in window.training_stats_label.text()
    assert "总盈亏 3.00" in window.training_stats_label.text()
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

    visible = window.chart_widget._revealed_window_bars(*window.chart_widget.current_x_range())
    assert window.chart_widget._cursor == window.engine.session.current_index
    assert visible[-1][0] == exit_index
    assert window.chart_widget._focused_trade_points is None
    assert window._trade_history_dialog.trade_history_toggle_button.text() == "切换到入场"

    window._trade_history_dialog._toggle_selected_trade_focus()

    visible = window.chart_widget._revealed_window_bars(*window.chart_widget.current_x_range())
    assert window.chart_widget._cursor == window.engine.session.current_index
    assert visible[-1][0] == entry_index
    assert window._trade_history_dialog.trade_history_toggle_button.text() == "切换到出场"


def test_trade_history_jump_outside_window_keeps_training_cursor(window: MainWindow, app: QApplication) -> None:
    case_dir = window.repo.db_path.parent if window.repo.db_path is not None else Path("C:/code/BarByBar/.pytest-temp")
    start = datetime(2025, 1, 1, 9, 0)
    csv_path = case_dir / "long-sample.csv"
    lines = ["datetime,open,high,low,close,volume"]
    for index in range(800):
        ts = start + timedelta(minutes=index)
        price = 100 + index * 0.1
        lines.append(f"{ts:%Y-%m-%d %H:%M:%S},{price:.2f},{price + 1:.2f},{price - 1:.2f},{price + 0.2:.2f},{1000 + index}")
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    dataset = window.repo.import_csv(csv_path, "IF", "1m", display_name="long-sample.csv")
    session = window.repo.create_session(dataset.id or 0, start_index=0)
    session.current_index = 170
    session.current_bar_time = start + timedelta(minutes=790)
    actions = [
        SessionAction(ActionType.OPEN_LONG, 1, start + timedelta(minutes=1), price=100.5, quantity=1),
        SessionAction(ActionType.CLOSE, 5, start + timedelta(minutes=5), price=101.5, quantity=1),
    ]
    window.repo.save_session(session, actions, [])
    window._load_session(session.id or 0)
    _wait_for_loaded_session(app, window)
    assert window.engine is not None

    exit_index = 5
    current_index = window.engine.session.current_index
    assert window.engine.session.chart_timeframe == "5m"
    assert window.engine.session.current_bar_time == start + timedelta(minutes=790)
    assert exit_index < window.engine.window_start_index

    window._update_ui_from_engine()
    window.open_trade_history_dialog()

    assert window._trade_history_dialog is not None
    item = window._trade_history_dialog.trade_history_list.item(window._trade_history_dialog.trade_history_list.count() - 1)
    window._trade_history_dialog._handle_item_clicked(item)

    visible = window.chart_widget._revealed_window_bars(*window.chart_widget.current_x_range())
    assert window.engine.session.current_index == current_index
    assert window.chart_widget._cursor == current_index
    assert visible[-1][0] == exit_index


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


def test_step_forward_keeps_zoom_when_forward_window_extends(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_engine(window)
    assert window.engine is not None

    extended_bars = [
        Bar(
            timestamp=datetime(2025, 1, 1, 9, 0) + timedelta(minutes=index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100.5 + index,
            volume=1000 + index,
        )
        for index in range(120)
    ]
    window.engine.session.current_index = 39
    window.engine.session.current_bar_time = window.engine.bars[39].timestamp
    window.chart_widget.set_window_data(
        window.engine.bars,
        window.engine.session.current_index,
        window.engine.total_count,
        window.engine.window_start_index,
    )
    window.chart_widget.zoom_x(anchor_x=30, scale=0.5)
    preserved_bars = window.chart_widget.viewport_state.bars_in_view

    def fake_get_chart_window(*_args, **_kwargs) -> WindowBars:
        return WindowBars(
            bars=extended_bars,
            global_start_index=0,
            global_end_index=len(extended_bars) - 1,
            anchor_global_index=window.engine.session.current_index,
            total_count=len(extended_bars),
        )

    monkeypatch.setattr(window.repo, "get_chart_window", fake_get_chart_window)

    window.step_forward()

    assert window.chart_widget.viewport_state.bars_in_view == preserved_bars
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_space_shortcut_steps_forward_when_focus_allows(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_engine(window)
    start_index = window.engine.session.current_index

    monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: window.chart_widget))
    window._handle_step_forward_shortcut()

    assert window.engine.session.current_index == start_index + 1
    window._auto_save_timer.stop()
    window._session_dirty = False


def test_space_shortcut_does_not_step_forward_while_typing(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_engine(window)
    start_index = window.engine.session.current_index
    input_widget = QLineEdit()

    monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: input_widget))
    assert window._focused_widget_blocks_step_forward_shortcut(input_widget) is True
    assert window._focused_widget_blocks_step_forward_shortcut(window.chart_widget) is False

    window._handle_step_forward_shortcut()

    assert window.engine.session.current_index == start_index


def test_step_forward_passes_flatten_toggle_state_to_engine(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_engine(window)
    captured: dict[str, bool] = {}

    def fake_step_forward(*, flatten_at_session_end: bool = False) -> bool:
        captured["flatten_at_session_end"] = flatten_at_session_end
        return False

    monkeypatch.setattr(window.engine, "step_forward", fake_step_forward)
    window.flatten_at_session_end_toggle_button.setChecked(False)

    window.step_forward()

    assert captured["flatten_at_session_end"] is False


def test_jump_to_bar_passes_flatten_toggle_state_to_engine(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_engine(window)
    captured: dict[str, object] = {}

    def fake_jump_to(index: int, *, flatten_at_session_end: bool = False) -> None:
        captured["index"] = index
        captured["flatten_at_session_end"] = flatten_at_session_end

    monkeypatch.setattr(window.engine, "jump_to", fake_jump_to)
    window.flatten_at_session_end_toggle_button.setChecked(False)

    window.jump_to_bar(30)
    window._auto_save_timer.stop()
    window._session_dirty = False

    assert captured["index"] == 30
    assert captured["flatten_at_session_end"] is False


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

    window._handle_chart_protective_order_created(OrderLineType.TAKE_PROFIT.value, 104.2, False)

    assert captured == [(OrderLineType.TAKE_PROFIT, 104.2)]


def test_average_price_created_protective_line_uses_full_position_quantity(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    window.engine.record_action(ActionType.OPEN_LONG, quantity=3, price=101)
    captured: list[tuple[OrderLineType, float, float]] = []
    monkeypatch.setattr(
        window,
        "_place_order_line_with_quantity",
        lambda order_type, price, quantity: captured.append((order_type, price, quantity)),
    )

    window._handle_chart_protective_order_created(OrderLineType.TAKE_PROFIT.value, 104.2, True)

    assert captured == [(OrderLineType.TAKE_PROFIT, 104.2, 3.0)]


def test_dragging_average_price_can_create_multiple_protective_lines(window: MainWindow, monkeypatch) -> None:
    _seed_engine(window)
    window.engine.record_action(ActionType.OPEN_LONG, quantity=1, price=101)
    monkeypatch.setattr(window, "save_session", lambda **kwargs: None)

    window._handle_chart_protective_order_created(OrderLineType.TAKE_PROFIT.value, 104.2, False)
    window._handle_chart_protective_order_created(OrderLineType.TAKE_PROFIT.value, 105.8, False)

    take_profit_lines = [
        line for line in window.engine.active_order_lines if line.order_type is OrderLineType.TAKE_PROFIT
    ]

    assert [line.price for line in take_profit_lines] == [104.0, 106.0]


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


def test_busy_overlay_is_a_top_banner_within_main_workspace(window: MainWindow) -> None:
    window.resize(1400, 900)
    window.show_busy_overlay("正在加载案例...", "正在读取数据并构建图表")

    assert window._busy_overlay is not None
    assert window._busy_overlay.geometry().x() == 0
    assert window._busy_overlay.geometry().y() == 0
    assert window._busy_overlay.geometry().width() == window.centralWidget().width()
    assert window._busy_overlay.geometry().height() < window.centralWidget().height()


def test_set_timeframe_choices_does_not_trigger_replay_bar_loading(window: MainWindow, monkeypatch) -> None:
    def fail_get_replay_bars(*args, **kwargs):
        raise AssertionError("get_replay_bars should not be called when only updating button states")

    monkeypatch.setattr(window.repo, "get_replay_bars", fail_get_replay_bars)

    window._set_timeframe_choices("1m", "5m")

    assert window.timeframe_buttons["5m"].isEnabled()
    assert window.timeframe_buttons["1d"].isEnabled()
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
    captured: list[tuple[str, str, str, str]] = []
    monkeypatch.setattr("barbybar.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(folder))
    monkeypatch.setattr(window, "_show_notice", lambda title, heading, summary, detail="": captured.append((title, heading, summary, detail)))

    window.import_csv_folder()
    _wait_for_batch_import(app, window)

    datasets = repo.list_datasets()
    assert [dataset.display_name for dataset in datasets] == ["sample.csv", valid_a.name]
    assert len(captured) == 1
    assert captured[0][0] == "批量导入结果"
    assert "成功 1 个，跳过 1 个" in captured[0][2]
    assert f"重复示例: {valid_a.name}" in captured[0][3]
    assert valid_b.name not in captured[0][3]
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
        assert dataset_dialog.dataset_filter.placeholderText() == "按名称或品种筛选"
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


def test_session_library_filters_by_title_symbol_and_tags(window: MainWindow) -> None:
    dataset = window.repo.list_datasets()[0]
    first = window.repo.create_session(dataset.id or 0, start_index=1, title="螺纹突破复盘")
    second = window.repo.create_session(dataset.id or 0, start_index=2, title="午后整理观察")
    first.tags = ["breakout", "morning"]
    second.tags = ["range", "afternoon"]
    window.repo.save_session(first, [], [])
    window.repo.save_session(second, [], [])

    session_dialog = SessionLibraryDialog(window.repo, window)
    try:
        assert session_dialog.session_filter.placeholderText() == "按名称、品种或标签筛选"

        session_dialog.session_filter.setText("突破")
        assert session_dialog.session_list.count() == 1
        assert "螺纹突破复盘" in session_dialog.session_list.item(0).text()

        session_dialog.session_filter.setText("if")
        assert session_dialog.session_list.count() >= 2

        session_dialog.session_filter.setText("AFTERNOON")
        assert session_dialog.session_list.count() == 1
        assert "午后整理观察" in session_dialog.session_list.item(0).text()

        session_dialog.session_filter.setText("")
        assert session_dialog.session_list.count() == 2
    finally:
        session_dialog.close()
        session_dialog.deleteLater()


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
    messages: list[tuple[str, str, str]] = []
    shown: list[tuple[str, str]] = []
    hidden: list[bool] = []
    monkeypatch.setattr("barbybar.ui.main_window.QFileDialog.getOpenFileName", lambda *args, **kwargs: (str(csv_path), "CSV Files (*.csv)"))
    monkeypatch.setattr(window, "_show_notice", lambda title, heading, summary, detail="": messages.append((title, heading, summary)))
    monkeypatch.setattr(window, "show_busy_overlay", lambda title, detail="": shown.append((title, detail)))
    monkeypatch.setattr(window, "hide_busy_overlay", lambda: hidden.append(True))

    window.import_csv()

    assert repo.list_datasets()[0].display_name == "dup.csv"
    assert messages == [("重复数据集", "该数据集已存在", "同名文件已存在：dup.csv")]
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
    monkeypatch.setattr(window, "_show_notice", lambda *args, **kwargs: None)
    monkeypatch.setattr(window, "show_busy_overlay", lambda title, detail="": shown.append((title, detail)))
    monkeypatch.setattr(window, "hide_busy_overlay", lambda: hidden.append(True))

    window.import_csv_folder()
    _wait_for_batch_import(app, window)

    assert shown == [("正在批量导入...", "正在准备文件列表")]
    assert hidden == [True]
    window.close()
    window.deleteLater()
    app.processEvents()


def test_batch_import_progress_updates_busy_overlay(window: MainWindow) -> None:
    window.show_busy_overlay("初始", "准备中")
    window._active_batch_import_token = 1

    window._handle_batch_import_progress(
        1,
        BatchImportProgress(
            current=3,
            total=8,
            current_name="sample.csv",
            imported_count=2,
            skipped_count=1,
            failed_count=0,
        ),
    )

    assert window._busy_overlay is not None
    assert window._busy_overlay.title_label.text() == "正在批量导入 3/8"
    assert window._busy_overlay.detail_label.text() == "当前文件: sample.csv\n成功 2 个，跳过 1 个，失败 0 个"
    assert window._busy_overlay.progress.maximum() == 8
    assert window._busy_overlay.progress.value() == 3


def test_dataset_manager_shows_batch_import_progress_in_dialog(window: MainWindow) -> None:
    dialog = DataSetManagerDialog(window.repo, window)
    try:
        window._active_batch_import_token = 1
        dialog._handle_batch_import_progress(
            1,
            BatchImportProgress(
                current=2,
                total=5,
                current_name="IC9999.CCFX_2005_1min.csv",
                imported_count=1,
                skipped_count=0,
                failed_count=1,
            ),
        )

        assert dialog._batch_progress_panel.isHidden() is False
        assert dialog._batch_progress_title.text() == "正在批量导入 2/5"
        assert dialog._batch_progress_detail.text() == (
            "当前文件: IC9999.CCFX_2005_1min.csv\n成功 1 个，跳过 0 个，失败 1 个"
        )
        assert dialog._batch_progress_bar.maximum() == 5
        assert dialog._batch_progress_bar.value() == 2
        assert dialog._import_button.isEnabled() is True
    finally:
        dialog.close()
        dialog.deleteLater()


def test_dataset_manager_reject_is_blocked_while_batch_import_active(window: MainWindow, monkeypatch) -> None:
    dialog = DataSetManagerDialog(window.repo, window)
    messages: list[tuple[str, str, str]] = []
    monkeypatch.setattr(window, "_show_notice", lambda title, heading, summary, detail="": messages.append((title, heading, summary)))
    try:
        dialog._set_batch_import_active(True)
        dialog.reject()

        assert messages == [("批量导入进行中", "批量导入仍在进行", "请等待当前导入任务完成后再关闭窗口。")]
        assert dialog.isVisible() is False
        assert dialog._batch_import_active is True
    finally:
        dialog._set_batch_import_active(False)
        dialog.close()
        dialog.deleteLater()


def test_batch_import_result_message_includes_failure_reason(window: MainWindow, monkeypatch) -> None:
    captured: list[tuple[str, str, str, str]] = []
    monkeypatch.setattr(window, "_show_notice", lambda title, heading, summary, detail="": captured.append((title, heading, summary, detail)))
    window._active_batch_import_token = 1

    window._handle_batch_import_finished(
        1,
        BatchImportOutcome(
            imported=["ok.csv"],
            skipped_duplicates=[],
            failed_files=["IC9999.CCFX_2005_1min.csv"],
            failure_details=[("IC9999.CCFX_2005_1min.csv", "Invalid row for timestamp 2005-01-04 09:16:00: numeric field 'close' is empty")],
        ),
    )

    assert len(captured) == 1
    assert "成功 1 个，跳过 0 个，失败 1 个" in captured[0][2]
    assert "IC9999.CCFX_2005_1min.csv: Invalid row for timestamp 2005-01-04 09:16:00: numeric field 'close' is empty" in captured[0][3]
