from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from barbybar.logging_config import setup_logging
from barbybar.paths import default_db_path
from barbybar.storage.data_safety import PendingRestoreError, apply_pending_restore
from barbybar.storage.repository import Repository
from barbybar.ui.main_window import MainWindow


def main() -> int:
    app_logger = setup_logging()
    try:
        restore_result = apply_pending_restore(current_database_path=default_db_path())
    except PendingRestoreError as exc:
        app_logger.exception("event=pending_restore_failed error={}", str(exc))
    else:
        if restore_result is not None:
            app_logger.bind(
                database_path=str(restore_result.database_path),
                safety_backup_path=str(restore_result.safety_backup_path or ""),
            ).info("event=pending_restore_applied")
            if restore_result.cleanup_warning:
                app_logger.warning(
                    "event=pending_restore_cleanup_warning warning={}",
                    restore_result.cleanup_warning,
                )
    app = QApplication(sys.argv)
    app.setApplicationName("BarByBar")
    icon_path = Path(__file__).resolve().parent / "assets" / "barbybar-icon.svg"
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        app.setWindowIcon(icon)
    repo = Repository()
    window = MainWindow(repo)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.resize(1600, 920)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
