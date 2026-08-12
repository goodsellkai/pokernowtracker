# PokerNow Tracker

A command line tracker and range analyser for [PokerNow](https://www.pokernow.club/) games. It reads the hand-history exports PokerNow already produces and turns them into per-player statistics, positional splits, results, and probabilistic preflop range estimates.

![The Range Finder](docs/range-finder.png)

A desktop application with a command line alongside it. Pick a player, a seat, and a
preflop action, and every starting hand is shaded by how likely it is to be in their
range. A dot marks a hand whose estimate was adjusted by cards you have actually seen.

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [The desktop application](#the-desktop-application)
- [Command line](#command-line)
- [Statistics](#statistics)
- [Range estimates](#range-estimates)
- [How the range model works](#how-the-range-model-works)
- [Where data is kept](#where-data-is-kept)
- [Development](#development)
- [License](#license)

## Installation

Requires Python 3.9 or newer.

```bash
git clone https://github.com/goodsellkai/pokernowtracker.git
cd pokernowtracker
pip install ".[gui]"
```

That installs two commands: `pokernow-gui` for the desktop application and `pokernow`
for the command line. The analysis engine itself has no dependencies, so if you only
want the command line, plain `pip install .` skips the interface toolkit entirely.

To work on the code, use `pip install -e ".[gui]"`.

## Quick start

In PokerNow, open the game's **Log** panel and download the hand-history CSV. Then:

```bash
pokernow import ~/Downloads/poker_now_log_*.csv
pokernow players
pokernow player Robin
pokernow range Robin --action open --position BTN
```

Statistics accumulate across every log you import. Players are matched by their PokerNow account id, so a changed nickname carries over, and players whose names differ only in case or spacing are merged automatically. Re-importing a log you have already processed is safe, because hands are deduplicated by hand id. Importing a longer export of a game you already have replaces the shorter one.

## The desktop application

Four tabs, and a player window behind every name.

**Import** takes hand histories by drag and drop, or through a file picker, and reports
what each file added.

**Players** shows a card per opponent with their headline numbers. Statistics that sit
well away from the table average carry an arrow, so the reads are relative to the game
you actually play in rather than to a generic population.

![Players](docs/players.png)

**Range Finder** is the screenshot at the top of this page. Four views are available:
weighted probabilities for one action, a best guess mixing observation with inference,
pure statistical tiers with sliders, and observations only.

**Data** shows where everything is stored, what is archived, and offers a rebuild, a
JSON backup, and a reset.

Selecting a player opens a window with their full statistics, positional splits, and
session history beside their range, along with notes, a tag, and merge and delete
controls.

![A player](docs/player.png)

## Command line

| Command | Purpose |
| --- | --- |
| `pokernow import <files>` | Read one or more hand-history exports |
| `pokernow players` | One line per player, with table-relative flags |
| `pokernow player <name>` | Full statistics, positional splits, and session history |
| `pokernow range <name>` | Estimate a range for a preflop action |
| `pokernow actions` | List the preflop actions a range can be built for |
| `pokernow sessions` | List imported sessions |
| `pokernow rebuild` | Regenerate every statistic from the archived logs |
| `pokernow data` | Show where data lives and what is archived |
| `pokernow merge <a> <b>` | Combine two player records |
| `pokernow note <name> <text>` | Attach a note or `--tag` to a player |
| `pokernow-gui` | Launch the desktop application |

Add `--no-color` for plain output, or set `NO_COLOR` in the environment. Grids fall back to short action codes when colour is unavailable, so piping to a file stays readable.

## Statistics

| Category | Metrics |
| --- | --- |
| Preflop | VPIP, PFR, RFI, limp, cold call, 3-bet, fold to 3-bet, 4-bet, steal attempt |
| Postflop | Saw flop, flop c-bet, fold to c-bet, aggression factor, aggression frequency, check-raises, won when saw flop, went to showdown, won at showdown |
| Results | Pots won, net winnings, big blinds per 100 hands, per-session history |

Every ratio is measured against genuine opportunities rather than against all hands, so a 3-bet percentage is not diluted by hands where nobody raised first. Preflop metrics are also broken out by seat.

Players are classified once they reach a 20-hand sample, and statistics that sit well away from the table average are flagged with an arrow. Comparison is against the rest of your table rather than a generic population, so the reads apply to the game you actually play in.

The parser handles blinds, straddles, missed and missing blind posts, all-in actions, run-it-twice, rebuys, dead-button hands, cards shown voluntarily after folding, and players who act while absent from the stacks line. Money is reconciled per hand and verified to sum to zero across the table. Heads-up hands are excluded, since heads-up ranges are wide enough to distort a full-ring sample.

## Range estimates

`pokernow range` estimates the probability that each of the 169 starting hands is in a player's range for a given action, drawn as a 13 by 13 grid. Cells whose estimate was adjusted by hands actually observed are marked with a dot.

The complete preflop decision tree is covered:

| Situation | Actions |
| --- | --- |
| First in | `fold`, `limp`, `open` |
| Versus limpers | `check`, `iso` |
| Versus a raise | `fold-vs-raise`, `call`, `3bet` |
| Versus a 3-bet | `fold-vs-3bet`, `call-3bet`, `4bet` |
| Versus a 4-bet | `fold-vs-4bet`, `call-4bet`, `5bet` |

Fold ranges are derived as the complement of the continuing ranges, conditioned on reaching that decision. A fold-to-a-3-bet range therefore contains only hands the player would have opened in the first place.

Four views are available through `--view`:

- `weighted`, the default, showing per-hand probabilities for one action.
- `best`, showing observed hands solid and everything else inferred from statistics.
- `estimated`, showing pure statistical tiers.
- `observed`, showing only hands actually seen, with counts.

Useful flags: `--size` supplies the raise size in big blinds, `--top N` lists the most likely hands with the evidence behind each, and `--numbers` prints probabilities instead of hand names.

Hole cards are collected from showdowns, from hands players choose to show after folding, and, for the account that exported the log, from every dealt hand. That account is detected automatically.

## How the range model works

The estimate combines a statistical model of how often a player takes an action with the specific hands they have been seen holding.

**Hand rankings are curated and context-specific.** Hands are ordered by a hand-tuned 169-entry strength list rather than a scoring formula. Each action then uses the ordering appropriate to how such ranges are actually built: calling ranges place pairs and suited connectors ahead of dominated offsuit broadways, limping ranges favour speculative suited and connected holdings, and players who 3-bet often get a partially polarised re-raising order that promotes suited-ace blockers.

**Frequencies are shrunk hierarchically.** A player's raw rate is first shrunk toward the pooled table average, so someone with a 50-hand sample reads as typical for the game until evidence accumulates. The positional sample is then shrunk toward that value adjusted by a positional prior, and the prior itself blends standard positional adjustments with the shape your own table exhibits once the pooled sample is large enough.

**Passive players are modelled as trapping.** When a player's raising rate sits well below their entry rate, part of their premium holdings is modelled as flatted rather than raised. This changes which hands appear in each line without changing any total, because the demoted premiums are offset by extending the cutoff. The measured frequencies already reflect the habit, so reducing them again would double-count it.

**Range mass is exact.** Each curve saturates, so hands well inside a cutoff reach a true 100% while the cutoff itself sits near 50%, and each curve's scale is solved numerically so its total mass equals the measured frequency at any width. At every decision point the raise, call, and fold shares stay proportional to the player's real frequencies and sum to 100%.

**Bet sizing is used where available.** For raising actions, `--size` compares the raise against that player's own sizing history, assembled from every sized raise in the imported logs. Raises above their average tighten the estimate and raises below widen it, scaled by the z-score. The direction of the relationship between size and strength is learned from raises whose cards were later revealed, so a player who sizes small with strong hands is read correctly. Weak correlations fall back to a modest generic prior rather than overfitting.

**Observations adjust the estimate within their context.** Observed actions are recorded together with the situation they occurred in: raises split into open, 3-bet, 4-bet, and 5-bet or jam; calls into versus raise, versus 3-bet, and versus 4-bet; folds into first in, versus raise, versus 3-bet, and versus 4-bet. Each observation therefore contributes only where it genuinely informs the question. An observed limp is evidence against opening, while an open raise says nothing about 3-betting, because that decision never arose. A single sighting adjusts the estimate modestly, three or more consistent sightings outweigh the statistical model, and mixed evidence stays a small adjustment.

**Unobserved hands are corrected for survivorship.** Opponents' folds are rarely visible, so each player is assigned a show rate: the proportion of hands they played for which cards were actually seen. An observation is then weighed against how often that combination should have appeared across the sample, and a real shortfall is treated as implied folds. The shortfall is discounted for variance, since small gaps are ordinary showdown luck, and for prior strength, since the absence of a hand the model is confident a player always plays carries little information.

## Where data is kept

Everything lives under `~/.pokernow-tracker`, or wherever `--data-dir` or the `POKERNOW_TRACKER_HOME` environment variable points.

- `data.json` holds players, statistics, and sessions.
- `logs/` holds the raw imports, so every statistic can be regenerated with `pokernow rebuild` whenever the analysis changes. The same file is never imported twice, and only the fullest export of each game is kept.

`pokernow data --export backup.json` writes a portable snapshot.

Hand-history exports contain the display names of everyone at the table. The included `.gitignore` excludes `*.csv` so logs are not committed by accident.

## Development

```bash
pip install -e ".[gui]" pytest
pytest
```

The test suite builds synthetic hand histories rather than depending on real ones, and
covers the parser, the money reconciliation, opportunity counting, the range model's
invariants (including that each decision's options sum to exactly 100% and that every
action's range mass matches the measured frequency), and the interface, which is
rendered offscreen so it can be checked on a build server. Interface tests are skipped
automatically when the toolkit is not installed.

Module layout:

| Module | Responsibility |
| --- | --- |
| `cards.py` | Hand notation, strength orderings, grid layout |
| `logparse.py` | Reading exports into hand records |
| `ingest.py` | Replaying hands into statistics |
| `stats.py` | Derived statistics and table-relative comparison |
| `ranges.py` | The range model |
| `store.py` | Persistence and the log archive |
| `render.py` | Terminal output |
| `cli.py` | Command line interface |
| `ui/` | Desktop interface |

The analysis engine knows nothing about either interface, so the same results back the
window and the terminal.

## License

Released under the [GNU Affero General Public License v3.0](LICENSE). Modified versions made available over a network must publish their source under the same terms.
