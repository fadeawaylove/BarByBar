from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from loguru import logger
from PySide6.QtCore import QObject, QPointF, QRectF, QSize, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
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
    QColorDialog,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor, QCloseEvent, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from barbybar.data.csv_importer import CsvImportError, MissingColumnsError, infer_symbol_from_filename
from barbybar.data.tick_size import format_price, price_decimals_for_tick, snap_price
from barbybar.data.timeframe import normalize_timeframe, supported_replay_timeframes
from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import (
    ActionType,
    ChartDrawing,
    DrawingToolType,
    DataSet,
    OrderLineType,
    PositionState,
    ReviewSession,
    SessionStats,
    SessionStatus,
    TradeReviewItem,
    WindowBars,
    normalize_drawing_style,
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


@dataclass(slots=True)
class BatchImportOutcome:
    imported: list[str]
    skipped_duplicates: list[str]
    failed_files: list[str]


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
            drawing_step = perf_counter()
            drawings = repo.get_drawings(session.id or 0)
            log.debug("event=get_drawings elapsed_ms={elapsed_ms:.3f}", elapsed_ms=(perf_counter() - drawing_step) * 1000)
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
                    "drawings": drawings,
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


class DrawingPropertiesDialog(QDialog):
    def __init__(self, drawing: ChartDrawing, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("画线属性")
        self._drawing = drawing
        style = normalize_drawing_style(drawing.tool_type, drawing.style)
        self._selected_color = str(style["color"])
        self._selected_fill_color = str(style["fill_color"])

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.color_button = QPushButton(self._selected_color)
        self.color_button.clicked.connect(self._pick_color)
        self._apply_button_color(self.color_button, self._selected_color)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 8)
        self.width_spin.setValue(int(style["width"]))
        self.line_style_combo = QComboBox()
        self.line_style_combo.addItem("实线", "solid")
        self.line_style_combo.addItem("虚线", "dash")
        self.line_style_combo.addItem("点线", "dot")
        self.line_style_combo.setCurrentIndex(max(0, self.line_style_combo.findData(style["line_style"])))

        self.extend_left_check = QCheckBox("向左延伸")
        self.extend_left_check.setChecked(bool(style["extend_left"]))
        self.extend_right_check = QCheckBox("向右延伸")
        self.extend_right_check.setChecked(bool(style["extend_right"]))
        if drawing.tool_type in {DrawingToolType.TREND_LINE, DrawingToolType.RAY, DrawingToolType.EXTENDED_LINE}:
            form.addRow("", self.extend_left_check)
            form.addRow("", self.extend_right_check)

        self.fill_color_button = QPushButton(self._selected_fill_color)
        self.fill_color_button.clicked.connect(self._pick_fill_color)
        self._apply_button_color(self.fill_color_button, self._selected_fill_color)
        self.fill_opacity_spin = QDoubleSpinBox()
        self.fill_opacity_spin.setRange(0.0, 1.0)
        self.fill_opacity_spin.setSingleStep(0.05)
        self.fill_opacity_spin.setDecimals(2)
        self.fill_opacity_spin.setValue(float(style["fill_opacity"]))

        self.show_price_label_check = QCheckBox("显示价格标签")
        self.show_price_label_check.setChecked(bool(style["show_price_label"]))
        self.show_level_labels_check = QCheckBox("显示比例标签")
        self.show_level_labels_check.setChecked(bool(style["show_level_labels"]))
        self.show_price_labels_check = QCheckBox("显示价格标签")
        self.show_price_labels_check.setChecked(bool(style["show_price_labels"]))
        self.fib_levels_label = QLabel(", ".join(str(level).rstrip("0").rstrip(".") for level in style["fib_levels"]))
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(str(style["text"]))
        self.text_edit.setMinimumHeight(90)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 48)
        self.font_size_spin.setValue(int(style["font_size"]))

        if drawing.tool_type is DrawingToolType.TEXT:
            form.addRow("文字颜色", self.color_button)
            form.addRow("字号", self.font_size_spin)
            form.addRow("内容", self.text_edit)
        else:
            form.addRow("颜色", self.color_button)
            form.addRow("线宽", self.width_spin)
            form.addRow("线型", self.line_style_combo)
            if drawing.tool_type in {DrawingToolType.RECTANGLE, DrawingToolType.PRICE_RANGE}:
                form.addRow("填充色", self.fill_color_button)
                form.addRow("填充透明度", self.fill_opacity_spin)
            if drawing.tool_type is DrawingToolType.FIB_RETRACEMENT:
                form.addRow("档位", self.fib_levels_label)
                form.addRow("", self.show_level_labels_check)
                form.addRow("", self.show_price_labels_check)
            else:
                form.addRow("", self.show_price_label_check)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if drawing.tool_type is DrawingToolType.TEXT:
            QTimer.singleShot(0, self._focus_text_input)

    def style_payload(self) -> dict[str, object]:
        payload = {
            "color": self._selected_color,
            "width": int(self.width_spin.value()),
            "line_style": str(self.line_style_combo.currentData()),
            "extend_left": bool(self.extend_left_check.isChecked()),
            "extend_right": bool(self.extend_right_check.isChecked()),
            "fill_color": self._selected_fill_color,
            "fill_opacity": float(self.fill_opacity_spin.value()),
            "show_price_label": bool(self.show_price_label_check.isChecked()),
            "fib_levels": [0.0, 0.5, 1.0, 2.0],
            "show_level_labels": bool(self.show_level_labels_check.isChecked()),
            "show_price_labels": bool(self.show_price_labels_check.isChecked()),
            "text": self.text_edit.toPlainText(),
            "font_size": int(self.font_size_spin.value()),
            "text_color": self._selected_color,
            "anchor_mode": "free",
        }
        return normalize_drawing_style(self._drawing.tool_type, payload)

    def _focus_text_input(self) -> None:
        self.text_edit.setFocus()
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(parent=self)
        if not color.isValid():
            return
        self._selected_color = color.name()
        self.color_button.setText(self._selected_color)
        self._apply_button_color(self.color_button, self._selected_color)

    def _pick_fill_color(self) -> None:
        color = QColorDialog.getColor(parent=self)
        if not color.isValid():
            return
        self._selected_fill_color = color.name()
        self.fill_color_button.setText(self._selected_fill_color)
        self._apply_button_color(self.fill_color_button, self._selected_fill_color)

    @staticmethod
    def _apply_button_color(button: QPushButton, color: str) -> None:
        button.setStyleSheet(f"background: {color}; color: #1f2933;")


class DataSetManagerDialog(QDialog):
    def __init__(self, repo: Repository, owner: MainWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repo = repo
        self.owner = owner
        self.setWindowTitle("数据集")
        self.resize(560, 520)

        layout = QVBoxLayout(self)
        import_button = QPushButton("导入单个 CSV")
        import_button.clicked.connect(self._import_csv)
        layout.addWidget(import_button)
        self._import_button = import_button
        import_folder_button = QPushButton("导入文件夹")
        import_folder_button.clicked.connect(self._import_csv_folder)
        layout.addWidget(import_folder_button)
        self._import_folder_button = import_folder_button

        self.dataset_filter = QLineEdit()
        self.dataset_filter.setPlaceholderText("按文件名或品种筛选")
        self.dataset_filter.textChanged.connect(self._refresh_datasets)
        layout.addWidget(self.dataset_filter)

        layout.addWidget(QLabel("数据集"))
        self.dataset_list = QListWidget()
        self.dataset_list.itemDoubleClicked.connect(lambda _: self._create_session())
        layout.addWidget(self.dataset_list)

        create_button = QPushButton("基于所选数据创建复盘")
        create_button.clicked.connect(self._create_session)
        layout.addWidget(create_button)

        delete_button = QPushButton("删除所选数据集")
        delete_button.clicked.connect(self._delete_dataset)
        layout.addWidget(delete_button)

        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.reject)
        layout.addWidget(close_button)

        self._refresh_datasets()

    def _refresh_datasets(self) -> None:
        self.dataset_list.clear()
        filter_text = self.dataset_filter.text().strip().lower()
        for dataset in self.repo.list_datasets():
            if filter_text:
                haystack = f"{dataset.display_name} {dataset.symbol}".lower()
                if filter_text not in haystack:
                    continue
            item = QListWidgetItem(
                f"{dataset.display_name} | "
                f"{dataset.start_time:%m-%d %H:%M} -> {dataset.end_time:%m-%d %H:%M}"
            )
            item.setData(32, dataset.id)
            self.dataset_list.addItem(item)

    def _selected_dataset_id(self) -> int | None:
        item = self.dataset_list.currentItem()
        if item is None:
            return None
        value = item.data(32)
        return int(value) if value is not None else None

    def _set_import_actions_enabled(self, enabled: bool) -> None:
        self._import_button.setEnabled(enabled)
        self._import_folder_button.setEnabled(enabled)

    def _import_csv(self) -> None:
        self._set_import_actions_enabled(False)
        try:
            self.owner.import_csv()
        finally:
            self._set_import_actions_enabled(True)
        self._refresh_datasets()

    def _import_csv_folder(self) -> None:
        self._set_import_actions_enabled(False)
        try:
            self.owner.import_csv_folder()
        finally:
            self._set_import_actions_enabled(True)
        self._refresh_datasets()

    def _create_session(self) -> None:
        dataset_id = self._selected_dataset_id()
        if dataset_id is None:
            QMessageBox.information(self, "提示", "请先选择一个数据集。")
            return
        self.owner.create_session_for_dataset(dataset_id)
        self.accept()

    def _delete_dataset(self) -> None:
        dataset_id = self._selected_dataset_id()
        if dataset_id is None:
            QMessageBox.information(self, "提示", "请先选择一个数据集。")
            return
        dataset = self.repo.get_dataset(dataset_id)
        confirm = QMessageBox.question(
            self,
            "删除数据集",
            f"删除数据集“{dataset.display_name}”会级联删除其下所有案例、动作和条件单，确定继续吗？",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.owner.delete_dataset_by_id(dataset_id)
        self._refresh_datasets()


class SessionLibraryDialog(QDialog):
    def __init__(self, repo: Repository, owner: MainWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repo = repo
        self.owner = owner
        self.setWindowTitle("案例库")
        self.resize(620, 560)

        layout = QVBoxLayout(self)
        self.session_filter = QLineEdit()
        self.session_filter.setPlaceholderText("按品种或标签筛选")
        self.session_filter.textChanged.connect(self._refresh_sessions)
        layout.addWidget(self.session_filter)

        self.session_list = QListWidget()
        self.session_list.itemDoubleClicked.connect(lambda _: self._open_session())
        layout.addWidget(self.session_list)

        open_button = QPushButton("打开所选案例")
        open_button.clicked.connect(self._open_session)
        layout.addWidget(open_button)

        delete_button = QPushButton("删除所选案例")
        delete_button.clicked.connect(self._delete_session)
        layout.addWidget(delete_button)

        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.reject)
        layout.addWidget(close_button)

        self._refresh_sessions()

    def _refresh_sessions(self) -> None:
        filter_text = self.session_filter.text().strip()
        self.session_list.clear()
        symbol = filter_text.upper() if filter_text.isalpha() else ""
        tag = filter_text if filter_text and not filter_text.isalpha() else ""
        for session in self.repo.list_sessions(symbol=symbol, tag=tag):
            status_text = "完成" if session.status is SessionStatus.COMPLETED else "进行中"
            item = QListWidgetItem(
                f"{session.title} | {session.timeframe} | {status_text} | PnL {session.stats.total_pnl:.2f}"
            )
            item.setData(32, session.id)
            self.session_list.addItem(item)

    def _open_session(self) -> None:
        item = self.session_list.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先选择一个案例。")
            return
        self.owner.open_session_by_id(int(item.data(32)))
        self.accept()

    def _delete_session(self) -> None:
        item = self.session_list.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先选择一个案例。")
            return
        session_id = int(item.data(32))
        confirm = QMessageBox.question(self, "删除案例", "确定删除所选案例吗？")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.owner.delete_session_by_id(session_id)
        self._refresh_sessions()


class TradeHistoryDialog(QDialog):
    def __init__(self, owner: MainWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.owner = owner
        self.setWindowTitle("历史交易")
        self.resize(760, 540)

        layout = QVBoxLayout(self)
        self.trade_history_sort = QComboBox()
        self.trade_history_sort.addItem("时间倒序", "time_desc")
        self.trade_history_sort.addItem("时间正序", "time_asc")
        self.trade_history_sort.addItem("盈亏从高到低", "pnl_desc")
        self.trade_history_sort.addItem("盈亏从低到高", "pnl_asc")
        self.trade_history_sort.addItem("方向分组", "direction")
        self.trade_history_sort.currentIndexChanged.connect(self.refresh_items)
        layout.addWidget(self.trade_history_sort)

        self.trade_history_list = QListWidget()
        self.trade_history_list.itemClicked.connect(self._handle_item_clicked)
        self.trade_history_list.itemDoubleClicked.connect(self._handle_item_double_clicked)
        layout.addWidget(self.trade_history_list)

        self.trade_history_toggle_button = QPushButton("切换到出场")
        self.trade_history_toggle_button.setFixedHeight(28)
        self.trade_history_toggle_button.clicked.connect(self._toggle_selected_trade_focus)
        layout.addWidget(self.trade_history_toggle_button)

        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.refresh_items()

    def refresh_items(self) -> None:
        selected_trade_number = self.owner._selected_trade_number
        self.trade_history_list.clear()
        for item in self.owner._sorted_trade_review_items(self.trade_history_sort.currentData()):
            quantity_text = int(item.quantity) if float(item.quantity).is_integer() else round(item.quantity, 2)
            label = (
                f"#{item.trade_number} {'多' if item.direction == 'long' else '空'} | "
                f"{item.entry_time:%m-%d %H:%M} -> {item.exit_time:%H:%M} | "
                f"PnL {item.pnl:.2f} | {quantity_text}手 | {item.holding_bars} bars | {item.exit_reason}"
            )
            widget_item = QListWidgetItem(label)
            widget_item.setData(Qt.ItemDataRole.UserRole, item.trade_number)
            widget_item.setToolTip(
                "\n".join(
                    [
                        f"入场 {item.entry_time:%Y-%m-%d %H:%M} @ {item.entry_price:.2f}",
                        f"出场 {item.exit_time:%Y-%m-%d %H:%M} @ {item.exit_price:.2f}",
                        f"PnL {item.pnl:.2f}",
                        f"止损保护 {'是' if item.had_stop_protection else '否'} | 亏损加仓 {'是' if item.had_adverse_add else '否'} | 按计划 {'是' if item.is_planned else '否'}",
                    ]
                )
            )
            self.trade_history_list.addItem(widget_item)
            if item.trade_number == selected_trade_number:
                self.trade_history_list.setCurrentItem(widget_item)
        self.trade_history_toggle_button.setEnabled(self.trade_history_list.count() > 0 and selected_trade_number is not None)
        self.trade_history_toggle_button.setText("切换到出场" if self.owner._selected_trade_view == "entry" else "切换到入场")

    def _handle_item_clicked(self, item: QListWidgetItem) -> None:
        trade_number = item.data(Qt.ItemDataRole.UserRole)
        if trade_number is None:
            return
        self.owner.select_trade_history_item(int(trade_number), focus_view="entry")
        self.refresh_items()

    def _handle_item_double_clicked(self, item: QListWidgetItem) -> None:
        trade_number = item.data(Qt.ItemDataRole.UserRole)
        if trade_number is None:
            return
        self.owner.select_trade_history_item(int(trade_number), focus_view="entry")
        self.owner.toggle_selected_trade_focus()
        self.refresh_items()

    def _toggle_selected_trade_focus(self) -> None:
        self.owner.toggle_selected_trade_focus()
        self.refresh_items()


class MainWindow(QMainWindow):
    _DRAWING_TOOL_ICON_SIZE = QSize(26, 20)
    _DRAWING_TOOL_BUTTON_SIZE = QSize(48, 36)

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
        self._drawing_tool_buttons: dict[DrawingToolType, QPushButton] = {}
        self._trade_markers_visible = True
        self._trade_links_visible = True
        self._trade_review_items: list[TradeReviewItem] = []
        self._selected_trade_number: int | None = None
        self._selected_trade_view: str = "entry"
        self._trade_history_dialog: TradeHistoryDialog | None = None

        self._build_ui()
        self._autoload_recent_session()

    def _build_ui(self) -> None:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(8, 8, 8, 6)
        top_bar.setSpacing(6)

        dataset_button = QPushButton("数据集")
        dataset_button.clicked.connect(self.open_dataset_manager)
        top_bar.addWidget(dataset_button)

        session_button = QPushButton("案例库")
        session_button.clicked.connect(self.open_session_library)
        top_bar.addWidget(session_button)
        top_bar.addStretch(1)
        container_layout.addLayout(top_bar)

        self.splitter = QSplitter()
        self.splitter.addWidget(self._build_center_panel())
        self.splitter.addWidget(self._build_right_panel())
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setSizes([1160, 240])
        container_layout.addWidget(self.splitter)

        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar())
        self._busy_overlay = BusyOverlay(container)
        self._busy_overlay.setGeometry(container.rect())

    def _build_center_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        chart_toolbar = QHBoxLayout()
        timeframe_toolbar = QHBoxLayout()
        timeframe_toolbar.setSpacing(6)
        drawing_toolbar = QHBoxLayout()
        drawing_toolbar.setSpacing(6)
        self.timeframe_button_group = QButtonGroup(self)
        self.timeframe_button_group.setExclusive(True)
        for timeframe in ["1m", "5m", "15m", "30m", "60m"]:
            button = QPushButton(timeframe)
            button.setCheckable(True)
            button.clicked.connect(lambda _, tf=timeframe: self.change_chart_timeframe(tf))
            self.timeframe_button_group.addButton(button)
            self.timeframe_buttons[timeframe] = button
            timeframe_toolbar.addWidget(button)
        for label, tool in [
            ("线段", DrawingToolType.TREND_LINE),
            ("斐波那契", DrawingToolType.FIB_RETRACEMENT),
            ("水平线", DrawingToolType.HORIZONTAL_LINE),
            ("矩形", DrawingToolType.RECTANGLE),
            ("文字", DrawingToolType.TEXT),
            ("箭头线", DrawingToolType.RAY),
        ]:
            button = QPushButton("")
            button.setCheckable(True)
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setIcon(self._drawing_tool_icon(tool))
            button.setIconSize(self._DRAWING_TOOL_ICON_SIZE)
            button.setFixedSize(self._DRAWING_TOOL_BUTTON_SIZE)
            button.setStyleSheet(self._drawing_tool_button_stylesheet())
            button.clicked.connect(lambda checked, drawing_tool=tool: self._toggle_drawing_tool(drawing_tool, checked))
            self._drawing_tool_buttons[tool] = button
            drawing_toolbar.addWidget(button)
        chart_toolbar.addLayout(timeframe_toolbar)
        chart_toolbar.addStretch(1)
        chart_toolbar.addLayout(drawing_toolbar)
        layout.addLayout(chart_toolbar)

        self.chart_widget = ChartWidget()
        self.chart_widget.drawingsChanged.connect(self._handle_chart_drawings_changed)
        self.chart_widget.drawingToolChanged.connect(self._sync_drawing_tool_buttons)
        self.chart_widget.drawingPropertiesRequested.connect(self._handle_drawing_properties_requested)
        self.chart_widget.interactionModeChanged.connect(self._sync_chart_interaction_controls)
        self.chart_widget.orderLineCreated.connect(self._handle_chart_order_line_created)
        self.chart_widget.orderLineMoved.connect(self._handle_chart_order_line_moved)
        self.chart_widget.protectiveOrderCreated.connect(self._handle_chart_protective_order_created)
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

        self.clear_lines_button = QPushButton("清除画线")
        self.clear_lines_button.clicked.connect(self.confirm_clear_drawings)
        controls.addWidget(self.clear_lines_button)

        controls.addStretch(1)
        self.progress_label = QLabel("未开始")
        controls.addWidget(self.progress_label)
        layout.addLayout(controls)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMaximumWidth(260)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        trade_box = QGroupBox("交易")
        trade_layout = QVBoxLayout(trade_box)
        trade_layout.setContentsMargins(8, 12, 8, 8)
        trade_layout.setSpacing(4)

        action_header = QLabel("即时")
        trade_layout.addWidget(action_header)

        quantity_row = QHBoxLayout()
        quantity_row.setSpacing(6)
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 9999)
        self.quantity_spin.setValue(1)
        self.quantity_spin.setSingleStep(1)
        self.quantity_spin.setFixedHeight(26)
        quantity_row.addWidget(QLabel("数量"))
        quantity_row.addWidget(self.quantity_spin)
        trade_layout.addLayout(quantity_row)

        price_row = QHBoxLayout()
        price_row.setSpacing(6)
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setDecimals(2)
        self.price_spin.setRange(-999999.0, 999999.0)
        self.price_spin.setValue(0.0)
        self.price_spin.setFixedHeight(26)
        price_row.addWidget(QLabel("价格"))
        price_row.addWidget(self.price_spin)
        trade_layout.addLayout(price_row)

        for label, action_type in [
            ("开多", ActionType.OPEN_LONG),
            ("开空", ActionType.OPEN_SHORT),
            ("立即平仓", ActionType.CLOSE),
        ]:
            button = QPushButton(label)
            button.setFixedHeight(26)
            button.clicked.connect(lambda _, kind=action_type: self.record_action(kind))
            trade_layout.addWidget(button)

        divider = QLabel("画线")
        trade_layout.addWidget(divider)

        draw_quantity_row = QHBoxLayout()
        draw_quantity_row.setSpacing(6)

        self.draw_quantity_spin = QSpinBox()
        self.draw_quantity_spin.setRange(1, 9999)
        self.draw_quantity_spin.setValue(1)
        self.draw_quantity_spin.setSingleStep(1)
        self.draw_quantity_spin.setFixedHeight(26)
        self.draw_quantity_spin.valueChanged.connect(self.quantity_spin.setValue)
        self.quantity_spin.valueChanged.connect(self.draw_quantity_spin.setValue)
        draw_quantity_row.addWidget(QLabel("手数"))
        draw_quantity_row.addWidget(self.draw_quantity_spin)
        trade_layout.addLayout(draw_quantity_row)

        tick_size_row = QHBoxLayout()
        tick_size_row.setSpacing(6)

        self.tick_size_spin = QDoubleSpinBox()
        self.tick_size_spin.setDecimals(2)
        self.tick_size_spin.setRange(0.01, 999999.0)
        self.tick_size_spin.setValue(1.0)
        self.tick_size_spin.setSingleStep(0.01)
        self.tick_size_spin.setFixedHeight(26)
        self.tick_size_spin.valueChanged.connect(self._handle_tick_size_changed)
        tick_size_row.addWidget(QLabel("最小跳动"))
        tick_size_row.addWidget(self.tick_size_spin)
        trade_layout.addLayout(tick_size_row)

        for label, order_type in [
            ("买", OrderLineType.ENTRY_LONG),
            ("卖", OrderLineType.ENTRY_SHORT),
            ("平", OrderLineType.EXIT),
            ("反", OrderLineType.REVERSE),
        ]:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setFixedHeight(26)
            button.clicked.connect(lambda checked, kind=order_type: self._toggle_draw_order_preview(kind, checked))
            self._draw_order_buttons[order_type] = button
            trade_layout.addWidget(button)
        cancel_draw_button = QPushButton("取消画线下单")
        cancel_draw_button.setFixedHeight(26)
        cancel_draw_button.clicked.connect(self.cancel_draw_order_preview)
        trade_layout.addWidget(cancel_draw_button)
        layout.addWidget(trade_box)

        self.stats_label = QLabel("方向 flat | 仓位 0 | 均价 0 | 已实现PnL 0")
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)

        stats_box = QGroupBox("训练统计")
        stats_layout = QVBoxLayout(stats_box)
        stats_layout.setContentsMargins(8, 12, 8, 8)
        stats_layout.setSpacing(4)
        self.training_stats_label = QLabel("暂无交易统计")
        self.training_stats_label.setWordWrap(True)
        stats_layout.addWidget(self.training_stats_label)
        layout.addWidget(stats_box)
        self.open_trade_history_button = QPushButton("历史交易")
        self.open_trade_history_button.setFixedHeight(26)
        self.open_trade_history_button.clicked.connect(self.open_trade_history_dialog)
        layout.addWidget(self.open_trade_history_button)

        self.show_trade_markers_check = QCheckBox("显示成交点")
        self.show_trade_markers_check.setChecked(True)
        self.show_trade_markers_check.toggled.connect(self._handle_trade_markers_toggled)
        layout.addWidget(self.show_trade_markers_check)

        self.show_trade_links_check = QCheckBox("显示交易连线")
        self.show_trade_links_check.setChecked(True)
        self.show_trade_links_check.toggled.connect(self._handle_trade_links_toggled)
        layout.addWidget(self.show_trade_links_check)

        save_button = QPushButton("保存会话")
        save_button.setFixedHeight(26)
        save_button.clicked.connect(self.save_session)
        layout.addWidget(save_button)

        complete_button = QPushButton("标记完成")
        complete_button.setFixedHeight(26)
        complete_button.clicked.connect(self.complete_session)
        layout.addWidget(complete_button)
        layout.addStretch(1)
        return panel

    def import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 CSV", str(Path.cwd()), "CSV Files (*.csv)")
        if not path:
            return
        display_name = Path(path).name
        if self.repo.find_dataset_by_display_name(display_name) is not None:
            QMessageBox.information(self, "重复数据集", f"同名文件已存在: {display_name}")
            return
        self.show_busy_overlay("正在导入 CSV...", "正在读取并校验数据")
        try:
            self._import_csv_with_mapping(
                path,
                infer_symbol_from_filename(path),
                "1m",
                display_name=display_name,
            )
        finally:
            self.hide_busy_overlay()

    def import_csv_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择 CSV 文件夹", str(Path.cwd()))
        if not folder:
            return
        self.show_busy_overlay("正在批量导入...", "正在逐个读取 CSV，请稍候")
        try:
            outcome = self._import_csv_folder_path(folder)
        finally:
            self.hide_busy_overlay()
        if not outcome.imported and not outcome.skipped_duplicates and not outcome.failed_files:
            QMessageBox.information(self, "批量导入", "所选文件夹中没有找到 CSV 文件。")
            return
        parts = [f"成功导入 {len(outcome.imported)} 个数据集"]
        if outcome.imported:
            parts.append("已导入: " + "、".join(outcome.imported))
        if outcome.skipped_duplicates:
            parts.append("重复跳过: " + "、".join(outcome.skipped_duplicates))
        if outcome.failed_files:
            parts.append("导入失败: " + "、".join(outcome.failed_files))
        self.statusBar().showMessage(f"批量导入完成，成功 {len(outcome.imported)} 个", 5000)
        QMessageBox.information(self, "批量导入结果", "\n".join(parts))

    def _import_csv_folder_path(self, folder: str | Path) -> BatchImportOutcome:
        directory = Path(folder)
        outcome = BatchImportOutcome(imported=[], skipped_duplicates=[], failed_files=[])
        files = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".csv")
        for csv_path in files:
            display_name = csv_path.name
            if self.repo.find_dataset_by_display_name(display_name) is not None:
                outcome.skipped_duplicates.append(csv_path.name)
                continue
            try:
                self._import_csv_with_mapping(
                    str(csv_path),
                    infer_symbol_from_filename(csv_path),
                    "1m",
                    display_name=display_name,
                    interactive=False,
                )
            except Exception:  # noqa: BLE001
                outcome.failed_files.append(csv_path.name)
                continue
            outcome.imported.append(display_name)
        return outcome

    def _import_csv_with_mapping(
        self,
        path: str,
        symbol: str,
        timeframe: str,
        field_map: dict[str, str] | None = None,
        *,
        display_name: str | None = None,
        interactive: bool = True,
    ) -> DataSet | None:
        log = logger.bind(component="csv_import", symbol=symbol, path=path, timeframe=timeframe, display_name=display_name or Path(path).name)
        try:
            dataset = self.repo.import_csv(path, symbol, timeframe, field_map=field_map, display_name=display_name)
        except MissingColumnsError as exc:
            if not interactive:
                log.warning("event=batch_import_missing_columns missing_fields={missing_fields}", missing_fields=",".join(exc.missing_fields))
                raise
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
                if interactive:
                    return None
                raise CsvImportError("Column mapping cancelled")
            try:
                dataset = self.repo.import_csv(path, symbol, timeframe, field_map=dialog.get_field_map(), display_name=display_name)
            except Exception as retry_exc:  # noqa: BLE001
                log.exception("event=import_failed_after_mapping error={error}", error=str(retry_exc))
                if interactive:
                    QMessageBox.critical(self, "导入失败", str(retry_exc))
                raise
        except Exception as exc:  # noqa: BLE001
            log.exception("event=import_failed error={error}", error=str(exc))
            if interactive:
                QMessageBox.critical(self, "导入失败", str(exc))
            raise
        log.info("event=import_success dataset_id={} timeframe={}", dataset.id, dataset.timeframe)
        if interactive:
            self.statusBar().showMessage(f"已导入 {dataset.display_name}", 5000)
        return dataset

    def create_session_for_dataset(self, dataset_id: int) -> None:
        dataset = self.repo.get_dataset(dataset_id)
        bars = self.repo.get_bars(dataset.id or 0)
        start_index = max(0, min(50, len(bars) - 1))
        session = self.repo.create_session(dataset.id or 0, start_index=start_index)
        logger.bind(component="session", session_id=session.id, dataset_id=dataset.id).info(
            "event=create_session start_index={start_index}",
            start_index=start_index,
        )
        self.current_dataset = dataset
        self.statusBar().showMessage("正在创建并加载复盘会话", 4000)
        self._start_session_load(
            session.id or 0,
            title="正在创建复盘...",
            detail="正在初始化会话并构建图表",
        )

    def open_dataset_manager(self) -> None:
        dialog = DataSetManagerDialog(self.repo, self, self)
        dialog.exec()

    def open_session_library(self) -> None:
        dialog = SessionLibraryDialog(self.repo, self, self)
        dialog.exec()

    def open_trade_history_dialog(self) -> None:
        if self._trade_history_dialog is None:
            self._trade_history_dialog = TradeHistoryDialog(self, self)
            self._trade_history_dialog.finished.connect(self._handle_trade_history_dialog_closed)
        self._trade_history_dialog.refresh_items()
        self._trade_history_dialog.show()
        self._trade_history_dialog.raise_()
        self._trade_history_dialog.activateWindow()

    def open_session_by_id(self, session_id: int) -> None:
        self._load_session(session_id)

    def _handle_trade_history_dialog_closed(self) -> None:
        if self._trade_history_dialog is not None:
            self._trade_history_dialog.deleteLater()
            self._trade_history_dialog = None

    def delete_dataset_by_id(self, dataset_id: int) -> None:
        active_uses_dataset = False
        if self.current_session_id is not None:
            try:
                active_uses_dataset = self.repo.get_session(self.current_session_id).dataset_id == dataset_id
            except KeyError:
                active_uses_dataset = False
        self.repo.delete_dataset(dataset_id)
        if self.current_dataset and self.current_dataset.id == dataset_id:
            self.current_dataset = None
        self.statusBar().showMessage("数据集已删除", 3000)
        if active_uses_dataset:
            self._clear_current_session()
            self._autoload_recent_session()

    def delete_session_by_id(self, session_id: int) -> None:
        deleting_current = self.current_session_id == session_id
        self.repo.delete_session(session_id)
        self.statusBar().showMessage("案例已删除", 3000)
        if deleting_current:
            self._clear_current_session()
            self._autoload_recent_session()

    def _autoload_recent_session(self) -> None:
        sessions = self.repo.list_sessions()
        if not sessions:
            self._clear_current_session()
            self.statusBar().showMessage("请先导入文件夹或打开数据集/案例库", 5000)
            return
        session_id = sessions[0].id
        if session_id is None:
            return
        logger.bind(component="startup", session_id=session_id).info("event=autoload_recent_session")
        self._load_session(
            session_id,
            title="正在恢复最近训练...",
            detail="正在读取最近一次训练会话并恢复图表",
        )

    def _load_session(self, session_id: int, *, title: str = "正在加载案例...", detail: str = "正在读取数据并构建图表") -> None:
        self._start_session_load(
            session_id,
            title=title,
            detail=detail,
        )

    def _clear_current_session(self) -> None:
        self.engine = None
        self.current_session_id = None
        self._trade_review_items = []
        self._selected_trade_number = None
        self._selected_trade_view = "entry"
        self.chart_widget.set_window_data([], -1, 0, 0)
        self.chart_widget.set_drawings([])
        self.chart_widget.set_trade_actions([])
        self.chart_widget.set_position_direction(None)
        self.chart_widget.set_trade_focus(None)
        self.chart_widget.set_active_drawing_tool(None)
        self.cancel_draw_order_preview()
        self.progress_label.setText("未开始")
        self.jump_spin.blockSignals(True)
        self.jump_spin.setMaximum(0)
        self.jump_spin.setValue(0)
        self.jump_spin.blockSignals(False)
        self.stats_label.setText("方向 flat | 仓位 0 | 均价 0 | 已实现PnL 0")
        self.training_stats_label.setText("暂无交易统计")
        self.open_trade_history_button.setEnabled(False)
        if self._trade_history_dialog is not None:
            self._trade_history_dialog.refresh_items()
        self.price_spin.blockSignals(True)
        self.price_spin.setValue(0.0)
        self.price_spin.blockSignals(False)
        self._sync_draw_order_controls()

    def _update_ui_from_engine(self) -> None:
        if not self.engine:
            return
        current = self.engine.session.current_index
        total = self.engine.total_count
        bar = self.engine.current_bar
        self.chart_widget.set_tick_size(self.engine.session.tick_size)
        self.chart_widget.set_position_direction(self.engine.session.position.direction)
        self.chart_widget.set_cursor(current)
        self.chart_widget.set_order_lines(self.engine.display_order_lines())
        self.chart_widget.set_trade_actions(self.engine.actions, self.engine.trades)
        self.chart_widget.set_trade_markers_visible(self._trade_markers_visible)
        self.chart_widget.set_trade_links_visible(self._trade_links_visible)
        self._trade_review_items = self.engine.trade_review_items()
        self.progress_label.setText(f"{current + 1}/{total} | {bar.timestamp:%Y-%m-%d %H:%M}")
        self.jump_spin.blockSignals(True)
        self.jump_spin.setValue(current)
        self.jump_spin.blockSignals(False)
        self._sync_trade_price_to_current_bar()
        position = self.engine.session.position
        direction = position.direction or "flat"
        quantity_text = (
            str(int(position.quantity))
            if float(position.quantity).is_integer()
            else f"{position.quantity:.2f}"
        )
        self.stats_label.setText(
            " | ".join(
                [
                    f"方向 {direction}",
                    f"仓位 {quantity_text}",
                    f"均价 {format_price(position.average_price, self.engine.session.tick_size)}",
                    f"已实现PnL {position.realized_pnl:.2f}",
                ]
            )
        )
        self._sync_draw_order_controls()
        self.tick_size_spin.blockSignals(True)
        self.tick_size_spin.setValue(self.engine.session.tick_size)
        self.tick_size_spin.blockSignals(False)
        self._update_training_stats()
        self._sync_selected_trade_focus()
        self.open_trade_history_button.setEnabled(bool(self._trade_review_items))
        if self._trade_history_dialog is not None:
            self._trade_history_dialog.refresh_items()

    def _handle_trade_markers_toggled(self, checked: bool) -> None:
        self._trade_markers_visible = checked
        self.chart_widget.set_trade_markers_visible(checked)

    def _handle_trade_links_toggled(self, checked: bool) -> None:
        self._trade_links_visible = checked
        self.chart_widget.set_trade_links_visible(checked)

    def _update_training_stats(self) -> None:
        if not self.engine:
            self.training_stats_label.setText("暂无交易统计")
            return
        stats = self.engine.session.stats
        planned_rate = (stats.planned_trades / stats.total_trades) if stats.total_trades else 0.0
        auto_rate = (stats.auto_trades / stats.total_trades) if stats.total_trades else 0.0
        self.training_stats_label.setText(
            "\n".join(
                [
                    f"胜率 {stats.win_rate:.0%} | 盈亏比 {stats.payoff_ratio:.2f} | Expectancy {stats.expectancy:.2f}",
                    f"均赢 {stats.average_win:.2f} | 均亏 {stats.average_loss:.2f} | 最大回撤 {stats.max_drawdown:.2f}",
                    f"平均持仓 {stats.avg_holding_bars:.1f} bars | 连赢 {stats.max_win_streak} | 连亏 {stats.max_loss_streak}",
                    f"有止损 {stats.trades_with_stop_rate:.0%} | 按计划 {planned_rate:.0%} | 自动平仓 {auto_rate:.0%}",
                ]
            )
        )

    def _sorted_trade_review_items(self, sort_key: str | None) -> list[TradeReviewItem]:
        items = list(self._trade_review_items)
        if sort_key == "time_asc":
            items.sort(key=lambda item: (item.entry_time, item.trade_number))
        elif sort_key == "pnl_desc":
            items.sort(key=lambda item: (-item.pnl, item.exit_time, item.trade_number))
        elif sort_key == "pnl_asc":
            items.sort(key=lambda item: (item.pnl, item.exit_time, item.trade_number))
        elif sort_key == "direction":
            items.sort(key=lambda item: (item.direction, item.entry_time, item.trade_number))
        else:
            items.sort(key=lambda item: (item.entry_time, item.trade_number), reverse=True)
        return items

    def _selected_trade_review_item(self) -> TradeReviewItem | None:
        if self._selected_trade_number is None:
            return None
        return next((item for item in self._trade_review_items if item.trade_number == self._selected_trade_number), None)

    def _sync_selected_trade_focus(self) -> None:
        item = self._selected_trade_review_item()
        if item is None:
            self.chart_widget.set_trade_focus(None)
            return
        self.chart_widget.set_trade_focus(
            item.trade_number,
            (item.entry_bar_index, item.entry_price, item.exit_bar_index, item.exit_price),
        )

    def select_trade_history_item(self, trade_number: int, *, focus_view: str = "entry") -> None:
        self._selected_trade_number = trade_number
        self._selected_trade_view = focus_view
        self._sync_selected_trade_focus()
        self._focus_selected_trade_view()

    def toggle_selected_trade_focus(self) -> None:
        if self._selected_trade_number is None:
            return
        self._selected_trade_view = "exit" if self._selected_trade_view == "entry" else "entry"
        self._sync_selected_trade_focus()
        self._focus_selected_trade_view()

    def _focus_selected_trade_view(self) -> None:
        item = self._selected_trade_review_item()
        if item is None:
            return
        target_index = item.entry_bar_index if self._selected_trade_view == "entry" else item.exit_bar_index
        if not self.engine:
            return
        if target_index < self.engine.window_start_index or target_index > self.engine.window_end_index:
            if not self.current_session_id:
                return
            anchor_time = self.repo.get_chart_bar_time(self.current_session_id, self.engine.session.chart_timeframe, target_index)
            self._start_session_load(
                self.current_session_id,
                chart_timeframe=self.engine.session.chart_timeframe,
                anchor_time=anchor_time,
                title="正在定位交易...",
                detail="正在加载目标交易附近的 K 线",
            )
            return
        self.chart_widget.set_cursor(target_index)
        self.chart_widget.reset_viewport(follow_latest=False)
        local_index = target_index - self.engine.window_start_index
        if 0 <= local_index < len(self.engine.bars):
            timestamp = self.engine.bars[local_index].timestamp
            self.progress_label.setText(f"查看交易 #{item.trade_number} | Bar {target_index + 1} | {timestamp:%Y-%m-%d %H:%M}")

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
        self.chart_widget.set_active_drawing_tool(None)
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
        saved = self.repo.save_session(
            self.engine.session,
            self.engine.actions,
            self.engine.order_lines,
            self.chart_widget.drawings(),
        )
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
            drawings = payload["drawings"]
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
            self.chart_widget.set_drawings(drawings)
            self._sync_chart_interaction_controls()
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
        if self._trade_history_dialog is not None:
            self._trade_history_dialog.close()
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
        if explicit_price is not None:
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
        logger.bind(
            component="chart_interaction",
            requested_order_type=order_type.value,
            checked=checked,
            interaction_mode=self.chart_widget.interaction_mode.value,
            active_drawing_tool=self.chart_widget.active_drawing_tool.value if self.chart_widget.active_drawing_tool else "",
        ).debug("event=toggle_draw_order_preview")
        if not checked:
            if self.chart_widget.trade_line_mode is None and self.chart_widget.last_hover_price is not None:
                self.chart_widget.cancel_order_preview()
            return
        self.chart_widget.set_active_drawing_tool(None)
        self.chart_widget.begin_order_preview(order_type.value, float(self.draw_quantity_spin.value()))
        self._sync_draw_order_controls(active_order_type=order_type)
        logger.bind(
            component="chart_interaction",
            requested_order_type=order_type.value,
            interaction_mode=self.chart_widget.interaction_mode.value,
            preview_order_type=self.chart_widget.preview_order_type or "",
        ).debug("event=toggle_draw_order_preview_applied")
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

    def _toggle_drawing_tool(self, tool: DrawingToolType, checked: bool) -> None:
        logger.bind(
            component="chart_interaction",
            requested_drawing_tool=tool.value,
            checked=checked,
            interaction_mode=self.chart_widget.interaction_mode.value,
            active_drawing_tool=self.chart_widget.active_drawing_tool.value if self.chart_widget.active_drawing_tool else "",
        ).debug("event=toggle_drawing_tool")
        if checked:
            self.cancel_draw_order_preview()
            self.chart_widget.set_active_drawing_tool(tool)
            logger.bind(
                component="chart_interaction",
                requested_drawing_tool=tool.value,
                interaction_mode=self.chart_widget.interaction_mode.value,
                active_drawing_tool=self.chart_widget.active_drawing_tool.value if self.chart_widget.active_drawing_tool else "",
                button_checked=self._drawing_tool_buttons[tool].isChecked(),
            ).debug("event=toggle_drawing_tool_applied")
            self.statusBar().showMessage(f"已切换到{self._drawing_tool_label(tool)}，完成一笔后自动回到 hover，Esc 可取消", 3000)
            return
        if self.chart_widget.active_drawing_tool is tool:
            self.chart_widget.set_active_drawing_tool(None)

    @Slot(object)
    def _sync_drawing_tool_buttons(self, active_tool: object) -> None:
        for tool, button in self._drawing_tool_buttons.items():
            button.blockSignals(True)
            button.setChecked(tool == active_tool)
            button.blockSignals(False)
        self._sync_chart_interaction_controls()

    @Slot(object)
    def _sync_chart_interaction_controls(self, *_args) -> None:
        active_order_type: OrderLineType | None = None
        if self.chart_widget.preview_order_type is not None:
            active_order_type = OrderLineType(self.chart_widget.preview_order_type)
        self._sync_draw_order_controls(active_order_type=active_order_type)

    @Slot()
    def _handle_chart_drawings_changed(self) -> None:
        if not self.engine:
            return
        self._schedule_auto_save("drawings_changed")

    def confirm_clear_drawings(self) -> None:
        if not self.chart_widget.drawings():
            return
        choice = QMessageBox.warning(
            self,
            "确认清除画线",
            "这会删除当前案例中的所有普通画线，且无法撤销。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice is QMessageBox.StandardButton.Yes:
            self.chart_widget.clear_lines()

    def _handle_tick_size_changed(self, value: float) -> None:
        tick_size = max(round(float(value), 2), 0.01)
        self.chart_widget.set_tick_size(tick_size)
        if self.engine:
            self.engine.session.tick_size = tick_size
            self._sync_price_spin_decimals()
            self.tick_size_spin.blockSignals(True)
            self.tick_size_spin.setValue(tick_size)
            self.tick_size_spin.blockSignals(False)
            self._sync_trade_price_to_current_bar()
            self._schedule_auto_save("tick_size_changed")

    def _place_order_line(self, order_type: OrderLineType, price: float) -> None:
        self._place_order_line_with_quantity(order_type, price, float(self.quantity_spin.value()))

    def _sync_trade_price_to_current_bar(self) -> None:
        if not self.engine:
            return
        self._sync_price_spin_decimals()
        latest_price = self._snap_price(self.engine.current_bar.close)
        self.price_spin.blockSignals(True)
        self.price_spin.setValue(latest_price)
        self.price_spin.blockSignals(False)

    def _sync_price_spin_decimals(self) -> None:
        self.price_spin.setDecimals(price_decimals_for_tick(self._current_tick_size()))

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
        self.save_session(trigger=f"place_order_line:{order_type.value}")
        self._update_ui_from_engine()

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

    @Slot(str, float)
    def _handle_chart_protective_order_created(self, order_type_value: str, price: float) -> None:
        self._place_order_line(OrderLineType(order_type_value), price)

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

    @Slot(object, int)
    def _handle_drawing_properties_requested(self, drawing: object, drawing_index: int) -> None:
        if not isinstance(drawing, ChartDrawing):
            return
        dialog = DrawingPropertiesDialog(drawing, self)
        result = dialog.exec()
        if result != QDialog.DialogCode.Accepted:
            if drawing.tool_type is DrawingToolType.TEXT and not drawing.style.get("text", "").strip():
                self.chart_widget.delete_drawing(drawing.id, drawing_index)
            return
        style = dialog.style_payload()
        if drawing.tool_type is DrawingToolType.TEXT and not str(style.get("text", "")).strip():
            self.chart_widget.delete_drawing(drawing.id, drawing_index)
            return
        self.chart_widget.update_drawing_style(drawing.id, style, drawing_index)

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

    @staticmethod
    def _drawing_tool_label(tool: DrawingToolType) -> str:
        labels = {
            DrawingToolType.TREND_LINE: "线段",
            DrawingToolType.RAY: "箭头线",
            DrawingToolType.EXTENDED_LINE: "扩展线",
            DrawingToolType.FIB_RETRACEMENT: "斐波那契",
            DrawingToolType.HORIZONTAL_LINE: "水平线",
            DrawingToolType.HORIZONTAL_RAY: "水平射线",
            DrawingToolType.VERTICAL_LINE: "垂直线",
            DrawingToolType.PARALLEL_CHANNEL: "平行通道",
            DrawingToolType.RECTANGLE: "矩形",
            DrawingToolType.PRICE_RANGE: "价格区间",
            DrawingToolType.TEXT: "文字",
        }
        return labels[tool]

    @staticmethod
    def _drawing_tool_button_stylesheet() -> str:
        return (
            "QPushButton {"
            " background: #f8fafc;"
            " border: 1px solid #cbd5e1;"
            " border-radius: 7px;"
            " padding: 0px;"
            "}"
            "QPushButton:hover {"
            " background: #eef4fb;"
            " border-color: #94a3b8;"
            "}"
            "QPushButton:pressed {"
            " background: #e2e8f0;"
            " border-color: #64748b;"
            "}"
            "QPushButton:checked {"
            " background: #dbeafe;"
            " border: 1px solid #3b82f6;"
            "}"
            "QPushButton:disabled {"
            " background: #f8fafc;"
            " border-color: #d7dee8;"
            "}"
        )

    @classmethod
    def _drawing_tool_icon(cls, tool: DrawingToolType) -> QIcon:
        icon = QIcon()
        for state, palette in [
            (QIcon.State.Off, ("#1f2937", "#1f2937", "#ffffff", "#cbd5e1", "#f8fafc")),
            (QIcon.State.On, ("#0f172a", "#2563eb", "#eff6ff", "#60a5fa", "#dbeafe")),
        ]:
            icon.addPixmap(cls._draw_drawing_tool_icon(tool, *palette), QIcon.Mode.Normal, state)
        disabled = cls._draw_drawing_tool_icon(tool, "#94a3b8", "#94a3b8", "#ffffff", "#d7dee8", "#f8fafc")
        icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.Off)
        icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.On)
        return icon

    @classmethod
    def _draw_drawing_tool_icon(
        cls,
        tool: DrawingToolType,
        line_color: str,
        accent_color: str,
        fill_color: str,
        secondary_color: str,
        accent_fill: str,
    ) -> QPixmap:
        size = cls._DRAWING_TOOL_ICON_SIZE
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        line_pen = QPen(QColor(line_color), 2.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        accent_pen = QPen(QColor(accent_color), 2.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        secondary_pen = QPen(QColor(secondary_color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        fill_brush = QColor(fill_color)
        accent_brush = QColor(accent_fill)
        center_x = size.width() / 2
        center_y = size.height() / 2

        def draw_anchor(point: QPointF, radius: float = 2.1) -> None:
            painter.setPen(QPen(QColor(accent_color), 1.4))
            painter.setBrush(fill_brush)
            painter.drawEllipse(point, radius, radius)

        def draw_arrow_tip(tip: QPointF, angle: float = 0.0, length: float = 4.2) -> None:
            painter.setPen(accent_pen)
            direction = QPointF(length, length * 0.72)
            points = [
                tip,
                QPointF(tip.x() - direction.x(), tip.y() + direction.y()),
                QPointF(tip.x() - direction.y(), tip.y() + direction.x()),
            ]
            if angle != 0.0:
                transform = []
                from math import cos, sin

                cos_v = cos(angle)
                sin_v = sin(angle)
                for point in points:
                    dx = point.x() - tip.x()
                    dy = point.y() - tip.y()
                    transform.append(QPointF(tip.x() + dx * cos_v - dy * sin_v, tip.y() + dx * sin_v + dy * cos_v))
                points = transform
            painter.setBrush(QColor(accent_color))
            painter.drawPolygon(QPolygonF(points))

        painter.setPen(line_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if tool is DrawingToolType.TREND_LINE:
            start = QPointF(4, size.height() - 4)
            end = QPointF(size.width() - 4, 4)
            painter.drawLine(start, end)
            draw_anchor(start)
            draw_anchor(end)
        elif tool is DrawingToolType.RAY:
            start = QPointF(4, size.height() - 5)
            end = QPointF(size.width() - 5, 5)
            painter.drawLine(start, end)
            draw_anchor(start)
            draw_arrow_tip(end, angle=0.32)
        elif tool is DrawingToolType.EXTENDED_LINE:
            start = QPointF(3, size.height() - 5)
            end = QPointF(size.width() - 3, 5)
            painter.drawLine(start, end)
            draw_arrow_tip(start, angle=3.46)
            draw_arrow_tip(end, angle=0.32)
        elif tool is DrawingToolType.FIB_RETRACEMENT:
            left = 5.0
            right = size.width() - 5.0
            top = 4.0
            bottom = size.height() - 4.0
            painter.setPen(accent_pen)
            painter.drawLine(QPointF(left, top), QPointF(left, bottom))
            painter.drawLine(QPointF(right, top), QPointF(right, bottom))
            painter.setPen(line_pen)
            for ratio in (0.0, 0.236, 0.382, 0.5, 0.618, 1.0):
                y = top + (bottom - top) * ratio
                painter.drawLine(QPointF(left + 2, y), QPointF(right - 2, y))
            draw_anchor(QPointF(left, top), radius=1.8)
            draw_anchor(QPointF(right, bottom), radius=1.8)
        elif tool is DrawingToolType.HORIZONTAL_LINE:
            painter.setPen(accent_pen)
            painter.drawLine(QPointF(3, center_y), QPointF(size.width() - 3, center_y))
        elif tool is DrawingToolType.HORIZONTAL_RAY:
            start = QPointF(4, center_y)
            end = QPointF(size.width() - 5, center_y)
            painter.setPen(accent_pen)
            painter.drawLine(start, end)
            draw_anchor(start)
            draw_arrow_tip(end)
        elif tool is DrawingToolType.VERTICAL_LINE:
            painter.setPen(accent_pen)
            painter.drawLine(QPointF(center_x, 3), QPointF(center_x, size.height() - 3))
        elif tool is DrawingToolType.RECTANGLE:
            rect = QRectF(4.5, 4.5, size.width() - 9.0, size.height() - 9.0)
            painter.setPen(accent_pen)
            painter.drawRect(rect)
            painter.setPen(secondary_pen)
            painter.drawLine(QPointF(rect.left(), rect.top()), QPointF(rect.left() + 4, rect.top()))
            painter.drawLine(QPointF(rect.left(), rect.top()), QPointF(rect.left(), rect.top() + 4))
            painter.drawLine(QPointF(rect.right(), rect.bottom()), QPointF(rect.right() - 4, rect.bottom()))
            painter.drawLine(QPointF(rect.right(), rect.bottom()), QPointF(rect.right(), rect.bottom() - 4))
        elif tool is DrawingToolType.PRICE_RANGE:
            rect = QRectF(5.0, 4.5, size.width() - 10.0, size.height() - 9.0)
            painter.setPen(accent_pen)
            painter.setBrush(accent_brush)
            painter.drawRect(rect)
            painter.setPen(line_pen)
            painter.drawLine(QPointF(rect.left() + 2, rect.center().y()), QPointF(rect.right() - 2, rect.center().y()))
        elif tool is DrawingToolType.PARALLEL_CHANNEL:
            painter.setPen(accent_pen)
            upper_start = QPointF(4, size.height() - 8)
            upper_end = QPointF(size.width() - 4, 4)
            lower_start = QPointF(4, size.height() - 4)
            lower_end = QPointF(size.width() - 4, 8)
            painter.drawLine(upper_start, upper_end)
            painter.drawLine(lower_start, lower_end)
            path = QPainterPath()
            path.moveTo(upper_start)
            path.lineTo(upper_end)
            path.lineTo(lower_end)
            path.lineTo(lower_start)
            path.closeSubpath()
            painter.fillPath(path, QColor(accent_fill))
        elif tool is DrawingToolType.TEXT:
            bubble = QRectF(4.0, 4.5, size.width() - 8.0, size.height() - 8.0)
            painter.setPen(accent_pen)
            painter.setBrush(QColor(fill_color))
            painter.drawRoundedRect(bubble, 4.0, 4.0)
            tail = QPolygonF([QPointF(8, bubble.bottom()), QPointF(11, bubble.bottom() + 4), QPointF(14, bubble.bottom())])
            painter.setBrush(QColor(fill_color))
            painter.drawPolygon(tail)
            text_pen = QPen(QColor(line_color), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(text_pen)
            painter.drawLine(QPointF(center_x, 8), QPointF(center_x, bubble.bottom() - 4))
            painter.drawLine(QPointF(center_x - 4, 8), QPointF(center_x + 4, 8))

        painter.end()
        return pixmap
