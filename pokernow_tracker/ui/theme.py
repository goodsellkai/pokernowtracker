"""Colours, typography, and the application stylesheet.

Cool ink neutrals with a steel-blue accent. Blue is deliberately kept out of
the hand grid's action colours, so the interface never competes with the data
it frames.
"""

from __future__ import annotations

from PySide6.QtGui import QColor

# Neutrals lean slightly blue, which reads as an instrument panel rather than
# plain grey and leaves the warm action colours room to speak.
BACKGROUND = "#101319"
SURFACE = "#171b23"
SURFACE_HIGH = "#1f242e"
LINE = "#2b313d"
LINE_SOFT = "#212630"

TEXT = "#dfe3ea"
TEXT_MUTED = "#8b93a2"
TEXT_FAINT = "#606775"

ACCENT = "#4d7fc4"
ACCENT_HOVER = "#5d8fd4"
ACCENT_PRESSED = "#3f6cab"
ACCENT_INK = "#f2f6fc"

POSITIVE = "#4f9e77"
NEGATIVE = "#c96150"
INFO = "#4d9d9a"
CAUTION = "#c2913f"

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
    "x": QColor(64, 124, 120),
    "f": QColor(72, 80, 92),
    "fv": QColor(72, 80, 92),
    "f3": QColor(72, 80, 92),
    "f4": QColor(72, 80, 92),
}

TIER_COLOUR = {
    "3bet": QColor(139, 92, 196),
    "open": QColor(196, 88, 74),
    "call": QColor(190, 152, 66),
    "fold": QColor(35, 41, 50),
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
    "check": QColor(64, 124, 120),
    "fold": QColor(94, 104, 120),
    "fold-vs-raise": QColor(94, 104, 120),
    "fold-vs-3bet": QColor(94, 104, 120),
    "fold-vs-4bet": QColor(94, 104, 120),
}

EMPTY_CELL = QColor(28, 33, 41)
GRID_BACKGROUND = QColor(14, 17, 22)

# Spacing scale ------------------------------------------------------------
#
# Every margin and gap in the interface comes from this scale. Spacing chosen
# per widget drifts into a dozen near-identical values that read as accidental,
# whereas a small fixed set gives the layout a rhythm the eye can follow.
TIGHT = 4      # between items that belong to one control
SNUG = 8       # between related controls
GAP = 12       # between rows within a panel
STEP = 16      # between a panel's edge and a page's edge
WIDE = 24      # between panels, and around a page
ROOMY = 32     # between major columns

#: Padding inside a panel: generous at the sides, a little less top and bottom.
PANEL_PADDING = (18, 16, 18, 16)
#: Margin around the content of a tab.
PAGE_MARGIN = (WIDE, STEP + 2, WIDE, STEP + 2)

#: Table geometry. Rows need enough height that figures do not feel crammed
#: against their neighbours, which matters most in the wide players table.
ROW_HEIGHT = 32
ROW_HEIGHT_COMPACT = 26
HEADER_HEIGHT = 34

STYLE_COLOUR = {
    "Nit": "#5e93b8",
    "Rock": "#5e93b8",
    "TAG": "#4f9e77",
    "LAG": "#c2913f",
    "Loose-passive": "#8f6fb5",
    "Calling station": "#8f6fb5",
    "Whale": "#8f6fb5",
    "Maniac": "#c96150",
    "Low sample": "#5a6270",
}


def blend(colour: QColor, weight: float, base: QColor = QColor(23, 27, 35)) -> QColor:
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
    return QColor(16, 19, 25) if luminance > 148 else QColor(236, 239, 244)


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
    padding: 11px 22px; margin: 0; border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}

/* Surfaces -------------------------------------------------------------- */
#Panel {{ background: {SURFACE}; border: 1px solid {LINE_SOFT}; border-radius: 5px; }}
#Inset {{ background: {BACKGROUND}; border: 1px solid {LINE_SOFT}; border-radius: 5px; }}
#Heading {{ color: {TEXT}; font-size: 13px; font-weight: 600; }}
#Subheading {{ color: {TEXT_MUTED}; font-size: 12px; font-weight: 600; }}
#Muted {{ color: {TEXT_MUTED}; }}
#Faint {{ color: {TEXT_FAINT}; font-size: 12px; }}
#Notice {{
    background: {SURFACE}; border-left: 2px solid {ACCENT};
    color: {TEXT_MUTED}; padding: 12px 15px; line-height: 150%;
}}
#NoticeWarning {{
    background: {SURFACE}; border-left: 2px solid {CAUTION};
    color: {TEXT_MUTED}; padding: 12px 15px; line-height: 150%;
}}

/* Buttons --------------------------------------------------------------- */
QPushButton {{
    background: #262c38; border: 1px solid #333b49;
    border-radius: 4px; color: {TEXT}; padding: 7px 17px; min-height: 17px;
}}
QPushButton:hover {{ background: #2f3644; border-color: #465061; }}
QPushButton:pressed {{ background: #1b202a; border-color: {LINE}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; background: {SURFACE}; border-color: {LINE_SOFT}; }}
QPushButton#Primary {{
    background: {ACCENT}; border-color: {ACCENT}; color: {ACCENT_INK}; font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#Primary:pressed {{ background: {ACCENT_PRESSED}; border-color: {ACCENT_PRESSED}; }}
QPushButton#Destructive {{ color: {NEGATIVE}; background: #2a1f21; border-color: #4d3134; }}
QPushButton#Destructive:hover {{ background: #35262a; border-color: {NEGATIVE}; }}
QPushButton#Quiet {{
    background: transparent; border: 1px solid transparent; color: {TEXT_MUTED};
    padding: 5px 12px;
}}
QPushButton#Quiet:hover {{ color: {TEXT}; background: {SURFACE_HIGH}; border-color: {LINE}; }}

/* Segmented selectors --------------------------------------------------- */
QPushButton#Segment {{
    background: {SURFACE_HIGH}; border: 1px solid {LINE};
    border-radius: 4px; color: {TEXT_MUTED};
    padding: 5px 13px; font-size: 12px;
}}
QPushButton#Segment:hover {{ color: {TEXT}; background: #2b3240; border-color: #3c4553; }}
QPushButton#Segment:checked {{
    background: {ACCENT}; border-color: {ACCENT}; color: {ACCENT_INK}; font-weight: 600;
}}
QPushButton#Segment:checked:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}

/* Inputs ---------------------------------------------------------------- */
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QTextEdit, QPlainTextEdit {{
    background: {BACKGROUND}; border: 1px solid {LINE}; border-radius: 4px;
    color: {TEXT}; padding: 7px 10px; min-height: 17px;
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
    gridline-color: transparent; border: 1px solid {LINE_SOFT}; border-radius: 5px;
    selection-background-color: #263043; selection-color: {TEXT};
    outline: none;
}}
QHeaderView::section {{
    background: {SURFACE}; color: {TEXT_FAINT}; border: none;
    border-bottom: 1px solid {LINE}; padding: 8px 9px; font-size: 12px; font-weight: 600;
}}
QHeaderView::section:hover {{ color: {TEXT_MUTED}; }}
QTableWidget::item {{ padding: 4px 9px; border-bottom: 1px solid {LINE_SOFT}; }}
QTableWidget#Compact::item {{ padding: 2px 10px; }}
QTableWidget::item:selected {{ background: #263043; }}

/* Scrollbars ------------------------------------------------------------ */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #333c4a; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: #414b5c; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #333c4a; border-radius: 4px; min-width: 28px; }}
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
    background: #0b0e13; color: {TEXT}; border: 1px solid {LINE};
    border-radius: 4px; padding: 6px 9px;
}}

#DropTarget {{
    background: {BACKGROUND}; border: 1px dashed #3a4353;
    border-radius: 5px; color: {TEXT_MUTED};
    padding: 24px; line-height: 165%;
}}
#DropTarget[active="true"] {{ border-color: {ACCENT}; color: {TEXT}; }}

QSplitter::handle {{ background: {LINE_SOFT}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
"""
