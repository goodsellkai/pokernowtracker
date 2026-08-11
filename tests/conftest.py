"""Shared fixtures: a synthetic hand-history export in PokerNow's format."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import pytest

SEATS = [("Alice", "a1"), ("Bob", "b1"), ("Cara", "c1"), ("Dan", "d1")]
WITHOUT_ALICE = SEATS[1:]


@dataclass
class SyntheticHand:
    """One hand: its action lines, who was dealt in, and the owner's cards."""

    actions: List[str]
    seats: Sequence[tuple[str, str]] = tuple(SEATS)
    hero: Optional[str] = None


def _stacks(seats: Sequence[tuple[str, str]]) -> str:
    parts = [f'#{i + 1} "{n} @ {p}" (100.00)' for i, (n, p) in enumerate(seats)]
    return "Player stacks: " + " | ".join(parts)


def build_log(hands: Sequence, dealer_index: int = 0) -> str:
    """Wrap hands into a full export, newest first as PokerNow writes them."""
    rows: List[tuple[str, str, int]] = []
    order = 1000

    for index, raw in enumerate(hands):
        hand = raw if isinstance(raw, SyntheticHand) else SyntheticHand(list(raw))
        seats = list(hand.seats)
        dealer = seats[(dealer_index + index) % len(seats)]
        stamp = f"2026-01-0{index % 9 + 1}T00:00:0"

        rows.append((
            f'-- starting hand #{index + 1} (id: hand{index:04d})  '
            f'No Limit Texas Hold\'em (dealer: "{dealer[0]} @ {dealer[1]}") --',
            stamp + "0.000Z", order,
        ))
        order += 1
        rows.append((_stacks(seats), stamp + "0.000Z", order))
        order += 1
        if hand.hero:
            rows.append((f"Your hand is {hand.hero}", stamp + "0.000Z", order))
            order += 1
        for line in hand.actions:
            rows.append((line, stamp + "1.000Z", order))
            order += 1
        rows.append((f"-- ending hand #{index + 1} --", stamp + "2.000Z", order))
        order += 1

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["entry", "at", "order"])
    for entry, at, seq in reversed(rows):  # exports run newest first
        writer.writerow([entry, at, seq])
    return buffer.getvalue()


def simple_hand() -> List[str]:
    """A raise, a call, two folds, and a flop the raiser takes down."""
    return [
        '"Bob @ b1" posts a small blind of 0.50',
        '"Cara @ c1" posts a big blind of 1.00',
        '"Dan @ d1" folds',
        '"Alice @ a1" raises to 3.00',
        '"Bob @ b1" folds',
        '"Cara @ c1" calls 3.00',
        "Flop:  [7♥, 2♠, K♣]",
        '"Cara @ c1" checks',
        '"Alice @ a1" bets 4.00',
        '"Cara @ c1" folds',
        'Uncalled bet of 4.00 returned to "Alice @ a1"',
        '"Alice @ a1" collected 6.50 from pot',
    ]


def showdown_hand() -> List[str]:
    """A hand that reaches showdown, so hole cards become visible."""
    return [
        '"Bob @ b1" posts a small blind of 0.50',
        '"Cara @ c1" posts a big blind of 1.00',
        '"Dan @ d1" raises to 3.00',
        '"Alice @ a1" calls 3.00',
        '"Bob @ b1" folds',
        '"Cara @ c1" folds',
        "Flop:  [7♥, 2♠, K♣]",
        '"Dan @ d1" bets 3.00',
        '"Alice @ a1" calls 3.00',
        "Turn: 7♥, 2♠, K♣ [9♦]",
        '"Dan @ d1" checks',
        '"Alice @ a1" checks',
        "River: 7♥, 2♠, K♣, 9♦ [3♣]",
        '"Dan @ d1" checks',
        '"Alice @ a1" checks',
        '"Dan @ d1" shows a A♥, K♦.',
        '"Alice @ a1" shows a Q♠, Q♣.',
        '"Alice @ a1" collected 13.50 from pot with Pair, Q\'s',
    ]


def hand_without_alice() -> List[str]:
    """Three-handed action, used for hands the log's owner sat out."""
    return [
        '"Cara @ c1" posts a small blind of 0.50',
        '"Dan @ d1" posts a big blind of 1.00',
        '"Bob @ b1" raises to 3.00',
        '"Cara @ c1" folds',
        '"Dan @ d1" folds',
        'Uncalled bet of 2.00 returned to "Bob @ b1"',
        '"Bob @ b1" collected 2.50 from pot',
    ]


@pytest.fixture
def sample_log() -> str:
    hands = [simple_hand() for _ in range(6)] + [showdown_hand() for _ in range(4)]
    return build_log(hands)


@pytest.fixture
def store(tmp_path):
    from pokernow_tracker.store import Store

    return Store(tmp_path / "data")
