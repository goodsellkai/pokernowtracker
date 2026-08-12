"""Colours, fonts, and the application stylesheet."""

from __future__ import annotations

from PySide6.QtGui import QColor

BACKGROUND = "#141416"
PANEL = "#1c1d20"
PANEL_RAISED = "#242528"
LINE = "#303136"
TEXT = "#e7e5e0"
DIM = "#96948e"
ACCENT = "#d9a23c"
ACCENT_INK = "#1c1503"
POSITIVE = "#58b97e"
NEGATIVE = "#e05c4b"
INFO = "#4aa3e0"

#: Colours per observed action, from most to least committed.
ACTION_COLOUR = {
    "q5": QColor(244, 63, 142),
    "q": QColor(214, 59, 168),
    "t": QColor(168, 85, 247),
    "o": QColor(224, 92, 75),
    "c": QColor(230, 184, 74),
    "c3": QColor(230, 184, 74),
    "c4": QColor(230, 184, 74),
    "l": QColor(230, 184, 74),
    "x": QColor(46, 95, 134),
    "f": QColor(88, 94, 104),
    "fv": QColor(88, 94, 104),
    "f3": QColor(88, 94, 104),
    "f4": QColor(88, 94, 104),
}

TIER_COLOUR = {
    "3bet": QColor(168, 85, 247),
    "open": QColor(224, 92, 75),
    "call": QColor(230, 184, 74),
    "fold": QColor(40, 42, 46),
}

#: Hue used for the weighted view, per action being asked about.
ACTION_HUE = {
    "open": QColor(224, 92, 75),
    "iso": QColor(224, 92, 75),
    "limp": QColor(230, 184, 74),
    "call": QColor(230, 184, 74),
    "call-3bet": QColor(230, 184, 74),
    "call-4bet": QColor(230, 184, 74),
    "3bet": QColor(168, 85, 247),
    "4bet": QColor(214, 59, 168),
    "5bet": QColor(244, 63, 142),
    "check": QColor(74, 163, 224),
    "fold": QColor(110, 130, 150),
    "fold-vs-raise": QColor(110, 130, 150),
    "fold-vs-3bet": QColor(110, 130, 150),
    "fold-vs-4bet": QColor(110, 130, 150),
}

EMPTY_CELL = QColor(35, 36, 39)

STYLE_BADGE = {
    "Nit": "#3b5b8a",
    "Rock": "#3b5b8a",
    "TAG": "#2a9d65",
    "LAG": "#b3622e",
    "Loose-passive": "#8a3bb0",
    "Calling station": "#8a3bb0",
    "Whale": "#8a3bb0",
    "Maniac": "#c0392b",
    "Low sample": "#566573",
}


def blend(colour: QColor, weight: float, base: QColor = QColor(28, 29, 32)) -> QColor:
    """Mix a colour toward the panel background."""
    weight = max(0.0, min(1.0, weight))
    return QColor(
        round(base.red() + (colour.red() - base.red()) * weight),
        round(base.green() + (colour.green() - base.green()) * weight),
        round(base.blue() + (colour.blue() - base.blue()) * weight),
    )


def readable_on(colour: QColor) -> QColor:
    """Black or white text, whichever reads better on a background."""
    luminance = 0.299 * colour.red() + 0.587 * colour.green() + 0.114 * colour.blue()
    return QColor(20, 20, 20) if luminance > 150 else QColor(240, 240, 240)


STYLESHEET = f"""
QWidget {{
    background: {BACKGROUND};
    color: {TEXT};
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{ background: {BACKGROUND}; }}
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}

#Header {{ background: #101012; border-bottom: 1px solid {LINE}; }}
#HeaderTitle {{
    font-size: 14px; font-weight: 800; letter-spacing: 2px; color: {TEXT};
}}
#HeaderTitle #Suit {{ color: {ACCENT}; }}

QTabWidget::pane {{ border: none; background: {BACKGROUND}; }}
QTabBar {{ background: #101012; }}
QTabBar::tab {{
    background: transparent; color: {DIM};
    padding: 12px 16px; border: none; border-bottom: 2px solid transparent;
    font-size: 13px;
}}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; font-weight: 600; }}

#Card {{
    background: {PANEL}; border: 1px solid {LINE}; border-radius: 4px;
}}
#CardTitle {{
    color: {TEXT}; font-size: 12px; font-weight: 700;
    letter-spacing: 1.4px; text-transform: uppercase;
}}
#SectionLabel {{
    color: {DIM}; font-size: 11px; font-weight: 600; letter-spacing: 1.4px;
}}
#Dim {{ color: {DIM}; }}
#Hint {{
    background: {PANEL_RAISED}; border: 1px solid {LINE}; border-radius: 3px;
    color: {DIM}; padding: 10px 13px;
}}
#Warning {{
    background: {PANEL_RAISED}; border: 1px solid #6b5426; border-radius: 3px;
    color: {DIM}; padding: 10px 13px;
}}

QPushButton {{
    background: transparent; border: 1px solid {LINE}; border-radius: 3px;
    color: {TEXT}; padding: 6px 14px;
}}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton:disabled {{ color: #5a5b60; border-color: #26272b; }}
QPushButton#Primary {{
    background: {ACCENT}; border-color: {ACCENT}; color: {ACCENT_INK}; font-weight: 700;
}}
QPushButton#Primary:hover {{ background: #e6ad46; color: {ACCENT_INK}; }}
QPushButton#Danger {{ border-color: #5a3230; color: {NEGATIVE}; }}
QPushButton#Danger:hover {{ border-color: {NEGATIVE}; color: {NEGATIVE}; }}

QPushButton#Chip {{
    border: 1px solid {LINE}; border-radius: 3px; color: {DIM};
    padding: 4px 11px; font-size: 12px;
}}
QPushButton#Chip:hover {{ color: {TEXT}; }}
QPushButton#Chip:checked {{
    background: {ACCENT}; border-color: {ACCENT}; color: {ACCENT_INK}; font-weight: 700;
}}

QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QTextEdit, QPlainTextEdit {{
    background: {BACKGROUND}; border: 1px solid {LINE}; border-radius: 3px;
    color: {TEXT}; padding: 5px 8px; selection-background-color: {ACCENT};
    selection-color: {ACCENT_INK};
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {PANEL}; border: 1px solid {LINE}; color: {TEXT};
    selection-background-color: {ACCENT}; selection-color: {ACCENT_INK};
    outline: none;
}}

QTableWidget, QTableView {{
    background: {PANEL}; alternate-background-color: #202125;
    gridline-color: #26272b; border: 1px solid {LINE}; border-radius: 3px;
    selection-background-color: #2f3036; selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {PANEL}; color: {DIM}; border: none;
    border-bottom: 1px solid {LINE}; padding: 6px 8px;
    font-size: 11px; font-weight: 600; letter-spacing: 1px;
}}
QTableWidget::item {{ padding: 4px 6px; }}

QScrollArea {{ border: none; background: {BACKGROUND}; }}
QScrollBar:vertical {{ background: {BACKGROUND}; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #3a3b40; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #4a4b50; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: {BACKGROUND}; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #3a3b40; border-radius: 5px; min-width: 30px; }}

QToolTip {{
    background: #0e0e10; color: {TEXT}; border: 1px solid {LINE};
    padding: 6px 8px;
}}

#DropZone {{
    background: {BACKGROUND}; border: 1px dashed #4a4b50; border-radius: 4px;
    color: {DIM};
}}
#DropZone[active="true"] {{ border-color: {ACCENT}; color: {TEXT}; }}

QProgressBar {{
    border: 1px solid {LINE}; border-radius: 3px; background: {BACKGROUND};
    text-align: center; color: {DIM};
}}
QProgressBar::chunk {{ background: {ACCENT}; }}
"""
