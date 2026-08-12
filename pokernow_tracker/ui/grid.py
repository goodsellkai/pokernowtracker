"""The 13 by 13 starting-hand grid."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..cards import RANKS, grid_hands
from . import theme


@dataclass
class Cell:
    """One square of the grid."""

    hand: str
    colour: QColor
    label: str = ""
    detail: str = ""       # small text under the label
    marked: bool = False   # observation adjusted this cell
    tooltip: str = ""
    faded: bool = False    # inferred rather than observed


class RangeGrid(QWidget):
    """Draws all 169 starting hands, coloured by whatever a view supplies.

    Pairs run down the diagonal, suited hands sit above it and offsuit below,
    which is the layout every poker tool uses.
    """

    hand_hovered = Signal(str)
    hand_clicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._cells: Dict[str, Cell] = {}
        self._layout = grid_hands()
        self._hover: Optional[str] = None
        self.setMouseTracking(True)
        self.setMinimumSize(420, 420)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_cells(self, cells: Sequence[Cell]) -> None:
        self._cells = {cell.hand: cell for cell in cells}
        self.update()

    def clear(self) -> None:
        self._cells = {}
        self.update()

    # ------------------------------------------------------------- geometry

    def _metrics(self):
        """(left edge, top edge, cell size), keeping the grid square and centred."""
        margin = 18  # room for the rank labels
        size = max(13.0, min(self.width() - margin, self.height() - margin))
        step = size / 13.0
        left = margin + max(0.0, (self.width() - margin - size) / 2)
        return left, margin, step

    def _hand_at(self, x: float, y: float) -> Optional[str]:
        left, top, step = self._metrics()
        col = int((x - left) // step)
        row = int((y - top) // step)
        if 0 <= row < 13 and 0 <= col < 13:
            return self._layout[row][col]
        return None

    # --------------------------------------------------------------- events

    def mouseMoveEvent(self, event) -> None:
        hand = self._hand_at(event.position().x(), event.position().y())
        if hand != self._hover:
            self._hover = hand
            cell = self._cells.get(hand) if hand else None
            self.setToolTip(cell.tooltip if cell and cell.tooltip else (hand or ""))
            self.hand_hovered.emit(hand or "")
            self.update()

    def leaveEvent(self, event) -> None:
        self._hover = None
        self.update()

    def mousePressEvent(self, event) -> None:
        hand = self._hand_at(event.position().x(), event.position().y())
        if hand:
            self.hand_clicked.emit(hand)

    # -------------------------------------------------------------- drawing

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(theme.BACKGROUND))

        left, top, step = self._metrics()
        if step <= 0:
            return

        label_font = QFont(self.font())
        label_font.setPointSizeF(max(6.0, min(9.5, step * 0.30)))
        detail_font = QFont(label_font)
        detail_font.setPointSizeF(max(5.0, label_font.pointSizeF() - 1.5))
        header_font = QFont(label_font)
        header_font.setBold(True)

        # Rank headers along the top and left edge.
        painter.setFont(header_font)
        painter.setPen(QPen(QColor(theme.DIM)))
        for index, rank in enumerate(RANKS):
            painter.drawText(
                QRectF(left + index * step, top - 18, step, 18),
                Qt.AlignCenter, rank,
            )
            painter.drawText(
                QRectF(left - 18, top + index * step, 18, step),
                Qt.AlignCenter, rank,
            )

        for row in range(13):
            for col in range(13):
                hand = self._layout[row][col]
                cell = self._cells.get(hand)
                rect = QRectF(
                    left + col * step + 1, top + row * step + 1,
                    step - 2, step - 2,
                )
                colour = cell.colour if cell else theme.EMPTY_CELL
                painter.fillRect(rect, colour)

                if cell and cell.faded:
                    # A hatch keeps inferred cells distinguishable without colour.
                    painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
                    painter.drawLine(rect.topLeft(), rect.bottomRight())

                if hand == self._hover:
                    painter.setPen(QPen(QColor(theme.ACCENT), 1.5))
                    painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))

                text_colour = theme.readable_on(colour)
                label = cell.label if cell and cell.label else hand
                detail = cell.detail if cell else ""

                painter.setPen(QPen(text_colour))
                if detail:
                    painter.setFont(label_font)
                    painter.drawText(
                        QRectF(rect.x(), rect.y(), rect.width(), rect.height() * 0.62),
                        Qt.AlignCenter, label,
                    )
                    painter.setFont(detail_font)
                    faded = QColor(text_colour)
                    faded.setAlpha(190)
                    painter.setPen(QPen(faded))
                    painter.drawText(
                        QRectF(rect.x(), rect.y() + rect.height() * 0.52,
                               rect.width(), rect.height() * 0.44),
                        Qt.AlignCenter, detail,
                    )
                else:
                    painter.setFont(label_font)
                    painter.drawText(rect, Qt.AlignCenter, label)

                if cell and cell.marked:
                    dot = min(4.0, step * 0.16)
                    painter.setPen(Qt.NoPen)
                    marker = QColor(text_colour)
                    marker.setAlpha(150)
                    painter.setBrush(marker)
                    painter.drawEllipse(
                        QRectF(rect.right() - dot - 1.5, rect.top() + 1.5, dot, dot)
                    )
                    painter.setBrush(Qt.NoBrush)

        painter.end()


class Legend(QWidget):
    """A row of colour swatches explaining a grid."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._entries: List[tuple[str, QColor]] = []
        self.setFixedHeight(20)

    def set_entries(self, entries: Sequence[tuple[str, QColor]]) -> None:
        self._entries = list(entries)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.BACKGROUND))
        metrics = QFontMetrics(self.font())
        x = 0.0
        for label, colour in self._entries:
            painter.fillRect(QRectF(x, 5, 11, 11), colour)
            x += 15
            painter.setPen(QPen(QColor(theme.DIM)))
            painter.drawText(QRectF(x, 0, metrics.horizontalAdvance(label) + 4, 20),
                             Qt.AlignVCenter | Qt.AlignLeft, label)
            x += metrics.horizontalAdvance(label) + 16
        painter.end()
