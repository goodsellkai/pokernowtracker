"""Small reusable pieces shared across the interface."""

from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from . import theme


def _wrap(buttons: Sequence[QPushButton], available: int, spacing: int = 4) -> list[list[QPushButton]]:
    """Split buttons into rows that fit the given width.

    Wrapping is decided once, from each button's own size hint, rather than
    through a height-for-width layout. Qt computes a widget's minimum height
    before it knows the final width, and a flow layout asked at that moment
    reports the fully stacked height, which inflates the whole window.
    """
    rows: list[list[QPushButton]] = [[]]
    used = 0
    for button in buttons:
        width = button.sizeHint().width()
        if rows[-1] and used + spacing + width > available:
            rows.append([])
            used = 0
        rows[-1].append(button)
        used += width + (spacing if used else 0)
    return rows


class Panel(QFrame):
    """A titled surface."""

    def __init__(self, title: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(10)
        if title:
            self._layout.addWidget(heading(title))

    def body(self) -> QVBoxLayout:
        return self._layout

    def add(self, widget: QWidget) -> QWidget:
        self._layout.addWidget(widget)
        return widget

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)


class Segmented(QWidget):
    """A labelled row of mutually exclusive options."""

    changed = Signal(str)

    def __init__(
        self,
        label: str,
        options: Sequence[Tuple[str, str]],
        current: str = "",
        parent: Optional[QWidget] = None,
        label_width: int = 0,
        vertical: bool = False,
        wrap_width: int = 0,
    ):
        super().__init__(parent)
        outer = QVBoxLayout(self) if vertical else QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6 if vertical else 4)

        if label:
            caption = QLabel(label)
            caption.setObjectName("Faint")
            if label_width:
                caption.setFixedWidth(label_width)
            outer.addWidget(caption)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        buttons = []
        for key, text in options:
            button = QPushButton(text)
            button.setObjectName("Segment")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked, k=key: self.changed.emit(k))
            self._group.addButton(button)
            self._buttons[key] = button
            buttons.append(button)

        rows = _wrap(buttons, wrap_width) if wrap_width else [buttons]
        stack = QVBoxLayout()
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(4)
        for line in rows:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            for button in line:
                row.addWidget(button)
            row.addStretch(1)
            stack.addLayout(row)
        outer.addLayout(stack)

        if current in self._buttons:
            self._buttons[current].setChecked(True)

    def set_current(self, key: str) -> None:
        button = self._buttons.get(key)
        if button:
            button.setChecked(True)
        elif self._group.checkedButton():
            self._group.setExclusive(False)
            self._group.checkedButton().setChecked(False)
            self._group.setExclusive(True)

    def current(self) -> Optional[str]:
        for key, button in self._buttons.items():
            if button.isChecked():
                return key
        return None


class Tag(QLabel):
    """A small colour-coded label for playing style."""

    def __init__(self, text: str, colour: str, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setStyleSheet(
            f"color:{colour};border:1px solid {colour};border-radius:2px;"
            "padding:0px 6px;font-size:11px;"
        )
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)


class Metric(QWidget):
    """A caption above a value, with an optional deviation marker."""

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
        column.setSpacing(0)

        head = QLabel(caption)
        head.setStyleSheet(f"color:{theme.TEXT_FAINT};font-size:11px;")
        column.addWidget(head)

        marker, text_colour = "", colour or theme.TEXT
        if direction == "high":
            marker, text_colour = " ▲", theme.NEGATIVE
        elif direction == "low":
            marker, text_colour = " ▼", theme.INFO

        body = QLabel(f"{value}{marker}")
        body.setStyleSheet(f"color:{text_colour};font-size:15px;")
        if average is not None and direction:
            body.setToolTip(f"table average {average:.0f}")
        column.addWidget(body)


class Rule(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background:{theme.LINE_SOFT};")


def heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Heading")
    return label


def subheading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Subheading")
    return label


def muted(text: str, wrap: bool = True) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setWordWrap(wrap)
    return label


def faint(text: str, wrap: bool = True) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Faint")
    label.setWordWrap(wrap)
    return label


def notice(text: str, warning: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName("NoticeWarning" if warning else "Notice")
    label.setWordWrap(True)
    return label


def money_colour(amount: float) -> str:
    return theme.POSITIVE if amount >= 0 else theme.NEGATIVE


def format_money(amount: float) -> str:
    return f"{'-' if amount < 0 else '+'}{abs(amount):,.2f}"


def format_percent(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.0f}%"


def format_factor(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if math.isinf(value):
        return "∞"
    return f"{value:.1f}"
