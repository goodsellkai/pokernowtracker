"""The main window."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..ingest import rebuild
from ..store import Player, Store
from . import theme
from .datatab import DataTab
from .detail import PlayerDetail
from .finder import RangeFinderTab
from .importer import ImportTab
from .players import PlayersTab


class MainWindow(QMainWindow):
    def __init__(self, store: Store, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._store = store
        self._windows: List[PlayerDetail] = []

        self.setWindowTitle("PokerNow Tracker")
        self.resize(1180, 820)

        root = QWidget()
        column = QVBoxLayout(root)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._build_header())

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._import = ImportTab(store)
        self._players = PlayersTab(store)
        self._finder = RangeFinderTab(store)
        self._data = DataTab(store)

        self._tabs.addTab(self._import, "Import")
        self._tabs.addTab(self._players, "Players")
        self._tabs.addTab(self._finder, "Range Finder")
        self._tabs.addTab(self._data, "Data")
        column.addWidget(self._tabs, 1)

        self.setCentralWidget(root)

        self._import.imported.connect(self.reload)
        self._players.player_opened.connect(self._open_player)
        self._data.changed.connect(self.reload)
        self._tabs.currentChanged.connect(lambda _i: self._refresh_current())

        self._check_stale()
        self.reload()
        if store.players:
            self._tabs.setCurrentWidget(self._players)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("Header")
        row = QHBoxLayout(header)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(9)

        suit = QLabel("♠")
        suit.setObjectName("WordmarkSuit")
        row.addWidget(suit)

        title = QLabel("PokerNow Tracker")
        title.setObjectName("Wordmark")
        row.addWidget(title)

        row.addStretch(1)

        self._meta = QLabel("")
        self._meta.setObjectName("HeaderMeta")
        row.addWidget(self._meta)

        reload_button = QPushButton("Reload")
        reload_button.setObjectName("Quiet")
        reload_button.setToolTip("Re-read saved data from disk and redraw")
        reload_button.clicked.connect(self._reload_from_disk)
        row.addWidget(reload_button)
        header.setFixedHeight(42)
        return header

    # --------------------------------------------------------------- events

    def _check_stale(self) -> None:
        if not (self._store.stale and self._store.players):
            return
        if self._store.archived_logs():
            rebuild(self._store)
            self._store.save()
        else:
            QMessageBox.warning(
                self, "Rebuild needed",
                "This data was produced by an earlier version and no logs are archived,"
                " so it cannot be regenerated automatically.\n\nImport your hand"
                " histories again to refresh it.",
            )

    def reload(self) -> None:
        self._players.reload()
        self._finder.reload()
        self._data.reload()

        players = len(self._store.players)
        hands = max((int(p.counters["hands"]) for p in self._store.players.values()), default=0)
        self._meta.setText(
            f"{players} players · {len(self._store.sessions)} sessions · {hands} hands"
            if players else ""
        )

    def _refresh_current(self) -> None:
        current = self._tabs.currentWidget()
        if current is self._players:
            self._players.reload()
        elif current is self._data:
            self._data.reload()

    def _reload_from_disk(self) -> None:
        self._store.load()
        self._store.merge_duplicate_names()
        self.reload()

    def _open_player(self, player: Player) -> None:
        window = PlayerDetail(player, self._store, self)
        window.changed.connect(self.reload)
        window.open_in_finder.connect(self._show_in_finder)
        window.show()
        self._windows.append(window)

    def _show_in_finder(self, player: Player, action: str, position: str) -> None:
        self._tabs.setCurrentWidget(self._finder)
        self._finder.show_player(player, action, position)

    def open_files(self, paths: List[Path]) -> None:
        """Import files handed to the application at startup."""
        self._tabs.setCurrentWidget(self._import)
        self._import._import(paths)
