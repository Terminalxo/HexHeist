from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Theme:
    bg: str
    panel: str
    panel_alt: str
    input_bg: str
    border: str
    text: str
    muted: str
    accent: str
    accent_2: str
    cyan: str
    success: str
    warning: str
    danger: str
    console: str


DARK = Theme(
    bg="#070B14",
    panel="#0E1524",
    panel_alt="#121C2E",
    input_bg="#0A1020",
    border="#24324A",
    text="#F8FAFC",
    muted="#9AA7BC",
    accent="#7C3AED",
    accent_2="#2563EB",
    cyan="#06B6D4",
    success="#22C55E",
    warning="#F59E0B",
    danger="#EF4444",
    console="#050812",
)

LIGHT = Theme(
    bg="#F3F6FB",
    panel="#FFFFFF",
    panel_alt="#F8FAFD",
    input_bg="#F9FBFF",
    border="#D8E0EC",
    text="#0B1220",
    muted="#667085",
    accent="#6D28D9",
    accent_2="#1D4ED8",
    cyan="#0891B2",
    success="#15803D",
    warning="#B45309",
    danger="#DC2626",
    console="#0A1020",
)


def resolve_theme(name: str, app: QApplication) -> tuple[str, Theme]:
    normalized = (name or "system").lower()
    if normalized == "dark":
        return "dark", DARK
    if normalized == "light":
        return "light", LIGHT

    window = app.palette().color(QPalette.ColorRole.Window)
    # Perceived luminance; enough to map Qt's system palette to our custom theme.
    luminance = (0.2126 * window.red()) + (0.7152 * window.green()) + (0.0722 * window.blue())
    return ("dark", DARK) if luminance < 128 else ("light", LIGHT)


def stylesheet(t: Theme) -> str:
    return f"""
    * {{
        font-family: Inter, SF Pro Text, Segoe UI, Arial;
        font-size: 13px;
    }}
    QMainWindow, QWidget#AppRoot {{ background: {t.bg}; color: {t.text}; }}
    QWidget {{ color: {t.text}; }}
    QFrame#Sidebar {{ background: {t.panel}; border-right: 1px solid {t.border}; }}
    QFrame#TopBar {{ background: {t.bg}; }}
    QFrame#Card {{
        background: {t.panel};
        border: 1px solid {t.border};
        border-radius: 16px;
    }}
    QLabel#Title {{ font-size: 25px; font-weight: 800; color: {t.text}; }}
    QLabel#Subtitle, QLabel#Muted {{ color: {t.muted}; }}
    QLabel#SectionTitle {{ font-size: 15px; font-weight: 750; color: {t.text}; }}
    QLabel#LogoText {{ font-size: 19px; font-weight: 900; color: {t.text}; }}
    QLabel#StatusGood {{ color: {t.success}; font-weight: 700; }}
    QLabel#StatusBad {{ color: {t.danger}; font-weight: 700; }}
    QLabel#StatusNeutral {{ color: {t.muted}; font-weight: 700; }}
    QLabel#ValueChip {{
        background: {t.panel_alt}; border: 1px solid {t.border}; border-radius: 10px;
        padding: 6px 10px; font-weight: 650;
    }}
    QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
        background: {t.input_bg};
        border: 1px solid {t.border};
        border-radius: 10px;
        padding: 8px 10px;
        selection-background-color: {t.accent};
        selection-color: white;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
        border: 1px solid {t.accent_2};
    }}
    QComboBox::drop-down {{ border: none; width: 26px; }}
    QComboBox QAbstractItemView {{
        background: {t.panel}; color: {t.text}; border: 1px solid {t.border};
        selection-background-color: {t.accent_2}; selection-color: white;
    }}
    QPushButton {{
        background: {t.panel_alt};
        border: 1px solid {t.border};
        border-radius: 10px;
        padding: 8px 13px;
        font-weight: 700;
    }}
    QPushButton:hover {{ border-color: {t.accent_2}; background: {t.input_bg}; }}
    QPushButton:pressed {{ padding-top: 9px; padding-bottom: 7px; }}
    QPushButton:disabled {{ color: {t.muted}; border-color: {t.border}; opacity: 0.6; }}
    QPushButton#Primary {{
        color: white; border: none;
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {t.accent}, stop:1 {t.accent_2});
        padding: 9px 15px;
    }}
    QPushButton#Danger {{ color: white; background: {t.danger}; border: none; }}
    QPushButton#Success {{ color: white; background: {t.success}; border: none; }}
    QPushButton#Ghost {{ background: transparent; border: 1px solid {t.border}; }}
    QPushButton#Nav {{
        text-align: left; padding: 10px 12px; border: none; border-radius: 10px;
        background: transparent; color: {t.muted}; font-weight: 700;
    }}
    QPushButton#Nav:hover {{ background: {t.panel_alt}; color: {t.text}; border: none; }}
    QPushButton#Nav:checked {{ background: {t.panel_alt}; color: {t.text}; border-left: 3px solid {t.accent}; }}
    QTableWidget {{
        background: transparent; alternate-background-color: {t.panel_alt};
        border: 1px solid {t.border}; border-radius: 10px; gridline-color: {t.border};
    }}
    QHeaderView::section {{
        background: {t.panel_alt}; color: {t.muted}; border: none; border-bottom: 1px solid {t.border};
        padding: 8px; font-weight: 700;
    }}
    QCheckBox {{ spacing: 7px; }}
    QCheckBox::indicator {{ width: 17px; height: 17px; }}
    QGroupBox {{ border: 1px solid {t.border}; border-radius: 12px; margin-top: 11px; padding-top: 13px; font-weight: 700; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 11px; padding: 0 6px; color: {t.muted}; }}
    QProgressBar {{
        border: none; border-radius: 3px; background: {t.panel_alt}; height: 6px; text-align: center;
    }}
    QProgressBar::chunk {{
        border-radius: 3px;
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {t.cyan}, stop:1 {t.accent});
    }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t.border}; min-height: 28px; border-radius: 5px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QStatusBar {{ background: {t.panel}; color: {t.muted}; border-top: 1px solid {t.border}; }}
    QMenuBar {{ background: {t.panel}; color: {t.text}; }}
    QMenuBar::item:selected, QMenu::item:selected {{ background: {t.accent_2}; color: white; }}
    QMenu {{ background: {t.panel}; color: {t.text}; border: 1px solid {t.border}; }}
    """
