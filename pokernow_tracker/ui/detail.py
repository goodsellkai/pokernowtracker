"""The player detail window."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

from ..ranges import TableAverages
from ..stats import Baselines, classify, positional, summarize
from ..store import POSITIONS, Player, Store
from . import theme
from .finder import RangePanel
from .widgets import (
    Badge, Separator, dim, format_factor, format_money, format_percent, section,
)

TAGS = ["", "Nit", "Rock", "TAG", "LAG", "Reg", "Fish", "Station", "Maniac", "Whale"]


class PlayerDetail(QDialog):
    """Everything known about one opponent, with their range alongside."""

    changed = Signal()
    open_in_finder = Signal(object, str, str)

    def __init__(self, player: Player, store: Store, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._player = player
        self._store = store

        self.setWindowTitle(player.name)
        self.setModal(False)
        self.resize(1080, 760)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        outer.addLayout(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(20)
        body.addWidget(self._build_left(), 1)
        body.addWidget(self._build_right(), 1)
        outer.addLayout(body, 1)

        outer.addLayout(self._build_footer())
        self._refresh_stats()

    # --------------------------------------------------------------- layout

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        name = QLabel(self._player.name)
        name.setStyleSheet("font-size:20px;font-weight:700;")
        row.addWidget(name)

        style = classify(self._player)
        row.addWidget(Badge(style, theme.STYLE_BADGE.get(style, "#566573")))

        stats = summarize(self._player)
        if stats.hands < 25:
            row.addWidget(dim("Small sample, treat these as rough.", wrap=False))
        row.addStretch(1)

        finder = QPushButton("Open in Range Finder")
        finder.clicked.connect(self._to_finder)
        row.addWidget(finder)

        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(close)
        return row

    def _build_left(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        panel = QWidget()
        column = QVBoxLayout(panel)
        column.setContentsMargins(0, 0, 8, 0)
        column.setSpacing(10)

        column.addWidget(section("Statistics"))
        column.addWidget(dim("▲ notably higher, ▼ notably lower than this table's average."))
        self._stats_table = self._make_table(2)
        column.addWidget(self._stats_table)

        column.addWidget(section("By position"))
        self._position_table = self._make_table(8)
        self._position_table.setHorizontalHeaderLabels(
            ["Seat", "Hands", "VPIP", "PFR", "RFI", "Limp", "Call", "3Bet"]
        )
        self._position_table.horizontalHeader().setVisible(True)
        column.addWidget(self._position_table)

        column.addWidget(section("Sessions"))
        self._session_table = self._make_table(3)
        self._session_table.setHorizontalHeaderLabels(["Date", "Hands", "Result"])
        self._session_table.horizontalHeader().setVisible(True)
        column.addWidget(self._session_table)

        column.addWidget(section("Tag"))
        self._tag = QComboBox()
        self._tag.addItems(["(none)" if t == "" else t for t in TAGS])
        current = self._player.tag or ""
        self._tag.setCurrentIndex(TAGS.index(current) if current in TAGS else 0)
        self._tag.currentIndexChanged.connect(self._on_tag)
        column.addWidget(self._tag)

        column.addWidget(section("Notes"))
        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Tells, tendencies, bet sizing")
        self._notes.setPlainText(self._player.note)
        self._notes.setFixedHeight(90)
        self._notes.textChanged.connect(self._on_note)
        column.addWidget(self._notes)

        column.addStretch(1)
        scroll.setWidget(panel)
        return scroll

    def _build_right(self) -> QWidget:
        panel = QWidget()
        column = QVBoxLayout(panel)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        column.addWidget(section("Preflop range"))
        self._panel = RangePanel(compact=True)
        self._panel.set_player(self._player, TableAverages(list(self._store.players.values())))
        column.addWidget(self._panel, 1)
        return panel

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(dim("Merge into", wrap=False))

        self._merge_target = QComboBox()
        self._merge_target.addItem("Select a player", None)
        for other in sorted(self._store.players.values(), key=lambda p: p.name.lower()):
            if other.id != self._player.id:
                self._merge_target.addItem(other.name, other.id)
        row.addWidget(self._merge_target)

        merge = QPushButton("Merge")
        merge.clicked.connect(self._on_merge)
        row.addWidget(merge)

        row.addStretch(1)
        delete = QPushButton("Delete player")
        delete.setObjectName("Danger")
        delete.clicked.connect(self._on_delete)
        row.addWidget(delete)
        return row

    def _make_table(self, columns: int) -> QTableWidget:
        table = QTableWidget(0, columns)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        return table

    # ----------------------------------------------------------------- data

    def _refresh_stats(self) -> None:
        player, counters = self._player, self._player.counters
        stats = summarize(player)
        baselines = Baselines(self._store.players.values())

        rows: list[tuple[str, str, str, str]] = []

        def add(label: str, value: str, key: str = "", note: str = "") -> None:
            direction, average = baselines.deviation(key, player) if key else ("", None)
            marker = {"high": "  ▲", "low": "  ▼"}.get(direction, "")
            parts = [note]
            if direction and average is not None:
                parts.append(f"table {average:.0f}")
            rows.append((label, value + marker, direction, "  ".join(p for p in parts if p)))

        rows.append(("PREFLOP", "", "", ""))
        add("Hands", str(stats.hands))
        add("VPIP", format_percent(stats.vpip), "vpip")
        add("PFR", format_percent(stats.pfr), "pfr")
        add("RFI", format_percent(stats.rfi), "rfi",
            f"{int(counters['rfi'])}/{int(counters['rfio'])}")
        add("Limp", format_percent(stats.limp), "limp")
        add("Cold call", format_percent(stats.cold_call), "cold_call")
        add("3-bet", format_percent(stats.three_bet), "three_bet",
            f"{int(counters['tb'])}/{int(counters['tbo'])}")
        add("Fold to 3-bet", format_percent(stats.fold_to_three_bet), "fold_to_three_bet",
            f"{int(counters['f3bX'])}/{int(counters['f3bF'])}")
        add("4-bets", str(stats.four_bets))
        add("Steal attempt", format_percent(stats.steal), "steal",
            f"{int(counters['ats'])}/{int(counters['atso'])}")

        rows.append(("POSTFLOP", "", "", ""))
        add("Saw flop", format_percent(stats.saw_flop), "saw_flop")
        add("C-bet flop", format_percent(stats.cbet), "cbet",
            f"{int(counters['cb'])}/{int(counters['cbo'])}")
        add("Fold to c-bet", format_percent(stats.fold_to_cbet), "fold_to_cbet",
            f"{int(counters['fcbX'])}/{int(counters['fcbF'])}")
        add("Aggression factor", format_factor(stats.aggression_factor), "aggression_factor")
        add("Aggression frequency", format_percent(stats.aggression_frequency),
            "aggression_frequency")
        add("Check-raises", str(stats.check_raises))
        add("Won when saw flop", format_percent(stats.wwsf), "wwsf")
        add("Went to showdown", format_percent(stats.wtsd), "wtsd")
        add("Won at showdown", format_percent(stats.won_showdown), "won_showdown")

        rows.append(("RESULTS", "", "", ""))
        add("Pots won", str(stats.pots_won))
        add("Net", format_money(stats.net))
        if stats.bb_per_100 is not None:
            add("Big blinds per 100", f"{stats.bb_per_100:+.1f}")

        table = self._stats_table
        table.setRowCount(len(rows))
        for index, (label, value, direction, note) in enumerate(rows):
            if not value and not note:
                header = QTableWidgetItem(label)
                header.setForeground(Qt.GlobalColor.transparent)
                item = QTableWidgetItem(label)
                item.setForeground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor(theme.ACCENT))
                font = item.font()
                font.setBold(True)
                font.setPointSizeF(font.pointSizeF() - 1)
                item.setFont(font)
                table.setItem(index, 0, item)
                table.setItem(index, 1, QTableWidgetItem(""))
                continue

            left = QTableWidgetItem(f"{label}   {note}" if note else label)
            right = QTableWidgetItem(value)
            right.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            from PySide6.QtGui import QColor

            if direction == "high":
                right.setForeground(QColor(theme.NEGATIVE))
            elif direction == "low":
                right.setForeground(QColor(theme.INFO))
            elif label == "Net":
                right.setForeground(QColor(theme.POSITIVE if stats.net >= 0 else theme.NEGATIVE))
            table.setItem(index, 0, left)
            table.setItem(index, 1, right)
        table.resizeRowsToContents()
        table.setFixedHeight(min(640, 4 + sum(table.rowHeight(r) for r in range(table.rowCount()))))

        seats = [(seat, positional(player, seat)) for seat in POSITIONS]
        seats = [(seat, values) for seat, values in seats if values]
        self._position_table.setRowCount(len(seats))
        for index, (seat, values) in enumerate(seats):
            cells = [
                seat, str(int(values["hands"])), format_percent(values["vpip"]),
                format_percent(values["pfr"]), format_percent(values["rfi"]),
                format_percent(values["limp"]), format_percent(values["cold_call"]),
                format_percent(values["three_bet"]),
            ]
            for column, text in enumerate(cells):
                self._position_table.setItem(index, column, QTableWidgetItem(text))
        self._position_table.resizeRowsToContents()
        self._position_table.setFixedHeight(
            30 + sum(self._position_table.rowHeight(r) for r in range(len(seats)))
        )

        sessions = player.sessions[-10:][::-1]
        self._session_table.setRowCount(len(sessions))
        from PySide6.QtGui import QColor

        for index, entry in enumerate(sessions):
            date = QTableWidgetItem(str(entry["t"])[:10])
            hands = QTableWidgetItem(str(int(entry["hands"])))
            result = QTableWidgetItem(format_money(entry["net"]))
            result.setForeground(QColor(theme.POSITIVE if entry["net"] >= 0 else theme.NEGATIVE))
            result.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            for column, item in enumerate((date, hands, result)):
                self._session_table.setItem(index, column, item)
        self._session_table.resizeRowsToContents()
        self._session_table.setFixedHeight(
            30 + sum(self._session_table.rowHeight(r) for r in range(len(sessions)))
        )

    # -------------------------------------------------------------- actions

    def _on_tag(self, index: int) -> None:
        self._player.tag = TAGS[index] if 0 <= index < len(TAGS) else ""
        self._store.save()
        self.changed.emit()

    def _on_note(self) -> None:
        self._player.note = self._notes.toPlainText()
        self._store.save()

    def _to_finder(self) -> None:
        _view, position, action, _size = self._panel.state()
        self.open_in_finder.emit(self._player, action, position)
        self.close()

    def _on_merge(self) -> None:
        target_id = self._merge_target.currentData()
        if target_id is None:
            return
        target = self._store.players.get(target_id)
        if target is None:
            return
        confirm = QMessageBox.question(
            self, "Merge players",
            f"Merge {self._player.name} into {target.name}?\n\n"
            "Their statistics, observed hands, and sessions are combined, and"
            f" {self._player.name} is removed.",
        )
        if confirm != QMessageBox.Yes:
            return
        self._store.merge(self._player, target)
        self._store.save()
        self.changed.emit()
        self.close()

    def _on_delete(self) -> None:
        confirm = QMessageBox.question(
            self, "Delete player",
            f"Delete {self._player.name} and all of their statistics?",
        )
        if confirm != QMessageBox.Yes:
            return
        self._store.players.pop(self._player.id, None)
        self._store.save()
        self.changed.emit()
        self.close()
