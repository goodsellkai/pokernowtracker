"""The Players tab: a card per tracked opponent."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from ..stats import Baselines, classify, summarize
from ..store import Player, Store
from . import theme
from .widgets import Badge, StatChip, dim, format_factor, format_money, format_percent, hint


class PlayerCard(QFrame):
    """One opponent at a glance."""

    clicked = Signal(object)

    def __init__(self, player: Player, baselines: Baselines, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._player = player
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"#Card {{ border-left: 3px solid {theme.LINE}; }}"
            f"#Card:hover {{ border-left: 3px solid {theme.ACCENT}; }}"
        )
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(8)

        stats = summarize(player)
        style = classify(player)

        heading = QHBoxLayout()
        heading.setSpacing(8)
        name = QLabel(player.name)
        name.setStyleSheet("font-size:15px;font-weight:700;")
        heading.addWidget(name)
        heading.addWidget(Badge(style, theme.STYLE_BADGE.get(style, "#566573")))
        if player.tag:
            heading.addWidget(Badge(player.tag, "#3d4148"))
        heading.addStretch(1)
        column.addLayout(heading)

        row = QHBoxLayout()
        row.setSpacing(14)
        for caption, key, value in (
            ("VPIP", "vpip", format_percent(stats.vpip)),
            ("PFR", "pfr", format_percent(stats.pfr)),
            ("RFI", "rfi", format_percent(stats.rfi)),
            ("3Bet", "three_bet", format_percent(stats.three_bet)),
            ("AF", "aggression_factor", format_factor(stats.aggression_factor)),
        ):
            direction, average = baselines.deviation(key, player)
            row.addWidget(StatChip(caption, value, direction, average))
        row.addWidget(StatChip(
            "Net", format_money(stats.net),
            colour=theme.POSITIVE if stats.net >= 0 else theme.NEGATIVE,
        ))
        row.addWidget(StatChip("Hands", str(stats.hands)))
        row.addStretch(1)
        column.addLayout(row)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._player)


class PlayersTab(QWidget):
    """Searchable list of everyone tracked."""

    player_opened = Signal(object)

    def __init__(self, store: Store, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._store = store
        self._search = ""

        column = QVBoxLayout(self)
        column.setContentsMargins(16, 14, 16, 14)
        column.setSpacing(12)

        self._banner = hint("", warning=True)
        self._banner.hide()
        column.addWidget(self._banner)

        header = QHBoxLayout()
        header.setSpacing(10)
        self._count = QLabel("Players")
        self._count.setObjectName("CardTitle")
        header.addWidget(self._count)
        header.addStretch(1)
        search = QLineEdit()
        search.setPlaceholderText("Search")
        search.setFixedWidth(200)
        search.textChanged.connect(self._on_search)
        header.addWidget(search)
        column.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(10)
        self._grid.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._container)
        column.addWidget(scroll, 1)

        self._empty = dim("No players yet. Import a hand history to get started.")
        column.addWidget(self._empty)

    def _on_search(self, text: str) -> None:
        self._search = text.strip().lower()
        self.reload()

    def reload(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        players: List[Player] = sorted(
            self._store.players.values(), key=lambda p: -p.counters["hands"]
        )
        if self._search:
            players = [p for p in players if self._search in p.name.lower()]

        baselines = Baselines(self._store.players.values())
        for index, player in enumerate(players):
            card = PlayerCard(player, baselines)
            card.clicked.connect(self.player_opened.emit)
            self._grid.addWidget(card, index // 2, index % 2)

        self._count.setText(f"Players ({len(players)})")
        self._empty.setVisible(not players and not self._search)

        observations = sum(p.observation_count for p in self._store.players.values())
        hands = any(p.counters["hands"] for p in self._store.players.values())
        if hands and observations == 0:
            self._banner.setText(
                "No hole cards are loaded even though hands are imported. Rebuild from the"
                " Data tab, or import a log to populate observed ranges."
            )
            self._banner.show()
        else:
            self._banner.hide()
