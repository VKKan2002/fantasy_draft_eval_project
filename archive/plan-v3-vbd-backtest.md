# Does Value-Based Drafting Actually Work? — Plan

## The question

> **Given identical information, does transforming ADP through value-over-replacement, roster
> state, and positional scarcity produce measurably better fantasy teams than following ADP as a
> ranked list — and which individual factors earn their keep?**

Every draft assistant in this category sells the same premise. `jjti/ff` ranks by VOR. FFL Draft
Day Picker publishes exact weights: ADP Value **30%**, Positional Scarcity **25%**, Roster Needs
**25%**, Bye Week **10%**, Elite Talent **10%**, with a **−15** penalty for Questionable/Out.

Nobody has shown those numbers are right. That is the gap this project fills.

**Phase 1 is the backtest only. No app.** If value-based drafting shows no edge over ADP-follow,
that is the finding, and it saves building a tool on a false premise. The tool is Phase 2, gated on
the result.

---

## The experimental design

### Identical information, different transformations

Every policy receives the same input: **ADP-implied expected points**. Map positional draft rank to
expected season total from prior seasons only —

```
f_pos(k) = mean realized PPR total of the k-th drafted player at that position,
           fit on seasons < t, smoothed monotone non-increasing (isotonic)
```

Per-position rather than overall, because a QB and an RB taken at the same overall pick have very
different point scales, and VOR needs each position on its own curve before subtracting replacement
level.

This is what makes the experiment tight. **No forecasting model exists.** Both the baseline and the
sophisticated policies are functions of ADP alone, so any measured difference is attributable purely
to the decision logic. Nothing is trained, so there is no feature pipeline, no walk-forward CV, and
almost no leakage surface — the one fitted object is `f_pos`, and gate G4 covers it.

### The policy ladder

| ID | Policy | What it tests |
|---|---|---|
| **P0** | **ADP-follow.** Lowest ADP available, subject only to roster legality | The baseline everyone claims to beat |
| **P1** | ADP + positional need (skip full positions) | What a casual drafter already does |
| **P2** | **Static VOR** — projection minus the `n+1`th at position, `n` = league starters | `jjti/ff`'s core claim |
| **P3** | **Dynamic VOR** — replacement level recomputed from remaining supply each pick | `jjti/ff`'s "computes VOR dynamically" |
| **P4** | VOR + roster need — marginal gain to *my* expected starting lineup | Whether "roster needs" is worth 25% |
| **P5** | VOR + scarcity-in-time — adds P(survives to my next pick) from ADP `stdev` | The one rung none of the inspirations implement |
| **P6** | **FFL replica** — the published 30/25/25/10/10 weights plus injury penalty | Their app, reproduced faithfully |

All analytic, all sub-50 ms per pick. **No lookahead, no Monte Carlo rollouts** — because none of
the inspirations do lookahead either, and the goal is to validate what the category actually ships.

### The ablation — the real payoff

Take P6 and zero out one factor at a time:

| Variant | Question answered |
|---|---|
| P6 − scarcity | Is positional scarcity worth 25%? |
| P6 − roster need | Is roster need worth 25%? |
| P6 − bye week | Does the bye-week term help, or is it noise dressed as insight? |
| P6 − elite talent | Does the elite-talent bonus do anything? |
| P6 − injury penalty | Is −15 correct, too harsh, or actively backwards? |
| P6 with swept weights | Are 30/25/25/10/10 anywhere near optimal? |

Reported as paired deltas with confidence intervals. This is the headline table.

### Opponent model

Eleven ADP-driven bots. Each pick is a Plackett–Luce draw over available players weighted by ADP
rank, constrained by plausible positional need, with temperature calibrated per (season, league
size).

**Fidelity gate (G3).** Simulate many drafts with no policy team present and confirm the *emergent*
per-player mean draft position and standard deviation reproduce FFC's observed `adp` and `stdev`. If
the simulated draft room does not behave like a real one, the whole backtest is theatre. This is a
concrete, falsifiable check that it does.

### Scoring a finished roster

The season already happened, so evaluation is a **table lookup, not a simulation** — index a dense
`realized_points[player, week]` matrix and pick the lineup. This is why the whole grid runs in
minutes.

Two lineup rules, both reported, because the choice is not neutral:

- **Committed** — start players by descending ADP-implied per-game points, subject to slot
  legality, skipping bye weeks and inactives. No knowledge of that week's actual scores.
- **Clairvoyant** — masked top-k on realized points. Perfect start/sit.

Committed is the headline; clairvoyant is an upper bound; **the gap is its own metric.** Clairvoyant
scoring silently over-rewards boom-bust depth — with two coin-flip players scoring 5 or 25,
committing in advance averages 15 while always picking the winner averages 20, and that phantom 5
scales with volatility. Since volatility preference is exactly what these policies differ on, the
bias points straight at the headline result. Reporting both bounds costs one extra argsort.

### Paired comparison

Every policy in a cell faces the same seeded opponent draws, which strips out shared draft-room
luck and buys far tighter intervals for the same compute. Note honestly that pairing is not perfect:
once a policy makes a different pick, the available pool diverges for everyone downstream. Random
numbers are held common; the realized draft is not identical.

**Cells:** season (2014–2025) × draft slot (1–12) × seed (50) × policy (~13). About 86,000 draft
simulations of 180 cheap-arithmetic picks each — minutes single-threaded, no compute gate needed,
though UoW 4 should confirm with a micro-benchmark before the full grid.

### Metrics

Realized starting-lineup points (committed and clairvoyant) · head-to-head win % against the eleven
bots · playoff and championship rates · **paired Δ vs P0 with bootstrap CIs blocked by season.**

Twelve seasons means roughly twelve independent draws of season-level shocks. Power comes from the
slot × seed cross-product and the paired design — never from treating correlated cells as
independent, and no p-hacking across the ablation grid.

---

## Data — three sources

Via **`nflreadpy`** (nflverse, MIT, CC-BY-4.0 data). Not `nfl_data_py`, the older third-party port.

| Source | Loader / endpoint | Role |
|---|---|---|
| Player weekly stats | `load_player_stats(summary_level="week")`, 1999+ | Realized weekly points, games played. Pre-aggregated, so **no play-by-play needed** |
| Schedules | `load_schedules()` | Bye weeks; Week 1 kickoff date for gate G1 |
| ID crosswalk | `load_players()` / `load_ff_playerids()` | FFC names → `merge_name` → `mfl_id` → `gsis_id` |
| ADP | `GET fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year={y}&position=all` | The market. Free, 2007–2026, with `adp`, `stdev`, `high`, `low`, and a `meta` draft window |

`stdev` is what makes P5's survival probabilities possible at all.

**Window: 2014–2025.** Pre-2014 ADP pools are too thin to fill a 180-pick draft.

**Simplification:** v1 league config has **no K or DST slots.** They are drafted in the last rounds,
they are close to random, and DST requires a team-level rather than player-level join. Excluding
them removes real plumbing for almost no loss of validity. Stated as a limitation.

---

## Gates

| # | Gate | Why |
|---|---|---|
| **G1** | **Point-in-time ADP.** Admit a season only if FFC `meta.end_date` precedes Week 1 kickoff | Verified: 2009 Non-PPR returns `end_date: 2010-06-20` — drafts held ten months *after* the season ended. Using that as draft-time consensus is catastrophic leakage |
| **G2** | **ID resolution ≥ 97%** of top-150-by-ADP rows resolve to `gsis_id`; unmatched emitted to a manual override table | A silent join failure is the likeliest path to a confidently wrong answer |
| **G3** | **Opponent fidelity.** Emergent simulated ADP mean and stdev reproduce FFC's observed values | Without this the simulated draft room is fiction |
| **G4** | **`f_pos` isolation.** Assert `max(train_seasons) < test_season` for every rank→points mapping fit | It feels like a lookup table. It is a fitted model |
| **G5** | **Pool depth.** `size × rounds` picks required vs. players available per cell | 12-team × 15 rounds = 180 picks against ~175 available players will bind. Document where |

`ingest_manifest` records source URL, fetch time, row count, and sha256 per pull — nflverse
retroactively corrects historical stats, so today's 2019 table is not byte-identical to 2019's.

---

## Warehouse (DuckDB, single file)

```
dim_player        (player_key PK, gsis_id, mfl_id, name, merge_name, position, birthdate)
dim_season        (season, week1_kickoff, regular_season_weeks)
dim_league        (league_id, teams, roster slots, flex rules, rounds, scoring_profile)
fact_player_week  (player_key, season, week, team, active, <raw stat counters>)
fact_adp          (season, format, teams, player_key, adp, stdev, high, low, times_drafted,
                   window_start, window_end, is_pre_kickoff)

market_baseline   (season, position, pos_rank, exp_total, exp_ppg)   -- f_pos, walk-forward
sim_draft         (sim_id, season, teams, slot, policy_id, seed)
sim_pick          (sim_id, pick_no, team_slot, player_key)
sim_result        (sim_id, team_slot, policy_id, points_committed, points_clairvoyant,
                   wins, rank, made_playoffs, champion)
ablation_summary  (policy_id, variant, season, delta_vs_p0, ci_low, ci_high)
ingest_manifest   (dataset, source_url, fetched_at, row_count, sha256)
```

Store **counters, not points** — points are a pure function of (counters × scoring profile), so
persisting counters keeps Half-PPR and Standard available for free later. v1 reports PPR only.

---

## Units of work

| UoW | Scope | Gates |
|---|---|---|
| **1** | Data foundation — ingest three sources, ID crosswalk, DuckDB build, manifest | G1, G2, G5 |
| **2** | Scoring engine + realized-season evaluator — counters → PPR, `realized_points` matrix, weekly lineup optimizer under both rules | property tests |
| **3** | Draft simulator + opponent model | G3 |
| **4** | Policy ladder, ablation harness, paired CRN grid, block bootstrap | G4 |

**One forward-looking constraint, free to honor now:** every policy must be a pure function of
`(draft_state, league_settings, projections) → ranked candidates`. That way Phase 2's API calls the
identical code the backtest validated, instead of a reimplementation that drifts from it.

## Repo layout

```
docs/           00-question.md  10-design.md  20-data-sources.md  30-findings.md
src/vbdtest/
  ingest/       nflverse.py  adp_ffc.py  ids.py  manifest.py
  warehouse/    ddl.sql  build.py
  scoring/      profiles.py  engine.py  lineup.py
  sim/          draft.py  opponents.py  evaluate.py
  policies/     base.py  adp.py  vor.py  ffl_replica.py
  experiment/   grid.py  bootstrap.py  ablation.py
  cli.py
tests/          pyproject.toml   README.md
```

---

## One thing I'd add back, your call

You declined the perfect-hindsight arm, which is fair — it isn't a projection source, it's a cheating
baseline. But it's about twenty lines (same simulator, realized points as the projection input), and
without it a null result is ambiguous: if P3 beats P0 by 1.5% with a CI straddling zero, you cannot
distinguish *"VBD doesn't work"* from *"only 2% was ever available and we captured most of it."*

It converts a bare delta into "captured 40% of the achievable edge." I'd include it as a diagnostic
rather than a headline. Say the word and it goes in; otherwise the plan stands as written.

## Risks and honest limitations

**Frozen rosters.** No waivers, trades, or in-season management. This isolates draft quality, which
is the question, but it punishes injuries harder than reality does — in a real league you drop the
injured player and stream a replacement. Caps external validity; must be stated in any write-up.

**The FFL replica is a reconstruction.** The published weights are known; the exact functional form
that combines them is not. P6 is a faithful-as-possible interpretation, not their code, and should
be labelled that way rather than as a definitive verdict on their app.

**Draft-time injury status is uncertain.** FFL's −15 penalty applies to Questionable/Out *at draft
time*. `load_injuries()` is weekly in-season from 2009; whether it carries usable late-August status
is unverified. If not, that one ablation row is not testable and should be dropped rather than
faked.

**A null result is a likely outcome.** ADP is the aggregate of thousands of drafters and may already
encode most of what VOR recovers. "The category's central premise is unsupported" is a real finding
and the design should be sound enough to publish it — which is the point of gates G3 and G4.

## Next step

Approve, then UoW 1 through the AI-DLC Construction gates in `CLAUDE.md`. Prior plans preserved in
[archive/](archive/) — v1's nflverse and FFC data investigation was verified live and still holds.
