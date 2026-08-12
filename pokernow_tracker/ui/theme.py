"""Colours, typography, and the application stylesheet.

The palette is built from felt-tinted neutrals with a muted brass accent, so
the saturated action colours in the hand grid stay the loudest thing on screen.
"""

from __future__ import annotations

from PySide6.QtGui import QColor

# Neutrals carry a faint green cast rather than being pure grey, which keeps
# the card-room feel without tinting the data.
BACKGROUND = "#141715"
SURFACE = "#1a1e1b"
SURFACE_HIGH = "#212724"
LINE = "#2c332e"
LINE_SOFT = "#242a26"

TEXT = "#e2e0d7"
TEXT_MUTED = "#8d948c"
TEXT_FAINT = "#646b65"

ACCENT = "#a8862f"
ACCENT_HOVER = "#c09a38"
ACCENT_INK = "#12100a"

POSITIVE = "#5f9c6d"
NEGATIVE = "#bd5a4d"
INFO = "#5b86a3"
CAUTION = "#b5893c"

#: Colours per observed action, from most to least committed.
ACTION_COLOUR = {
    "q5": QColor(206, 76, 132),
    "q": QColor(178, 74, 150),
    "t": QColor(139, 92, 196),
    "o": QColor(196, 88, 74),
    "c": QColor(190, 152, 66),
    "c3": QColor(190, 152, 66),
    "c4": QColor(190, 152, 66),
    "l": QColor(190, 152, 66),
    "x": QColor(70, 106, 132),
    "f": QColor(74, 82, 78),
    "fv": QColor(74, 82, 78),
    "f3": QColor(74, 82, 78),
    "f4": QColor(74, 82, 78),
}

TIER_COLOUR = {
    "3bet": QColor(139, 92, 196),
    "open": QColor(196, 88, 74),
    "call": QColor(190, 152, 66),
    "fold": QColor(38, 44, 40),
}

#: Hue used for the weighted view, depending on the action being asked about.
ACTION_HUE = {
    "open": QColor(196, 88, 74),
    "iso": QColor(196, 88, 74),
    "limp": QColor(190, 152, 66),
    "call": QColor(190, 152, 66),
    "call-3bet": QColor(190, 152, 66),
    "call-4bet": QColor(190, 152, 66),
    "3bet": QColor(139, 92, 196),
    "4bet": QColor(178, 74, 150),
    "5bet": QColor(206, 76, 132),
    "check": QColor(70, 106, 132),
    "fold": QColor(96, 112, 104),
    "fold-vs-raise": QColor(96, 112, 104),
    "fold-vs-3bet": QColor(96, 112, 104),
    "fold-vs-4bet": QColor(96, 112, 104),
}

EMPTY_CELL = QColor(31, 36, 33)
GRID_BACKGROUND = QColor(20, 23, 21)

STYLE_COLOUR = {
    "Nit": "#4a6d8c",
    "Rock": "#4a6d8c",
    "TAG": "#4f8a63",
    "LAG": "#a2703a",
    "Loose-passive": "#7c5a99",
    "Calling station": "#7c5a99",
    "Whale": "#7c5a99",
    "Maniac": "#b1544a",
    "Low sample": "#5c635e",
}


def blend(colour: QColor, weight: float, base: QColor = QColor(26, 30, 27)) -> QColor:
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
    return QColor(18, 20, 18) if luminance > 148 else QColor(238, 238, 234)


STYLESHEET = f"""
QWidget {{
    background: {BACKGROUND};
    color: {TEXT};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{ background: {BACKGROUND}; }}
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}

/* Title bar ------------------------------------------------------------- */
#Header {{ background: {SURFACE}; border-bottom: 1px solid {LINE}; }}
#Wordmark {{ font-size: 14px; font-weight: 600; color: {TEXT}; }}
#WordmarkSuit {{ font-size: 15px; color: {ACCENT}; }}
#HeaderMeta {{ color: {TEXT_FAINT}; font-size: 12px; }}

/* Navigation ------------------------------------------------------------ */
QTabWidget::pane {{ border: none; background: {BACKGROUND}; }}
QTabBar {{ background: {SURFACE}; }}
QTabBar::tab {{
    background: transparent; color: {TEXT_MUTED};
    padding: 9px 18px; margin: 0; border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}

/* Surfaces -------------------------------------------------------------- */
#Panel {{ background: {SURFACE}; border: 1px solid {LINE_SOFT}; border-radius: 2px; }}
#Inset {{ background: {BACKGROUND}; border: 1px solid {LINE_SOFT}; border-radius: 2px; }}
#Heading {{ color: {TEXT}; font-size: 13px; font-weight: 600; }}
#Subheading {{ color: {TEXT_MUTED}; font-size: 12px; font-weight: 600; }}
#Muted {{ color: {TEXT_MUTED}; }}
#Faint {{ color: {TEXT_FAINT}; font-size: 12px; }}
#Notice {{
    background: {SURFACE}; border-left: 2px solid {LINE};
    color: {TEXT_MUTED}; padding: 9px 12px;
}}
#NoticeWarning {{
    background: {SURFACE}; border-left: 2px solid {CAUTION};
    color: {TEXT_MUTED}; padding: 9px 12px;
}}

/* Buttons --------------------------------------------------------------- */
QPushButton {{
    background: {SURFACE_HIGH}; border: 1px solid {LINE};
    border-radius: 2px; color: {TEXT}; padding: 6px 13px;
}}
QPushButton:hover {{ background: #2a312c; border-color: #3d453f; }}
QPushButton:pressed {{ background: #171b18; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; background: {SURFACE}; border-color: {LINE_SOFT}; }}
QPushButton#Primary {{
    background: {ACCENT}; border-color: {ACCENT}; color: {ACCENT_INK}; font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#Destructive {{ color: {NEGATIVE}; border-color: #4a2d2a; }}
QPushButton#Destructive:hover {{ border-color: {NEGATIVE}; background: #2a1e1c; }}
QPushButton#Quiet {{
    background: transparent; border: 1px solid transparent; color: {TEXT_MUTED};
    padding: 4px 8px;
}}
QPushButton#Quiet:hover {{ color: {TEXT}; background: {SURFACE_HIGH}; }}

/* Segmented selectors --------------------------------------------------- */
QPushButton#Segment {{
    background: transparent; border: 1px solid {LINE};
    border-radius: 2px; color: {TEXT_MUTED};
    padding: 4px 10px; font-size: 12px;
}}
QPushButton#Segment:hover {{ color: {TEXT}; border-color: #3d453f; }}
QPushButton#Segment:checked {{
    background: {ACCENT}; border-color: {ACCENT}; color: {ACCENT_INK}; font-weight: 600;
}}

/* Inputs ---------------------------------------------------------------- */
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QTextEdit, QPlainTextEdit {{
    background: {BACKGROUND}; border: 1px solid {LINE}; border-radius: 2px;
    color: {TEXT}; padding: 5px 8px;
    selection-background-color: {ACCENT}; selection-color: {ACCENT_INK};
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 16px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {LINE}; color: {TEXT};
    selection-background-color: {ACCENT}; selection-color: {ACCENT_INK}; outline: none;
}}

/* Tables ---------------------------------------------------------------- */
QTableWidget, QTableView {{
    background: {SURFACE}; alternate-background-color: {SURFACE};
    gridline-color: transparent; border: 1px solid {LINE_SOFT}; border-radius: 2px;
    selection-background-color: #2b332d; selection-color: {TEXT};
    outline: none;
}}
QHeaderView::section {{
    background: {SURFACE}; color: {TEXT_FAINT}; border: none;
    border-bottom: 1px solid {LINE}; padding: 6px 8px; font-size: 12px; font-weight: 600;
}}
QHeaderView::section:hover {{ color: {TEXT_MUTED}; }}
QTableWidget::item {{ padding: 3px 8px; border-bottom: 1px solid {LINE_SOFT}; }}
QTableWidget#Compact::item {{ padding: 1px 8px; }}
QTableWidget::item:selected {{ background: #2b332d; }}

/* Scrollbars ------------------------------------------------------------ */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #333b35; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: #414a44; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #333b35; border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* Sliders --------------------------------------------------------------- */
QSlider::groove:horizontal {{ height: 3px; background: {LINE}; border-radius: 1px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 1px; }}
QSlider::handle:horizontal {{
    background: {TEXT}; width: 11px; height: 11px;
    margin: -4px 0; border-radius: 5px;
}}

QToolTip {{
    background: #0f120f; color: {TEXT}; border: 1px solid {LINE}; padding: 5px 7px;
}}

#DropTarget {{
    background: {BACKGROUND}; border: 1px dashed #3b443d;
    border-radius: 2px; color: {TEXT_MUTED};
}}
#DropTarget[active="true"] {{ border-color: {ACCENT}; color: {TEXT}; }}

QSplitter::handle {{ background: {LINE_SOFT}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
"""
