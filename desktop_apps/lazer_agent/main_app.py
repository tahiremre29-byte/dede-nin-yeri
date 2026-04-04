# main_app.py — DD1 Lazer Agent
# Giriş noktası: Yalnızca Lazer / DXF araçları
# Ses & HiFi araçları için: dd1_ses_hifi/main_app.py

import sys
import os

# PyInstaller onefile modunda kaynak dosya yolunu bul
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS  # type: ignore[attr-defined]
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QFont

import ui_interface
from vector_module import DXFSVGTab


APP_NAME    = "DD1 Lazer Agent"
APP_VERSION = "1.1.0"
WIN_W, WIN_H = 1280, 780
MIN_W, MIN_H  = 900, 600


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

        # ── DXF / SVG Çizim Aracı ─────────────────────────
        dxf_tab = DXFSVGTab()
        tabs.addTab(dxf_tab, "✂  DXF / SVG Çizim Aracı")

        self.setCentralWidget(tabs)

        self.statusBar().showMessage(
            f"{APP_NAME}  ·  Lazer Atölye Araçları  ·  v{APP_VERSION}"
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
