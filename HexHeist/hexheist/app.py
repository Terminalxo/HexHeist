from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def run() -> int:
    QCoreApplication.setOrganizationName("HexHeist")
    QCoreApplication.setApplicationName("HexHeist")
    QCoreApplication.setApplicationVersion("1.0.0")

    app = QApplication(sys.argv)
    app.setApplicationDisplayName("HexHeist")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()
