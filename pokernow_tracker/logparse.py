"""Reading PokerNow hand-history exports.

The export is a CSV of ``entry,at,order`` rows in reverse chronological order.
Each hand is delimited by ``-- starting hand #N (id: ...) --`` and
``-- ending hand #N --`` markers, with the action lines in between.

This module turns that into :class:`Hand` records. It does not interpret the
action; :mod:`pokernow_tracker.ingest` does that.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .cards import RANK_VALUE, canonical

START_RE = re.compile(r"^-- starting hand #\d+\s*\(id: (\w+)\)")
END_RE = re.compile(r"^-- ending hand")
DEALER_RE = re.compile(r'dealer: "(.+?) @ ([\w-]+)"')
SEAT_RE = re.compile(r'#(\d+) "(.+?) @ ([\w-]+)" \(([\d.]+)\)')
SEATED_RE = re.compile(r'@ ([\w-]+)" \(')
SHOWS_RE = re.compile(r'^"(.+?) @ ([\w-]+)" shows a (.+?)\.?$')
POSTS_RE = re.compile(r'^"(.+?) @ ([\w-]+)" posts a .*? of ([\d.]+)')
UNCALLED_RE = re.compile(r'^Uncalled bet of ([\d.]+) returned to "(.+?) @ ([\w-]+)"')
COLLECT_RE = re.compile(r'^"(.+?) @ ([\w-]+)" collected ([\d.]+) from pot')
ACTION_RE = re.compile(
    r'^"(.+?) @ ([\w-]+)" (folds|checks|calls ([\d.]+)|bets ([\d.]+)|raises to ([\d.]+))'
)
COLLECTED_ANY_RE = re.compile(r" collected [\d.]+ from pot")

HERO_PREFIX = "Your hand is "


@dataclass
class Hand:
    """One hand, with its action lines in chronological order."""

    id: str
    timestamp: str
    dealer: Optional[str] = None
    hero_cards: Optional[str] = None
    rows: List[str] = field(default_factory=list)
    ended: bool = False

    def line(self, prefix: str) -> Optional[str]:
        for row in self.rows:
            if row.startswith(prefix):
                return row
        return None

    @property
    def is_complete(self) -> bool:
        """A finished hand always awards the pot to somebody.

        A hand without that line was cut off mid-play, usually because the log
        was exported while it was still running.
        """
        return any(COLLECTED_ANY_RE.search(row) for row in self.rows)

    def seats(self) -> List[Tuple[int, str, str]]:
        """(seat number, display name, player id) from the stacks line."""
        stacks = self.line("Player stacks:")
        if not stacks:
            return []
        return [(int(m[1]), m[2], m[3]) for m in SEAT_RE.finditer(stacks)]


def parse_cards(text: str) -> List[Tuple[str, str]]:
    """``"A♥, 10♣"`` to ``[("A", "♥"), ("T", "♣")]``."""
    out: List[Tuple[str, str]] = []
    for token in (t.strip() for t in text.split(",")):
        if not token:
            continue
        rank, suit = token[:-1].strip(), token[-1]
        if rank == "10":
            rank = "T"
        if rank in RANK_VALUE and suit:
            out.append((rank, suit))
    return out


def parse_hand_notation(text: str) -> Optional[str]:
    """A shown-cards string to shorthand notation, or None if unusable."""
    return canonical(parse_cards(text))


def read_hands(text: str) -> List[Hand]:
    """Split an export into chronologically ordered hands."""
    rows = [
        row
        for row in csv.reader(io.StringIO(text))
        if len(row) >= 3 and row[0] != "entry" and row[2]
    ]
    rows.sort(key=lambda r: int(r[2]))  # the export is newest first

    hands: List[Hand] = []
    current: Optional[Hand] = None

    for entry, at, _order in rows:
        start = START_RE.match(entry)
        if start:
            dealer = DEALER_RE.search(entry)
            current = Hand(id=start.group(1), timestamp=at, dealer=dealer.group(2) if dealer else None)
            hands.append(current)
            continue

        if END_RE.match(entry):
            if current:
                current.ended = True
            continue

        if current is None:
            continue

        if current.ended:
            # Players who folded may still choose to show. Those lines land
            # after the end marker, before the next hand begins.
            if '" shows a ' in entry:
                current.rows.append(entry)
            continue

        if entry.startswith(HERO_PREFIX):
            current.hero_cards = entry[len(HERO_PREFIX) :]
        else:
            current.rows.append(entry)

    return hands


def detect_hero(hands: List[Hand]) -> Optional[str]:
    """Identify whose account exported the log.

    Their hole cards appear on every hand they were dealt into, as
    ``Your hand is ...``. The hero is the one player dealt in for exactly
    those hands.
    """
    hero_hands = sum(1 for h in hands if h.hero_cards)
    if not hero_hands:
        return None

    dealt: Dict[str, List[int]] = {}
    for hand in hands:
        stacks = hand.line("Player stacks:")
        if not stacks:
            continue
        for player in {m.group(1) for m in SEATED_RE.finditer(stacks)}:
            counts = dealt.setdefault(player, [0, 0])
            counts[0] += 1
            if hand.hero_cards:
                counts[1] += 1

    candidates = [
        player
        for player, (total, with_hero) in dealt.items()
        if with_hero == hero_hands and total - hero_hands <= 2
    ]
    return candidates[0] if len(candidates) == 1 else None
