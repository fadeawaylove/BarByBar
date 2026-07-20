from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from barbybar import paths
from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import ActionType, Bar, DrawingToolType, OrderLineType, PositionState, ReviewSession, SessionStats, SessionStatus, TradeReviewItem
from barbybar.storage.repository import Repository
from barbybar.ui.main_window import (
    DataSetManagerDialog,
    MainWindow,
    SessionLibraryDialog,
    SettingsDialog,
    TradeHistoryDialog,
    UpdateActionDialog,
)


OUTPUT_DIR = Path("C:/tmp/reframe-review-workflow-shots")


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


def _process_events(app: QApplication, cycles: int = 6) -> None:
    for _ in range(cycles):
        app.processEvents()


def _build_repo() -> tuple[Repository, Path]:
    root = Path("C:/code/BarByBar/.pytest-temp") / f"screenshot-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    data_dir = root / "app-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    paths.APP_DIR_ENV_VAR
    import os

    os.environ[paths.APP_DIR_ENV_VAR] = str(data_dir)
    repo = Repository(root / "barbybar.db")
    start = datetime(2025, 1, 1, 9, 0)
    csv_path = root / "sample.csv"
    lines = ["datetime,open,high,low,close,volume"]
    for index in range(240):
        ts = start + timedelta(minutes=index)
        price = 100 + index * 0.2
        lines.append(f"{ts:%Y-%m-%d %H:%M:%S},{price:.2f},{price + 1:.2f},{price - 1:.2f},{price + 0.3:.2f},{1000 + index}")
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    dataset = repo.import_csv(csv_path, "IF", "1m", display_name="smoke.csv")
    repo.create_session(dataset.id or 0, start_index=28, title="截图示例案例")
    return repo, root


def _seed_engine(window: MainWindow) -> None:
    bars = [
        Bar(
            timestamp=datetime(2025, 1, 1, 9, 0) + timedelta(minutes=index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100.5 + index,
            volume=1000 + index,
        )
        for index in range(90)
    ]
    session = ReviewSession(
        id=1,
        dataset_id=1,
        symbol="IF",
        timeframe="1m",
        chart_timeframe="1m",
        start_index=0,
        current_index=28,
        current_bar_time=bars[28].timestamp,
        status=SessionStatus.ACTIVE,
        title="沪深主连 · 突破训练",
        notes="",
        tags=[],
        position=PositionState(),
        stats=SessionStats(),
        created_at=bars[0].timestamp,
        updated_at=bars[0].timestamp,
    )
    window.engine = ReviewEngine(session, bars, window_start_index=0, total_count=len(bars))
    window.current_session_id = 1
    window.chart_widget.set_window_data(bars, session.current_index, len(bars), 0, timeframe=session.chart_timeframe)
    window._update_ui_from_engine()


def _seed_trade_review(window: MainWindow) -> None:
    start = datetime(2025, 1, 1, 9, 0)
    window._trade_review_items = [
        TradeReviewItem(1, start, start + timedelta(minutes=2), "long", 1, 100, 98, -2, 1, 3, 2, "stop_loss", True, True, False, False),
        TradeReviewItem(2, start + timedelta(minutes=5), start + timedelta(minutes=9), "short", 1, 106, 102, 4, 5, 9, 4, "manual_close", True, False, False, True),
        TradeReviewItem(3, start + timedelta(minutes=12), start + timedelta(minutes=17), "long", 1, 108, 112, 4, 12, 17, 5, "take_profit", True, False, False, True),
    ]
    window._trade_review_controller.select_trade(2)
    window._selected_trade_number = 2


def _save_widget(widget, target: Path, app: QApplication, size: QSize | None = None) -> None:  # noqa: ANN001
    if size is not None:
        widget.resize(size)
    widget.show()
    widget.raise_()
    _process_events(app)
    pixmap = widget.grab()
    pixmap.save(str(target))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app = _app()
    repo, _root = _build_repo()
    window = MainWindow(repo)
    window.resize(1460, 920)

    captures: dict[str, str] = {}

    try:
        _save_widget(window, OUTPUT_DIR / "01-empty-startup.png", app)
        captures["empty_startup"] = "01-empty-startup.png"

        _seed_engine(window)
        _process_events(app)
        _save_widget(window, OUTPUT_DIR / "02-replay-mode.png", app)
        captures["replay_mode"] = "02-replay-mode.png"

        window._toggle_draw_order_preview(OrderLineType.ENTRY_LONG, True)
        _process_events(app)
        _save_widget(window, OUTPUT_DIR / "03-plan-mode.png", app)
        captures["plan_mode"] = "03-plan-mode.png"

        window.cancel_draw_order_preview()
        window._toggle_drawing_tool(DrawingToolType.TREND_LINE, True)
        _process_events(app)
        _save_widget(window, OUTPUT_DIR / "04-annotate-mode.png", app)
        captures["annotate_mode"] = "04-annotate-mode.png"

        window._toggle_drawing_tool(DrawingToolType.TREND_LINE, False)
        _seed_trade_review(window)
        window._selected_trade_view = "entry"
        window.open_trade_history_dialog()
        _process_events(app)
        _save_widget(window, OUTPUT_DIR / "05-review-mode-sidebar.png", app)
        captures["review_mode_sidebar"] = "05-review-mode-sidebar.png"

        window.engine.session.position = PositionState(direction="long", quantity=2, average_price=126.5)
        window._update_ui_from_engine()
        _process_events(app)
        _save_widget(window, OUTPUT_DIR / "06-active-long-position.png", app)
        captures["active_long_position"] = "06-active-long-position.png"

        window.engine.session.position = PositionState(direction="short", quantity=1, average_price=124.0)
        window._update_ui_from_engine()
        _process_events(app)
        _save_widget(window, OUTPUT_DIR / "07-active-short-position.png", app)
        captures["active_short_position"] = "07-active-short-position.png"

        window.engine.session.position = PositionState()
        window.engine.session.status = SessionStatus.COMPLETED
        window._update_ui_from_engine()
        _process_events(app)
        _save_widget(window, OUTPUT_DIR / "08-completed-session.png", app)
        captures["completed_session"] = "08-completed-session.png"

        window.engine.session.status = SessionStatus.ACTIVE
        window._record_save_failure("数据库暂时不可写，请检查磁盘空间后重试")
        _save_widget(window, OUTPUT_DIR / "08b-save-failure-recovery.png", app)
        captures["save_failure_recovery"] = "08b-save-failure-recovery.png"
        window._clear_save_failure()
        window._session_dirty = False
        window._sync_case_header()

        _seed_trade_review(window)
        trade_dialog = TradeHistoryDialog(window, window)
        trade_dialog.refresh_items()
        _save_widget(trade_dialog, OUTPUT_DIR / "09-full-trade-review-workspace.png", app, QSize(1180, 760))
        captures["full_trade_review_workspace"] = "09-full-trade-review-workspace.png"
        trade_dialog.close()

        settings_dialog = SettingsDialog(window, window)
        settings_dialog.sync_from_owner()
        _save_widget(settings_dialog, OUTPUT_DIR / "10-settings-entry.png", app, QSize(1080, 760))
        captures["settings_entry"] = "10-settings-entry.png"
        settings_dialog.close()

        error_dialog = UpdateActionDialog(
            "保存失败",
            "未能保存当前案例",
            "更改仍保留在当前窗口中，请检查磁盘或数据库状态后重试。",
            "数据库暂时不可写（database is locked）",
            accept_text="知道了",
            cancel_text=None,
            accept_role="danger",
            parent=window,
        )
        _save_widget(error_dialog, OUTPUT_DIR / "10b-error-dialog.png", app, QSize(620, 420))
        captures["error_dialog"] = "10b-error-dialog.png"
        error_dialog.close()

        dataset_dialog = DataSetManagerDialog(repo, window, window)
        _save_widget(dataset_dialog, OUTPUT_DIR / "11-dataset-manager-entry.png", app, QSize(860, 700))
        captures["dataset_manager_entry"] = "11-dataset-manager-entry.png"
        dataset_dialog._show_batch_progress("正在批量导入 2/5", "当前文件：sample-02.csv", 2, 5)
        _save_widget(dataset_dialog, OUTPUT_DIR / "11b-dataset-manager-batch.png", app, QSize(860, 700))
        captures["dataset_manager_batch"] = "11b-dataset-manager-batch.png"
        dataset_dialog.close()

        empty_repo = Repository(_root / "empty.db")
        empty_dataset_dialog = DataSetManagerDialog(empty_repo, window, window)
        _save_widget(empty_dataset_dialog, OUTPUT_DIR / "11c-dataset-manager-empty.png", app, QSize(860, 700))
        captures["dataset_manager_empty"] = "11c-dataset-manager-empty.png"
        empty_dataset_dialog.close()

        session_dialog = SessionLibraryDialog(repo, window, window)
        _save_widget(session_dialog, OUTPUT_DIR / "12-session-library-entry.png", app, QSize(920, 720))
        captures["session_library_entry"] = "12-session-library-entry.png"
        session_dialog.session_filter.setText("截图示例")
        _save_widget(session_dialog, OUTPUT_DIR / "12b-session-library-filtered.png", app, QSize(920, 720))
        captures["session_library_filtered"] = "12b-session-library-filtered.png"
        session_dialog.close()

        empty_session_dialog = SessionLibraryDialog(empty_repo, window, window)
        _save_widget(empty_session_dialog, OUTPUT_DIR / "12c-session-library-empty.png", app, QSize(920, 720))
        captures["session_library_empty"] = "12c-session-library-empty.png"
        empty_session_dialog.close()

        _seed_trade_review(window)
        window.open_trade_history_dialog()
        _process_events(app)
        _save_widget(window, OUTPUT_DIR / "13-narrow-supported-desktop.png", app, QSize(1240, 820))
        captures["narrow_supported_desktop"] = "13-narrow-supported-desktop.png"
    finally:
        window.close()
        window.deleteLater()
        _process_events(app)

    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(captures, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(OUTPUT_DIR), "captures": captures}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
