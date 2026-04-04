from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
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
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import ActionType, DataSet, SessionStatus
from barbybar.storage.repository import Repository
from barbybar.ui.chart_widget import ChartWidget


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository) -> None:
        super().__init__()
        self.repo = repo
        self.setWindowTitle("BarByBar")
        self.engine: ReviewEngine | None = None
        self.current_dataset: DataSet | None = None
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.step_forward)

        self._build_ui()
        self._refresh_lists()

    def _build_ui(self) -> None:
        splitter = QSplitter()
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([280, 900, 360])
        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())

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
        self.chart_widget = ChartWidget()
        layout.addWidget(self.chart_widget)

        controls = QHBoxLayout()
        self.prev_button = QPushButton("上一步")
        self.prev_button.clicked.connect(self.step_back)
        controls.addWidget(self.prev_button)

        self.next_button = QPushButton("下一根")
        self.next_button.clicked.connect(self.step_forward)
        controls.addWidget(self.next_button)

        self.play_button = QPushButton("自动播放")
        self.play_button.setCheckable(True)
        self.play_button.clicked.connect(self.toggle_playback)
        controls.addWidget(self.play_button)

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "2x", "4x"])
        self.speed_combo.setCurrentText("1x")
        controls.addWidget(self.speed_combo)

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
        self.quantity_spin = QDoubleSpinBox()
        self.quantity_spin.setRange(0.1, 9999.0)
        self.quantity_spin.setValue(1.0)
        self.quantity_spin.setSingleStep(1.0)
        action_layout.addRow("数量", self.quantity_spin)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setDecimals(4)
        self.price_spin.setRange(-999999.0, 999999.0)
        self.price_spin.setValue(0.0)
        action_layout.addRow("价格(0=当前收盘)", self.price_spin)

        grid = QGridLayout()
        action_defs = [
            ("开多", ActionType.OPEN_LONG),
            ("开空", ActionType.OPEN_SHORT),
            ("加仓", ActionType.ADD),
            ("减仓", ActionType.REDUCE),
            ("平仓", ActionType.CLOSE),
            ("止损", ActionType.SET_STOP_LOSS),
            ("止盈", ActionType.SET_TAKE_PROFIT),
            ("记笔记", ActionType.NOTE),
        ]
        for index, (label, action_type) in enumerate(action_defs):
            button = QPushButton(label)
            button.clicked.connect(lambda _, kind=action_type: self.record_action(kind))
            grid.addWidget(button, index // 2, index % 2)
        action_layout.addRow(grid)
        layout.addWidget(action_box)

        meta_box = QGroupBox("会话信息")
        meta_layout = QFormLayout(meta_box)
        self.title_edit = QLineEdit()
        meta_layout.addRow("标题", self.title_edit)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("标签用逗号分隔")
        meta_layout.addRow("标签", self.tags_edit)

        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("记录你的想法、原因和执行计划")
        meta_layout.addRow("笔记", self.note_edit)
        layout.addWidget(meta_box)

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
        timeframe, ok = QInputDialog.getText(self, "周期", "输入周期，例如 1m")
        if not ok or not timeframe.strip():
            return
        try:
            dataset = self.repo.import_csv(path, symbol.strip().upper(), timeframe.strip())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "导入失败", str(exc))
            return
        self.statusBar().showMessage(f"已导入 {dataset.symbol} {dataset.timeframe}", 5000)
        self._refresh_lists()

    def create_session(self) -> None:
        if not self.current_dataset:
            QMessageBox.information(self, "提示", "请先选择一个数据集。")
            return
        start_index = max(0, min(50, self.current_dataset.total_bars - 1))
        session = self.repo.create_session(self.current_dataset.id or 0, start_index=start_index)
        self._load_session(session.id or 0)
        self.statusBar().showMessage("已创建新复盘会话", 4000)

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
            item = QListWidgetItem(f"{session.title} | {status_text} | PnL {session.stats.total_pnl:.2f}")
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
        session = self.repo.get_session(session_id)
        bars = self.repo.get_bars(session.dataset_id)
        actions = self.repo.get_session_actions(session.id or 0)
        self.engine = ReviewEngine(session, bars)
        for action in actions:
            self.engine._apply_action(action)
            self.engine.actions.append(action)
        self.current_dataset = self.repo.get_dataset(session.dataset_id)
        self.jump_spin.blockSignals(True)
        self.jump_spin.setMaximum(len(bars) - 1)
        self.jump_spin.setValue(session.current_index)
        self.jump_spin.blockSignals(False)
        self.title_edit.setText(session.title)
        self.tags_edit.setText(", ".join(session.tags))
        self.note_edit.setPlainText(session.notes)
        self.chart_widget.set_full_data(bars)
        self._update_ui_from_engine()

    def _update_ui_from_engine(self) -> None:
        if not self.engine:
            return
        current = self.engine.session.current_index
        total = len(self.engine.bars)
        bar = self.engine.current_bar
        self.chart_widget.set_cursor(current)
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

    def step_forward(self) -> None:
        if not self.engine:
            return
        if not self.engine.step_forward():
            self.play_timer.stop()
            self.play_button.setChecked(False)
            self.play_button.setText("自动播放")
        self._update_ui_from_engine()

    def step_back(self) -> None:
        if not self.engine:
            return
        self.engine.step_back()
        self._update_ui_from_engine()

    def toggle_playback(self, checked: bool) -> None:
        if not self.engine:
            self.play_button.setChecked(False)
            return
        if checked:
            interval_map = {"0.5x": 1500, "1x": 800, "2x": 400, "4x": 200}
            self.play_timer.start(interval_map[self.speed_combo.currentText()])
            self.play_button.setText("暂停")
        else:
            self.play_timer.stop()
            self.play_button.setText("自动播放")

    def jump_to_bar(self, index: int) -> None:
        if not self.engine:
            return
        self.engine.jump_to(index)
        self._update_ui_from_engine()

    def record_action(self, action_type: ActionType) -> None:
        if not self.engine:
            QMessageBox.information(self, "提示", "请先创建或打开一个复盘会话。")
            return
        price = self.price_spin.value() or None
        note = self.note_edit.toPlainText().strip() if action_type is ActionType.NOTE else ""
        try:
            self.engine.record_action(action_type, quantity=self.quantity_spin.value(), price=price, note=note)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "动作失败", str(exc))
            return
        self._sync_metadata()
        self._update_ui_from_engine()
        self.save_session()

    def _sync_metadata(self) -> None:
        if not self.engine:
            return
        self.engine.session.title = self.title_edit.text().strip() or self.engine.session.title
        self.engine.set_notes(self.note_edit.toPlainText().strip())
        self.engine.set_tags(self.tags_edit.text().split(","))

    def save_session(self) -> None:
        if not self.engine:
            return
        self._sync_metadata()
        saved = self.repo.save_session(self.engine.session, self.engine.actions)
        self.engine.session = saved
        self._refresh_session_list()
        self.statusBar().showMessage("会话已保存", 2500)

    def complete_session(self) -> None:
        if not self.engine:
            return
        self.engine.complete()
        self.save_session()
        self._update_ui_from_engine()
