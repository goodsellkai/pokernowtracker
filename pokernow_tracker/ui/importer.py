"""The Import tab: drag a hand history in, or browse for one."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QHeaderView, QLabel, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ..ingest import import_file
from ..stats import ratio
from ..store import Store
from . import theme
from .widgets import Card, dim, format_money, hint


class DropZone(QLabel):
    """A drop target that also opens a file dialog when clicked."""

    files_dropped = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(130)
        self.setCursor(Qt.PointingHandCursor)
        self.setAcceptDrops(True)
        self.setText("Drop hand history CSV files here, or click to browse")
        self.setProperty("active", "false")

    def _set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, event) -> None:
        self._set_active(False)

    def dropEvent(self, event) -> None:
        self._set_active(False)
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.toLocalFile().lower().endswith(".csv")
        ]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()

    def mousePressEvent(self, event) -> None:
        names, _filter = QFileDialog.getOpenFileNames(
            self, "Choose hand history exports", "", "Hand histories (*.csv);;All files (*)"
        )
        if names:
            self.files_dropped.emit([Path(name) for name in names])


class ImportTab(QWidget):
    """Bring hand histories in and show what each one added."""

    imported = Signal()

    def __init__(self, store: Store, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._store = store

        column = QVBoxLayout(self)
        column.setContentsMargins(16, 14, 16, 14)
        column.setSpacing(12)

        column.addWidget(hint(
            "In PokerNow, open the game's Log panel and download the hand history CSV, then"
            " drop it here. Statistics accumulate across every log you import. Re-importing"
            " a log you already have is safe, because hands are matched by their id."
        ))

        card = Card("Import hand histories")
        zone = DropZone()
        zone.files_dropped.connect(self._import)
        card.add(zone)

        self._summary = dim("")
        card.add(self._summary)

        self._results = QTableWidget(0, 5)
        self._results.setHorizontalHeaderLabels(["Player", "Hands", "VPIP", "PFR", "Result"])
        self._results.verticalHeader().setVisible(False)
        self._results.setEditTriggers(QTableWidget.NoEditTriggers)
        self._results.setSelectionMode(QTableWidget.NoSelection)
        self._results.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._results.setAlternatingRowColors(True)
        self._results.setShowGrid(False)
        self._results.hide()
        card.add(self._results)

        column.addWidget(card)
        column.addStretch(1)

    def _import(self, paths: List[Path]) -> None:
        from PySide6.QtGui import QColor

        lines: List[str] = []
        rows: List[tuple] = []
        added = 0

        for path in paths:
            try:
                result = import_file(path, self._store)
            except Exception as error:  # a malformed file should not kill the app
                lines.append(f"{path.name}: could not be read ({error})")
                continue

            added += result.hands
            detail = f"{result.hands} new hands"
            if result.duplicates:
                detail += f", {result.duplicates} already known"
            if result.hero_name:
                detail += f", exported by {result.hero_name}"
            lines.append(f"{path.name}: {detail}")

            for summary in result.per_player.values():
                rows.append((
                    summary["name"], int(summary["hands"]),
                    None, None, summary["net"],
                ))

        merged = self._store.merge_duplicate_names()
        if merged:
            lines.append(f"Merged {merged} duplicate player record(s).")
        self._store.save()

        lines.append(
            f"{added} hands added. {len(self._store.players)} players tracked."
        )
        self._summary.setText("\n".join(lines))

        rows.sort(key=lambda r: -r[4])
        self._results.setRowCount(len(rows))
        for index, (name, hands, _v, _p, net) in enumerate(rows):
            player = next(
                (p for p in self._store.players.values() if p.name == name), None
            )
            vpip = ratio(player.counters["vpip"], player.counters["hands"]) if player else None
            pfr = ratio(player.counters["pfr"], player.counters["hands"]) if player else None

            cells = [
                QTableWidgetItem(name),
                QTableWidgetItem(str(hands)),
                QTableWidgetItem("-" if vpip is None else f"{vpip:.0f}%"),
                QTableWidgetItem("-" if pfr is None else f"{pfr:.0f}%"),
                QTableWidgetItem(format_money(net)),
            ]
            cells[4].setForeground(QColor(theme.POSITIVE if net >= 0 else theme.NEGATIVE))
            for column, item in enumerate(cells):
                if column:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._results.setItem(index, column, item)
        self._results.setVisible(bool(rows))
        self.imported.emit()
