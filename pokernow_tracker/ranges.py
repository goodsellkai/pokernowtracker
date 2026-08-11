"""Estimating what an opponent holds when they take a preflop action.

The estimate combines two sources. The first is a statistical model of how
often the player takes that action, shrunk toward the table average and
adjusted for position. The second is the hands they have actually been seen
holding, which are folded in only where they genuinely bear on the question
being asked.

Every range is expressed as a probability per starting hand, and each action's
probabilities sum to the player's measured frequency for it, so at any decision
point the raise, call, and fold shares stay proportional and total 100%.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .cards import (
    HAND_ORDER, ORDER_BLOCKER, ORDER_CALL, ORDER_LIMP,
    TOTAL_COMBOS, combos, grid_hands,
)
from .stats import ratio, summarize
from .store import Player

ANY_POSITION = "ANY"

ACTION_GROUPS: Sequence[Tuple[str, Sequence[Tuple[str, str]]]] = (
    ("First in", (("fold", "Fold"), ("limp", "Limp"), ("open", "Raise"))),
    ("Versus limpers", (("check", "Check (BB)"), ("iso", "Iso-raise"))),
    ("Versus a raise", (("fold-vs-raise", "Fold"), ("call", "Call"), ("3bet", "3-bet"))),
    ("Versus a 3-bet", (("fold-vs-3bet", "Fold"), ("call-3bet", "Call"), ("4bet", "4-bet"))),
    ("Versus a 4-bet", (("fold-vs-4bet", "Fold"), ("call-4bet", "Call"), ("5bet", "5-bet or jam"))),
)

ACTIONS: Dict[str, str] = {key: label for _group, pairs in ACTION_GROUPS for key, label in pairs}

SIZEABLE = ("open", "iso", "3bet", "4bet", "5bet")

#: Actions where the player puts money in, and so might reach a showdown. The
#: survivorship correction only applies to these; folds are invisible by nature.
_VISIBLE = set(ACTIONS) - {"fold", "fold-vs-raise", "fold-vs-3bet", "fold-vs-4bet", "check"}

#: How each statistic typically scales by seat. Used as a prior where the
#: player's own positional sample is thin.
POSITION_PRIOR: Dict[str, Dict[str, float]] = {
    "rfi": {"EP": 0.70, "MP": 0.85, "CO": 1.10, "BTN": 1.40, "SB": 1.00, "BB": 1.00},
    "three_bet": {"EP": 0.80, "MP": 0.90, "CO": 1.00, "BTN": 1.20, "SB": 1.10, "BB": 1.20},
    "call": {"EP": 0.80, "MP": 0.90, "CO": 1.00, "BTN": 1.20, "SB": 0.70, "BB": 1.50},
    "limp": {"EP": 0.90, "MP": 0.90, "CO": 1.00, "BTN": 1.10, "SB": 1.60, "BB": 1.00},
}

#: Which observed actions confirm or contradict each question. An observation
#: only votes where the player actually faced that decision: an open raise says
#: nothing about 3-betting, because the chance never arose.
RELEVANCE: Dict[str, Tuple[Sequence[str], Sequence[str]]] = {
    "open": (("o", "t", "q", "q5"), ("l", "f")),
    "iso": (("o",), ("l", "x", "f")),
    "limp": (("l",), ("o", "t", "q", "q5", "f")),
    "fold": (("f",), ("o", "t", "q", "q5", "l")),
    "check": (("x",), ("o", "t", "q", "q5")),
    "call": (("c",), ("t", "q", "q5", "fv")),
    "3bet": (("t", "q", "q5"), ("c", "fv")),
    "fold-vs-raise": (("fv",), ("c", "t", "q", "q5")),
    "call-3bet": (("c3",), ("q", "f3")),
    "4bet": (("q", "q5"), ("c3", "f3")),
    "fold-vs-3bet": (("f3",), ("c3", "q", "q5")),
    "call-4bet": (("c4",), ("q5", "f4")),
    "5bet": (("q5",), ("c4", "f4")),
    "fold-vs-4bet": (("f4",), ("q5", "c4")),
}

CATEGORY_LABELS = {
    "q5": "5-bet or jam", "q": "4-bet", "t": "3-bet", "o": "Open raise",
    "c": "Call vs raise", "c3": "Call vs 3-bet", "c4": "Call vs 4-bet",
    "l": "Limp", "x": "Check", "f": "Fold (first in)", "fv": "Fold vs raise",
    "f3": "Fold vs 3-bet", "f4": "Fold vs 4-bet",
}

#: Categories where the player voluntarily put money in, used to work out how
#: often we get to see their cards at all.
_PLAYED = ("o", "t", "q", "q5", "c", "c3", "c4", "l")

_ESTIMATE_WEIGHT = 4.0  # the statistical model's weight against observations


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def observations(player: Player, position: str = ANY_POSITION) -> Dict[str, Dict[str, int]]:
    """Observed hands as ``{hand: {category: count}}``, optionally by seat."""
    out: Dict[str, Dict[str, int]] = {}
    for hand, by_position in player.observed.items():
        merged: Dict[str, int] = {}
        for seat, counts in by_position.items():
            if position != ANY_POSITION and seat != position:
                continue
            for category, count in counts.items():
                merged[category] = merged.get(category, 0) + count
        if merged:
            out[hand] = merged
    return out


def show_rate(player: Player) -> float:
    """Fraction of hands a player voluntarily played that we saw cards for.

    Opponents only reveal at showdown or by choice, so this is well below 1 for
    everyone except the account that exported the log.
    """
    seen = sum(
        count
        for by_position in player.observed.values()
        for counts in by_position.values()
        for category, count in counts.items()
        if category in _PLAYED
    )
    return clamp(seen / max(1.0, player.counters["vpip"]), 0.06, 1.0)


class TableAverages:
    """Pooled frequencies across every tracked player.

    Individual rates are shrunk toward these, so a player with a small sample
    reads as typical for the game until evidence says otherwise.
    """

    def __init__(self, players: Sequence[Player]):
        self.overall: Dict[str, Tuple[float, float]] = {}
        self.by_position: Dict[str, Dict[str, Tuple[float, float]]] = {}

        totals = {k: [0.0, 0.0] for k in ("rfi", "three_bet", "call", "limp")}
        positional: Dict[str, Dict[str, List[float]]] = {}

        for player in players:
            c = player.counters
            totals["rfi"][0] += c["rfi"]; totals["rfi"][1] += c["rfio"]
            totals["three_bet"][0] += c["tb"]; totals["three_bet"][1] += c["tbo"]
            totals["call"][0] += c["call"]; totals["call"][1] += c["tbo"]
            totals["limp"][0] += c["limp"]; totals["limp"][1] += c["rfio"]

            for seat, counts in player.positions.items():
                bucket = positional.setdefault(seat, {k: [0.0, 0.0] for k in totals})
                bucket["rfi"][0] += counts["fi"]; bucket["rfi"][1] += counts["fio"]
                bucket["three_bet"][0] += counts["t"]; bucket["three_bet"][1] += counts["to"]
                bucket["call"][0] += counts["c"]; bucket["call"][1] += counts["to"]
                bucket["limp"][0] += counts["l"]; bucket["limp"][1] += counts["fio"]

        self.overall = {k: (v[0], v[1]) for k, v in totals.items()}
        self.by_position = {
            seat: {k: (v[0], v[1]) for k, v in bucket.items()}
            for seat, bucket in positional.items()
        }


_FALLBACK = {"rfi": 18.0, "three_bet": 7.0, "call": 14.0, "limp": 10.0}
_TABLE_WEIGHT = 40.0     # opportunities of pull toward the table average
_POSITION_WEIGHT = 25.0  # opportunities of pull toward the positional prior


@dataclass
class Blend:
    """One frequency after shrinking, with the inputs that produced it."""

    value: float
    overall: Optional[float]
    overall_n: float
    positional: Optional[float]
    positional_n: float
    table_average: float


def blend(kind: str, player: Player, position: str, table: TableAverages) -> Blend:
    """Shrink a player's rate toward the table, then toward a positional prior."""
    c = player.counters
    sources = {
        "rfi": (c["rfi"], c["rfio"], "fi", "fio"),
        "three_bet": (c["tb"], c["tbo"], "t", "to"),
        "call": (c["call"], c["tbo"], "c", "to"),
        "limp": (c["limp"], c["rfio"], "l", "fio"),
    }
    made, opportunities, pos_made, pos_opps = sources[kind]

    overall = ratio(made, opportunities)
    overall_n = opportunities

    positional_value: Optional[float] = None
    positional_n = 0.0
    if position != ANY_POSITION:
        counts = player.positions.get(position)
        if counts:
            positional_value = ratio(counts[pos_made], counts[pos_opps])
            positional_n = counts[pos_opps]

    pooled_made, pooled_opps = table.overall.get(kind, (0.0, 0.0))
    table_average = (
        min(98.0, 100.0 * pooled_made / pooled_opps)
        if pooled_opps >= 100
        else _FALLBACK[kind]
    )

    if overall is None:
        overall_for_blend, overall_n = table_average, 0.0
    else:
        overall_for_blend = min(overall, 98.0)

    shrunk = (overall_n * overall_for_blend + _TABLE_WEIGHT * table_average) / (
        overall_n + _TABLE_WEIGHT
    )

    multiplier = 1.0
    if position != ANY_POSITION:
        hard = POSITION_PRIOR.get(kind, {}).get(position, 1.0)
        seat_totals = table.by_position.get(position, {}).get(kind)
        learned = None
        if seat_totals and seat_totals[1] >= 150 and pooled_opps > 0 and pooled_made > 0:
            learned = (seat_totals[0] / seat_totals[1]) / (pooled_made / pooled_opps)
        if learned is not None:
            weight = seat_totals[1] / (seat_totals[1] + 300)
            multiplier = hard * (1 - weight) + learned * weight
        else:
            multiplier = hard

    prior = min(95.0, shrunk * multiplier)
    if positional_value is None:
        value = prior
    else:
        capped = min(positional_value, 98.0)
        value = (positional_n * capped + _POSITION_WEIGHT * prior) / (
            positional_n + _POSITION_WEIGHT
        )

    return Blend(
        value=round(value, 1),
        overall=overall,
        overall_n=overall_n,
        positional=positional_value,
        positional_n=positional_n,
        table_average=round(table_average, 1),
    )


Curve = Callable[[str], float]


def _mass(curve: Curve) -> float:
    """A curve's total share of all starting hands, as a percentage."""
    return sum(curve(hand) * combos(hand) for hand in HAND_ORDER) / (TOTAL_COMBOS / 100.0)


def _curve(target: float, strength: Callable[[str], float], sharpness: float) -> Curve:
    """A saturating curve whose total mass equals ``target`` percent.

    Hands well inside the cutoff reach a true 100%, the cutoff itself sits near
    50%, and there is a smooth tail beyond it. The scale is solved numerically
    so the mass is exact at any width, including very wide calling ranges where
    a closed-form approximation would fall short.
    """
    target = clamp(target, 0.0, 99.5)
    if target <= 0.01:
        return lambda hand: 0.0

    low, high = 0.05, 600.0
    for _ in range(30):
        middle = (low + high) / 2

        def probe(hand: str, scale: float = middle) -> float:
            return 1.0 / (1.0 + (strength(hand) / scale) ** sharpness)

        if _mass(probe) < target:
            low = middle
        else:
            high = middle

    scale = (low + high) / 2
    return lambda hand: 1.0 / (1.0 + (strength(hand) / scale) ** sharpness)


@dataclass
class RangeModel:
    """A probability per starting hand, plus how it was arrived at."""

    action: str
    probability: Curve
    explanation: str
    blend: Blend
    trap: float = 0.0
    polarity: float = 0.0
    size_note: str = ""


def build_model(
    player: Player,
    position: str,
    action: str,
    table: TableAverages,
    size_bb: float = 0.0,
) -> RangeModel:
    """Assemble the frequency model for one player, seat, and action."""
    rfi = blend("rfi", player, position, table)
    three_bet = blend("three_bet", player, position, table)
    cold_call = blend("call", player, position, table)
    limp = blend("limp", player, position, table)

    c = player.counters
    faced_3bets = c["f3bF"]
    four_bet_rate = (c["fb"] / faced_3bets) if faced_3bets >= 3 else 0.25
    call_3bet_rate = (
        max(0.0, faced_3bets - c["f3bX"] - c["fb"]) / faced_3bets if faced_3bets >= 3 else 0.45
    )

    # Sharper curves once the sample supports them, so charts commit rather
    # than washing out into a band of middling probabilities.
    sharpness = 3.4 + 2.2 * min(1.0, c["hands"] / 250.0)

    R, T, C, L = rfi.value, three_bet.value, cold_call.value, limp.value

    def by_strength(order: Dict[str, float]) -> Callable[[float], Curve]:
        return lambda target: _curve(target, lambda hand: order[hand], sharpness)

    top = by_strength(HAND_ORDER)

    # Players who 3-bet often do it with a polarised range: premiums plus
    # suited-ace blockers rather than a band of second-best hands.
    polarity = clamp((T - 6.0) / 12.0, 0.0, 0.5)

    def blended_strength(hand: str) -> float:
        return (1 - polarity) * HAND_ORDER[hand] + polarity * ORDER_BLOCKER[hand]

    def aggressive(target: float) -> Curve:
        return _curve(target, blended_strength, sharpness)

    # A player whose raising lags their entry rate is flatting hands others
    # would raise. That moves premiums into the calling line without changing
    # any total, since the measured frequencies already reflect the habit.
    vpip = c["vpip"]
    passivity = max(0.0, 1.0 - (c["pfr"] / vpip)) if vpip else 0.5
    trap = min(0.35, 0.30 * passivity * passivity)
    limp_trap = max(0.0, passivity - 0.5) * 0.25

    def with_traps(target: float, family: Callable[[float], Curve], weight: float) -> Curve:
        base = family(target)
        if weight < 0.01:
            return base
        offset = min(target * 0.6, 1.2 + target * 0.1)
        upper, lower = family(offset + target), family(offset)
        return lambda hand: (1 - weight) * base(hand) + weight * clamp(
            upper(hand) - lower(hand), 0.0, 1.0
        )

    four_bet_pct = max(1.2, R * four_bet_rate)
    five_bet_pct = max(1.0, T * 0.18)

    open_base = top(R)
    three_bet_base = aggressive(T)
    open_range = with_traps(R, top, limp_trap)
    iso_range = top(R * 0.9)
    three_bet_range = with_traps(T, aggressive, trap)
    four_bet_range = with_traps(four_bet_pct, aggressive, trap)
    five_bet_range = with_traps(five_bet_pct, aggressive, trap)

    continue_first_in = _curve(R + L, lambda hand: ORDER_LIMP[hand], sharpness)
    continue_vs_raise = _curve(T + C, lambda hand: ORDER_CALL[hand], sharpness)
    continue_vs_3bet = top(max(2.0, R * (four_bet_rate + call_3bet_rate)))
    continue_vs_4bet = aggressive(max(1.5, T * 0.6))

    def difference(wider: Curve, narrower: Curve) -> Curve:
        return lambda hand: clamp(wider(hand) - narrower(hand), 0.0, 1.0)

    def complement(*taken: Curve) -> Curve:
        return lambda hand: clamp(1.0 - sum(c(hand) for c in taken), 0.0, 1.0)

    limp_range = difference(continue_first_in, open_range)
    call_range = difference(continue_vs_raise, three_bet_range)
    call_3bet_range = difference(continue_vs_3bet, four_bet_range)
    call_4bet_range = difference(continue_vs_4bet, five_bet_range)

    percent = lambda v: round(v)
    trap_note = (
        f" They read passive, so about {percent(trap * 100)}% of their strongest raising"
        " hands are modelled as flatted rather than raised."
        if trap >= 0.05
        else ""
    )
    polar_note = (
        f" Re-raising ranges are modelled about {percent(polarity * 100)}% polarised"
        " toward suited-ace blockers."
        if polarity >= 0.08
        else ""
    )

    curves: Dict[str, Tuple[Curve, Blend, str]] = {
        "open": (open_range, rfi, f"opens about {R}% of hands when first in"),
        "iso": (iso_range, rfi, f"iso-raises roughly as wide as the {R}% they open first in"),
        "limp": (
            limp_range, limp,
            f"limps about {L}% of first-in spots, below the {R}% they would raise",
        ),
        "fold": (
            complement(open_range, limp_range), rfi,
            f"folds whatever they neither open ({R}%) nor limp ({L}%)",
        ),
        "check": (
            complement(iso_range), rfi,
            f"checks the big blind with everything outside the {percent(R * 0.9)}% they raise",
        ),
        "call": (
            call_range, cold_call,
            f"cold-calls about {C}% facing a raise, after 3-betting their top {T}%.{trap_note}",
        ),
        "3bet": (three_bet_range, three_bet, f"3-bets about {T}% facing a raise.{polar_note}{trap_note}"),
        "fold-vs-raise": (
            complement(three_bet_range, call_range), cold_call,
            f"folds whatever they neither 3-bet ({T}%) nor call ({C}%)",
        ),
        "call-3bet": (
            call_3bet_range, rfi,
            f"having opened {R}%, 4-bets {percent(four_bet_rate * 100)}% and calls"
            f" {percent(call_3bet_rate * 100)}% against a 3-bet"
            f" ({int(c['f3bX'])} folds and {int(c['fb'])} 4-bets over {int(faced_3bets)} faced)",
        ),
        "4bet": (
            four_bet_range, rfi,
            f"4-bets {percent(four_bet_rate * 100)}% of the {R}% they open.{polar_note}{trap_note}",
        ),
        "fold-vs-3bet": (
            difference(open_range, lambda hand: four_bet_range(hand) + call_3bet_range(hand)), rfi,
            f"folds to a 3-bet {percent(max(0.0, 1 - four_bet_rate - call_3bet_rate) * 100)}%"
            f" of the time, from the bottom of their {R}% opening range",
        ),
        "call-4bet": (
            call_4bet_range, three_bet,
            f"calls a 4-bet with the middle of their {T}% 3-betting range"
            " (estimated: responses to 4-bets are too rare to measure directly)",
        ),
        "5bet": (
            five_bet_range, three_bet,
            f"5-bets or jams the very top of their {T}% 3-betting range"
            " (estimated: responses to 4-bets are too rare to measure directly)",
        ),
        "fold-vs-4bet": (
            difference(three_bet_base, lambda hand: five_bet_range(hand) + call_4bet_range(hand)),
            three_bet,
            f"folds the bottom of their {T}% 3-betting range to a 4-bet"
            " (estimated: responses to 4-bets are too rare to measure directly)",
        ),
    }

    curve, source, explanation = curves[action]
    model = RangeModel(
        action=action, probability=curve, explanation=explanation,
        blend=source, trap=trap, polarity=polarity,
    )

    if size_bb > 0 and action in SIZEABLE:
        _apply_size_read(model, player, action, size_bb, sharpness, {
            "open": (R, top, limp_trap), "iso": (R * 0.9, top, 0.0),
            "3bet": (T, aggressive, trap), "4bet": (four_bet_pct, aggressive, trap),
            "5bet": (five_bet_pct, aggressive, trap),
        }, with_traps)

    return model


_SIZE_CATEGORY = {"open": "o", "iso": "o", "3bet": "t", "4bet": "q", "5bet": "q5"}


def _apply_size_read(
    model: RangeModel,
    player: Player,
    action: str,
    size_bb: float,
    sharpness: float,
    families: Dict[str, Tuple[float, Callable[[float], Curve], float]],
    with_traps,
) -> None:
    """Narrow or widen a raising range based on how the raise was sized.

    The comparison is against the player's own history rather than a rule of
    thumb, and the direction is learned from raises whose cards were revealed,
    so a player who sizes small with strong hands is read correctly.
    """
    stats = player.sizing.get(_SIZE_CATEGORY[action])
    if not stats or stats["n"] < 8:
        model.size_note = (
            f" Size entered, but fewer than eight sized raises of this kind are"
            " recorded, so no sizing read is available yet."
        )
        return

    mean = stats["sx"] / stats["n"]
    variance = max(0.01, stats["sxx"] / stats["n"] - mean * mean)
    deviation = clamp((size_bb - mean) / max(math.sqrt(variance), 0.4), -2.5, 2.5)

    rate, direction, learned = 0.22, 1.0, False
    if stats["ns"] >= 6:
        n = stats["ns"]
        mx, my = stats["bx"] / n, stats["by"] / n
        vx, vy = stats["bxx"] / n - mx * mx, stats["byy"] / n - my * my
        covariance = stats["bxy"] / n - mx * my
        correlation = covariance / math.sqrt(vx * vy) if vx > 0.01 and vy > 1 else 0.0
        if abs(correlation) > 0.25:
            rate = 0.2 + 0.5 * min(1.0, abs(correlation))
            direction = math.copysign(1.0, correlation)
            learned = True

    multiplier = clamp(math.exp(-rate * direction * deviation), 0.3, 2.5)
    if abs(multiplier - 1.0) > 0.02:
        target, family, weight = families[action]
        model.probability = with_traps(max(0.6, target * multiplier), family, weight)

    source = (
        f"direction learned from {int(stats['ns'])} revealed hands"
        if learned
        else "generic prior that larger means stronger"
    )
    model.size_note = (
        f" Sizing: {size_bb:g}bb against their usual {mean:.1f}bb"
        f" ({deviation:+.1f} standard deviations over {int(stats['n'])} sized raises,"
        f" {source}), so the range is"
        f" {'narrowed' if multiplier < 1 else 'widened'} by a factor of {multiplier:.2f}."
    )


@dataclass
class Cell:
    hand: str
    probability: float
    estimate: float
    observed: Dict[str, int] = field(default_factory=dict)
    adjusted: bool = False
    detail: str = ""


@dataclass
class RangeChart:
    player: Player
    action: str
    position: str
    cells: Dict[str, Cell]
    mass: float
    adjusted: int
    model: RangeModel

    def rows(self) -> List[List[Cell]]:
        return [[self.cells[hand] for hand in row] for row in grid_hands()]


def weighted_range(
    player: Player,
    position: str,
    action: str,
    table: TableAverages,
    size_bb: float = 0.0,
) -> RangeChart:
    """The probability that each starting hand is in a player's range."""
    model = build_model(player, position, action, table, size_bb)
    seen_everywhere = observations(player)
    seen_here = observations(player, position) if position != ANY_POSITION else {}
    confirming, contradicting = RELEVANCE[action]

    visible = action in _VISIBLE
    rate = show_rate(player) if visible else 1.0
    hands_played = player.counters["hands"]

    cells: Dict[str, Cell] = {}
    mass = 0.0
    adjusted = 0

    for hand in HAND_ORDER:
        estimate = model.probability(hand)
        probability = estimate
        observed = seen_everywhere.get(hand, {})
        detail = ""

        if observed:
            here = seen_here.get(hand, {})

            def weight(category: str) -> float:
                # Sightings from the seat being asked about count for more.
                return observed.get(category, 0) + 0.3 * here.get(category, 0)

            for_action = sum(weight(k) for k in confirming)
            against = sum(weight(k) for k in contradicting)

            implied_folds = 0.0
            if visible and for_action > 0:
                total_sightings = sum(observed.values())
                expected = hands_played * combos(hand) / TOTAL_COMBOS * rate
                implied_folds = max(0.0, expected - total_sightings)
                # A small gap is ordinary showdown variance, and a hand the
                # model is confident they always play tells us little by its
                # absence, so discount on both counts.
                implied_folds *= 1.0 - math.exp(-implied_folds / 3.0)
                implied_folds *= 1.0 - estimate * estimate

            evidence = for_action + against + implied_folds
            if evidence > 0.2:
                signal = for_action / evidence
                consistency = abs(for_action - (against + implied_folds)) / evidence
                # One sighting nudges; a repeated, consistent trend outweighs
                # the statistical model.
                strength = 1.5 * min(evidence, 3.0) + 2.5 * max(0.0, evidence - 1.0) * consistency
                probability = (_ESTIMATE_WEIGHT * estimate + strength * signal) / (
                    _ESTIMATE_WEIGHT + strength
                )
                adjusted += 1
                parts = [
                    f"{CATEGORY_LABELS[k]} x{observed[k]}"
                    for k in CATEGORY_LABELS
                    if observed.get(k) and (k in confirming or k in contradicting)
                ]
                detail = f"estimate {estimate * 100:.0f}%, seen: {', '.join(parts)}"
                if implied_folds > 0.5:
                    detail += f", about {implied_folds:.1f} unseen deals treated as folds"

        mass += probability * combos(hand) / TOTAL_COMBOS
        cells[hand] = Cell(
            hand=hand, probability=probability, estimate=estimate,
            observed=observed, adjusted=bool(detail), detail=detail,
        )

    return RangeChart(
        player=player, action=action, position=position,
        cells=cells, mass=mass * 100, adjusted=adjusted, model=model,
    )


# --------------------------------------------------------------------- views


@dataclass
class Tiers:
    vpip: float
    open: float
    three_bet: float
    source: str
    used_rfi: bool


def tiers(player: Player, position: str) -> Tiers:
    """Cutoffs for the estimated view, positional where the sample allows."""
    if position != ANY_POSITION:
        counts = player.positions.get(position)
        if counts and counts["h"] >= 10:
            rfi = ratio(counts["fi"], counts["fio"]) if counts["fio"] >= 5 else None
            vpip = ratio(counts["v"], counts["h"]) or 25.0
            raise_pct = rfi if rfi is not None else (ratio(counts["r"], counts["h"]) or 15.0)
            return Tiers(
                vpip=vpip,
                open=min(raise_pct, vpip),
                three_bet=min(ratio(counts["t"], counts["to"]) or 0.0, raise_pct),
                source=position,
                used_rfi=rfi is not None,
            )

    stats = summarize(player)
    rfi = stats.rfi if player.counters["rfio"] >= 10 else None
    vpip = stats.vpip if stats.vpip is not None else 25.0
    raise_pct = rfi if rfi is not None else (stats.pfr if stats.pfr is not None else 15.0)
    raise_pct = min(raise_pct, vpip)
    return Tiers(
        vpip=vpip,
        open=raise_pct,
        three_bet=min(stats.three_bet or 0.0, raise_pct),
        source="overall",
        used_rfi=rfi is not None,
    )


def estimated_tier(hand: str, cut: Tiers) -> str:
    """Which tier a hand falls into for the estimated view."""
    percentile = HAND_ORDER[hand]
    if cut.three_bet and percentile <= cut.three_bet:
        return "3bet"
    if percentile <= cut.open:
        return "open"
    if percentile <= cut.vpip:
        return "call"
    return "fold"


def dominant_action(counts: Dict[str, int]) -> Optional[str]:
    """The most frequent action seen with a hand, ignoring uninformative checks."""
    best, best_count = None, 0
    for category, count in counts.items():
        if category == "x":
            continue
        if count > best_count:
            best, best_count = category, count
    return best


def best_guess(player: Player, position: str) -> Dict[str, Tuple[str, bool, str]]:
    """Observed hands drawn solid, everything else inferred from the statistics.

    An observation only overrides an inferred tier it genuinely contradicts.
    Calling a raise says nothing about whether a hand would be opened first in,
    and an open raise never had the opportunity to 3-bet.
    """
    seen = observations(player, position)
    cut = tiers(player, position)

    # If the hands a player showed up with ran looser than the model predicted,
    # widen the cutoffs to cover what was actually observed.
    played, raised, three_bet = [], [], []
    for hand, counts in seen.items():
        percentile = HAND_ORDER[hand]
        if any(counts.get(k) for k in ("l", "c", "c3", "c4", "o", "t", "q", "q5")):
            played.append(percentile)
        if any(counts.get(k) for k in ("o", "t", "q", "q5")):
            raised.append(percentile)
        if any(counts.get(k) for k in ("t", "q", "q5")):
            three_bet.append(percentile)

    def upper_quartile(values: List[float]) -> float:
        if len(values) < 4:
            return 0.0
        values.sort()
        return values[int(len(values) * 0.75)]

    vpip = max(cut.vpip, upper_quartile(played))
    open_pct = min(max(cut.open, upper_quartile(raised)), vpip)
    tb_pct = min(max(cut.three_bet, upper_quartile(three_bet)), open_pct)
    adjusted_cut = Tiers(vpip, open_pct, tb_pct, cut.source, cut.used_rfi)

    out: Dict[str, Tuple[str, bool, str]] = {}
    for hand in HAND_ORDER:
        counts = seen.get(hand)
        inferred = estimated_tier(hand, adjusted_cut)
        if not counts:
            out[hand] = (inferred, False, "")
            continue

        def has(category: str) -> int:
            return counts.get(category, 0)

        if has("q5") or has("q") or has("t"):
            out[hand] = (dominant_action(counts) or inferred, True, "")
        elif has("o"):
            if inferred == "3bet" and not has("c"):
                out[hand] = (inferred, False, "seen opening, no 3-bet opportunity observed")
            else:
                out[hand] = ("o", True, "")
        elif has("l"):
            out[hand] = ("l", True, "")
        elif has("c"):
            if inferred in ("open", "3bet"):
                out[hand] = (inferred, False, "seen calling a raise, never seen first in")
            else:
                out[hand] = ("c", True, "")
        elif has("c3") or has("c4"):
            if inferred in ("open", "3bet"):
                out[hand] = (inferred, False, "seen calling a re-raise only")
            else:
                out[hand] = ("c3" if has("c3") else "c4", True, "")
        elif any(has(k) for k in ("f", "fv", "f3", "f4")):
            out[hand] = ("f", True, "")
        else:
            out[hand] = (inferred, False, "")
    return out
