from __future__ import annotations

from pathlib import Path

import pytest

from conftest import build_log, showdown_hand, simple_hand
from pokernow_tracker.ingest import import_log

pytest.importorskip("PySide6", reason="the desktop interface is an optional extra")

from pokernow_tracker.ranges import ACTIONS, ANY_POSITION, TableAverages  # noqa: E402
from pokernow_tracker.ui import theme, views  # noqa: E402
from pokernow_tracker.ui.grid import RangeGrid  # noqa: E402


@pytest.fixture
def populated(store):
    log = build_log([simple_hand() for _ in range(6)] + [showdown_hand() for _ in range(4)])
    import_log(log, store)
    return store


def _player(store, name="Alice"):
    return next(p for p in store.players.values() if p.name == name)


def test_every_view_produces_a_full_grid(app, populated):
    player = _player(populated)
    table = TableAverages(list(populated.players.values()))

    builders = [
        lambda: views.weighted_cells(player, ANY_POSITION, "open", table)[0],
        lambda: views.best_guess_cells(player, ANY_POSITION)[0],
        lambda: views.estimated_cells(player, ANY_POSITION)[0],
        lambda: views.observed_cells(player, ANY_POSITION)[0],
    ]
    for build in builders:
        cells = build()
        assert len(cells) == 169
        assert len({cell.hand for cell in cells}) == 169
        for cell in cells:
            assert cell.colour.isValid()


@pytest.mark.parametrize("action", sorted(ACTIONS))
def test_weighted_view_covers_every_action(app, populated, action):
    player = _player(populated)
    table = TableAverages(list(populated.players.values()))
    cells, caption, legend = views.weighted_cells(player, ANY_POSITION, action, table)
    assert len(cells) == 169
    assert caption and legend


def test_grid_maps_clicks_to_the_right_hand(app, populated):
    grid = RangeGrid()
    grid.resize(440, 440)
    table = TableAverages(list(populated.players.values()))
    grid.set_cells(views.weighted_cells(_player(populated), ANY_POSITION, "open", table)[0])

    left, top, step = grid._metrics()
    # Top left is the strongest pair, and the diagonal holds the other pairs.
    assert grid._hand_at(left + step / 2, top + step / 2) == "AA"
    assert grid._hand_at(left + step * 1.5, top + step * 1.5) == "KK"
    # Above the diagonal is suited, below is offsuit.
    assert grid._hand_at(left + step * 1.5, top + step * 0.5) == "AKs"
    assert grid._hand_at(left + step * 0.5, top + step * 1.5) == "AKo"
    # Outside the grid maps to nothing.
    assert grid._hand_at(left - 40, top + step) is None


def test_grid_renders_without_error(app, populated):
    grid = RangeGrid()
    grid.resize(500, 500)
    table = TableAverages(list(populated.players.values()))
    grid.set_cells(views.weighted_cells(_player(populated), ANY_POSITION, "open", table)[0])
    assert not grid.grab().isNull()


def test_window_builds_and_switches_tabs(app, populated):
    from pokernow_tracker.ui.window import MainWindow

    window = MainWindow(populated)
    window.resize(1100, 780)
    assert window._tabs.count() == 4
    for index in range(window._tabs.count()):
        window._tabs.setCurrentIndex(index)
        assert not window.grab().isNull()
    window.close()


def test_player_detail_builds(app, populated):
    from pokernow_tracker.ui.detail import PlayerDetail

    dialog = PlayerDetail(_player(populated), populated)
    assert dialog._stats_table.rowCount() > 10
    assert not dialog.grab().isNull()
    dialog.close()


def test_theme_colours_are_defined_for_every_action(app):
    from pokernow_tracker.ranges import CATEGORY_LABELS

    for category in CATEGORY_LABELS:
        assert category in theme.ACTION_COLOUR, category
    for action in ACTIONS:
        assert action in theme.ACTION_HUE, action


def test_data_folder_can_be_moved_from_the_app(app, populated, tmp_path, monkeypatch):
    from pokernow_tracker import store as store_module
    from pokernow_tracker.ui.window import MainWindow

    settings = tmp_path / "settings.json"
    monkeypatch.setattr(store_module, "SETTINGS_PATH", settings)

    window = MainWindow(populated)
    destination = tmp_path / "elsewhere"
    destination.mkdir()

    window._use_folder(destination)

    assert window._store.dir == destination
    # Every tab follows the move, so nothing keeps writing to the old folder.
    for tab in (window._import, window._players, window._finder, window._data):
        assert tab._store is window._store
    assert store_module.load_settings() == {}  # _use_folder does not itself persist
    window.close()


def test_remembered_folder_is_used_next_time(tmp_path, monkeypatch):
    from pokernow_tracker import store as store_module

    monkeypatch.delenv("POKERNOW_TRACKER_HOME", raising=False)
    monkeypatch.setattr(store_module, "SETTINGS_PATH", tmp_path / "settings.json")

    store_module.remember_data_dir(tmp_path / "chosen")
    assert store_module.default_data_dir() == tmp_path / "chosen"

    store_module.remember_data_dir(None)
    assert store_module.default_data_dir() == Path.home() / ".pokernow-tracker"


def test_every_gap_comes_from_the_spacing_scale():
    """Spacing is a small fixed scale, not a value chosen per widget."""
    import re

    from pokernow_tracker.ui import theme

    scale = {theme.TIGHT, theme.SNUG, theme.GAP, theme.STEP, theme.WIDE, theme.ROOMY}
    # A couple of half-steps are deliberate: a control's own parts sit closer
    # together than the controls themselves do.
    allowed = scale | {theme.TIGHT + 1, theme.TIGHT + 2, 0}

    root = Path(__file__).resolve().parent.parent / "pokernow_tracker" / "ui"
    offenders = []
    for path in root.glob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            found = re.search(r"\.setSpacing\((\d+)\)", line)
            if found and int(found.group(1)) not in allowed:
                offenders.append(f"{path.name}:{number} {line.strip()}")
    assert not offenders, "spacing outside the scale: " + "; ".join(offenders)


def test_the_main_window_fits_on_a_small_display(app, populated):
    from pokernow_tracker.ui.window import MainWindow

    window = MainWindow(populated)
    # A 1366x768 laptop is the floor worth supporting. The tall Range Finder
    # scrolls rather than forcing a window bigger than the screen.
    assert window.minimumSizeHint().height() <= 700
    assert window.minimumSizeHint().width() <= 1300
    window.close()


def test_a_player_window_fits_on_a_small_display(app, populated):
    from pokernow_tracker.ui.detail import PlayerDetail

    player = next(iter(populated.players.values()))
    detail = PlayerDetail(player, populated)
    assert detail.minimumSizeHint().height() <= 700
    detail.close()
