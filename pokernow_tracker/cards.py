"""Starting-hand notation, strength orderings, and 13x13 grid layout.

A starting hand is written in the usual shorthand: ``AA`` for a pair, ``AKs``
for suited, ``AKo`` for offsuit. There are 169 such hands covering all 1326
two-card combinations.

Each ordering maps a hand to the percentile at which it enters a range built
top-down from that ordering. ``HAND_ORDER["AA"]`` is about 0.45, meaning AA is
inside any range wider than 0.45% of hands; ``HAND_ORDER["72o"]`` is 100.0.
Ranges are therefore expressed as a single cutoff percentage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

RANKS = "AKQJT98765432"
RANK_VALUE: Dict[str, int] = {r: v for r, v in zip(RANKS, range(14, 1, -1))}

TOTAL_COMBOS = 1326

# Hand-tuned strength order, strongest first. Used as the spine for every
# ordering below; the context orderings reweight it rather than replace it.
_ORDER_SOURCE = """
AA KK QQ JJ AKs AQs TT AKo AJs KQs 99 ATs AQo KJs QJs KTs 88 AJo JTs QTs
A9s KQo 77 ATo A8s K9s T9s A5s 66 A7s Q9s J9s A4s KJo A6s QJo A3s 55 K8s JTo
98s T8s A2s K7s Q8s KTo 44 J8s 87s QTo A9o K6s 97s T7s 33 K5s 76s 22 Q7s 86s
K4s A8o J7s 65s 96s T9o K3s Q6s 75s A7o K2s 54s Q5s 64s 85s T6s J6s A5o Q4s 95s
T8o J9o A6o K9o J5s Q3s 53s 63s 84s 74s J4s A4o Q2s 43s 98o K8o J3s T5s A3o 94s
Q9o T4s J2s 87o K7o 52s 42s A2o 73s 93s T3s J8o 83s 62s Q8o K6o T2s 97o 32s 76o
92s K5o T7o 82s 65o J7o Q7o K4o 72s 54o 86o K3o 96o Q6o 64o K2o Q5o 75o 85o J6o
Q4o 53o T6o J5o 43o Q3o 63o 74o J4o T5o 95o Q2o J3o 84o T4o 52o 94o J2o 42o T3o
73o 93o T2o 62o 83o 32o 92o 82o 72o
"""

ORDER_BASE = _ORDER_SOURCE.split()


def combos(hand: str) -> int:
    """Number of two-card combinations a hand represents."""
    if len(hand) == 2:
        return 6
    return 4 if hand.endswith("s") else 12


@dataclass(frozen=True)
class HandClass:
    """Structural facts about a hand, used to reweight the base ordering."""

    pair: bool
    suited: bool
    high: int
    low: int

    @property
    def small_pair(self) -> bool:
        return self.pair and self.high <= 8

    @property
    def suited_ace(self) -> bool:
        return self.suited and self.high == 14

    @property
    def wheel_ace_suited(self) -> bool:
        return self.suited and self.high == 14 and self.low <= 5

    @property
    def suited_connector(self) -> bool:
        return self.suited and (self.high - self.low) <= 2 and self.high <= 11 and self.low >= 4

    @property
    def offsuit_broadway(self) -> bool:
        return not self.suited and not self.pair and self.high >= 10 and self.low >= 10

    @property
    def offsuit_ace(self) -> bool:
        return not self.suited and not self.pair and self.high == 14


def classify_hand(hand: str) -> HandClass:
    pair = len(hand) == 2
    suited = not pair and hand[2] == "s"
    return HandClass(pair, suited, RANK_VALUE[hand[0]], RANK_VALUE[hand[1]])


def build_order(weight: Optional[Callable[[HandClass], float]] = None) -> Dict[str, float]:
    """Build a hand -> inclusion-percentile map, optionally reweighted.

    A weight below 1 promotes a hand (it enters ranges earlier), above 1
    demotes it. Percentiles are combo-weighted so a range's percentage always
    refers to a share of all 1326 combinations.
    """
    scored = [
        (index + 1 if weight is None else (index + 1) * weight(classify_hand(name)), name)
        for index, name in enumerate(ORDER_BASE)
    ]
    scored.sort()

    order: Dict[str, float] = {}
    cumulative = 0
    for _, name in scored:
        cumulative += combos(name)
        order[name] = 100.0 * cumulative / TOTAL_COMBOS
    return order


def _call_weight(c: HandClass) -> float:
    # Calling ranges are built for playability: set-mining pairs and suited
    # connectors beat dominated offsuit broadways once money is already in.
    if c.small_pair:
        return 0.50
    if c.pair:
        return 0.70
    if c.suited_connector:
        return 0.72
    if c.suited_ace:
        return 0.90
    if c.offsuit_broadway:
        return 1.35
    if c.offsuit_ace:
        return 1.30
    return 1.0


def _limp_weight(c: HandClass) -> float:
    # Limping ranges skew speculative: cheap hands that flop well multiway.
    if c.small_pair:
        return 0.50
    if c.suited_connector:
        return 0.60
    if c.pair:
        return 0.75
    if c.suited:
        return 0.80
    if c.offsuit_broadway:
        return 1.25
    if c.offsuit_ace:
        return 1.15
    return 1.0


def _blocker_weight(c: HandClass) -> float:
    # Polarised re-raising ranges lean on ace blockers as the bluff half.
    if c.wheel_ace_suited:
        return 0.30
    if c.suited_ace:
        return 0.65
    if c.suited and c.high == 13 and c.low >= 10:
        return 0.80
    return 1.0


HAND_ORDER = build_order()
ORDER_CALL = build_order(_call_weight)
ORDER_LIMP = build_order(_limp_weight)
ORDER_BLOCKER = build_order(_blocker_weight)


def hand_at(row: int, col: int) -> str:
    """Grid cell to hand name: pairs on the diagonal, suited above it."""
    if row == col:
        return RANKS[row] * 2
    if row < col:
        return RANKS[row] + RANKS[col] + "s"
    return RANKS[col] + RANKS[row] + "o"


def grid_hands() -> list[list[str]]:
    """The 13x13 grid as rows of hand names."""
    return [[hand_at(r, c) for c in range(13)] for r in range(13)]


def canonical(cards: list[tuple[str, str]]) -> Optional[str]:
    """Two (rank, suit) pairs to shorthand notation."""
    if len(cards) != 2:
        return None
    (r1, s1), (r2, s2) = cards
    if RANK_VALUE[r1] < RANK_VALUE[r2]:
        (r1, s1), (r2, s2) = (r2, s2), (r1, s1)
    if r1 == r2:
        return r1 + r2
    return r1 + r2 + ("s" if s1 == s2 else "o")
