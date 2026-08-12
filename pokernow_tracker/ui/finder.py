"""The range panel and the Range Finder tab."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget,
)

from ..ranges import ACTION_GROUPS, ACTIONS, ANY_POSITION, SIZEABLE, TableAverages, tiers
from ..stats import classify
from ..store import POSITIONS, Player, Store
from . import theme, views
from .grid import Legend, RangeGrid
from .widgets import Card, ChipRow, dim, format_percent, section

POSITION_OPTIONS = [(ANY_POSITION, "Any")] + [(p, p) for p in POSITIONS]


class RangePanel(QWidget):
    """Range chart with its view, position, and action controls.

    Used both as the Range Finder tab's body and inside a player's detail
    window, so the two always agree.
    """

    def __init__(self, compact: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._player: Optional[Player] = None
        self._table: Optional[TableAverages] = None
        self._view = views.WEIGHTED
        self._position = ANY_POSITION
        self._action = "open"
        self._overrides: Optional[tuple[float, float, float]] = None

        # Controls sit beside the grid when there is room, and above it when the
        # panel is embedded somewhere narrow.
        controls = QWidget()
        column = QVBoxLayout(controls)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)

        self._views = ChipRow("View", views.VIEW_LABELS, self._view, label_width=58)
        self._views.changed.connect(self._on_view)
        column.addWidget(self._views)

        self._positions = ChipRow("Position", POSITION_OPTIONS, self._position, label_width=58)
        self._positions.changed.connect(self._on_position)
        column.addWidget(self._positions)

        self._action_rows: List[ChipRow] = []
        for group, actions in ACTION_GROUPS:
            row = ChipRow(group, list(actions), self._action if any(
                key == self._action for key, _ in actions) else "", label_width=96)
            row.changed.connect(self._on_action)
            column.addWidget(row)
            self._action_rows.append(row)

        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        self._size_label = QLabel("Raise size")
        self._size_label.setObjectName("Dim")
        self._size_label.setFixedWidth(96 if not compact else 58)
        size_row.addWidget(self._size_label)
        self._size = QDoubleSpinBox()
        self._size.setRange(0.0, 500.0)
        self._size.setSingleStep(0.5)
        self._size.setDecimals(1)
        self._size.setSpecialValueText("any")
        self._size.setSuffix(" bb")
        self._size.setFixedWidth(90)
        self._size.valueChanged.connect(lambda _v: self.refresh())
        size_row.addWidget(self._size)
        self._size_hint = dim("Optional. Compared against their own sizing history.", wrap=False)
        size_row.addWidget(self._size_hint)
        size_row.addStretch(1)
        self._size_widget = QWidget()
        self._size_widget.setLayout(size_row)
        column.addWidget(self._size_widget)

        # Sliders, shown only for the estimated view.
        self._slider_widget = QWidget()
        sliders = QVBoxLayout(self._slider_widget)
        sliders.setContentsMargins(0, 0, 0, 0)
        sliders.setSpacing(4)
        self._vpip_slider, self._vpip_value = self._make_slider("Entered", sliders)
        self._open_slider, self._open_value = self._make_slider("Raised", sliders)
        column.addWidget(self._slider_widget)

        column.addStretch(1)

        display = QWidget()
        right = QVBoxLayout(display)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(8)

        self._grid = RangeGrid()
        right.addWidget(self._grid, 1)

        self._legend = Legend()
        right.addWidget(self._legend)

        self._caption = dim("")
        right.addWidget(self._caption)

        if compact:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(10)
            outer.addWidget(controls)
            outer.addWidget(display, 1)
        else:
            controls.setFixedWidth(470)
            outer = QHBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(24)
            outer.addWidget(controls)
            outer.addWidget(display, 1)

    def _make_slider(self, label: str, parent_layout) -> tuple[QSlider, QLabel]:
        row = QHBoxLayout()
        row.setSpacing(8)
        caption = QLabel(label)
        caption.setObjectName("Dim")
        caption.setFixedWidth(58)
        row.addWidget(caption)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.valueChanged.connect(self._on_slider)
        row.addWidget(slider, 1)
        value = QLabel("0%")
        value.setFixedWidth(42)
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(value)
        parent_layout.addLayout(row)
        return slider, value

    # -------------------------------------------------------------- wiring

    def set_player(self, player: Player, table: TableAverages) -> None:
        self._player = player
        self._table = table
        self._overrides = None
        self._sync_sliders()
        self.refresh()

    def set_action(self, action: str) -> None:
        self._action = action
        for row in self._action_rows:
            row.set_current(action)
        self.refresh()

    def set_position(self, position: str) -> None:
        self._position = position
        self._positions.set_current(position)
        self.refresh()

    def state(self) -> tuple[str, str, str, float]:
        return self._view, self._position, self._action, self._size.value()

    def _on_view(self, view: str) -> None:
        self._view = view
        self._views.set_current(view)
        self._overrides = None
        self._sync_sliders()
        self.refresh()

    def _on_position(self, position: str) -> None:
        self._position = position
        self._positions.set_current(position)
        self._overrides = None
        self._sync_sliders()
        self.refresh()

    def _on_action(self, action: str) -> None:
        self._action = action
        for row in self._action_rows:
            if row.current() != action:
                row.set_current("")
        self.refresh()

    def _on_slider(self) -> None:
        if self._view != views.ESTIMATED or self._player is None:
            return
        vpip = float(self._vpip_slider.value())
        open_pct = min(float(self._open_slider.value()), vpip)
        cut = tiers(self._player, self._position)
        self._overrides = (vpip, open_pct, min(cut.three_bet, open_pct))
        self._vpip_value.setText(f"{vpip:.0f}%")
        self._open_value.setText(f"{open_pct:.0f}%")
        self.refresh()

    def _sync_sliders(self) -> None:
        if self._player is None:
            return
        cut = tiers(self._player, self._position)
        for slider, value, amount in (
            (self._vpip_slider, self._vpip_value, cut.vpip),
            (self._open_slider, self._open_value, cut.open),
        ):
            slider.blockSignals(True)
            slider.setValue(int(round(amount)))
            slider.blockSignals(False)
            value.setText(f"{amount:.0f}%")

    # ------------------------------------------------------------ rendering

    def refresh(self) -> None:
        weighted = self._view == views.WEIGHTED
        for row in self._action_rows:
            row.setVisible(weighted)
        self._size_widget.setVisible(weighted and self._action in SIZEABLE)
        self._slider_widget.setVisible(self._view == views.ESTIMATED)

        if self._player is None or self._table is None:
            self._grid.clear()
            self._caption.setText("")
            return

        if weighted:
            cells, caption, legend = views.weighted_cells(
                self._player, self._position, self._action, self._table, self._size.value()
            )
        elif self._view == views.BEST:
            cells, caption, legend = views.best_guess_cells(self._player, self._position)
        elif self._view == views.ESTIMATED:
            cells, caption, legend = views.estimated_cells(
                self._player, self._position, self._overrides
            )
        else:
            cells, caption, legend = views.observed_cells(self._player, self._position)

        self._grid.set_cells(cells)
        self._legend.set_entries(legend)
        self._caption.setText(caption)


class RangeFinderTab(QWidget):
    """Pick a player, a seat, and an action, and see what they are likely holding."""

    def __init__(self, store: Store, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._store = store
        self._players: List[Player] = []

        column = QVBoxLayout(self)
        column.setContentsMargins(16, 14, 16, 14)
        column.setSpacing(12)

        card = Card()
        header = QHBoxLayout()
        header.setSpacing(10)
        self._picker = QComboBox()
        self._picker.setMinimumWidth(220)
        self._picker.currentIndexChanged.connect(self._on_pick)
        header.addWidget(self._picker)
        self._summary = dim("", wrap=False)
        header.addWidget(self._summary)
        header.addStretch(1)
        card.add_layout(header)

        self._panel = RangePanel()
        card.add(self._panel)
        column.addWidget(card, 1)

        self._empty = dim("No players yet. Import a hand history to get started.")
        column.addWidget(self._empty)

    def reload(self) -> None:
        self._players = sorted(
            self._store.players.values(), key=lambda p: -p.counters["hands"]
        )
        self._picker.blockSignals(True)
        self._picker.clear()
        for player in self._players:
            self._picker.addItem(f"{player.name}  ({int(player.counters['hands'])} hands)", player.id)
        self._picker.blockSignals(False)

        has_players = bool(self._players)
        self._empty.setVisible(not has_players)
        self._picker.setVisible(has_players)
        self._summary.setVisible(has_players)
        self._panel.setVisible(has_players)
        if has_players:
            self._on_pick(0)

    def show_player(self, player: Player, action: str = "", position: str = "") -> None:
        for index, candidate in enumerate(self._players):
            if candidate.id == player.id:
                self._picker.setCurrentIndex(index)
                break
        if position:
            self._panel.set_position(position)
        if action:
            self._panel.set_action(action)

    def _on_pick(self, index: int) -> None:
        if not self._players or index < 0 or index >= len(self._players):
            return
        player = self._players[index]
        from ..stats import summarize

        stats = summarize(player)
        self._summary.setText(
            f"{classify(player)}   ·   VPIP {format_percent(stats.vpip)}"
            f"   ·   RFI {format_percent(stats.rfi)}"
            f"   ·   3-bet {format_percent(stats.three_bet)}"
        )
        table = TableAverages(list(self._store.players.values()))
        self._panel.set_player(player, table)
