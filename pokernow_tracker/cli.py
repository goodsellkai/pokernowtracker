"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__
from .ingest import import_file, rebuild
from .ranges import (
    ACTION_GROUPS, ACTIONS, ANY_POSITION, SIZEABLE,
    TableAverages, best_guess, observations, tiers, weighted_range,
)
from .render import (
    Palette, categorical_grid, code_legend, colour_enabled, estimated_grid, format_money,
    legend, observed_grid, player_table, positional_table, stat_block,
    weighted_grid, wrap,
)
from .stats import Baselines, classify, summarize
from .store import POSITIONS, Player, Store


def _store(args: argparse.Namespace) -> Store:
    store = Store(Path(args.data_dir) if args.data_dir else None)
    if store.stale and store.players:
        logs = store.archived_logs()
        if logs:
            print("Analysis has changed since this data was built. Rebuilding from archived logs.")
            rebuild(store)
            store.save()
        else:
            print(
                "Warning: this data was built by an earlier version and no logs are archived,"
                " so it cannot be rebuilt. Re-import your logs to refresh it.",
                file=sys.stderr,
            )
    return store


def _palette(args: argparse.Namespace) -> Palette:
    if args.no_color:
        return Palette(False)
    return Palette(colour_enabled())


def _resolve_player(store: Store, name: str) -> Optional[Player]:
    matches = store.find(name)
    if not matches:
        print(f"No player matching {name!r}. Try: pokernow players", file=sys.stderr)
        return None
    if len(matches) > 1:
        exact = [p for p in matches if p.name.lower() == name.lower()]
        if len(exact) == 1:
            return exact[0]
        names = ", ".join(sorted(p.name for p in matches))
        print(f"{name!r} matches several players: {names}", file=sys.stderr)
        return None
    return matches[0]


# ------------------------------------------------------------------ commands


def cmd_import(args: argparse.Namespace) -> int:
    store = _store(args)
    paths: List[Path] = []
    for pattern in args.paths:
        path = Path(pattern)
        paths.extend(sorted(path.parent.glob(path.name)) if "*" in pattern else [path])

    if not paths:
        print("No files matched.", file=sys.stderr)
        return 1

    total_new = 0
    for path in paths:
        if not path.exists():
            print(f"Skipping {path}, no such file.", file=sys.stderr)
            continue
        result = import_file(path, store)
        total_new += result.hands
        detail = f"{result.hands} new hands"
        if result.duplicates:
            detail += f", {result.duplicates} already known"
        if result.hero_name:
            detail += f", exported by {result.hero_name}"
        print(f"{path.name}: {detail}")

    merged = store.merge_duplicate_names()
    if merged:
        print(f"Merged {merged} duplicate player record(s).")
    store.save()
    print(f"\n{total_new} hands added. {len(store.players)} players tracked.")
    return 0


def cmd_players(args: argparse.Namespace) -> int:
    store = _store(args)
    palette = _palette(args)
    players = [p for p in store.players.values() if p.counters["hands"] >= args.min_hands]
    if not players:
        print("No players yet. Import a log first: pokernow import <file.csv>")
        return 0

    players.sort(key=lambda p: -p.counters["hands"])
    baselines = Baselines(store.players.values())
    print(player_table(players, baselines, palette))
    print()
    print(palette.dim(f"{len(players)} players, {len(store.sessions)} sessions imported."))
    return 0


def cmd_player(args: argparse.Namespace) -> int:
    store = _store(args)
    palette = _palette(args)
    player = _resolve_player(store, args.name)
    if player is None:
        return 1

    baselines = Baselines(store.players.values())
    stats = summarize(player)
    print(palette.bold(player.name) + palette.dim(f"   {classify(player)}, {stats.hands} hands"))
    if player.tag:
        print(palette.dim(f"  tag: {player.tag}"))
    print(stat_block(player, baselines, palette))
    print()
    print(palette.dim("BY POSITION"))
    print(positional_table(player, palette))

    if player.sessions:
        print()
        print(palette.dim("RECENT SESSIONS"))
        for session in player.sessions[-8:]:
            date = str(session["t"])[:10]
            colour = (88, 185, 126) if session["net"] >= 0 else (224, 92, 75)
            money = palette.text(format_money(session["net"]), colour)
            print(f"  {date}  {str(session['hands']).rjust(5)} hands   {money}")

    if player.note:
        print()
        print(palette.dim("NOTES"))
        print(wrap(player.note, indent="  "))
    return 0


def cmd_range(args: argparse.Namespace) -> int:
    store = _store(args)
    palette = _palette(args)
    player = _resolve_player(store, args.name)
    if player is None:
        return 1

    position = args.position.upper() if args.position else ANY_POSITION
    if position not in POSITIONS and position != ANY_POSITION:
        print(f"Unknown position {position!r}. Choose from {', '.join(POSITIONS)}.", file=sys.stderr)
        return 1

    if args.action not in ACTIONS:
        print(f"Unknown action {args.action!r}. Try: pokernow actions", file=sys.stderr)
        return 1

    where = "any position" if position == ANY_POSITION else position
    heading = f"{player.name}, {ACTIONS[args.action].lower()} from {where}"
    print(palette.bold(heading))

    if args.view == "observed":
        seen = observations(player, position)
        if not seen:
            elsewhere = player.observation_count
            if elsewhere and position != ANY_POSITION:
                print(palette.dim(
                    f"  No hands seen from {position}, though {elsewhere} were seen elsewhere."
                    " Omit --position to include them."
                ))
            else:
                print(palette.dim(
                    "  No hole cards seen yet. Cards come from showdowns, from hands shown"
                    " after folding, and from every hand dealt to the account that exported"
                    " the log."
                ))
            return 0
        print(observed_grid(seen, palette))
        total = sum(sum(counts.values()) for counts in seen.values())
        print()
        print(legend(["q5", "q", "t", "o", "c", "f"], palette))
        if not palette.enabled:
            print(code_legend(palette))
        print(palette.dim(f"  {len(seen)} hands seen, {total} observations."))
        return 0

    if args.view == "estimated":
        cut = tiers(player, position)
        print(estimated_grid(cut, palette))
        print()
        print(legend(["3bet", "open", "call", "fold"], palette))
        if not palette.enabled:
            print(code_legend(palette, tiers_only=True))
        source = "overall" if cut.source == "overall" else f"{cut.source} only"
        basis = "raise first in" if cut.used_rfi else "preflop raise"
        print(palette.dim(
            f"  Tiers from {source} statistics: 3-bet {cut.three_bet:.0f}%,"
            f" {basis} {cut.open:.0f}%, entered {cut.vpip:.0f}%."
        ))
        return 0

    if args.view == "best":
        assignments = best_guess(player, position)
        print(categorical_grid(assignments, palette))
        solid = sum(1 for _c, is_solid, _n in assignments.values() if is_solid)
        print()
        print(legend(["q5", "q", "t", "o", "c", "l", "f"], palette))
        if not palette.enabled:
            print(code_legend(palette))
        print(palette.dim(
            f"  {solid} hands drawn from observation, the rest inferred from statistics."
            " Faded cells are inferred."
        ))
        return 0

    table = TableAverages(list(store.players.values()))
    chart = weighted_range(player, position, args.action, table, args.size or 0.0)
    print(weighted_grid(chart, palette, numbers=args.numbers))
    print()

    model = chart.model
    blend = model.blend
    summary = model.explanation.rstrip().rstrip(".")
    lines = [f"{player.name} {summary}."]
    if position != ANY_POSITION:
        if blend.positional_n:
            lines.append(
                f"From {position}: {blend.positional:.0f}% over {blend.positional_n:.0f} spots,"
                f" blended with {blend.overall:.0f}% overall and a positional prior."
                if blend.positional is not None
                else ""
            )
        else:
            lines.append(f"No {position} sample yet, so overall rates adjusted by a positional prior.")
    if model.size_note:
        lines.append(model.size_note.strip())
    lines.append(f"Range covers about {chart.mass:.0f}% of all hands.")
    if chart.adjusted:
        lines.append(
            f"{chart.adjusted} hands adjusted by observation, marked with a dot."
        )
    else:
        lines.append("No relevant observed hands for this action yet.")
    print(wrap(" ".join(part for part in lines if part), indent="  "))

    if args.top:
        ranked = sorted(chart.cells.values(), key=lambda c: -c.probability)[: args.top]
        print()
        print(palette.dim(f"MOST LIKELY {args.top} HANDS"))
        for cell in ranked:
            bar = "#" * round(cell.probability * 20)
            detail = f"   {palette.dim(cell.detail)}" if cell.detail else ""
            print(f"  {cell.hand:<4} {cell.probability * 100:5.1f}%  {bar}{detail}")
    return 0


def cmd_actions(args: argparse.Namespace) -> int:
    palette = _palette(args)
    for group, pairs in ACTION_GROUPS:
        print(palette.dim(group))
        for key, label in pairs:
            sizeable = "  (accepts --size)" if key in SIZEABLE else ""
            print(f"  {key:<16}{label}{palette.dim(sizeable)}")
    return 0


def cmd_sessions(args: argparse.Namespace) -> int:
    store = _store(args)
    palette = _palette(args)
    if not store.sessions:
        print("No sessions imported yet.")
        return 0
    print(palette.dim("Date        Hands  Stakes    Source"))
    for session in store.sessions:
        date = str(session.start)[:10]
        print(f"{date}  {str(session.hands).rjust(5)}  {session.stakes:<8}  {session.name}")
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    store = _store(args)
    count = rebuild(store)
    if not count:
        print("No archived logs to rebuild from. Import a log first.", file=sys.stderr)
        return 1
    store.save()
    print(f"Rebuilt from {count} archived log(s). {len(store.players)} players tracked.")
    return 0


def cmd_data(args: argparse.Namespace) -> int:
    store = _store(args)
    palette = _palette(args)
    logs, hands, size = store.archive_summary()
    print(palette.bold("Storage"))
    print(f"  Location        {store.dir}")
    print(f"  Players         {len(store.players)}")
    print(f"  Sessions        {len(store.sessions)}")
    print(f"  Archived logs   {logs} ({hands} hands, {size / 1_048_576:.1f} MB)")
    print()
    print(wrap(
        "Imported logs are kept so every statistic can be rebuilt automatically when the"
        " analysis changes. The same file is never imported twice.",
        indent="  ",
    ))
    if args.export:
        payload = {
            "players": [p.to_dict() for p in store.players.values()],
            "sessions": [s.to_dict() for s in store.sessions],
        }
        Path(args.export).write_text(json.dumps(payload, indent=1), encoding="utf-8")
        print(f"\nExported to {args.export}")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    store = _store(args)
    source = _resolve_player(store, args.source)
    target = _resolve_player(store, args.into)
    if source is None or target is None:
        return 1
    if not store.merge(source, target):
        print("Nothing to merge.", file=sys.stderr)
        return 1
    store.save()
    print(f"Merged {source.name} into {target.name}.")
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    store = _store(args)
    player = _resolve_player(store, args.name)
    if player is None:
        return 1
    if args.tag:
        player.tag = args.tag
    if args.text:
        player.note = f"{player.note}\n{args.text}".strip() if player.note else args.text
    store.save()
    print(f"Updated {player.name}.")
    return 0


# -------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    # Shared options are attached to every subcommand as well as the root, so
    # they work in either position.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", help="where to keep tracked data (default ~/.pokernow-tracker)")
    common.add_argument("--no-color", action="store_true", help="disable coloured output")

    parser = argparse.ArgumentParser(
        prog="pokernow",
        parents=[common],
        description="Track PokerNow opponents and estimate their preflop ranges.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", required=True, parser_class=argparse.ArgumentParser)

    def add(name: str, **kwargs) -> argparse.ArgumentParser:
        return sub.add_parser(name, parents=[common], **kwargs)

    p = add("import", help="import one or more hand-history exports")
    p.add_argument("paths", nargs="+", help="CSV files exported from PokerNow")
    p.set_defaults(func=cmd_import)

    p = add("players", help="list tracked players")
    p.add_argument("--min-hands", type=int, default=0, help="hide players below this sample size")
    p.set_defaults(func=cmd_players)

    p = add("player", help="full statistics for one player")
    p.add_argument("name")
    p.set_defaults(func=cmd_player)

    p = add("range", help="estimate a player's range for a preflop action")
    p.add_argument("name")
    p.add_argument("-a", "--action", default="open", help="preflop action (see: pokernow actions)")
    p.add_argument("-p", "--position", help="restrict to a seat: EP MP CO BTN SB BB")
    p.add_argument("-s", "--size", type=float, help="raise size in big blinds, sharpens the read")
    p.add_argument(
        "-v", "--view", default="weighted",
        choices=("weighted", "best", "estimated", "observed"),
        help="weighted probabilities, best guess, pure statistics, or observations only",
    )
    p.add_argument("--numbers", action="store_true", help="print probabilities instead of hand names")
    p.add_argument("--top", type=int, default=0, help="also list the N most likely hands")
    p.set_defaults(func=cmd_range)

    p = add("actions", help="list the preflop actions a range can be built for")
    p.set_defaults(func=cmd_actions)

    p = add("sessions", help="list imported sessions")
    p.set_defaults(func=cmd_sessions)

    p = add("rebuild", help="regenerate all statistics from archived logs")
    p.set_defaults(func=cmd_rebuild)

    p = add("data", help="show where data lives and what is archived")
    p.add_argument("--export", help="write a JSON snapshot to this path")
    p.set_defaults(func=cmd_data)

    p = add("merge", help="combine two player records")
    p.add_argument("source")
    p.add_argument("into")
    p.set_defaults(func=cmd_merge)

    p = add("note", help="attach a note or tag to a player")
    p.add_argument("name")
    p.add_argument("text", nargs="?", help="note to append")
    p.add_argument("--tag", help="short label, for example TAG or Whale")
    p.set_defaults(func=cmd_note)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
