"""Player records, persistence, and the raw-log archive.

Everything derived from a log (statistics, positional splits, observed hands,
sizing models) can be regenerated from the logs themselves, so the archive is
the source of truth. When the analysis changes, :data:`DATA_VERSION` is raised
and the derived data is rebuilt from the archive rather than migrated.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

DATA_VERSION = 1

#: Cumulative per-player counters. Ratios are derived from pairs of these:
#: a numerator and the count of genuine opportunities for it.
COUNTERS = (
    "hands", "vpip", "pfr", "rfi", "rfio", "limp", "call", "tb", "tbo",
    "f3bF", "f3bX", "fb", "ats", "atso", "sf", "cb", "cbo", "fcbF", "fcbX",
    "xr", "pfB", "pfC", "pfF", "pfX", "sd", "wsd", "won", "wwsf", "net", "netbb",
)

POSITIONS = ("EP", "MP", "CO", "BTN", "SB", "BB")

#: Per-position preflop counters: hands, vpip, raises, limps, cold calls,
#: 3-bets, 3-bet opportunities, first-in raises, first-in opportunities.
POS_COUNTERS = ("h", "v", "r", "l", "c", "t", "to", "fi", "fio")

#: Sufficient statistics for the bet-sizing model, per raise category. ``n``
#: and the ``s*`` sums cover every sized raise; the ``b*`` sums cover only
#: raises whose cards were later revealed, giving a size/strength correlation.
SIZE_FIELDS = ("n", "sx", "sxx", "ns", "bx", "bxx", "by", "bxy", "byy")


def normalize_name(name: str) -> str:
    return "".join(name.lower().split())


def _zeroed(keys: Iterable[str]) -> Dict[str, float]:
    return {k: 0 for k in keys}


@dataclass
class Player:
    id: int
    name: str
    player_id: Optional[str] = None  # the PokerNow account id
    note: str = ""
    tag: str = ""
    counters: Dict[str, float] = field(default_factory=lambda: _zeroed(COUNTERS))
    positions: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # hand -> position -> action category -> count
    observed: Dict[str, Dict[str, Dict[str, int]]] = field(default_factory=dict)
    sizing: Dict[str, Dict[str, float]] = field(default_factory=dict)
    sessions: List[Dict[str, float]] = field(default_factory=list)

    def position(self, name: str) -> Dict[str, float]:
        return self.positions.setdefault(name, _zeroed(POS_COUNTERS))

    def size_model(self, category: str) -> Dict[str, float]:
        return self.sizing.setdefault(category, _zeroed(SIZE_FIELDS))

    @property
    def observation_count(self) -> int:
        return sum(
            count
            for by_position in self.observed.values()
            for counts in by_position.values()
            for count in counts.values()
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "player_id": self.player_id,
            "note": self.note,
            "tag": self.tag,
            "counters": self.counters,
            "positions": self.positions,
            "observed": self.observed,
            "sizing": self.sizing,
            "sessions": self.sessions,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Player":
        counters = _zeroed(COUNTERS)
        counters.update(raw.get("counters", {}))
        return cls(
            id=raw["id"],
            name=raw["name"],
            player_id=raw.get("player_id"),
            note=raw.get("note", ""),
            tag=raw.get("tag", ""),
            counters=counters,
            positions=raw.get("positions", {}),
            observed=raw.get("observed", {}),
            sizing=raw.get("sizing", {}),
            sessions=raw.get("sessions", []),
        )


@dataclass
class Session:
    id: int
    name: str
    stakes: str
    start: str
    end: str
    hands: int

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "stakes": self.stakes,
            "start": self.start, "end": self.end, "hands": self.hands,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Session":
        return cls(**raw)


def default_data_dir() -> Path:
    override = os.environ.get("POKERNOW_TRACKER_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".pokernow-tracker"


class Store:
    """Player records plus the archive of imported logs."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.dir = Path(data_dir) if data_dir else default_data_dir()
        self.log_dir = self.dir / "logs"
        self.path = self.dir / "data.json"
        self.players: Dict[int, Player] = {}
        self.sessions: List[Session] = []
        self.seen: Dict[str, int] = {}  # hand id -> version it was processed at
        self.next_id = 1
        self.version = DATA_VERSION
        self.stale = False  # derived data predates the current analysis
        self.load()

    # ---------------------------------------------------------------- state

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.players = {int(p["id"]): Player.from_dict(p) for p in raw.get("players", [])}
        self.sessions = [Session.from_dict(s) for s in raw.get("sessions", [])]
        self.seen = raw.get("seen", {})
        self.next_id = raw.get("next_id", 1)
        self.version = raw.get("version", 0)
        self.stale = self.version != DATA_VERSION

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": DATA_VERSION,
            "next_id": self.next_id,
            "seen": self.seen,
            "players": [p.to_dict() for p in self.players.values()],
            "sessions": [s.to_dict() for s in self.sessions],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        tmp.replace(self.path)
        self.version = DATA_VERSION
        self.stale = False

    def reset(self) -> None:
        self.players.clear()
        self.sessions.clear()
        self.seen.clear()
        self.next_id = 1
        self.stale = False

    # -------------------------------------------------------------- players

    def resolve(self, player_id: str, name: str) -> Player:
        """Find or create the player behind a PokerNow account id.

        A returning player is issued a fresh account id, so a matching display
        name (ignoring case and spacing) is treated as the same person.
        """
        for player in self.players.values():
            if player.player_id == player_id:
                player.name = name
                return player

        target = normalize_name(name)
        for player in self.players.values():
            if normalize_name(player.name) == target:
                player.player_id = player_id
                player.name = name
                return player

        player = Player(id=self.next_id, name=name, player_id=player_id)
        self.next_id += 1
        self.players[player.id] = player
        return player

    def find(self, needle: str) -> List[Player]:
        """Players matching a name, exactly first, then by substring."""
        target = normalize_name(needle)
        exact = [p for p in self.players.values() if normalize_name(p.name) == target]
        if exact:
            return exact
        return [p for p in self.players.values() if target in normalize_name(p.name)]

    def merge(self, source: Player, target: Player) -> bool:
        if source is target:
            return False

        for key in COUNTERS:
            target.counters[key] += source.counters.get(key, 0)

        for hand, by_position in source.observed.items():
            dest_hand = target.observed.setdefault(hand, {})
            for position, counts in by_position.items():
                dest_pos = dest_hand.setdefault(position, {})
                for category, count in counts.items():
                    dest_pos[category] = dest_pos.get(category, 0) + count

        for position, counts in source.positions.items():
            dest = target.position(position)
            for key, value in counts.items():
                dest[key] = dest.get(key, 0) + value

        for category, model in source.sizing.items():
            dest = target.size_model(category)
            for key, value in model.items():
                dest[key] = dest.get(key, 0) + value

        target.sessions = sorted(target.sessions + source.sessions, key=lambda s: s["t"])
        if source.note:
            target.note = f"{target.note}\n{source.note}".strip()
        if source.player_id and not target.player_id:
            target.player_id = source.player_id
        if source.tag and not target.tag:
            target.tag = source.tag

        del self.players[source.id]
        return True

    def merge_duplicate_names(self) -> int:
        by_name: Dict[str, Player] = {}
        merged = 0
        for player in list(self.players.values()):
            key = normalize_name(player.name)
            existing = by_name.get(key)
            if existing is None:
                by_name[key] = player
                continue
            keep, drop = (
                (existing, player)
                if existing.counters["hands"] >= player.counters["hands"]
                else (player, existing)
            )
            if self.merge(drop, keep):
                merged += 1
            by_name[key] = keep
        return merged

    # -------------------------------------------------------------- archive

    def _index_path(self) -> Path:
        return self.log_dir / "index.json"

    def archive_index(self) -> Dict[str, dict]:
        try:
            return json.loads(self._index_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def archive_log(self, text: str, name: str, hand_ids: List[str]) -> bool:
        """Store a log, keeping only the fullest export of each game.

        Returns False when a stored log already contains every hand in this
        one, in which case nothing is written.
        """
        digest = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]
        index = self.archive_index()
        ids = set(hand_ids)

        if ids:
            for other_hash, meta in index.items():
                if other_hash == digest:
                    continue
                other_ids = set(meta.get("hand_ids", []))
                if other_ids and ids <= other_ids:
                    return False

        self.log_dir.mkdir(parents=True, exist_ok=True)
        (self.log_dir / f"{digest}.csv").write_text(text, encoding="utf-8")
        index[digest] = {"name": name, "hand_ids": sorted(ids)}

        if ids:
            for other_hash in [h for h in list(index) if h != digest]:
                other_ids = set(index[other_hash].get("hand_ids", []))
                if other_ids and other_ids <= ids:
                    index.pop(other_hash, None)
                    (self.log_dir / f"{other_hash}.csv").unlink(missing_ok=True)

        self._index_path().write_text(json.dumps(index, indent=1), encoding="utf-8")
        return True

    def archived_logs(self) -> List[tuple[str, str]]:
        """(display name, contents) for every archived log, fullest first."""
        index = self.archive_index()
        entries = sorted(index.items(), key=lambda kv: -len(kv[1].get("hand_ids", [])))
        out: List[tuple[str, str]] = []
        for digest, meta in entries:
            path = self.log_dir / f"{digest}.csv"
            if path.exists():
                out.append((meta.get("name", digest), path.read_text(encoding="utf-8")))
        return out

    def archive_summary(self) -> tuple[int, int, int]:
        """(log count, total hands, bytes on disk)."""
        index = self.archive_index()
        hands = sum(len(meta.get("hand_ids", [])) for meta in index.values())
        size = sum(
            (self.log_dir / f"{digest}.csv").stat().st_size
            for digest in index
            if (self.log_dir / f"{digest}.csv").exists()
        )
        return len(index), hands, size

    def clear_archive(self) -> None:
        if self.log_dir.exists():
            for path in self.log_dir.glob("*.csv"):
                path.unlink()
            self._index_path().unlink(missing_ok=True)
