# ui_interface.py — DD1 Lazer Agent
# Ortak UI yardımcıları, tema ve stil sabitleri

from PyQt6.QtWidgets import QApplication, QFrame
from PyQt6.QtGui import QPalette, QColor, QFont
from PyQt6.QtCore import Qt


# ── Renk paleti ──────────────────────────────────────────────
BG_DARK      = "#1a1a2e"
BG_MEDIUM    = "#16213e"
BG_CARD      = "#0f3460"
ACCENT       = "#e94560"
ACCENT_HOVER = "#ff6b6b"
TEXT_MAIN    = "#eaeaea"
TEXT_DIM     = "#a0a0b0"
BORDER       = "#2a2a4a"


# ── Global stil sayfası ───────────────────────────────────────
GLOBAL_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_MAIN};
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {BG_MEDIUM};
    border-radius: 6px;
}}

QTabBar::tab {{
    background: {BG_DARK};
    color: {TEXT_DIM};
    padding: 10px 28px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    min-width: 160px;
}}

QTabBar::tab:selected {{
    background: {ACCENT};
    color: #ffffff;
    border-color: {ACCENT};
}}

QTabBar::tab:hover:!selected {{
    background: {BG_CARD};
    color: {TEXT_MAIN};
}}

QPushButton {{
    background-color: {ACCENT};
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 22px;
    font-size: 13px;
    font-weight: 600;
    min-height: 34px;
}}

QPushButton:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton:pressed {{
    background-color: #c73652;
}}

QPushButton:disabled {{
    background-color: #3a3a5a;
    color: {TEXT_DIM};
}}

QPushButton#secondary {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
}}

QPushButton#secondary:hover {{
    background-color: #1a4a80;
}}

QTextEdit, QLineEdit, QPlainTextEdit {{
    background-color: {BG_MEDIUM};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px;
    selection-background-color: {ACCENT};
}}

QTextEdit:focus, QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: {BORDER};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {ACCENT};
    border: none;
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}}

QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}

QCheckBox {{
    color: {TEXT_MAIN};
    spacing: 8px;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER};
    border-radius: 4px;
    background: {BG_MEDIUM};
}}

QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}

QLabel {{
    color: {TEXT_MAIN};
}}

QLabel#dim {{
    color: {TEXT_DIM};
    font-size: 11px;
}}

QLabel#title {{
    font-size: 16px;
    font-weight: 700;
    color: {TEXT_MAIN};
}}

QScrollBar:vertical {{
    background: {BG_DARK};
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QProgressBar {{
    background: {BG_MEDIUM};
    border: 1px solid {BORDER};
    border-radius: 5px;
    text-align: center;
    color: {TEXT_MAIN};
    height: 18px;
}}

QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}

QGraphicsView {{
    background: #0a0a1a;
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

QFrame#card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
"""


def apply_theme(app: QApplication) -> None:
    """Uygulamaya koyu tema ve global stil sayfasını uygular."""
    app.setStyle("Fusion")
    app.setStyleSheet(GLOBAL_STYLESHEET)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(BG_DARK))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT_MAIN))
    palette.setColor(QPalette.ColorRole.Base,            QColor(BG_MEDIUM))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(BG_DARK))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(TEXT_MAIN))
    palette.setColor(QPalette.ColorRole.Text,            QColor(TEXT_MAIN))
    palette.setColor(QPalette.ColorRole.Button,          QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.BrightText,      QColor(ACCENT_HOVER))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)


def make_separator() -> QFrame:
    """Yatay ince bir ayırıcı çizgi döndürür."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    sep.setStyleSheet(f"background: {BORDER}; max-height: 1px; border: none;")
    return sep
