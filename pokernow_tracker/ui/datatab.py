"""The Data tab: storage, the log archive, backups, and reset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..ingest import rebuild
from ..store import Store, remember_data_dir
from .widgets import Panel, Rule, faint, muted, notice


class DataTab(QWidget):
    """Where everything is kept, and how to regenerate or export it."""

    changed = Signal()
    relocated = Signal(object)

    def __init__(self, store: Store, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._store = store

        column = QVBoxLayout(self)
        column.setContentsMargins(16, 14, 16, 14)
        column.setSpacing(12)

        storage = Panel("Storage")
        self._location = muted("")
        storage.add(self._location)
        self._counts = muted("")
        storage.add(self._counts)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        move = QPushButton("Change folder")
        move.setToolTip("Keep tracked data somewhere else")
        move.clicked.connect(self._relocate)
        buttons.addWidget(move)
        export = QPushButton("Export backup")
        export.setObjectName("Primary")
        export.clicked.connect(self._export)
        buttons.addWidget(export)
        buttons.addStretch(1)
        reset = QPushButton("Reset everything")
        reset.setObjectName("Destructive")
        reset.clicked.connect(self._reset)
        buttons.addWidget(reset)
        storage.add_layout(buttons)
        column.addWidget(storage)

        archive = Panel("Log archive")
        archive.add(muted(
            "Imported logs are kept so every statistic can be regenerated whenever the"
            " analysis changes. The same file is never imported twice, and only the"
            " fullest export of each game is stored."
        ))
        self._archive_summary = muted("")
        archive.add(self._archive_summary)

        archive_buttons = QHBoxLayout()
        archive_buttons.setSpacing(8)
        rebuild_button = QPushButton("Rebuild from archived logs")
        rebuild_button.clicked.connect(self._rebuild)
        archive_buttons.addWidget(rebuild_button)
        archive_buttons.addStretch(1)
        clear = QPushButton("Clear archive")
        clear.setObjectName("Destructive")
        clear.clicked.connect(self._clear)
        archive_buttons.addWidget(clear)
        archive.add_layout(archive_buttons)
        column.addWidget(archive)

        sessions = Panel("Imported sessions")
        self._sessions = QTableWidget(0, 4)
        self._sessions.setHorizontalHeaderLabels(["Date", "Hands", "Stakes", "Source"])
        self._sessions.verticalHeader().setVisible(False)
        self._sessions.setEditTriggers(QTableWidget.NoEditTriggers)
        self._sessions.setSelectionMode(QTableWidget.NoSelection)
        self._sessions.setAlternatingRowColors(True)
        self._sessions.setShowGrid(False)
        header = self._sessions.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        sessions.add(self._sessions)
        column.addWidget(sessions, 1)

    def reload(self) -> None:
        self._location.setText(f"Location:  {self._store.dir}")
        self._counts.setText(
            f"{len(self._store.players)} players   ·   "
            f"{len(self._store.sessions)} sessions   ·   "
            f"{sum(p.observation_count for p in self._store.players.values())} observed hands"
        )
        logs, hands, size = self._store.archive_summary()
        self._archive_summary.setText(
            f"{logs} log{'s' if logs != 1 else ''} archived"
            f"   ·   {hands} hands   ·   {size / 1_048_576:.1f} MB"
            if logs
            else "No logs archived yet. Import one to enable automatic rebuilds."
        )

        rows = self._store.sessions
        self._sessions.setRowCount(len(rows))
        for index, session in enumerate(rows):
            cells = [
                str(session.start)[:10], str(session.hands),
                session.stakes or "-", session.name or "-",
            ]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if column == 1:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._sessions.setItem(index, column, item)

    def set_store(self, store: Store) -> None:
        self._store = store
        self.reload()

    def _relocate(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose where to keep tracked data", str(self._store.dir)
        )
        if not chosen:
            return
        remember_data_dir(Path(chosen))
        self.relocated.emit(Path(chosen))
        QMessageBox.information(
            self, "Data folder changed",
            f"Tracked data now lives in\n{chosen}\n\nAnything already saved stays"
            " where it was; import your logs again, or copy the old folder's"
            " contents across, to bring it with you.",
        )

    def _rebuild(self) -> None:
        count = rebuild(self._store)
        if not count:
            QMessageBox.information(
                self, "Nothing to rebuild",
                "No logs are archived yet. Import a hand history first.",
            )
            return
        self._store.save()
        self.changed.emit()
        self.reload()
        QMessageBox.information(
            self, "Rebuilt",
            f"Regenerated every statistic from {count} archived log"
            f"{'s' if count != 1 else ''}.",
        )

    def _clear(self) -> None:
        confirm = QMessageBox.question(
            self, "Clear archive",
            "Clear the archived logs?\n\nCurrent statistics stay, but they could no"
            " longer be regenerated automatically after a future update.",
        )
        if confirm == QMessageBox.Yes:
            self._store.clear_archive()
            self.reload()

    def _export(self) -> None:
        name, _filter = QFileDialog.getSaveFileName(
            self, "Export backup", "pokernow-backup.json", "JSON (*.json)"
        )
        if not name:
            return
        payload = {
            "players": [p.to_dict() for p in self._store.players.values()],
            "sessions": [s.to_dict() for s in self._store.sessions],
        }
        Path(name).write_text(json.dumps(payload, indent=1), encoding="utf-8")
        QMessageBox.information(self, "Exported", f"Backup written to {name}")

    def _reset(self) -> None:
        confirm = QMessageBox.question(
            self, "Reset everything",
            "Delete all players, statistics, and sessions?\n\nThis cannot be undone."
            " Archived logs are kept, so you can rebuild afterwards.",
        )
        if confirm != QMessageBox.Yes:
            return
        self._store.reset()
        self._store.save()
        self.changed.emit()
        self.reload()
