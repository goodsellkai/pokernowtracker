"""The range panel and the Range Finder tab."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QScrollArea, QSlider,
    QVBoxLayout, QWidget,
)

from ..ranges import ACTION_GROUPS, ANY_POSITION, SIZEABLE, TableAverages, tiers
from ..stats import classify, summarize
from ..store import POSITIONS, Player, Store
from . import theme, views
from .grid import Legend, RangeGrid
from .widgets import (
    Panel, Rule, Segmented, faint, format_percent, heading, muted, subheading,
)

POSITION_OPTIONS = [(ANY_POSITION, "Any")] + [(p, p) for p in POSITIONS]

#: Width of the controls rail beside the grid; selectors wrap to fit it.
RAIL_WIDTH = 268


class RangePanel(QWidget):
    """A range chart with its view, position, and action controls.

    Used by the Range Finder tab and by the player window, so the two always
    agree on what a range looks like.
    """

    def __init__(self, compact: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._player: Optional[Player] = None
        self._table: Optional[TableAverages] = None
        self._view = views.WEIGHTED
        self._position = ANY_POSITION
        self._action = "open"
        self._overrides: Optional[tuple[float, float, float]] = None

        controls = self._build_controls(compact)
        display = self._build_display()

        if compact:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(12)
            outer.addWidget(controls)
            outer.addWidget(display, 1)
        else:
            controls.setFixedWidth(RAIL_WIDTH)
            outer = QHBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(22)
            outer.addWidget(controls)
            outer.addWidget(display, 1)

    def _build_controls(self, compact: bool) -> QWidget:
        controls = QWidget()
        column = QVBoxLayout(controls)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)

        wrap = 0 if compact else RAIL_WIDTH
        self._views = Segmented(
            "View", views.VIEW_LABELS, self._view, vertical=not compact, wrap_width=wrap
        )
        self._views.changed.connect(self._on_view)
        column.addWidget(self._views)

        self._positions = Segmented(
            "Position", POSITION_OPTIONS, self._position, vertical=not compact,
            wrap_width=wrap,
        )
        self._positions.changed.connect(self._on_position)
        column.addWidget(self._positions)

        self._action_block = QWidget()
        actions = QVBoxLayout(self._action_block)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.addWidget(Rule())

        self._action_rows: List[Segmented] = []
        for group, options in ACTION_GROUPS:
            current = self._action if any(key == self._action for key, _ in options) else ""
            row = Segmented(
                group, list(options), current, vertical=not compact, wrap_width=wrap
            )
            row.changed.connect(self._on_action)
            actions.addWidget(row)
            self._action_rows.append(row)

        self._size_block = QWidget()
        size_column = QVBoxLayout(self._size_block)
        size_column.setContentsMargins(0, 0, 0, 0)
        size_column.setSpacing(4)
        size_column.addWidget(faint("Raise size"))
        size_row = QHBoxLayout()
        size_row.setSpacing(8)
        self._size = QDoubleSpinBox()
        self._size.setRange(0.0, 500.0)
        self._size.setSingleStep(0.5)
        self._size.setDecimals(1)
        self._size.setSpecialValueText("any")
        self._size.setSuffix(" bb")
        self._size.setFixedWidth(96)
        self._size.setToolTip("Compared against this player's own sizing history")
        self._size.valueChanged.connect(lambda _v: self.refresh())
        size_row.addWidget(self._size)
        size_row.addStretch(1)
        size_column.addLayout(size_row)
        actions.addWidget(self._size_block)
        column.addWidget(self._action_block)

        self._slider_block = QWidget()
        sliders = QVBoxLayout(self._slider_block)
        sliders.setContentsMargins(0, 0, 0, 0)
        sliders.setSpacing(6)
        sliders.addWidget(Rule())
        sliders.addWidget(faint("Adjust the cutoffs"))
        self._vpip_slider, self._vpip_value = self._make_slider("Entered", sliders)
        self._open_slider, self._open_value = self._make_slider("Raised", sliders)
        column.addWidget(self._slider_block)

        column.addStretch(1)
        return controls

    def _build_display(self) -> QWidget:
        display = QWidget()
        column = QVBoxLayout(display)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)

        self._grid = RangeGrid()
        column.addWidget(self._grid, 1)

        self._legend = Legend()
        column.addWidget(self._legend)

        self._caption = muted("")
        self._caption.setMinimumHeight(46)
        self._caption.setAlignment(Qt.AlignTop)
        column.addWidget(self._caption)
        return display

    def _make_slider(self, label: str, parent_layout) -> tuple[QSlider, QLabel]:
        row = QHBoxLayout()
        row.setSpacing(8)
        caption = QLabel(label)
        caption.setObjectName("Faint")
        caption.setFixedWidth(52)
        row.addWidget(caption)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.valueChanged.connect(self._on_slider)
        row.addWidget(slider, 1)
        value = QLabel("0%")
        value.setFixedWidth(38)
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(value)
        parent_layout.addLayout(row)
        return slider, value

    # --------------------------------------------------------------- wiring

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
        self._action_block.setVisible(weighted)
        self._size_block.setVisible(weighted and self._action in SIZEABLE)
        self._slider_block.setVisible(self._view == views.ESTIMATED)

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
        column.setContentsMargins(18, 16, 18, 16)
        column.setSpacing(12)

        panel = Panel()
        header = QHBoxLayout()
        header.setSpacing(12)
        self._picker = QComboBox()
        self._picker.setMinimumWidth(230)
        self._picker.currentIndexChanged.connect(self._on_pick)
        header.addWidget(self._picker)
        self._summary = faint("", wrap=False)
        header.addWidget(self._summary)
        header.addStretch(1)
        panel.add_layout(header)
        panel.add(Rule())

        self._panel = RangePanel()
        panel.add(self._panel)
        column.addWidget(panel, 1)

        self._empty = muted("No players yet. Import a hand history from the Import tab.")
        column.addWidget(self._empty)

    def reload(self) -> None:
        previous = self._picker.currentData()
        self._players = sorted(
            self._store.players.values(), key=lambda p: -p.counters["hands"]
        )
        self._picker.blockSignals(True)
        self._picker.clear()
        for player in self._players:
            self._picker.addItem(
                f"{player.name}   {int(player.counters['hands'])} hands", player.id
            )
        self._picker.blockSignals(False)

        has_players = bool(self._players)
        self._empty.setVisible(not has_players)
        self._picker.setVisible(has_players)
        self._summary.setVisible(has_players)
        self._panel.setVisible(has_players)

        if has_players:
            index = next(
                (i for i, p in enumerate(self._players) if p.id == previous), 0
            )
            self._picker.setCurrentIndex(index)
            self._on_pick(index)

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
        if not self._players or not 0 <= index < len(self._players):
            return
        player = self._players[index]
        stats = summarize(player)
        self._summary.setText(
            f"{classify(player)}     VPIP {format_percent(stats.vpip)}"
            f"     RFI {format_percent(stats.rfi)}"
            f"     3-bet {format_percent(stats.three_bet)}"
        )
        self._panel.set_player(player, TableAverages(list(self._store.players.values())))
