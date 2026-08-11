"""Terminal rendering: hand grids, statistics tables, and player listings."""

from __future__ import annotations

import math
import os
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .cards import RANKS, grid_hands
from .ranges import CATEGORY_LABELS, RangeChart, Tiers, estimated_tier
from .stats import Baselines, Stats, summarize
from .store import Player

RESET = "\x1b[0m"

#: Base colours per action family. Raising is red through pink as commitment
#: rises, passive actions are amber, folds and checks are muted.
ACTION_COLOUR: Dict[str, Tuple[int, int, int]] = {
    "q5": (244, 63, 142), "q": (214, 59, 168), "t": (168, 85, 247), "o": (224, 92, 75),
    "c": (230, 184, 74), "c3": (230, 184, 74), "c4": (230, 184, 74), "l": (230, 184, 74),
    "x": (46, 95, 134), "f": (88, 94, 104), "fv": (88, 94, 104),
    "f3": (88, 94, 104), "f4": (88, 94, 104),
}

TIER_COLOUR: Dict[str, Tuple[int, int, int]] = {
    "3bet": (168, 85, 247), "open": (224, 92, 75),
    "call": (230, 184, 74), "fold": (40, 42, 46),
}

ACTION_HUE: Dict[str, Tuple[int, int, int]] = {
    "open": (224, 92, 75), "iso": (224, 92, 75),
    "limp": (230, 184, 74), "call": (230, 184, 74),
    "call-3bet": (230, 184, 74), "call-4bet": (230, 184, 74),
    "3bet": (168, 85, 247), "4bet": (214, 59, 168), "5bet": (244, 63, 142),
    "check": (74, 163, 224),
    "fold": (110, 130, 150), "fold-vs-raise": (110, 130, 150),
    "fold-vs-3bet": (110, 130, 150), "fold-vs-4bet": (110, 130, 150),
}


def colour_enabled(stream=sys.stdout) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return bool(getattr(stream, "isatty", lambda: False)())


class Palette:
    """Wraps text in colour, or leaves it alone when colour is unavailable."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def cell(self, text: str, background: Tuple[int, int, int], foreground: Tuple[int, int, int]) -> str:
        if not self.enabled:
            return text
        br, bg, bb = background
        fr, fg, fb = foreground
        return f"\x1b[48;2;{br};{bg};{bb}m\x1b[38;2;{fr};{fg};{fb}m{text}{RESET}"

    def text(self, value: str, colour: Tuple[int, int, int], bold: bool = False) -> str:
        if not self.enabled:
            return value
        r, g, b = colour
        weight = "\x1b[1m" if bold else ""
        return f"{weight}\x1b[38;2;{r};{g};{b}m{value}{RESET}"

    def dim(self, value: str) -> str:
        return self.text(value, (150, 148, 142))

    def bold(self, value: str) -> str:
        return f"\x1b[1m{value}{RESET}" if self.enabled else value


def _readable(background: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Black or white text, whichever reads better on a background."""
    r, g, b = background
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return (20, 20, 20) if luminance > 150 else (240, 240, 240)


def _blend(colour: Tuple[int, int, int], weight: float, base=(28, 29, 32)) -> Tuple[int, int, int]:
    weight = max(0.0, min(1.0, weight))
    return tuple(round(base[i] + (colour[i] - base[i]) * weight) for i in range(3))  # type: ignore


def format_money(amount: float) -> str:
    sign = "-" if amount < 0 else "+"
    return f"{sign}{abs(amount):,.2f}"


def format_percent(value: Optional[float], width: int = 0) -> str:
    text = "-" if value is None else f"{value:.0f}%"
    return text.rjust(width) if width else text


def format_factor(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if math.isinf(value):
        return "inf"
    return f"{value:.1f}"


# ---------------------------------------------------------------- hand grids


def _grid(rows: List[List[Tuple[str, Tuple[int, int, int], str]]], palette: Palette) -> str:
    """Render pre-coloured cells as a labelled 13x13 grid."""
    out = ["    " + "".join(f"{r:^5}" for r in RANKS)]
    for index, row in enumerate(rows):
        line = [f" {RANKS[index]}  "]
        for text, background, marker in row:
            body = f"{text:^4}"[:4] + (marker or " ")
            line.append(palette.cell(body, background, _readable(background)))
        out.append("".join(line))
    return "\n".join(out)


#: Short codes so the grids stay readable when colour is unavailable, such as
#: when output is piped to a file.
CATEGORY_CODE = {
    "q5": "5B", "q": "4B", "t": "3B", "o": "R", "c": "C", "c3": "C", "c4": "C",
    "l": "L", "x": "X", "f": "F", "fv": "F", "f3": "F", "f4": "F",
}
TIER_CODE = {"3bet": "3B", "open": "R", "call": "C", "fold": "."}


def weighted_grid(chart: RangeChart, palette: Palette, numbers: bool = False) -> str:
    """Probability as colour intensity, with a dot marking adjusted cells.

    Without colour the probabilities are printed instead, since intensity is
    the only thing carrying the meaning.
    """
    show_numbers = numbers or not palette.enabled
    hue = ACTION_HUE.get(chart.action, (200, 200, 200))
    rows = []
    for row in grid_hands():
        cells = []
        for hand in row:
            cell = chart.cells[hand]
            label = f"{cell.probability * 100:.0f}" if show_numbers else hand
            weight = 0.10 + 0.90 * cell.probability if cell.probability >= 0.03 else 0.0
            cells.append((label, _blend(hue, weight), "." if cell.adjusted else " "))
        rows.append(cells)
    return _grid(rows, palette)


def categorical_grid(assignments: Dict[str, Tuple[str, bool, str]], palette: Palette) -> str:
    """Best-guess view: solid where observed, faded where inferred."""
    rows = []
    for row in grid_hands():
        cells = []
        for hand in row:
            category, solid, _note = assignments[hand]
            colour = ACTION_COLOUR.get(category) or TIER_COLOUR.get(category, (40, 42, 46))
            if palette.enabled:
                label = hand
            else:
                code = CATEGORY_CODE.get(category) or TIER_CODE.get(category, ".")
                label = code if solid else code.lower()
            cells.append((label, _blend(colour, 1.0 if solid else 0.32), " "))
        rows.append(cells)
    return _grid(rows, palette)


def observed_grid(seen: Dict[str, Dict[str, int]], palette: Palette) -> str:
    """Only hands actually seen, annotated with how many times."""
    from .ranges import dominant_action

    rows = []
    for row in grid_hands():
        cells = []
        for hand in row:
            counts = seen.get(hand)
            if not counts:
                cells.append(("." if not palette.enabled else hand, (32, 33, 36), " "))
                continue
            category = dominant_action(counts) or "x"
            total = sum(counts.values())
            marker = str(total) if 1 < total < 10 else ("+" if total >= 10 else " ")
            label = hand if palette.enabled else CATEGORY_CODE.get(category, "?")
            cells.append((label, ACTION_COLOUR.get(category, (60, 62, 68)), marker))
        rows.append(cells)
    return _grid(rows, palette)


def estimated_grid(cut: Tiers, palette: Palette) -> str:
    rows = []
    for row in grid_hands():
        cells = []
        for hand in row:
            tier = estimated_tier(hand, cut)
            label = hand if palette.enabled else TIER_CODE[tier]
            cells.append((label, TIER_COLOUR[tier], " "))
        rows.append(cells)
    return _grid(rows, palette)


def code_legend(palette: Palette, tiers_only: bool = False) -> str:
    """Explain the short codes used when colour is unavailable."""
    if palette.enabled:
        return ""
    if tiers_only:
        return palette.dim("  3B 3-bet, R raise, C call, . fold")
    return palette.dim(
        "  5B 5-bet, 4B 4-bet, 3B 3-bet, R raise, C call, L limp, F fold,"
        " X check; lower case means inferred rather than seen"
    )


def legend(categories: Sequence[str], palette: Palette) -> str:
    parts = []
    for category in categories:
        colour = ACTION_COLOUR.get(category) or TIER_COLOUR.get(category, (60, 62, 68))
        label = CATEGORY_LABELS.get(category, category)
        parts.append(palette.cell("  ", colour, _readable(colour)) + " " + palette.dim(label))
    return "  ".join(parts)


# ----------------------------------------------------------------- summaries


def _arrow(direction: str, average: Optional[float], palette: Palette) -> str:
    if not direction:
        return "  "
    symbol = "^" if direction == "high" else "v"
    colour = (224, 92, 75) if direction == "high" else (74, 163, 224)
    return palette.text(f" {symbol}", colour)


def player_table(players: Sequence[Player], baselines: Baselines, palette: Palette) -> str:
    """One line per player: the headline reads plus sample size and result."""
    headers = ["Player", "Style", "VPIP", "PFR", "RFI", "3Bet", "AF", "Net", "Hands"]
    widths = [max(18, max((len(p.name) for p in players), default=6) + 1), 16, 7, 7, 7, 7, 7, 12, 7]

    lines = [palette.dim("".join(h.ljust(w) for h, w in zip(headers, widths)))]
    for player in players:
        stats = summarize(player)
        from .stats import classify

        cells = [
            player.name.ljust(widths[0])[: widths[0]],
            classify(player).ljust(widths[1])[: widths[1]],
        ]

        for key, value, width in (
            ("vpip", stats.vpip, widths[2]),
            ("pfr", stats.pfr, widths[3]),
            ("rfi", stats.rfi, widths[4]),
            ("three_bet", stats.three_bet, widths[5]),
        ):
            direction, average = baselines.deviation(key, player)
            cells.append(format_percent(value, 4) + _arrow(direction, average, palette) + " ")

        direction, _ = baselines.deviation("aggression_factor", player)
        cells.append(format_factor(stats.aggression_factor).rjust(4) + _arrow(direction, None, palette) + " ")

        money = format_money(stats.net)
        colour = (88, 185, 126) if stats.net >= 0 else (224, 92, 75)
        cells.append(palette.text(money.rjust(widths[7] - 1), colour) + " ")
        cells.append(str(stats.hands).rjust(widths[8] - 1))
        lines.append("".join(cells))
    return "\n".join(lines)


def _row(label: str, value: str, note: str, palette: Palette) -> str:
    tail = f"  {palette.dim(note)}" if note else ""
    return f"  {label.ljust(24)}{value.rjust(8)}{tail}"


def stat_block(player: Player, baselines: Baselines, palette: Palette) -> str:
    """The full statistics table for one player."""
    stats = summarize(player)
    c = player.counters
    lines: List[str] = []

    def section(title: str) -> None:
        lines.append("")
        lines.append(palette.dim(title.upper()))

    def stat(label: str, key: Optional[str], value: str, note: str = "") -> None:
        marker = ""
        if key:
            direction, average = baselines.deviation(key, player)
            if direction:
                marker = _arrow(direction, average, palette)
                if average is not None:
                    note = (note + f" table {average:.0f}").strip()
        lines.append(_row(label, value + marker, note, palette))

    section("Preflop")
    stat("Hands", None, str(stats.hands))
    stat("VPIP", "vpip", format_percent(stats.vpip))
    stat("PFR", "pfr", format_percent(stats.pfr))
    stat("RFI", "rfi", format_percent(stats.rfi), f"{int(c['rfi'])}/{int(c['rfio'])}")
    stat("Limp", "limp", format_percent(stats.limp))
    stat("Cold call", "cold_call", format_percent(stats.cold_call))
    stat("3-bet", "three_bet", format_percent(stats.three_bet), f"{int(c['tb'])}/{int(c['tbo'])}")
    stat("Fold to 3-bet", "fold_to_three_bet", format_percent(stats.fold_to_three_bet),
         f"{int(c['f3bX'])}/{int(c['f3bF'])}")
    stat("4-bets", None, str(stats.four_bets))
    stat("Steal attempt", "steal", format_percent(stats.steal), f"{int(c['ats'])}/{int(c['atso'])}")

    section("Postflop")
    stat("Saw flop", "saw_flop", format_percent(stats.saw_flop))
    stat("C-bet flop", "cbet", format_percent(stats.cbet), f"{int(c['cb'])}/{int(c['cbo'])}")
    stat("Fold to c-bet", "fold_to_cbet", format_percent(stats.fold_to_cbet),
         f"{int(c['fcbX'])}/{int(c['fcbF'])}")
    stat("Aggression factor", "aggression_factor", format_factor(stats.aggression_factor),
         "bets and raises per call")
    stat("Aggression frequency", "aggression_frequency", format_percent(stats.aggression_frequency))
    stat("Check-raises", None, str(stats.check_raises))
    stat("Won when saw flop", "wwsf", format_percent(stats.wwsf))
    stat("Went to showdown", "wtsd", format_percent(stats.wtsd))
    stat("Won at showdown", "won_showdown", format_percent(stats.won_showdown))

    section("Results")
    stat("Pots won", None, str(stats.pots_won))
    colour = (88, 185, 126) if stats.net >= 0 else (224, 92, 75)
    lines.append(_row("Net", palette.text(format_money(stats.net), colour), "", palette))
    if stats.bb_per_100 is not None:
        lines.append(_row("Big blinds per 100", f"{stats.bb_per_100:+.1f}", "", palette))
    return "\n".join(lines)


def positional_table(player: Player, palette: Palette) -> str:
    from .stats import positional

    headers = ["Seat", "Hands", "VPIP", "PFR", "RFI", "Limp", "Call", "3Bet"]
    lines = [palette.dim("  " + "".join(h.ljust(8) for h in headers))]
    from .store import POSITIONS

    any_rows = False
    for seat in POSITIONS:
        values = positional(player, seat)
        if not values:
            continue
        any_rows = True
        lines.append(
            "  "
            + seat.ljust(8)
            + str(int(values["hands"])).ljust(8)
            + format_percent(values["vpip"]).ljust(8)
            + format_percent(values["pfr"]).ljust(8)
            + format_percent(values["rfi"]).ljust(8)
            + format_percent(values["limp"]).ljust(8)
            + format_percent(values["cold_call"]).ljust(8)
            + format_percent(values["three_bet"]).ljust(8)
        )
    return "\n".join(lines) if any_rows else palette.dim("  No positional data yet.")


def wrap(text: str, width: int = 88, indent: str = "") -> str:
    import textwrap

    return "\n".join(
        textwrap.fill(paragraph, width=width, initial_indent=indent, subsequent_indent=indent)
        for paragraph in text.split("\n")
    )
