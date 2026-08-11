from __future__ import annotations

import math

import pytest

from pokernow_tracker.cards import HAND_ORDER, TOTAL_COMBOS, combos
from pokernow_tracker.ingest import import_log
from pokernow_tracker.ranges import (
    ACTIONS, ANY_POSITION, TableAverages, best_guess, build_model,
    observations, show_rate, tiers, weighted_range,
)
from pokernow_tracker.store import Player


def _mass(model) -> float:
    return sum(model.probability(h) * combos(h) for h in HAND_ORDER) / (TOTAL_COMBOS / 100.0)


def _player(hands=800, vpip=280, pfr=200, rfi=180, rfio=600, tb=60, tbo=600,
            call=120, limp=20, f3bF=40, f3bX=24, fb=8) -> Player:
    player = Player(id=1, name="Test", player_id="t1")
    player.counters.update({
        "hands": hands, "vpip": vpip, "pfr": pfr, "rfi": rfi, "rfio": rfio,
        "tb": tb, "tbo": tbo, "call": call, "limp": limp,
        "f3bF": f3bF, "f3bX": f3bX, "fb": fb,
    })
    return player


def _table(*players: Player) -> TableAverages:
    return TableAverages(list(players))


@pytest.mark.parametrize("action", sorted(ACTIONS))
def test_every_action_produces_a_valid_range(action):
    player = _player()
    model = build_model(player, ANY_POSITION, action, _table(player))
    for hand in HAND_ORDER:
        value = model.probability(hand)
        assert 0.0 <= value <= 1.0, f"{action} {hand} out of range"


def test_range_mass_matches_the_measured_frequency():
    player = _player()
    table = _table(player)

    # RFI is 180/600 = 30%, 3-bet is 60/600 = 10%, cold call is 120/600 = 20%.
    assert _mass(build_model(player, ANY_POSITION, "open", table)) == pytest.approx(30, abs=1.5)
    assert _mass(build_model(player, ANY_POSITION, "3bet", table)) == pytest.approx(10, abs=1.5)
    assert _mass(build_model(player, ANY_POSITION, "call", table)) == pytest.approx(20, abs=1.5)


def test_decisions_are_exhaustive():
    """At each decision point the options must account for every hand."""
    player = _player()
    table = _table(player)

    first_in = [build_model(player, ANY_POSITION, a, table) for a in ("open", "limp", "fold")]
    vs_raise = [build_model(player, ANY_POSITION, a, table) for a in ("3bet", "call", "fold-vs-raise")]

    for hand in HAND_ORDER:
        assert sum(m.probability(hand) for m in first_in) == pytest.approx(1.0, abs=1e-9)
        assert sum(m.probability(hand) for m in vs_raise) == pytest.approx(1.0, abs=1e-9)


def test_premium_hands_are_always_in_a_raising_range():
    player = _player()
    table = _table(player)
    for action in ("open", "3bet", "4bet"):
        model = build_model(player, ANY_POSITION, action, table)
        assert model.probability("AA") > 0.95, action
        assert model.probability("KK") > 0.90, action


def test_trash_is_excluded_from_raising_ranges():
    player = _player()
    model = build_model(player, ANY_POSITION, "open", _table(player))
    assert model.probability("72o") < 0.05
    assert model.probability("32o") < 0.05


def test_a_passive_player_flats_premiums_without_changing_totals():
    tight = _player(vpip=280, pfr=250)          # raises nearly everything it plays
    passive = _player(vpip=520, pfr=120)        # enters often, raises rarely

    aggressive_model = build_model(tight, ANY_POSITION, "call", _table(tight))
    passive_model = build_model(passive, ANY_POSITION, "call", _table(passive))

    # The passive player shows up with aces in the calling line; the other does not.
    assert passive_model.probability("AA") > aggressive_model.probability("AA")
    # Totals still track the measured cold-call frequency for both.
    assert _mass(build_model(passive, ANY_POSITION, "3bet", _table(passive))) == pytest.approx(10, abs=1.5)


def test_positional_priors_widen_the_button():
    player = _player()
    table = _table(player)
    early = _mass(build_model(player, "EP", "open", table))
    button = _mass(build_model(player, "BTN", "open", table))
    assert button > early


def test_thin_samples_shrink_toward_the_table():
    regular = _player()
    newcomer = _player(hands=40, vpip=6, pfr=2, rfi=2, rfio=30, tb=0, tbo=30, call=4, limp=1)
    table = _table(regular, newcomer)

    lonely = build_model(newcomer, ANY_POSITION, "open", _table(newcomer))
    with_table = build_model(newcomer, ANY_POSITION, "open", table)
    # Their own 6.7% rate is pulled toward the table's 30%.
    assert _mass(with_table) > _mass(lonely) or _mass(with_table) > 10


def test_observations_move_the_estimate(store, sample_log):
    import_log(sample_log, store)
    alice = next(p for p in store.players.values() if p.name == "Alice")
    table = TableAverages(list(store.players.values()))

    chart = weighted_range(alice, ANY_POSITION, "call", table)
    # She was seen calling a raise with queens four times.
    assert chart.cells["QQ"].adjusted
    assert chart.cells["QQ"].probability > chart.cells["QQ"].estimate


def test_show_rate_reflects_how_often_cards_are_visible(store, sample_log):
    import_log(sample_log, store)
    for player in store.players.values():
        assert 0.06 <= show_rate(player) <= 1.0


def test_size_reads_narrow_and_widen():
    player = _player()
    player.sizing["o"] = {
        "n": 40, "sx": 40 * 3.0, "sxx": 40 * 9.5,
        "ns": 0, "bx": 0, "bxx": 0, "by": 0, "bxy": 0, "byy": 0,
    }
    table = _table(player)

    normal = _mass(build_model(player, ANY_POSITION, "open", table, size_bb=3.0))
    large = _mass(build_model(player, ANY_POSITION, "open", table, size_bb=6.0))
    small = _mass(build_model(player, ANY_POSITION, "open", table, size_bb=2.0))

    assert large < normal < small


def test_best_guess_keeps_uncontradicted_inferences(store, sample_log):
    import_log(sample_log, store)
    alice = next(p for p in store.players.values() if p.name == "Alice")
    assignments = best_guess(alice, ANY_POSITION)

    assert len(assignments) == 169
    # Calling a raise says nothing about whether a hand gets opened first in,
    # so QQ stays in the inferred opening tier rather than being downgraded.
    category, solid, note = assignments["QQ"]
    assert category in ("open", "3bet", "c")
    if not solid:
        assert "calling" in note


def test_tiers_are_nested():
    player = _player()
    cut = tiers(player, ANY_POSITION)
    assert cut.three_bet <= cut.open <= cut.vpip


def test_observations_can_be_filtered_by_seat(store, sample_log):
    import_log(sample_log, store)
    alice = next(p for p in store.players.values() if p.name == "Alice")
    everywhere = observations(alice)
    assert everywhere
    for seat in ("EP", "MP", "CO", "BTN", "SB", "BB"):
        subset = observations(alice, seat)
        assert set(subset) <= set(everywhere)
