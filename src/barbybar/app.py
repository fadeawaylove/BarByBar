from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from barbybar.logging_config import setup_logging
from barbybar.storage.repository import Repository
from barbybar.ui.main_window import MainWindow


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("BarByBar")
    repo = Repository()
    window = MainWindow(repo)
    window.resize(1600, 920)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
