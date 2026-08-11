"""Derived statistics, player classification, and table-relative comparison.

Every ratio here is measured against genuine opportunities rather than against
all hands, so a 3-bet percentage is not diluted by hands the player never had
the chance to 3-bet.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

from .store import Player


def ratio(numerator: float, denominator: float) -> Optional[float]:
    """Percentage, or None when there is nothing to divide by."""
    if not denominator:
        return None
    return 100.0 * numerator / denominator


@dataclass
class Stats:
    hands: int
    vpip: Optional[float]
    pfr: Optional[float]
    rfi: Optional[float]
    limp: Optional[float]
    cold_call: Optional[float]
    three_bet: Optional[float]
    fold_to_three_bet: Optional[float]
    four_bets: int
    steal: Optional[float]
    saw_flop: Optional[float]
    cbet: Optional[float]
    fold_to_cbet: Optional[float]
    aggression_factor: Optional[float]
    aggression_frequency: Optional[float]
    check_raises: int
    wwsf: Optional[float]
    wtsd: Optional[float]
    won_showdown: Optional[float]
    pots_won: int
    net: float
    bb_per_100: Optional[float]


def summarize(player: Player) -> Stats:
    c = player.counters
    aggressive, called, folded = c["pfB"], c["pfC"], c["pfF"]
    postflop_actions = aggressive + called + folded
    return Stats(
        hands=int(c["hands"]),
        vpip=ratio(c["vpip"], c["hands"]),
        pfr=ratio(c["pfr"], c["hands"]),
        rfi=ratio(c["rfi"], c["rfio"]),
        limp=ratio(c["limp"], c["hands"]),
        cold_call=ratio(c["call"], c["hands"]),
        three_bet=ratio(c["tb"], c["tbo"]),
        fold_to_three_bet=ratio(c["f3bX"], c["f3bF"]),
        four_bets=int(c["fb"]),
        steal=ratio(c["ats"], c["atso"]),
        saw_flop=ratio(c["sf"], c["hands"]),
        cbet=ratio(c["cb"], c["cbo"]),
        fold_to_cbet=ratio(c["fcbX"], c["fcbF"]),
        aggression_factor=(aggressive / called) if called else (math.inf if aggressive else None),
        aggression_frequency=ratio(aggressive, postflop_actions),
        check_raises=int(c["xr"]),
        wwsf=ratio(c["wwsf"], c["sf"]),
        wtsd=ratio(c["sd"], c["sf"]),
        won_showdown=ratio(c["wsd"], c["sd"]),
        pots_won=int(c["won"]),
        net=c["net"],
        bb_per_100=(c["netbb"] / c["hands"] * 100) if c["hands"] else None,
    )


def classify(player: Player) -> str:
    """A one-word read on a player's style, once the sample supports one."""
    stats = summarize(player)
    if stats.hands < 20:
        return "Low sample"

    vpip = stats.vpip or 0.0
    pfr = stats.pfr or 0.0
    aggression = pfr / vpip if vpip else 0.0

    if vpip <= 15:
        return "Nit" if aggression >= 0.60 else "Rock"
    if vpip <= 26:
        return "TAG" if aggression >= 0.60 else "Loose-passive"
    if vpip <= 40:
        return "LAG" if aggression >= 0.55 else "Calling station"
    return "Maniac" if aggression >= 0.55 else "Whale"


# Each definition returns a comparable value, or None when the player's sample
# is too thin for that particular statistic to mean anything.
def _guarded(numerator: str, denominator: str, minimum: int) -> Callable[[Player], Optional[float]]:
    def read(player: Player) -> Optional[float]:
        c = player.counters
        if c[denominator] < minimum:
            return None
        return ratio(c[numerator], c[denominator])

    return read


def _aggression_factor(player: Player) -> Optional[float]:
    c = player.counters
    return (c["pfB"] / c["pfC"]) if c["pfC"] >= 5 else None


def _aggression_frequency(player: Player) -> Optional[float]:
    c = player.counters
    total = c["pfB"] + c["pfC"] + c["pfF"]
    return ratio(c["pfB"], total) if total >= 10 else None


COMPARABLE: Dict[str, Callable[[Player], Optional[float]]] = {
    "vpip": _guarded("vpip", "hands", 1),
    "pfr": _guarded("pfr", "hands", 1),
    "rfi": _guarded("rfi", "rfio", 5),
    "limp": _guarded("limp", "hands", 1),
    "cold_call": _guarded("call", "hands", 1),
    "three_bet": _guarded("tb", "tbo", 5),
    "fold_to_three_bet": _guarded("f3bX", "f3bF", 3),
    "steal": _guarded("ats", "atso", 5),
    "saw_flop": _guarded("sf", "hands", 1),
    "cbet": _guarded("cb", "cbo", 3),
    "fold_to_cbet": _guarded("fcbX", "fcbF", 3),
    "aggression_factor": _aggression_factor,
    "aggression_frequency": _aggression_frequency,
    "wtsd": _guarded("sd", "sf", 10),
    "won_showdown": _guarded("wsd", "sd", 3),
    "wwsf": _guarded("wwsf", "sf", 10),
}

#: Below this much deviation a difference is not worth flagging, even when the
#: table happens to be unusually uniform.
_FLOOR = {"aggression_factor": 0.6}
_DEFAULT_FLOOR = 5.0


class Baselines:
    """Table averages used to judge whether a player stands out.

    Comparison is against the rest of the table rather than a generic
    population, so reads are relative to the game actually being played.
    """

    def __init__(self, players: Iterable[Player], minimum_hands: int = 20):
        pool = [p for p in players if p.counters["hands"] >= minimum_hands]
        self._values: Dict[str, List[tuple[int, float]]] = {}
        for key, read in COMPARABLE.items():
            samples = []
            for player in pool:
                value = read(player)
                if value is not None and math.isfinite(value):
                    samples.append((player.id, value))
            if len(samples) >= 3:
                self._values[key] = samples

    def deviation(self, key: str, player: Player) -> tuple[str, Optional[float]]:
        """('high' | 'low' | '', table average) for one statistic."""
        samples = self._values.get(key)
        if not samples:
            return "", None

        read = COMPARABLE[key]
        value = read(player)
        if value is None or not math.isfinite(value):
            return "", None

        others = [v for pid, v in samples if pid != player.id]
        if len(others) < 2:
            return "", None

        mean = sum(others) / len(others)
        variance = sum((v - mean) ** 2 for v in others) / len(others)
        spread = max(math.sqrt(variance), _FLOOR.get(key, _DEFAULT_FLOOR))

        if value >= mean + spread:
            return "high", mean
        if value <= mean - spread:
            return "low", mean
        return "", mean


def positional(player: Player, position: str) -> Optional[Dict[str, Optional[float]]]:
    """Preflop statistics restricted to one seat, if the sample supports it."""
    counters = player.positions.get(position)
    if not counters or counters["h"] < 1:
        return None
    return {
        "hands": counters["h"],
        "vpip": ratio(counters["v"], counters["h"]),
        "pfr": ratio(counters["r"], counters["h"]),
        "rfi": ratio(counters["fi"], counters["fio"]),
        "limp": ratio(counters["l"], counters["h"]),
        "cold_call": ratio(counters["c"], counters["h"]),
        "three_bet": ratio(counters["t"], counters["to"]),
    }
