"""The Players tab: every tracked opponent, sortable."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..stats import Baselines, classify, summarize
from ..store import Player, Store
from . import theme
from .widgets import (
    Panel, faint, format_factor, format_money, format_percent, heading, muted, notice,
)

COLUMNS = [
    ("Player", "name", ""),
    ("Style", "style", ""),
    ("Hands", "hands", ""),
    ("VPIP", "vpip", "vpip"),
    ("PFR", "pfr", "pfr"),
    ("RFI", "rfi", "rfi"),
    ("3-bet", "three_bet", "three_bet"),
    ("Fold to 3B", "fold_to_three_bet", "fold_to_three_bet"),
    ("C-bet", "cbet", "cbet"),
    ("AF", "aggression_factor", "aggression_factor"),
    ("WTSD", "wtsd", "wtsd"),
    ("Net", "net", ""),
    ("bb/100", "bb_per_100", ""),
]


class SortableItem(QTableWidgetItem):
    """Sorts on a real number rather than on the text shown."""

    def __init__(self, text: str, value: Optional[float]):
        super().__init__(text)
        self._value = value if value is not None else float("-inf")
        self.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

    def __lt__(self, other) -> bool:
        if isinstance(other, SortableItem):
            return self._value < other._value
        return super().__lt__(other)


class PlayersTab(QWidget):
    """A table of everyone tracked, with table-relative flags."""

    player_opened = Signal(object)

    def __init__(self, store: Store, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._store = store
        self._search = ""
        self._rows: List[Player] = []

        column = QVBoxLayout(self)
        column.setContentsMargins(18, 16, 18, 16)
        column.setSpacing(12)

        self._banner = notice("", warning=True)
        self._banner.hide()
        column.addWidget(self._banner)

        panel = Panel()
        header = QHBoxLayout()
        header.setSpacing(10)
        self._title = heading("Players")
        header.addWidget(self._title)
        self._hint = faint("Select a player for their full record and range.", wrap=False)
        header.addWidget(self._hint)
        header.addStretch(1)
        search = QLineEdit()
        search.setPlaceholderText("Filter by name")
        search.setFixedWidth(180)
        search.textChanged.connect(self._on_search)
        header.addWidget(search)
        panel.add_layout(header)

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.setCursor(Qt.PointingHandCursor)
        self._table.cellDoubleClicked.connect(self._on_activate)
        self._table.cellClicked.connect(self._on_activate)

        header_view = self._table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        for index in range(2, len(COLUMNS)):
            header_view.setSectionResizeMode(index, QHeaderView.ResizeToContents)
        header_view.setHighlightSections(False)
        panel.add(self._table)
        column.addWidget(panel, 1)

        self._empty = muted("No players yet. Import a hand history from the Import tab.")
        column.addWidget(self._empty)

    def _on_search(self, text: str) -> None:
        self._search = text.strip().lower()
        self.reload()

    def _on_activate(self, row: int, _column: int) -> None:
        item = self._table.item(row, 0)
        if item is None:
            return
        player = self._store.players.get(item.data(Qt.UserRole))
        if player:
            self.player_opened.emit(player)

    def reload(self) -> None:
        players = sorted(self._store.players.values(), key=lambda p: -p.counters["hands"])
        if self._search:
            players = [p for p in players if self._search in p.name.lower()]
        self._rows = players

        baselines = Baselines(self._store.players.values())
        header_view = self._table.horizontalHeader()
        sort_column = header_view.sortIndicatorSection() if self._table.isSortingEnabled() else 2
        sort_order = header_view.sortIndicatorOrder() if self._table.isSortingEnabled() else Qt.DescendingOrder
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(players))

        for row, player in enumerate(players):
            stats = summarize(player)
            style = classify(player)

            name = QTableWidgetItem(player.name)
            name.setData(Qt.UserRole, player.id)
            name.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._table.setItem(row, 0, name)

            style_item = QTableWidgetItem(style)
            style_item.setForeground(QColor(theme.STYLE_COLOUR.get(style, theme.TEXT_MUTED)))
            style_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._table.setItem(row, 1, style_item)

            values = {
                "hands": (str(stats.hands), float(stats.hands)),
                "vpip": (format_percent(stats.vpip), stats.vpip),
                "pfr": (format_percent(stats.pfr), stats.pfr),
                "rfi": (format_percent(stats.rfi), stats.rfi),
                "three_bet": (format_percent(stats.three_bet), stats.three_bet),
                "fold_to_three_bet": (
                    format_percent(stats.fold_to_three_bet), stats.fold_to_three_bet,
                ),
                "cbet": (format_percent(stats.cbet), stats.cbet),
                "aggression_factor": (
                    format_factor(stats.aggression_factor), stats.aggression_factor,
                ),
                "wtsd": (format_percent(stats.wtsd), stats.wtsd),
                "net": (format_money(stats.net), stats.net),
                "bb_per_100": (
                    "—" if stats.bb_per_100 is None else f"{stats.bb_per_100:+.1f}",
                    stats.bb_per_100,
                ),
            }

            for index, (_label, key, compare) in enumerate(COLUMNS):
                if index < 2:
                    continue
                text, number = values[key]
                direction, average = ("", None)
                if compare:
                    direction, average = baselines.deviation(compare, player)
                    if direction:
                        text += " ▲" if direction == "high" else " ▼"

                item = SortableItem(text, number)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if direction == "high":
                    item.setForeground(QColor(theme.NEGATIVE))
                elif direction == "low":
                    item.setForeground(QColor(theme.INFO))
                elif key in ("net", "bb_per_100") and number is not None:
                    item.setForeground(
                        QColor(theme.POSITIVE if number >= 0 else theme.NEGATIVE)
                    )
                if average is not None and direction:
                    item.setToolTip(f"table average {average:.0f}")
                self._table.setItem(row, index, item)

        self._table.setSortingEnabled(True)
        self._table.sortItems(sort_column, sort_order)
        self._title.setText(f"Players  ({len(players)})")

        has_any = bool(self._store.players)
        self._empty.setVisible(not has_any)
        self._hint.setVisible(has_any)

        observed = sum(p.observation_count for p in self._store.players.values())
        if has_any and observed == 0:
            self._banner.setText(
                "No hole cards are loaded even though hands are imported. Rebuild from"
                " the Data tab, or import a log, to populate observed ranges."
            )
            self._banner.show()
        else:
            self._banner.hide()
