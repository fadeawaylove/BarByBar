from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from barbybar.logging_config import setup_logging
from barbybar.storage.repository import Repository
from barbybar.ui.main_window import MainWindow


def main() -> int:
    setup_logging()
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
