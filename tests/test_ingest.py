from __future__ import annotations

from conftest import (
    SyntheticHand, WITHOUT_ALICE, build_log, hand_without_alice,
    showdown_hand, simple_hand,
)

from pokernow_tracker.ingest import import_log, rebuild
from pokernow_tracker.logparse import detect_hero, read_hands
from pokernow_tracker.stats import summarize


def test_hands_are_read_in_chronological_order(sample_log):
    hands = read_hands(sample_log)
    assert len(hands) == 10
    assert hands[0].id == "hand0000"
    assert hands[-1].id == "hand0009"
    assert all(hand.is_complete for hand in hands)


def test_money_balances_across_the_table(sample_log, store):
    import_log(sample_log, store)
    total = sum(player.counters["net"] for player in store.players.values())
    assert abs(total) < 1e-6


def test_opportunities_are_counted_not_assumed(sample_log, store):
    import_log(sample_log, store)
    alice = next(p for p in store.players.values() if p.name == "Alice")

    # Alice raised first in on six hands and called a raise on four.
    assert alice.counters["hands"] == 10
    assert alice.counters["rfi"] == 6
    assert alice.counters["vpip"] == 10
    # A 3-bet chance only exists when someone raised ahead of her.
    assert alice.counters["tbo"] == 4
    assert alice.counters["tb"] == 0


def test_hands_without_a_winner_are_skipped(store):
    truncated = simple_hand()[:-1]  # drop the line awarding the pot
    import_log(build_log([truncated]), store)
    assert not store.players


def test_heads_up_hands_are_excluded(store):
    import csv, io

    log = build_log([simple_hand()])
    rows = list(csv.reader(io.StringIO(log)))
    for row in rows:
        if row and row[0].startswith("Player stacks:"):
            row[0] = 'Player stacks: #1 "Alice @ a1" (100.00) | #2 "Bob @ b1" (100.00)'
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)

    import_log(buffer.getvalue(), store)
    assert not store.players


def test_showdown_cards_are_recorded_with_their_action(sample_log, store):
    import_log(sample_log, store)
    alice = next(p for p in store.players.values() if p.name == "Alice")
    # She called a raise with queens four times, so QQ is filed under "call".
    # Sightings are kept per seat, and the button moves between hands.
    assert "QQ" in alice.observed
    by_category: dict[str, int] = {}
    for counts in alice.observed["QQ"].values():
        for category, count in counts.items():
            by_category[category] = by_category.get(category, 0) + count
    assert by_category == {"c": 4}


def test_reimporting_the_same_log_changes_nothing(sample_log, store):
    first = import_log(sample_log, store)
    before = {p.name: dict(p.counters) for p in store.players.values()}

    second = import_log(sample_log, store)
    after = {p.name: dict(p.counters) for p in store.players.values()}

    assert first.hands == 10
    assert second.hands == 0
    assert second.duplicates == 10
    assert before == after


def test_hero_detection_finds_the_exporting_account(store):
    # An export carries its owner's hole cards on every hand they were dealt,
    # and only on those, which is what identifies them.
    hands = [SyntheticHand(hand_without_alice(), seats=WITHOUT_ALICE) for _ in range(3)]
    hands += [SyntheticHand(simple_hand(), hero="A♠, K♠") for _ in range(5)]
    log = build_log(hands)

    assert detect_hero(read_hands(log)) == "a1"

    # Those cards feed the owner's observed range even without a showdown,
    # which is why their own chart is far more complete than anyone else's.
    import_log(log, store)
    alice = next(p for p in store.players.values() if p.name == "Alice")
    assert "AKs" in alice.observed
    assert sum(sum(c.values()) for c in alice.observed["AKs"].values()) == 5


def test_hero_stays_unidentified_when_ambiguous():
    # Everyone played every hand, so nothing distinguishes the owner.
    log = build_log([SyntheticHand(simple_hand(), hero="A♠, K♠") for _ in range(4)])
    assert detect_hero(read_hands(log)) is None


def test_rebuild_reproduces_the_same_numbers(sample_log, store, tmp_path):
    path = tmp_path / "session.csv"
    path.write_text(sample_log, encoding="utf-8")

    from pokernow_tracker.ingest import import_file

    import_file(path, store)
    before = {p.name: dict(p.counters) for p in store.players.values()}

    assert rebuild(store) == 1
    after = {p.name: dict(p.counters) for p in store.players.values()}
    assert before == after


def test_statistics_are_ratios_of_real_opportunities(sample_log, store):
    import_log(sample_log, store)
    dan = next(p for p in store.players.values() if p.name == "Dan")
    stats = summarize(dan)
    # Dan folded first in six times and raised first in four.
    assert stats.rfi is not None and 30 < stats.rfi < 50
    assert stats.hands == 10
