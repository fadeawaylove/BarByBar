from __future__ import annotations

import threading
from pathlib import Path
from time import perf_counter

from loguru import logger
from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QCloseEvent

from barbybar.data.csv_importer import MissingColumnsError
from barbybar.data.tick_size import snap_price
from barbybar.data.timeframe import normalize_timeframe, supported_replay_timeframes
from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import (
    ActionType,
    DataSet,
    OrderLineType,
    PositionState,
    ReviewSession,
    SessionStats,
    SessionStatus,
    WindowBars,
)
from barbybar.storage.repository import Repository
from barbybar.ui.chart_widget import ChartWidget

REQUIRED_IMPORT_FIELDS = ["datetime", "open", "high", "low", "close", "volume"]
INITIAL_WINDOW_BEFORE = 150
INITIAL_WINDOW_AFTER = 30
EXTEND_WINDOW_BEFORE = 150
EXTEND_WINDOW_AFTER = 150
WINDOW_BUFFER_THRESHOLD = 20
AUTO_SAVE_DELAY_MS = 800


def _thread_id() -> int:
    return threading.get_ident()


class BusyOverlay(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("busyOverlay")
        self.setStyleSheet(
            "#busyOverlay { background: rgba(246, 248, 251, 180); }"
            "#busyCard { background: rgba(255,255,255,245); border: 1px solid #d9e0e6; border-radius: 10px; }"
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        self.card = QWidget(self)
        self.card.setObjectName("busyCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(8)
        self.title_label = QLabel("正在处理...")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #2c2c2c;")
        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("font-size: 12px; color: #4f5b66;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        card_layout.addWidget(self.title_label)
        card_layout.addWidget(self.detail_label)
        card_layout.addWidget(self.progress)
        layout.addWidget(self.card, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        self.hide()

    def set_message(self, title: str, detail: str = "") -> None:
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))


class SessionLoadWorker(QObject):
    finished = Signal(int, object)
    failed = Signal(int, str)

    def __init__(
        self,
        db_path: str | Path | None,
        session_id: int,
        chart_timeframe: str | None,
        anchor_time,
        load_id: int,
    ) -> None:
        super().__init__()
        self.db_path = db_path
        self.session_id = session_id
        self.chart_timeframe = chart_timeframe
        self.anchor_time = anchor_time
        self.load_id = load_id

    def run(self) -> None:
        started = perf_counter()
        log = logger.bind(
            component="session_load_worker",
            session_id=self.session_id,
            load_id=self.load_id,
            chart_timeframe=self.chart_timeframe or "",
            thread_id=_thread_id(),
        )
        try:
            repo = Repository(self.db_path)
            session_step = perf_counter()
            session = repo.get_session(self.session_id)
            log.debug("event=get_session elapsed_ms={elapsed_ms:.3f}", elapsed_ms=(perf_counter() - session_step) * 1000)
            dataset_step = perf_counter()
            dataset = repo.get_dataset(session.dataset_id)
            log = log.bind(dataset_id=session.dataset_id)
            log.debug("event=get_dataset elapsed_ms={elapsed_ms:.3f}", elapsed_ms=(perf_counter() - dataset_step) * 1000)
            actions_step = perf_counter()
            actions = repo.get_session_actions(session.id or 0)
            log.debug("event=get_session_actions elapsed_ms={elapsed_ms:.3f}", elapsed_ms=(perf_counter() - actions_step) * 1000)
            order_step = perf_counter()
            order_lines = repo.get_order_lines(session.id or 0)
            log.debug("event=get_order_lines elapsed_ms={elapsed_ms:.3f}", elapsed_ms=(perf_counter() - order_step) * 1000)
            timeframe = self.chart_timeframe or session.chart_timeframe
            window_step = perf_counter()
            window = repo.get_chart_window(
                session.id or 0,
                timeframe,
                self.anchor_time or session.current_bar_time,
                INITIAL_WINDOW_BEFORE,
                INITIAL_WINDOW_AFTER,
            )
            log.bind(chart_timeframe=timeframe).debug(
                "event=get_chart_window elapsed_ms={elapsed_ms:.3f} bars={bars} start={start} end={end} total={total}",
                elapsed_ms=(perf_counter() - window_step) * 1000,
                bars=len(window.bars),
                start=window.global_start_index,
                end=window.global_end_index,
                total=window.total_count,
            )
            log.bind(chart_timeframe=timeframe).info(
                "event=session_load_complete elapsed_ms={elapsed_ms:.3f}",
                elapsed_ms=(perf_counter() - started) * 1000,
            )
            self.finished.emit(
                self.load_id,
                {
                    "session": session,
                    "dataset": dataset,
                    "actions": actions,
                    "order_lines": order_lines,
                    "chart_timeframe": timeframe,
                    "anchor_time": self.anchor_time or session.current_bar_time,
                    "window": window,
                }
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("event=session_load_failed error={error}", error=str(exc))
            self.failed.emit(self.load_id, str(exc))


class ColumnMappingDialog(QDialog):
    def __init__(
        self,
        csv_path: str,
        available_headers: list[str],
        detected_field_map: dict[str, str],
        missing_fields: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("映射 CSV 列")
        self._available_headers = available_headers
        self._combos: dict[str, QComboBox] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"文件: {Path(csv_path).name}"))
        layout.addWidget(QLabel("请确认 CSV 列与系统字段的对应关系。"))

        form = QFormLayout()
        for field in REQUIRED_IMPORT_FIELDS:
            combo = QComboBox()
            combo.addItem("请选择列名")
            for header in available_headers:
                combo.addItem(header)
            preset = detected_field_map.get(field)
            if preset and preset in available_headers:
                combo.setCurrentText(preset)
            self._combos[field] = combo
            label = field
            if field in missing_fields:
                label = f"{field} *"
            form.addRow(label, combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_field_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for field, combo in self._combos.items():
            value = combo.currentText().strip()
            if value and value != "请选择列名":
                result[field] = value
        return result

    def accept(self) -> None:
        selected = self.get_field_map()
        missing = [field for field in REQUIRED_IMPORT_FIELDS if field not in selected]
        if missing:
            QMessageBox.warning(self, "映射不完整", f"请补齐以下字段: {', '.join(missing)}")
            return
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository) -> None:
        super().__init__()
        self.repo = repo
        self.setWindowTitle("BarByBar")
        self.engine: ReviewEngine | None = None
        self.current_dataset: DataSet | None = None
        self.current_session_id: int | None = None
        self.timeframe_buttons: dict[str, QPushButton] = {}
        self._busy_overlay: BusyOverlay | None = None
        self._busy_cursor_active = False
        self._active_loader_thread: QThread | None = None
        self._active_loader_worker: SessionLoadWorker | None = None
        self._active_loader_token = 0
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.timeout.connect(self._perform_auto_save)
        self._session_dirty = False
        self._draw_order_buttons: dict[OrderLineType, QPushButton] = {}

        self._build_ui()
        self._refresh_lists()

    def _build_ui(self) -> None:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.splitter = QSplitter()
        self.splitter.addWidget(self._build_left_panel())
        self.splitter.addWidget(self._build_center_panel())
        self.splitter.addWidget(self._build_right_panel())
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([280, 900, 360])
        container_layout.addWidget(self.splitter)

        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar())
        self._busy_overlay = BusyOverlay(container)
        self._busy_overlay.setGeometry(container.rect())

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        import_button = QPushButton("导入 CSV")
        import_button.clicked.connect(self.import_csv)
        layout.addWidget(import_button)

        self.dataset_list = QListWidget()
        self.dataset_list.itemSelectionChanged.connect(self._handle_dataset_selection)
        layout.addWidget(QLabel("数据集"))
        layout.addWidget(self.dataset_list)

        create_session_button = QPushButton("基于所选数据创建复盘")
        create_session_button.clicked.connect(self.create_session)
        layout.addWidget(create_session_button)

        layout.addWidget(QLabel("案例库"))
        self.session_filter = QLineEdit()
        self.session_filter.setPlaceholderText("按品种或标签筛选")
        self.session_filter.textChanged.connect(self._refresh_session_list)
        layout.addWidget(self.session_filter)

        self.session_list = QListWidget()
        self.session_list.itemDoubleClicked.connect(self._open_selected_session)
        layout.addWidget(self.session_list)
        return panel

    def _build_center_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        chart_toolbar = QHBoxLayout()
        self.timeframe_button_group = QButtonGroup(self)
        self.timeframe_button_group.setExclusive(True)
        for timeframe in ["1m", "5m", "15m", "30m", "60m"]:
            button = QPushButton(timeframe)
            button.setCheckable(True)
            button.clicked.connect(lambda _, tf=timeframe: self.change_chart_timeframe(tf))
            self.timeframe_button_group.addButton(button)
            self.timeframe_buttons[timeframe] = button
            chart_toolbar.addWidget(button)
        chart_toolbar.addStretch(1)
        layout.addLayout(chart_toolbar)

        self.chart_widget = ChartWidget()
        self.chart_widget.orderLineCreated.connect(self._handle_chart_order_line_created)
        self.chart_widget.orderLineMoved.connect(self._handle_chart_order_line_moved)
        self.chart_widget.orderPreviewConfirmed.connect(self._handle_order_preview_confirmed)
        self.chart_widget.orderLineActionRequested.connect(self._handle_order_line_action_requested)
        layout.addWidget(self.chart_widget)

        controls = QHBoxLayout()
        self.prev_button = QPushButton("上一步")
        self.prev_button.clicked.connect(self.step_back)
        controls.addWidget(self.prev_button)

        self.next_button = QPushButton("下一根")
        self.next_button.clicked.connect(self.step_forward)
        controls.addWidget(self.next_button)

        self.jump_spin = QSpinBox()
        self.jump_spin.setMinimum(0)
        self.jump_spin.valueChanged.connect(self.jump_to_bar)
        controls.addWidget(QLabel("跳转 Bar"))
        controls.addWidget(self.jump_spin)

        self.reset_view_button = QPushButton("重置视图")
        self.reset_view_button.clicked.connect(lambda: self.chart_widget.reset_viewport(follow_latest=True))
        controls.addWidget(self.reset_view_button)

        self.draw_button = QPushButton("画线模式")
        self.draw_button.setCheckable(True)
        self.draw_button.clicked.connect(lambda checked: self.chart_widget.set_draw_mode(checked))
        controls.addWidget(self.draw_button)

        self.clear_lines_button = QPushButton("清除画线")
        self.clear_lines_button.clicked.connect(self.chart_widget.clear_lines)
        controls.addWidget(self.clear_lines_button)

        controls.addStretch(1)
        self.progress_label = QLabel("未开始")
        controls.addWidget(self.progress_label)
        layout.addLayout(controls)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        action_box = QGroupBox("交易动作")
        action_layout = QFormLayout(action_box)
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 9999)
        self.quantity_spin.setValue(1)
        self.quantity_spin.setSingleStep(1)
        action_layout.addRow("数量", self.quantity_spin)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setDecimals(4)
        self.price_spin.setRange(-999999.0, 999999.0)
        self.price_spin.setValue(0.0)
        action_layout.addRow("价格(0=悬停价/当前收盘)", self.price_spin)

        grid = QGridLayout()
        action_defs = [
            ("开多", ActionType.OPEN_LONG),
            ("开空", ActionType.OPEN_SHORT),
            ("立即平仓", ActionType.CLOSE),
        ]
        for index, (label, action_type) in enumerate(action_defs):
            button = QPushButton(label)
            button.clicked.connect(lambda _, kind=action_type: self.record_action(kind))
            grid.addWidget(button, index // 2, index % 2)
        action_layout.addRow(grid)

        draw_box = QGroupBox("画线下单")
        draw_layout = QFormLayout(draw_box)

        self.draw_quantity_spin = QSpinBox()
        self.draw_quantity_spin.setRange(1, 9999)
        self.draw_quantity_spin.setValue(1)
        self.draw_quantity_spin.setSingleStep(1)
        self.draw_quantity_spin.valueChanged.connect(self.quantity_spin.setValue)
        self.quantity_spin.valueChanged.connect(self.draw_quantity_spin.setValue)
        draw_layout.addRow("手数", self.draw_quantity_spin)

        self.tick_size_spin = QDoubleSpinBox()
        self.tick_size_spin.setDecimals(4)
        self.tick_size_spin.setRange(0.0001, 999999.0)
        self.tick_size_spin.setValue(1.0)
        self.tick_size_spin.setSingleStep(0.1)
        self.tick_size_spin.valueChanged.connect(self._handle_tick_size_changed)
        draw_layout.addRow("最小跳动", self.tick_size_spin)

        draw_grid = QGridLayout()
        for index, (label, order_type) in enumerate(
            [
                ("买", OrderLineType.ENTRY_LONG),
                ("卖", OrderLineType.ENTRY_SHORT),
                ("平", OrderLineType.EXIT),
                ("反", OrderLineType.REVERSE),
            ]
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, kind=order_type: self._toggle_draw_order_preview(kind, checked))
            self._draw_order_buttons[order_type] = button
            draw_grid.addWidget(button, index // 2, index % 2)
        cancel_draw_button = QPushButton("取消画线下单")
        cancel_draw_button.clicked.connect(self.cancel_draw_order_preview)
        draw_grid.addWidget(cancel_draw_button, 2, 0, 1, 2)
        draw_layout.addRow(draw_grid)
        action_layout.addRow(draw_box)

        line_grid = QGridLayout()
        line_defs = [
            ("图上止损线", OrderLineType.STOP_LOSS),
            ("图上止盈线", OrderLineType.TAKE_PROFIT),
        ]
        for index, (label, order_type) in enumerate(line_defs):
            button = QPushButton(label)
            button.clicked.connect(lambda _, kind=order_type: self.create_order_line(kind))
            line_grid.addWidget(button, 1 + (index // 2), index % 2)
        action_layout.addRow(line_grid)

        manage_grid = QGridLayout()
        cancel_entries_button = QPushButton("撤销条件单")
        cancel_entries_button.clicked.connect(self.cancel_entry_order_lines)
        manage_grid.addWidget(cancel_entries_button, 0, 0)

        clear_protective_button = QPushButton("清除止损止盈")
        clear_protective_button.clicked.connect(self.clear_protective_lines)
        manage_grid.addWidget(clear_protective_button, 0, 1)

        break_even_button = QPushButton("一键保本")
        break_even_button.clicked.connect(self.move_stop_to_break_even)
        manage_grid.addWidget(break_even_button, 1, 0, 1, 2)
        action_layout.addRow(manage_grid)
        layout.addWidget(action_box)

        stats_box = QGroupBox("统计")
        stats_layout = QVBoxLayout(stats_box)
        self.stats_label = QLabel("暂无统计")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)
        layout.addWidget(stats_box)

        session_actions = QHBoxLayout()
        save_button = QPushButton("保存会话")
        save_button.clicked.connect(self.save_session)
        session_actions.addWidget(save_button)

        complete_button = QPushButton("标记完成")
        complete_button.clicked.connect(self.complete_session)
        session_actions.addWidget(complete_button)
        layout.addLayout(session_actions)
        layout.addStretch(1)
        return panel

    def import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 CSV", str(Path.cwd()), "CSV Files (*.csv)")
        if not path:
            return
        symbol, ok = QInputDialog.getText(self, "品种代码", "输入品种代码，例如 IF")
        if not ok or not symbol.strip():
            return
        self._import_csv_with_mapping(path, symbol.strip().upper())

    def _import_csv_with_mapping(self, path: str, symbol: str, field_map: dict[str, str] | None = None) -> None:
        log = logger.bind(component="csv_import", symbol=symbol, path=path)
        try:
            dataset = self.repo.import_csv(path, symbol, "1m", field_map=field_map)
        except MissingColumnsError as exc:
            log.warning("event=missing_columns missing_fields={missing_fields}", missing_fields=",".join(exc.missing_fields))
            dialog = ColumnMappingDialog(
                csv_path=path,
                available_headers=exc.available_headers,
                detected_field_map=exc.detected_field_map,
                missing_fields=exc.missing_fields,
                parent=self,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                log.info("event=column_mapping_cancelled")
                return
            try:
                dataset = self.repo.import_csv(path, symbol, "1m", field_map=dialog.get_field_map())
            except Exception as retry_exc:  # noqa: BLE001
                log.exception("event=import_failed_after_mapping error={error}", error=str(retry_exc))
                QMessageBox.critical(self, "导入失败", str(retry_exc))
                return
        except Exception as exc:  # noqa: BLE001
            log.exception("event=import_failed error={error}", error=str(exc))
            QMessageBox.critical(self, "导入失败", str(exc))
            return
        log.info("event=import_success dataset_id={} timeframe={}", dataset.id, dataset.timeframe)
        self.statusBar().showMessage(f"已导入 {dataset.symbol} 1m", 5000)
        self._refresh_lists()

    def create_session(self) -> None:
        if not self.current_dataset:
            QMessageBox.information(self, "提示", "请先选择一个数据集。")
            return
        bars = self.repo.get_bars(self.current_dataset.id or 0)
        start_index = max(0, min(50, len(bars) - 1))
        session = self.repo.create_session(self.current_dataset.id or 0, start_index=start_index)
        logger.bind(component="session", session_id=session.id, dataset_id=self.current_dataset.id).info(
            "event=create_session start_index={start_index}",
            start_index=start_index,
        )
        self.statusBar().showMessage("正在创建并加载复盘会话", 4000)
        self._start_session_load(
            session.id or 0,
            title="正在创建复盘...",
            detail="正在初始化会话并构建图表",
        )

    def _refresh_lists(self) -> None:
        self.dataset_list.clear()
        for dataset in self.repo.list_datasets():
            item = QListWidgetItem(
                f"{dataset.symbol} {dataset.timeframe} | "
                f"{dataset.start_time:%m-%d %H:%M} -> {dataset.end_time:%m-%d %H:%M}"
            )
            item.setData(32, dataset.id)
            self.dataset_list.addItem(item)
        self._refresh_session_list()

    def _refresh_session_list(self) -> None:
        filter_text = self.session_filter.text().strip()
        self.session_list.clear()
        symbol = filter_text.upper() if filter_text.isalpha() else ""
        tag = filter_text if filter_text and not filter_text.isalpha() else ""
        for session in self.repo.list_sessions(symbol=symbol, tag=tag):
            status_text = "完成" if session.status is SessionStatus.COMPLETED else "进行中"
            item = QListWidgetItem(f"{session.title} | {session.timeframe} | {status_text} | PnL {session.stats.total_pnl:.2f}")
            item.setData(32, session.id)
            self.session_list.addItem(item)

    def _handle_dataset_selection(self) -> None:
        item = self.dataset_list.currentItem()
        if item is None:
            return
        dataset_id = item.data(32)
        self.current_dataset = self.repo.get_dataset(dataset_id)

    def _open_selected_session(self, item: QListWidgetItem) -> None:
        self._load_session(item.data(32))

    def _load_session(self, session_id: int) -> None:
        self._start_session_load(
            session_id,
            title="正在加载案例...",
            detail="正在读取数据并构建图表",
        )

    def _update_ui_from_engine(self) -> None:
        if not self.engine:
            return
        current = self.engine.session.current_index
        total = self.engine.total_count
        bar = self.engine.current_bar
        self.chart_widget.set_cursor(current)
        self.chart_widget.set_order_lines(self.engine.display_order_lines())
        self.progress_label.setText(f"{current + 1}/{total} | {bar.timestamp:%Y-%m-%d %H:%M}")
        self.jump_spin.blockSignals(True)
        self.jump_spin.setValue(current)
        self.jump_spin.blockSignals(False)
        position = self.engine.session.position
        stats = self.engine.session.stats
        direction = position.direction or "flat"
        self.stats_label.setText(
            "\n".join(
                [
                    f"方向: {direction}",
                    f"周期: 原始 {self.engine.session.timeframe} / 当前 {self.engine.session.chart_timeframe}",
                    f"仓位: {position.quantity:.2f}",
                    f"均价: {position.average_price:.2f}",
                    f"止损/止盈: {position.stop_loss or '-'} / {position.take_profit or '-'}",
                    f"已实现 PnL: {position.realized_pnl:.2f}",
                    f"总交易: {stats.total_trades}",
                    f"胜率: {stats.win_rate:.1%}",
                    f"盈亏比: {stats.profit_factor:.2f}",
                    f"最大回撤: {stats.max_drawdown:.2f}",
                ]
            )
        )
        self._sync_draw_order_controls()
        self.tick_size_spin.blockSignals(True)
        self.tick_size_spin.setValue(self.engine.session.tick_size)
        self.tick_size_spin.blockSignals(False)
        self.chart_widget.set_tick_size(self.engine.session.tick_size)

    def step_forward(self) -> None:
        if not self.engine:
            return
        self._ensure_window_for_forward()
        if not self.engine.step_forward():
            return
        self._update_ui_from_engine()
        self._schedule_auto_save("step_forward")

    def step_back(self) -> None:
        if not self.engine:
            return
        self._ensure_window_for_backward()
        self.engine.step_back()
        self._update_ui_from_engine()
        self._schedule_auto_save("step_back")

    def jump_to_bar(self, index: int) -> None:
        if not self.engine:
            return
        if index < self.engine.window_start_index or index > self.engine.window_end_index:
            if not self.current_session_id:
                return
            self._flush_pending_auto_save("jump_to_remote_bar")
            anchor_time = self.repo.get_chart_bar_time(self.current_session_id, self.engine.session.chart_timeframe, index)
            self._start_session_load(
                self.current_session_id,
                chart_timeframe=self.engine.session.chart_timeframe,
                anchor_time=anchor_time,
                title="正在跳转...",
                detail="正在定位目标 K 线并刷新图表",
            )
            return
        self.engine.jump_to(index)
        self._update_ui_from_engine()
        self._schedule_auto_save("jump_to_bar")

    def record_action(self, action_type: ActionType) -> None:
        if not self.engine:
            QMessageBox.information(self, "提示", "请先创建或打开一个复盘会话。")
            return
        price = self._resolve_price(self.price_spin.value() or None)
        try:
            self.engine.record_action(action_type, quantity=float(self.quantity_spin.value()), price=price)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "event=record_action_failed session_id={} action_type={} error={}",
                self.current_session_id,
                action_type.value,
                str(exc),
            )
            QMessageBox.warning(self, "动作失败", str(exc))
            return
        self._update_ui_from_engine()
        self.save_session(trigger="record_action")

    def create_order_line(self, order_type: OrderLineType) -> None:
        if not self.engine:
            QMessageBox.information(self, "提示", "请先创建或打开一个复盘会话。")
            return
        explicit_price = self.price_spin.value()
        if explicit_price:
            self._place_order_line(order_type, explicit_price)
            return
        hover_price = self.chart_widget.last_hover_price
        if hover_price is not None:
            self._place_order_line(order_type, hover_price)
            return
        if self.draw_button.isChecked():
            self.draw_button.setChecked(False)
            self.chart_widget.set_draw_mode(False)
        self.chart_widget.set_trade_line_mode(order_type.value)
        self.statusBar().showMessage(f"请在图上点击价格创建{self._order_type_label(order_type)}", 3000)

    def cancel_entry_order_lines(self) -> None:
        if not self.engine:
            return
        self.engine.cancel_entry_order_lines()
        self._update_ui_from_engine()
        self.save_session(trigger="cancel_entry_orders")

    def clear_protective_lines(self) -> None:
        if not self.engine:
            return
        self.engine.clear_protective_lines()
        self._update_ui_from_engine()
        self.save_session(trigger="clear_protective_lines")

    def move_stop_to_break_even(self) -> None:
        if not self.engine:
            return
        try:
            self.engine.move_stop_to_break_even()
        except Exception as exc:  # noqa: BLE001
            logger.warning("event=move_stop_to_break_even_failed session_id={} error={}", self.current_session_id, str(exc))
            QMessageBox.warning(self, "操作失败", str(exc))
            return
        self._update_ui_from_engine()
        self.save_session(trigger="move_stop_to_break_even")

    def save_session(self, *, trigger: str = "manual") -> None:
        if not self.engine:
            return
        self._auto_save_timer.stop()
        self.engine.session.current_bar_time = self.engine.current_bar.timestamp
        saved = self.repo.save_session(self.engine.session, self.engine.actions, self.engine.order_lines)
        self.engine.session = saved
        self.engine.order_lines = self.repo.get_order_lines(saved.id or 0)
        self._session_dirty = False
        logger.bind(
            component="session",
            session_id=saved.id,
            chart_timeframe=saved.chart_timeframe,
            current_index=saved.current_index,
            trigger=trigger,
        ).info("event=save_session")
        self._refresh_session_list()
        self.statusBar().showMessage("会话已保存", 2500)

    def complete_session(self) -> None:
        if not self.engine:
            return
        self.engine.complete()
        self.save_session(trigger="complete_session")
        self._update_ui_from_engine()

    def change_chart_timeframe(self, timeframe: str) -> None:
        if not self.engine or not self.current_session_id or not timeframe:
            return
        normalized = normalize_timeframe(timeframe)
        if normalized not in self.timeframe_buttons:
            logger.bind(component="chart", session_id=self.current_session_id, requested_timeframe=normalized).warning(
                "event=unsupported_chart_timeframe"
            )
            return
        if normalized == self.engine.session.chart_timeframe:
            return
        self._flush_pending_auto_save("change_chart_timeframe")
        logger.bind(component="chart", session_id=self.current_session_id, chart_timeframe=normalized).info(
            "event=change_chart_timeframe"
        )
        anchor_time = self.engine.session.current_bar_time or self.engine.current_bar.timestamp
        self._start_session_load(
            self.current_session_id,
            chart_timeframe=normalized,
            anchor_time=anchor_time,
            title=f"正在切换到 {normalized}...",
            detail="正在重建周期数据并刷新图表",
        )

    def _set_timeframe_choices(self, source_timeframe: str, current_timeframe: str) -> None:
        choices = supported_replay_timeframes(source_timeframe)
        current = normalize_timeframe(current_timeframe)
        for timeframe, button in self.timeframe_buttons.items():
            button.blockSignals(True)
            button.setEnabled(timeframe in choices)
            button.setChecked(timeframe == current)
            button.blockSignals(False)

    def _build_engine(
        self,
        session: ReviewSession,
        actions,
        order_lines,
        chart_timeframe: str,
        anchor_time,
        window: WindowBars,
    ) -> ReviewEngine:
        bars = window.bars
        if not bars:
            raise ValueError(f"当前数据不足以生成 {chart_timeframe} K线。")
        rebuilt_session = ReviewSession(
            id=session.id,
            dataset_id=session.dataset_id,
            symbol=session.symbol,
            timeframe=session.timeframe,
            chart_timeframe=chart_timeframe,
            start_index=min(session.start_index, max(0, window.total_count - 1)),
            current_index=window.anchor_global_index,
            current_bar_time=anchor_time,
            tick_size=session.tick_size,
            status=session.status,
            title=session.title,
            notes=session.notes,
            tags=list(session.tags),
            position=PositionState(),
            stats=SessionStats(),
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        engine = ReviewEngine(
            rebuilt_session,
            bars,
            window_start_index=window.global_start_index,
            total_count=window.total_count,
        )
        for action in actions:
            engine._apply_action(action)
            engine.actions.append(action)
        engine.order_lines = list(order_lines)
        engine._reconcile_state()
        if bars:
            engine.session.current_bar_time = anchor_time or engine.current_bar.timestamp
        return engine

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._resize_busy_overlay()

    def show_busy_overlay(self, title: str, detail: str = "") -> None:
        if not self._busy_overlay:
            return
        self._log_ui_thread("show_busy_overlay")
        self._busy_overlay.set_message(title, detail)
        self._resize_busy_overlay()
        if not self._busy_cursor_active:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self._busy_cursor_active = True
        logger.bind(component="busy_overlay", thread_id=_thread_id()).debug(
            "event=show_busy_overlay title={title}",
            title=title,
        )
        self._busy_overlay.raise_()
        self._busy_overlay.show()

    def hide_busy_overlay(self) -> None:
        if not self._busy_overlay:
            return
        self._log_ui_thread("hide_busy_overlay")
        self._busy_overlay.hide()
        if self._busy_cursor_active:
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
        self._busy_cursor_active = False
        logger.bind(component="busy_overlay", thread_id=_thread_id()).debug("event=hide_busy_overlay")

    def _resize_busy_overlay(self) -> None:
        if self._busy_overlay and self.centralWidget():
            self._log_ui_thread("resize_busy_overlay")
            self._busy_overlay.setGeometry(self.centralWidget().rect())

    def _start_session_load(
        self,
        session_id: int,
        *,
        chart_timeframe: str | None = None,
        anchor_time=None,
        title: str,
        detail: str = "",
    ) -> None:
        self._flush_pending_auto_save("start_session_load")
        self.current_session_id = session_id
        self._active_loader_token += 1
        token = self._active_loader_token
        logger.bind(
            component="session_load",
            session_id=session_id,
            load_id=token,
            chart_timeframe=chart_timeframe or "",
            thread_id=_thread_id(),
        ).info("event=start_load title={title}", title=title)
        self.show_busy_overlay(title, detail)

        thread = QThread(self)
        worker = SessionLoadWorker(self.repo.db_path, session_id, chart_timeframe, anchor_time, token)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_loaded_session, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._handle_load_failed, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._handle_loader_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._active_loader_thread = thread
        self._active_loader_worker = worker
        thread.start()

    @Slot(int, object)
    def _handle_loaded_session(self, token: int, payload: object) -> None:
        self._log_ui_thread("handle_loaded_session")
        if token != self._active_loader_token:
            logger.bind(component="session_load", load_id=token).debug("event=discard_stale_load_result")
            return
        started = perf_counter()
        log = logger.bind(component="session_load", load_id=token, thread_id=_thread_id())
        assert isinstance(payload, dict)
        try:
            session = payload["session"]
            actions = payload["actions"]
            order_lines = payload["order_lines"]
            dataset = payload["dataset"]
            chart_timeframe = payload["chart_timeframe"]
            anchor_time = payload["anchor_time"]
            window = payload["window"]
            session.chart_timeframe = chart_timeframe
            if anchor_time is not None:
                session.current_bar_time = anchor_time
            self.current_dataset = dataset
            choice_step = perf_counter()
            self._set_timeframe_choices(dataset.timeframe, chart_timeframe)
            log.bind(session_id=session.id, dataset_id=dataset.id).debug(
                "event=set_timeframe_choices elapsed_ms={elapsed_ms:.3f}",
                elapsed_ms=(perf_counter() - choice_step) * 1000,
            )
            engine_step = perf_counter()
            self.engine = self._build_engine(session, actions, order_lines, chart_timeframe, session.current_bar_time, window)
            log.bind(session_id=session.id, dataset_id=dataset.id).debug(
                "event=build_engine elapsed_ms={elapsed_ms:.3f}",
                elapsed_ms=(perf_counter() - engine_step) * 1000,
            )
            self.jump_spin.blockSignals(True)
            self.jump_spin.setMaximum(max(0, self.engine.total_count - 1))
            self.jump_spin.setValue(self.engine.session.current_index)
            self.jump_spin.blockSignals(False)
            chart_step = perf_counter()
            self.chart_widget.set_window_data(
                self.engine.bars,
                self.engine.session.current_index,
                self.engine.total_count,
                self.engine.window_start_index,
            )
            log.bind(session_id=session.id, dataset_id=dataset.id).debug(
                "event=set_window_data elapsed_ms={elapsed_ms:.3f} bars={bars} start={start} end={end}",
                elapsed_ms=(perf_counter() - chart_step) * 1000,
                bars=len(self.engine.bars),
                start=self.engine.window_start_index,
                end=self.engine.window_end_index,
            )
            ui_step = perf_counter()
            self._update_ui_from_engine()
            log.bind(session_id=session.id, dataset_id=dataset.id).debug(
                "event=update_ui elapsed_ms={elapsed_ms:.3f}",
                elapsed_ms=(perf_counter() - ui_step) * 1000,
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("event=handle_loaded_session_failed error={error}", error=str(exc))
            self._handle_load_failed(token, str(exc))
            return
        log.bind(session_id=session.id, dataset_id=dataset.id, chart_timeframe=chart_timeframe).info(
            "event=load_applied elapsed_ms={elapsed_ms:.3f}",
            elapsed_ms=(perf_counter() - started) * 1000,
        )
        self.hide_busy_overlay()

    @Slot(int, str)
    def _handle_load_failed(self, token: int, message: str) -> None:
        self._log_ui_thread("handle_load_failed")
        if token != self._active_loader_token:
            return
        self.hide_busy_overlay()
        logger.bind(component="session_load", load_id=token, thread_id=_thread_id()).warning(
            "event=load_failed message={message}",
            message=message,
        )
        QMessageBox.warning(self, "加载失败", message)

    @Slot()
    def _handle_loader_thread_finished(self) -> None:
        self._active_loader_thread = None
        self._active_loader_worker = None
        logger.bind(component="session_load", thread_id=_thread_id()).debug("event=loader_thread_finished")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._flush_pending_auto_save("close_event")
        self.hide_busy_overlay()
        if self._active_loader_thread and self._active_loader_thread.isRunning():
            logger.bind(component="session_load").warning("event=close_waiting_for_loader_thread")
            self._active_loader_thread.quit()
            self._active_loader_thread.wait(2000)
        super().closeEvent(event)

    def _log_ui_thread(self, operation: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        current_thread = QThread.currentThread()
        main_thread = app.thread()
        if current_thread is not main_thread:
            logger.bind(
                component="ui_thread",
                operation=operation,
                thread_id=_thread_id(),
            ).error("event=wrong_ui_thread")

    def _ensure_window_for_forward(self) -> None:
        if (
            not self.engine
            or not self.current_session_id
            or not self.engine.can_step_forward()
            or self.engine.forward_buffer > WINDOW_BUFFER_THRESHOLD
        ):
            return
        logger.bind(
            component="chart_window",
            session_id=self.current_session_id,
            chart_timeframe=self.engine.session.chart_timeframe,
        ).debug("event=extend_forward_window current_index={} buffer={}", self.engine.session.current_index, self.engine.forward_buffer)
        window = self.repo.get_chart_window(
            self.current_session_id,
            self.engine.session.chart_timeframe,
            self.engine.current_bar.timestamp,
            EXTEND_WINDOW_BEFORE,
            EXTEND_WINDOW_AFTER,
        )
        self.engine.replace_window(window.bars, window.global_start_index, window.total_count)
        self.chart_widget.set_window_data(
            self.engine.bars,
            self.engine.session.current_index,
            self.engine.total_count,
            self.engine.window_start_index,
            preserve_viewport=True,
        )

    def _ensure_window_for_backward(self) -> None:
        if not self.engine or not self.current_session_id:
            return
        previous_index = self.engine.previous_history_index()
        if previous_index is None:
            return
        if previous_index >= self.engine.window_start_index and self.engine.backward_buffer > WINDOW_BUFFER_THRESHOLD:
            return
        logger.bind(
            component="chart_window",
            session_id=self.current_session_id,
            chart_timeframe=self.engine.session.chart_timeframe,
        ).debug("event=extend_backward_window current_index={} buffer={}", self.engine.session.current_index, self.engine.backward_buffer)
        window = self.repo.get_chart_window(
            self.current_session_id,
            self.engine.session.chart_timeframe,
            self.engine.current_bar.timestamp,
            EXTEND_WINDOW_BEFORE,
            EXTEND_WINDOW_AFTER,
        )
        self.engine.replace_window(window.bars, window.global_start_index, window.total_count)
        self.chart_widget.set_window_data(
            self.engine.bars,
            self.engine.session.current_index,
            self.engine.total_count,
            self.engine.window_start_index,
            preserve_viewport=True,
        )

    def _schedule_auto_save(self, reason: str) -> None:
        if not self.engine:
            return
        self._session_dirty = True
        logger.bind(
            component="session",
            session_id=self.engine.session.id,
            reason=reason,
            delay_ms=AUTO_SAVE_DELAY_MS,
        ).debug("event=auto_save_scheduled")
        self._auto_save_timer.start(AUTO_SAVE_DELAY_MS)

    def _flush_pending_auto_save(self, reason: str) -> None:
        if self._auto_save_timer.isActive():
            self._auto_save_timer.stop()
        if self._session_dirty:
            self.save_session(trigger=f"auto_flush:{reason}")

    @Slot()
    def _perform_auto_save(self) -> None:
        if not self._session_dirty or not self.engine:
            return
        self.save_session(trigger="auto_timer")

    def _resolve_price(self, explicit_price: float | None) -> float | None:
        if explicit_price not in (None, 0):
            return self._snap_price(explicit_price)
        if self.chart_widget.last_hover_price is not None:
            return self._snap_price(self.chart_widget.last_hover_price)
        if self.engine:
            return self._snap_price(self.engine.current_bar.close)
        return explicit_price

    def _current_tick_size(self) -> float:
        if self.engine:
            return self.engine.session.tick_size
        return max(self.tick_size_spin.value(), 0.0001)

    def _snap_price(self, price: float) -> float:
        return snap_price(price, self._current_tick_size())

    def _toggle_draw_order_preview(self, order_type: OrderLineType, checked: bool) -> None:
        if not self.engine:
            QMessageBox.information(self, "提示", "请先创建或打开一个复盘会话。")
            return
        if not checked:
            if self.chart_widget.trade_line_mode is None and self.chart_widget.last_hover_price is not None:
                self.chart_widget.cancel_order_preview()
            return
        if self.draw_button.isChecked():
            self.draw_button.setChecked(False)
            self.chart_widget.set_draw_mode(False)
        self.chart_widget.begin_order_preview(order_type.value, float(self.draw_quantity_spin.value()))
        self._sync_draw_order_controls(active_order_type=order_type)
        self.statusBar().showMessage(f"移动鼠标选择价格，再点击图表创建{self._order_type_label(order_type)}", 3000)

    def cancel_draw_order_preview(self) -> None:
        self.chart_widget.cancel_order_preview()
        self._sync_draw_order_controls()

    def _sync_draw_order_controls(self, active_order_type: OrderLineType | None = None) -> None:
        has_position = bool(self.engine and self.engine.session.position.is_open)
        for order_type, button in self._draw_order_buttons.items():
            enabled = has_position or order_type not in {OrderLineType.EXIT, OrderLineType.REVERSE}
            button.setEnabled(enabled)
            button.blockSignals(True)
            button.setChecked(active_order_type is order_type)
            button.blockSignals(False)

    def _handle_tick_size_changed(self, value: float) -> None:
        tick_size = max(float(value), 0.0001)
        self.chart_widget.set_tick_size(tick_size)
        if self.engine:
            self.engine.session.tick_size = tick_size
            self.price_spin.blockSignals(True)
            self.price_spin.setValue(self._snap_price(self.price_spin.value()))
            self.price_spin.blockSignals(False)
            self._schedule_auto_save("tick_size_changed")

    def _place_order_line(self, order_type: OrderLineType, price: float) -> None:
        self._place_order_line_with_quantity(order_type, price, float(self.quantity_spin.value()))

    def _place_order_line_with_quantity(self, order_type: OrderLineType, price: float, quantity: float) -> None:
        if not self.engine:
            return
        try:
            self.engine.place_order_line(order_type, price=self._snap_price(price), quantity=float(int(quantity)))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "event=place_order_line_failed session_id={} order_type={} error={}",
                self.current_session_id,
                order_type.value,
                str(exc),
            )
            QMessageBox.warning(self, "下单失败", str(exc))
            return
        self.cancel_draw_order_preview()
        self.chart_widget.set_trade_line_mode(None)
        self._update_ui_from_engine()
        self.save_session(trigger=f"place_order_line:{order_type.value}")

    @Slot(str, float)
    def _handle_chart_order_line_created(self, order_type_value: str, price: float) -> None:
        self._place_order_line(OrderLineType(order_type_value), price)

    @Slot(str, float, float)
    def _handle_order_preview_confirmed(self, order_type_value: str, price: float, quantity: float) -> None:
        self._place_order_line_with_quantity(OrderLineType(order_type_value), price, quantity)

    @Slot(int, float)
    def _handle_chart_order_line_moved(self, order_id: int, price: float) -> None:
        if not self.engine:
            return
        try:
            self.engine.update_order_line(order_id, self._snap_price(price))
        except Exception as exc:  # noqa: BLE001
            logger.warning("event=move_order_line_failed session_id={} order_id={} error={}", self.current_session_id, order_id, str(exc))
            QMessageBox.warning(self, "修改失败", str(exc))
            return
        self._update_ui_from_engine()
        self.save_session(trigger="move_order_line")

    @Slot(int, str)
    def _handle_order_line_action_requested(self, order_id: int, action: str) -> None:
        if not self.engine:
            return
        line = next((item for item in self.engine.active_order_lines if item.id == order_id), None)
        if line is None:
            return
        try:
            if action == "edit_price":
                tick_size = max(self.engine.session.tick_size, 0.0001)
                tick_text = f"{tick_size:.8f}".rstrip("0").rstrip(".")
                decimals = len(tick_text.split(".")[1]) if "." in tick_text else 0
                value, ok = QInputDialog.getDouble(
                    self,
                    "修改价格",
                    "新价格",
                    line.price,
                    -9999999.0,
                    9999999.0,
                    decimals,
                )
                if not ok:
                    return
                self.engine.update_order_line(order_id, self._snap_price(value))
                trigger = "edit_order_line_price"
            elif action == "edit_quantity":
                value, ok = QInputDialog.getInt(
                    self,
                    "修改手数",
                    "新手数",
                    int(round(line.quantity)),
                    1,
                    999999,
                    1,
                )
                if not ok:
                    return
                self.engine.update_order_line_quantity(order_id, value)
                trigger = "edit_order_line_quantity"
            elif action == "delete":
                self.engine.cancel_order_line(order_id)
                trigger = "delete_order_line"
            else:
                return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "event=order_line_context_action_failed session_id={} order_id={} action={} error={}",
                self.current_session_id,
                order_id,
                action,
                str(exc),
            )
            QMessageBox.warning(self, "修改失败", str(exc))
            return
        self._update_ui_from_engine()
        self.save_session(trigger=trigger)

    @staticmethod
    def _order_type_label(order_type: OrderLineType) -> str:
        labels = {
            OrderLineType.ENTRY_LONG: "开多线",
            OrderLineType.ENTRY_SHORT: "开空线",
            OrderLineType.EXIT: "平仓线",
            OrderLineType.REVERSE: "反手线",
            OrderLineType.STOP_LOSS: "止损线",
            OrderLineType.TAKE_PROFIT: "止盈线",
        }
        return labels[order_type]
