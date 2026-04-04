# main_app.py — DD1 Ses & HiFi
# Giriş noktası: Ses Ustası (Groq AI) + HiFi Stüdyo iki sekmeli masaüstü uygulaması

import sys
import os

# Kendi klasörünü path'e ekle
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QFont

import ui_interface
from ai_module   import SesUstasiTab
from hifi_module import HiFiTab

APP_NAME    = "DD1 Ses & HiFi"
APP_VERSION = "1.0.0"
WIN_W, WIN_H = 1200, 760
MIN_W, MIN_H = 900, 580


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        self.resize(WIN_W, WIN_H)
        self.setMinimumSize(MIN_W, MIN_H)
        self._build_ui()

    def _build_ui(self) -> None:
        tabs = QTabWidget()
        tabs.setDocumentMode(False)
        tabs.setMovable(False)

        # ── Sekme 1: Ses Ustası ─────────────────────────────
        ses_tab = SesUstasiTab()
        tabs.addTab(ses_tab, "🎙  Ses Ustası")

        # ── Sekme 2: HiFi Stüdyo ──────────────────────────
        hifi_tab = HiFiTab()
        tabs.addTab(hifi_tab, "🎛  HiFi Stüdyo")

        self.setCentralWidget(tabs)

        self.statusBar().showMessage(
            f"{APP_NAME}  ·  Akustik & Ses Mühendisliği Araçları  ·  v{APP_VERSION}"
        )
        self.statusBar().setStyleSheet(
            "QStatusBar { color: #606080; font-size: 11px; }"
        )


def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("DD1")

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    ui_interface.apply_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
