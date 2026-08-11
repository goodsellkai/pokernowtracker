from __future__ import annotations

from pokernow_tracker.cards import (
    HAND_ORDER, ORDER_BLOCKER, ORDER_CALL, ORDER_LIMP, ORDER_BASE,
    TOTAL_COMBOS, canonical, combos, grid_hands, hand_at,
)


def test_orderings_cover_every_starting_hand():
    for order in (HAND_ORDER, ORDER_CALL, ORDER_LIMP, ORDER_BLOCKER):
        assert len(order) == 169
        assert set(order) == set(ORDER_BASE)


def test_combos_sum_to_every_two_card_combination():
    assert sum(combos(hand) for hand in ORDER_BASE) == TOTAL_COMBOS


def test_percentiles_span_the_full_range():
    assert HAND_ORDER["AA"] < 1.0
    assert HAND_ORDER["72o"] == 100.0
    assert HAND_ORDER["AA"] < HAND_ORDER["KK"] < HAND_ORDER["QQ"]
    # Trash belongs at the bottom, not the middle.
    assert HAND_ORDER["32o"] > 90


def test_context_orderings_move_hands_the_intended_way():
    # Set-mining pairs and suited connectors gain value once calling.
    assert ORDER_CALL["22"] < HAND_ORDER["22"]
    assert ORDER_CALL["76s"] < HAND_ORDER["76s"]
    # Dominated offsuit broadways lose it.
    assert ORDER_CALL["KJo"] > HAND_ORDER["KJo"]
    # Speculative hands lead a limping range.
    assert ORDER_LIMP["76s"] < HAND_ORDER["76s"]
    # Blocker-heavy hands lead a polarised re-raising range.
    assert ORDER_BLOCKER["A5s"] < HAND_ORDER["A5s"]


def test_grid_layout():
    assert hand_at(0, 0) == "AA"
    assert hand_at(0, 1) == "AKs"   # suited above the diagonal
    assert hand_at(1, 0) == "AKo"   # offsuit below it
    grid = grid_hands()
    assert len(grid) == 13 and all(len(row) == 13 for row in grid)
    assert {hand for row in grid for hand in row} == set(ORDER_BASE)


def test_canonical_notation():
    assert canonical([("A", "h"), ("A", "s")]) == "AA"
    assert canonical([("K", "d"), ("A", "d")]) == "AKs"
    assert canonical([("K", "d"), ("A", "s")]) == "AKo"
    assert canonical([("A", "s")]) is None
