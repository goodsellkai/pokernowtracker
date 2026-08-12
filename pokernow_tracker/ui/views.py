"""Turning range results into grid cells and captions."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from PySide6.QtGui import QColor

from ..cards import HAND_ORDER
from ..ranges import (
    ANY_POSITION, CATEGORY_LABELS, TableAverages, best_guess, dominant_action,
    estimated_tier, observations, tiers, weighted_range,
)
from ..store import Player
from . import theme
from .grid import Cell

WEIGHTED = "weighted"
BEST = "best"
ESTIMATED = "estimated"
OBSERVED = "observed"

VIEW_LABELS = (
    (WEIGHTED, "Weighted"),
    (BEST, "Best guess"),
    (ESTIMATED, "Estimated"),
    (OBSERVED, "Observed"),
)


def _counts_tooltip(hand: str, counts: dict) -> str:
    parts = [f"{CATEGORY_LABELS[k]} x{v}" for k, v in counts.items() if k in CATEGORY_LABELS]
    return f"{hand}: {', '.join(parts)}" if parts else hand


def weighted_cells(
    player: Player,
    position: str,
    action: str,
    table: TableAverages,
    size_bb: float = 0.0,
) -> Tuple[List[Cell], str, List[Tuple[str, QColor]]]:
    """Probability per hand, shaded by likelihood."""
    chart = weighted_range(player, position, action, table, size_bb)
    hue = theme.ACTION_HUE.get(action, QColor(200, 200, 200))

    cells: List[Cell] = []
    for hand, cell in chart.cells.items():
        weight = 0.10 + 0.90 * cell.probability if cell.probability >= 0.03 else 0.0
        percent = round(cell.probability * 100)
        tooltip = f"{hand}: {percent}% likely"
        if cell.detail:
            tooltip += f"\n{cell.detail}"
        cells.append(Cell(
            hand=hand,
            colour=theme.blend(hue, weight),
            label=hand,
            detail=f"{percent}%" if percent >= 8 else "",
            marked=cell.adjusted,
            tooltip=tooltip,
        ))

    model = chart.model
    blend = model.blend
    sentences = [f"{player.name} {model.explanation.rstrip().rstrip('.')}."]
    if position != ANY_POSITION:
        if blend.positional_n and blend.positional is not None:
            sentences.append(
                f"From {position}: {blend.positional:.0f}% over {blend.positional_n:.0f}"
                f" spots, blended with {blend.overall:.0f}% overall and a positional prior."
                if blend.overall is not None
                else ""
            )
        else:
            sentences.append(
                f"No {position} sample yet, so overall rates are adjusted by a positional prior."
            )
    if model.size_note:
        sentences.append(model.size_note.strip())
    sentences.append(f"Range covers about {chart.mass:.0f}% of all hands.")
    sentences.append(
        f"{chart.adjusted} hands adjusted by observation, marked with a dot."
        if chart.adjusted
        else "No relevant observed hands for this action yet."
    )

    legend = [("Less likely", theme.blend(hue, 0.15)), ("More likely", hue)]
    return cells, " ".join(s for s in sentences if s), legend


def best_guess_cells(player: Player, position: str) -> Tuple[List[Cell], str, List[Tuple[str, QColor]]]:
    """Observed hands solid, everything else inferred from the statistics."""
    assignments = best_guess(player, position)
    seen = observations(player, position)

    cells: List[Cell] = []
    solid_count = 0
    for hand, (category, solid, note) in assignments.items():
        colour = theme.ACTION_COLOUR.get(category) or theme.TIER_COLOUR.get(category, theme.EMPTY_CELL)
        counts = seen.get(hand, {})
        total = sum(counts.values())
        if solid:
            solid_count += 1
            tooltip = _counts_tooltip(hand, counts)
        else:
            label = {"3bet": "3-bet", "open": "open", "call": "call or limp", "fold": "fold"}.get(
                category, category
            )
            tooltip = f"{hand}: inferred {label}"
            if note:
                tooltip += f"\n{note}"
        cells.append(Cell(
            hand=hand,
            colour=theme.blend(colour, 1.0 if solid else 0.32),
            label=hand,
            detail=str(total) if solid and total > 1 else "",
            tooltip=tooltip,
            faded=not solid,
        ))

    caption = (
        f"{solid_count} hands drawn from cards actually seen, the rest inferred from"
        " their statistics. Inferred cells are faded and hatched."
    )
    legend = [
        ("4-bet or better", theme.ACTION_COLOUR["q"]),
        ("3-bet", theme.ACTION_COLOUR["t"]),
        ("Raise", theme.ACTION_COLOUR["o"]),
        ("Call or limp", theme.ACTION_COLOUR["c"]),
        ("Fold", theme.ACTION_COLOUR["f"]),
    ]
    return cells, caption, legend


def observed_cells(player: Player, position: str) -> Tuple[List[Cell], str, List[Tuple[str, QColor]]]:
    """Only hands actually seen, with sighting counts."""
    seen = observations(player, position)
    cells: List[Cell] = []
    for hand in HAND_ORDER:
        counts = seen.get(hand)
        if not counts:
            cells.append(Cell(hand=hand, colour=theme.EMPTY_CELL, label=hand,
                              tooltip=f"{hand}: never seen"))
            continue
        category = dominant_action(counts) or "x"
        total = sum(counts.values())
        cells.append(Cell(
            hand=hand,
            colour=theme.ACTION_COLOUR.get(category, QColor(60, 62, 68)),
            label=hand,
            detail=str(total) if total > 1 else "",
            tooltip=_counts_tooltip(hand, counts),
        ))

    total_sightings = sum(sum(c.values()) for c in seen.values())
    if seen:
        where = "" if position == ANY_POSITION else f" from {position}"
        caption = f"{len(seen)} hands seen, {total_sightings} sightings{where}."
    else:
        elsewhere = player.observation_count
        if elsewhere and position != ANY_POSITION:
            caption = (
                f"No hands seen from {position}, though {elsewhere} were seen from other"
                " seats. Switch to Any position to include them."
            )
        else:
            caption = (
                "No hole cards seen yet. Cards come from showdowns, from hands shown"
                " after folding, and from every hand dealt to the account that exported"
                " the log."
            )

    legend = [
        ("5-bet or jam", theme.ACTION_COLOUR["q5"]),
        ("4-bet", theme.ACTION_COLOUR["q"]),
        ("3-bet", theme.ACTION_COLOUR["t"]),
        ("Raise", theme.ACTION_COLOUR["o"]),
        ("Call or limp", theme.ACTION_COLOUR["c"]),
        ("Fold", theme.ACTION_COLOUR["f"]),
    ]
    return cells, caption, legend


def estimated_cells(
    player: Player,
    position: str,
    override: Optional[Tuple[float, float, float]] = None,
) -> Tuple[List[Cell], str, List[Tuple[str, QColor]]]:
    """Pure statistical tiers, optionally with hand-picked cutoffs."""
    cut = tiers(player, position)
    if override:
        vpip, open_pct, three_bet = override
        from ..ranges import Tiers

        cut = Tiers(vpip, open_pct, three_bet, cut.source, cut.used_rfi)

    labels = {"3bet": "3-bet", "open": "raise", "call": "call or limp", "fold": "fold"}
    cells = [
        Cell(
            hand=hand,
            colour=theme.TIER_COLOUR[estimated_tier(hand, cut)],
            label=hand,
            tooltip=f"{hand}: {labels[estimated_tier(hand, cut)]}",
        )
        for hand in HAND_ORDER
    ]

    basis = "raise first in" if cut.used_rfi else "preflop raise"
    source = "overall" if cut.source == "overall" else f"{cut.source} only"
    caption = (
        f"Tiers from {source} statistics: 3-bet {cut.three_bet:.0f}%,"
        f" {basis} {cut.open:.0f}%, entered {cut.vpip:.0f}%."
        " Drag the sliders to explore other frequencies."
    )
    legend = [
        ("3-bet", theme.TIER_COLOUR["3bet"]),
        ("Raise", theme.TIER_COLOUR["open"]),
        ("Call or limp", theme.TIER_COLOUR["call"]),
        ("Fold", theme.TIER_COLOUR["fold"]),
    ]
    return cells, caption, legend
