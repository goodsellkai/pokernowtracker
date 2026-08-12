"""Small reusable pieces: cards, chip selectors, labelled values."""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from . import theme


class Card(QFrame):
    """A titled panel."""

    def __init__(self, title: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(10)
        if title:
            label = QLabel(title)
            label.setObjectName("CardTitle")
            self._layout.addWidget(label)

    def body(self) -> QVBoxLayout:
        return self._layout

    def add(self, widget: QWidget) -> QWidget:
        self._layout.addWidget(widget)
        return widget

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)


class ChipRow(QWidget):
    """A labelled row of mutually exclusive chips."""

    changed = Signal(str)

    def __init__(
        self,
        label: str,
        options: Sequence[Tuple[str, str]],
        current: str = "",
        parent: Optional[QWidget] = None,
        label_width: int = 78,
    ):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        if label:
            caption = QLabel(label)
            caption.setObjectName("Dim")
            caption.setFixedWidth(label_width)
            row.addWidget(caption)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        for key, text in options:
            button = QPushButton(text)
            button.setObjectName("Chip")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked, k=key: self.changed.emit(k))
            self._group.addButton(button)
            self._buttons[key] = button
            row.addWidget(button)

        row.addStretch(1)
        if current in self._buttons:
            self._buttons[current].setChecked(True)

    def set_current(self, key: str) -> None:
        button = self._buttons.get(key)
        if button:
            button.setChecked(True)

    def current(self) -> Optional[str]:
        for key, button in self._buttons.items():
            if button.isChecked():
                return key
        return None


class Badge(QLabel):
    """A small coloured label, used for playing style."""

    def __init__(self, text: str, colour: str, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setStyleSheet(
            f"background:{colour};color:#f2f2f2;border-radius:2px;"
            "padding:1px 7px;font-size:10px;letter-spacing:0.5px;"
        )
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)


class StatChip(QWidget):
    """A caption above a value, with an optional deviation arrow."""

    def __init__(
        self,
        caption: str,
        value: str,
        direction: str = "",
        average: Optional[float] = None,
        colour: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(1)

        head = QLabel(caption.upper())
        head.setStyleSheet(f"color:{theme.DIM};font-size:9px;letter-spacing:1px;")
        column.addWidget(head)

        arrow = ""
        text_colour = colour or theme.TEXT
        if direction == "high":
            arrow, text_colour = "  ▲", theme.NEGATIVE
        elif direction == "low":
            arrow, text_colour = "  ▼", theme.INFO

        body = QLabel(f"{value}{arrow}")
        body.setStyleSheet(f"color:{text_colour};font-size:14px;font-weight:600;")
        if average is not None and direction:
            body.setToolTip(f"table average {average:.0f}")
        column.addWidget(body)


class Separator(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setStyleSheet(f"color:{theme.LINE};background:{theme.LINE};max-height:1px;")


def hint(text: str, warning: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Warning" if warning else "Hint")
    label.setWordWrap(True)
    return label


def dim(text: str, wrap: bool = True) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Dim")
    label.setWordWrap(wrap)
    return label


def section(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("SectionLabel")
    return label


def money_colour(amount: float) -> str:
    return theme.POSITIVE if amount >= 0 else theme.NEGATIVE


def format_money(amount: float) -> str:
    return f"{'-' if amount < 0 else '+'}{abs(amount):,.2f}"


def format_percent(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.0f}%"


def format_factor(value: Optional[float]) -> str:
    import math

    if value is None:
        return "-"
    if math.isinf(value):
        return "∞"
    return f"{value:.1f}"
