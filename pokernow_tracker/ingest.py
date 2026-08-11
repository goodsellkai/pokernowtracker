"""Turning parsed hands into player statistics.

Each hand is replayed action by action so that every ratio is measured against
genuine opportunities: a 3-bet percentage counts only spots where the player
actually faced a raise, and a raise-first-in percentage counts only unopened
pots. Money is reconciled from the betting action and sums to zero across the
table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .cards import HAND_ORDER
from .logparse import (
    ACTION_RE, COLLECT_RE, POSTS_RE, SHOWS_RE, UNCALLED_RE,
    Hand, detect_hero, parse_hand_notation, read_hands,
)
from .store import DATA_VERSION, Player, Session, Store

#: Observed preflop actions, in order of increasing commitment. A hand shown
#: once is filed under the strongest action taken with it that hand.
CATEGORY_RANK = {
    "f": 0, "fv": 1, "f3": 2, "f4": 3,   # folds, by what was faced
    "x": 4,                              # checked the big blind
    "l": 5,                              # limped
    "c": 6, "c3": 7, "c4": 8,            # calls, by what was faced
    "o": 9, "t": 10, "q": 11, "q5": 12,  # open, 3-bet, 4-bet, 5-bet or jam
}

MINIMUM_PLAYERS = 3  # heads-up ranges are too different to pool with full ring


@dataclass
class _Seat:
    """Mutable per-player state while a single hand is replayed."""

    name: str
    invested: float = 0.0
    street_invested: float = 0.0
    voluntary: bool = False
    raised_preflop: bool = False
    raise_index: Optional[int] = None
    acted_preflop: bool = False
    folded: bool = False
    saw_flop: bool = False
    collected: float = 0.0
    uncalled: float = 0.0
    won_showdown: bool = False
    won_pot: bool = False
    checked_street: bool = False
    cbet_resolved: bool = False
    faced_cbet: bool = False
    category: Optional[str] = None
    cards: Optional[str] = None
    counts: Dict[str, float] = field(default_factory=dict)
    raise_sizes: List[tuple[str, float]] = field(default_factory=list)

    def add(self, key: str, amount: float = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + amount

    def note_category(self, category: str) -> None:
        if self.category is None or CATEGORY_RANK[category] > CATEGORY_RANK[self.category]:
            self.category = category


@dataclass
class ImportResult:
    hands: int = 0
    duplicates: int = 0
    big_blind: float = 0.0
    hero_id: Optional[str] = None
    hero_name: str = ""
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    hand_ids: List[str] = field(default_factory=list)
    per_player: Dict[str, Dict[str, float]] = field(default_factory=dict)


def _positions(seats: List[tuple[int, str, str]], dealer: Optional[str]) -> Dict[str, str]:
    """Assign seats to positions, working backwards from the button.

    The blinds are corrected later from the actual blind posts, which is more
    reliable than seat order when players sit out or post out of turn.
    """
    if dealer is None:
        return {}
    ordered = [player_id for _seat, _name, player_id in sorted(seats)]
    if dealer not in ordered:
        return {}

    count = len(ordered)
    button = ordered.index(dealer)
    labels = {}
    for step in range(count):
        player_id = ordered[(button - step) % count]
        labels[player_id] = {0: "BTN", 1: "CO", 2: "MP"}.get(step, "EP")
    return labels


def process_hand(hand: Hand, store: Store, result: ImportResult, hero_id: Optional[str]) -> None:
    """Replay one hand into the store."""
    if store.seen.get(hand.id, 0) >= DATA_VERSION:
        result.duplicates += 1
        return
    if not hand.line("Player stacks:") or not hand.is_complete:
        return

    seats = hand.seats()
    if len(seats) < MINIMUM_PLAYERS:
        return

    store.seen[hand.id] = DATA_VERSION
    result.hands += 1

    players: Dict[str, _Seat] = {}

    def seat_for(player_id: str, name: str) -> _Seat:
        # Players sometimes act without appearing on the stacks line, having
        # sat down mid-orbit. Create them on first sight so the money balances.
        if player_id not in players:
            players[player_id] = _Seat(name=name)
        return players[player_id]

    for _seat, name, player_id in seats:
        seat_for(player_id, name)

    if hero_id and hero_id in players and hand.hero_cards:
        players[hero_id].cards = parse_hand_notation(hand.hero_cards)
        result.hero_name = players[hero_id].name

    positions = _positions(seats, hand.dealer)
    button = hand.dealer
    ordered = [pid for _s, _n, pid in sorted(seats)]
    cutoff = (
        ordered[(ordered.index(button) - 1) % len(ordered)]
        if button in ordered and len(seats) >= 4
        else None
    )
    small_blind: Optional[str] = None

    street = "preflop"
    raises = 0
    last_aggressor: Optional[str] = None
    anyone_limped = False
    big_blind = result.big_blind
    street_bets = 0
    cbet_made = False
    showdown = False

    def close_street() -> None:
        nonlocal street_bets
        for seat in players.values():
            seat.invested += seat.street_invested
            seat.street_invested = 0.0
            seat.checked_street = False
        street_bets = 0

    for entry in hand.rows:
        posted = POSTS_RE.match(entry)
        if posted:
            name, player_id, amount = posted.group(1), posted.group(2), float(posted.group(3))
            seat = seat_for(player_id, name)
            if "missing small blind" in entry:
                seat.invested += amount  # dead money, does not match a bet
            else:
                seat.street_invested = max(seat.street_invested, amount)
            if "posts a small blind" in entry and small_blind is None:
                small_blind = player_id
                positions[player_id] = "SB"
            if "posts a big blind" in entry:
                big_blind = amount
                positions[player_id] = "BB"
            continue

        if entry.startswith("Flop") and "second run" not in entry:
            close_street()
            street = "flop"
            for seat in players.values():
                if not seat.folded:
                    seat.saw_flop = True
                    seat.add("sf")
            continue
        if entry.startswith("Turn") and "second run" not in entry:
            close_street()
            street = "turn"
            continue
        if entry.startswith("River") and "second run" not in entry:
            close_street()
            street = "river"
            continue

        uncalled = UNCALLED_RE.match(entry)
        if uncalled:
            seat_for(uncalled.group(3), uncalled.group(2)).uncalled += float(uncalled.group(1))
            continue

        collected = COLLECT_RE.match(entry)
        if collected:
            seat = seat_for(collected.group(2), collected.group(1))
            seat.collected += float(collected.group(3))
            seat.won_pot = True
            if " from pot with " in entry:
                showdown = True
                seat.won_showdown = True
            continue

        shown = SHOWS_RE.match(entry)
        if shown:
            notation = parse_hand_notation(shown.group(3))
            if notation:
                seat_for(shown.group(2), shown.group(1)).cards = notation
            continue

        action = ACTION_RE.match(entry)
        if not action:
            continue

        player_id = action.group(2)
        seat = seat_for(player_id, action.group(1))
        verb = action.group(3)
        amount = float(next((g for g in action.group(4, 5, 6) if g), 0) or 0)

        if verb.startswith("folds"):
            kind = "fold"
        elif verb.startswith("checks"):
            kind = "check"
        elif verb.startswith("calls"):
            kind = "call"
        elif verb.startswith("bets"):
            kind = "bet"
        else:
            kind = "raise"

        if street == "preflop":
            facing, first_action = raises, not seat.acted_preflop
            seat.acted_preflop = True

            if facing == 1:
                seat.add("tbo")
            if seat.raise_index == 1 and raises == 2:
                seat.add("f3bF")
                if kind == "fold":
                    seat.add("f3bX")
            if first_action and facing == 0 and not anyone_limped:
                seat.add("rfio")
                if kind == "raise":
                    seat.add("rfi")
                if len(seats) >= 4 and player_id in (cutoff, button, small_blind):
                    seat.add("atso")
                    if kind == "raise":
                        seat.add("ats")

            if kind == "fold":
                seat.folded = True
                seat.note_category({0: "f", 1: "fv", 2: "f3"}.get(facing, "f4"))
            elif kind == "call":
                seat.street_invested = max(seat.street_invested, amount)
                if not seat.voluntary:
                    seat.voluntary = True
                    seat.add("vpip")
                if facing == 0:
                    seat.add("limp")
                    anyone_limped = True
                    seat.note_category("l")
                else:
                    seat.add("call")
                    seat.note_category({1: "c", 2: "c3"}.get(facing, "c4"))
            elif kind == "raise":
                seat.street_invested = max(seat.street_invested, amount)
                if not seat.voluntary:
                    seat.voluntary = True
                    seat.add("vpip")
                if not seat.raised_preflop:
                    seat.raised_preflop = True
                    seat.add("pfr")
                if facing == 1:
                    seat.add("tb")
                if facing >= 2:
                    seat.add("fb")
                category = {0: "o", 1: "t", 2: "q"}.get(facing, "q5")
                if big_blind > 0 and amount > 0:
                    seat.raise_sizes.append((category, amount / big_blind))
                seat.note_category(category)
                raises += 1
                seat.raise_index = raises
                last_aggressor = player_id
        else:
            if kind == "check":
                seat.checked_street = True
                seat.add("pfX")
            elif kind == "fold":
                seat.folded = True
                seat.add("pfF")
            elif kind == "call":
                seat.street_invested = max(seat.street_invested, amount)
                seat.add("pfC")
            else:
                seat.street_invested = max(seat.street_invested, amount)
                seat.add("pfB")
                if seat.checked_street:
                    seat.add("xr")

            if street == "flop":
                if player_id == last_aggressor and not seat.cbet_resolved:
                    if street_bets == 0:
                        seat.add("cbo")
                        if kind == "bet":
                            cbet_made = True
                            seat.add("cb")
                    seat.cbet_resolved = True
                elif cbet_made and not seat.faced_cbet and street_bets == 1 and kind != "check":
                    seat.faced_cbet = True
                    seat.add("fcbF")
                    if kind == "fold":
                        seat.add("fcbX")

            if kind in ("bet", "raise"):
                street_bets += 1

    for seat in players.values():
        seat.invested += seat.street_invested

    if showdown:
        for seat in players.values():
            if not seat.folded:
                seat.add("sd")
                if seat.won_showdown:
                    seat.add("wsd")

    result.big_blind = big_blind
    _record(players, positions, store, result, big_blind)


def _record(
    players: Dict[str, _Seat],
    positions: Dict[str, str],
    store: Store,
    result: ImportResult,
    big_blind: float,
) -> None:
    """Fold one replayed hand into the persistent player records."""
    for player_id, seat in players.items():
        player = store.resolve(player_id, seat.name)
        position = positions.get(player_id)

        if seat.cards:
            category = seat.category or ("f" if seat.folded else "x")
            by_position = player.observed.setdefault(seat.cards, {})
            counts = by_position.setdefault(position or "?", {})
            counts[category] = counts.get(category, 0) + 1

        for category, size in seat.raise_sizes:
            model = player.size_model(category)
            model["n"] += 1
            model["sx"] += size
            model["sxx"] += size * size
            if seat.cards:
                strength = 100.0 - HAND_ORDER[seat.cards]
                model["ns"] += 1
                model["bx"] += size
                model["bxx"] += size * size
                model["by"] += strength
                model["bxy"] += size * strength
                model["byy"] += strength * strength

        if position:
            counters = player.position(position)
            counters["h"] += 1
            counters["v"] += 1 if seat.voluntary else 0
            counters["r"] += 1 if seat.raised_preflop else 0
            counters["l"] += seat.counts.get("limp", 0)
            counters["c"] += seat.counts.get("call", 0)
            counters["t"] += seat.counts.get("tb", 0)
            counters["to"] += seat.counts.get("tbo", 0)
            counters["fi"] += seat.counts.get("rfi", 0)
            counters["fio"] += seat.counts.get("rfio", 0)

        seat.add("hands")
        if seat.won_pot:
            seat.add("won")
            if seat.saw_flop:
                seat.add("wwsf")

        net = seat.collected + seat.uncalled - seat.invested
        seat.add("net", net)
        seat.add("netbb", net / big_blind if big_blind > 0 else 0)

        for key, value in seat.counts.items():
            player.counters[key] = player.counters.get(key, 0) + value

        summary = result.per_player.setdefault(
            player_id, {"name": seat.name, "hands": 0, "net": 0.0, "netbb": 0.0}
        )
        summary["hands"] += 1
        summary["net"] += net
        summary["netbb"] += net / big_blind if big_blind > 0 else 0


def import_log(text: str, store: Store) -> ImportResult:
    """Read a log and fold every new hand in it into the store."""
    hands = read_hands(text)
    result = ImportResult()
    result.hand_ids = [hand.id for hand in hands]
    result.hero_id = detect_hero(hands)
    if hands:
        result.first_seen = hands[0].timestamp
        result.last_seen = hands[-1].timestamp

    for hand in hands:
        process_hand(hand, store, result, result.hero_id)

    if result.hands:
        stakes = f"{big_blind_label(result.big_blind)}" if result.big_blind else ""
        store.sessions.append(
            Session(
                id=store.next_id,
                name="",
                stakes=stakes,
                start=result.first_seen or "",
                end=result.last_seen or "",
                hands=result.hands,
            )
        )
        store.next_id += 1
        for player_id, summary in result.per_player.items():
            player = store.resolve(player_id, str(summary["name"]))
            player.sessions.append(
                {
                    "t": result.first_seen or "",
                    "hands": summary["hands"],
                    "net": round(summary["net"], 2),
                    "netbb": round(summary["netbb"], 1),
                }
            )
    return result


def big_blind_label(big_blind: float) -> str:
    def trim(value: float) -> str:
        return f"{value:g}"

    return f"{trim(big_blind / 2)}/{trim(big_blind)}"


def import_file(path, store: Store, archive: bool = True) -> ImportResult:
    """Import one log file, archiving it so derived data can be rebuilt."""
    from pathlib import Path

    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    result = import_log(text, store)
    if store.sessions and result.hands:
        store.sessions[-1].name = path.stem
    if archive:
        store.archive_log(text, path.stem, result.hand_ids)
    return result


def rebuild(store: Store) -> int:
    """Regenerate every statistic from the archived logs."""
    logs = store.archived_logs()
    if not logs:
        return 0

    keep = {
        player.id: (player.name, player.note, player.tag)
        for player in store.players.values()
        if player.note or player.tag
    }
    notes = {name.lower(): (note, tag) for name, note, tag in keep.values()}

    store.reset()
    for name, text in logs:
        result = import_log(text, store)
        if store.sessions and result.hands:
            store.sessions[-1].name = name

    store.merge_duplicate_names()
    for player in store.players.values():
        saved = notes.get(player.name.lower())
        if saved:
            player.note = player.note or saved[0]
            player.tag = player.tag or saved[1]
    return len(logs)
