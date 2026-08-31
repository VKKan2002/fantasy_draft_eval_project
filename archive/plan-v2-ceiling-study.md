# How Forecastable Is Fantasy Football? — Plan

## The question

> **How much of the gap between preseason market expectation and realized fantasy outcome is
> availability (games missed) versus per-game production — and how much of each is predictable
> at all?**

The output is a **bound**: *"availability accounts for X% of outcome variance and is only Y%
predictable; production accounts for Z% and is only W% predictable; therefore no preseason model
can close more than N% of the gap the market leaves open."*

That is a falsifiable, quantitative claim about a ceiling. It is useful precisely because most
fantasy analytics projects assume the ceiling is high without ever measuring it.

## Why this question instead of "beat the market"

The obvious project is a model that drafts better than average draft position. The problem is that
its thesis — that meaningful forecastable signal remains — is an *assumption*, and it might be
wrong. Fantasy outcomes are dominated by injury and situation change, neither of which is
forecastable in August. A project built on that assumption can burn months and then discover the
achievable edge was inches wide.

This project measures the ceiling first. It is smaller, it cannot fail to produce a result (a low
ceiling is as publishable as a high one), and if the ceiling turns out to be high it hands the
follow-up project its exact target.

---

## Method, part 1 — the decomposition

This part is arithmetic, not modelling. That is deliberate: it is the core result and it should be
impossible to get subtly wrong.

For each player-season, realized total points factor exactly:

```
Y = G · P        Y = realized total (PPR)
                 G = games played
                 P = points per game played
```

The market's expectation comes from ADP. ADP gives a draft rank, not a projection, so map rank to
points empirically — `f(r) = ` mean realized total for players drafted at rank `r`, fit **only on
seasons before the target season**. Split it the same way:

```
E[Y] = f(r)                        market-implied expected total
E[G] = g(r, position)              market-implied expected games
E[P] = f(r) / g(r, position)       market-implied expected points per game
```

Then the error decomposes exactly, with no residual:

```
Y − E[Y] = (G − E[G]) · E[P]              ← availability effect
         + E[G] · (P − E[P])              ← production effect
         + (G − E[G]) · (P − E[P])        ← interaction
```

**Variance shares.** Because the three terms sum exactly to the total error, attribute variance by
covariance with the total rather than by raw variance:

```
share_k = Cov(term_k, Y − E[Y]) / Var(Y − E[Y])
```

These sum to exactly 1 by construction. Naive `Var(term_k) / Var(total)` does not, because the
terms are correlated — using it is the most likely way to produce a wrong headline number.

Also report **how much the market itself explains**, for context:

```
R²_market = 1 − Var(Y − E[Y]) / Var(Y − Ȳ)
```

Reported overall, per position, and per season.

## Method, part 2 — predictability, and the ceiling

Two small models, both walk-forward (train on seasons `< t`, predict `t`, expanding window):

| Model | Target | Features |
|---|---|---|
| **Availability** | games played `G` | prior 1–3 season games played, age, position, prior-season workload (touches/game), injury-report appearances and severity, rookie flag + draft round |
| **Production** | points per game `P` | prior per-game component rates, prior target share, team change, head-coach change, age, position |

Skill is measured **against the market-implied baseline**, not against zero:

```
skill_k = 1 − MSE(model) / MSE(market-implied baseline)
```

So `skill_availability = 0.15` means the model removes 15% of the squared error the market leaves
in the availability component. Then:

```
ceiling ≈ share_availability · skill_availability + share_production · skill_production
```

Interaction is reported separately and treated as unaddressed, which makes the ceiling a
**conservative lower bound** — an honest direction to err in.

LightGBM, point predictions. No quantile models, no Monte Carlo, no GPU. Residual spread is
reported but not modelled in v1.

---

## Data — four sources

Via **`nflreadpy`** (nflverse, MIT, CC-BY-4.0 data). Not `nfl_data_py`, which is the older
third-party package.

| Source | Loader / endpoint | Role |
|---|---|---|
| Player weekly stats | `load_player_stats(summary_level="week")`, 1999+ | Ground truth: realized points, games played, component rates |
| Schedules | `load_schedules()` | Bye weeks; **Week 1 kickoff date for the point-in-time gate** |
| Injuries | `load_injuries()`, 2009+ | Availability model features |
| ID crosswalk | `load_players()` / `load_ff_playerids()` | Join ADP names → `gsis_id` |
| ADP | `GET fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year={y}&position=all` | Market expectation. Free, 2007–2026, and its `meta` block exposes the draft window |

**Deliberately not used:** play-by-play, Next Gen Stats, PFR advanced, snap counts, combine,
contracts, FTN charting, and `load_ff_opportunity()`. Dropping play-by-play is what removes all
memory pressure — the pre-aggregated weekly table is a few hundred MB, and nothing in this project
needs 47,000 plays a season.

**Windows.** Models train on 2010–2025 (injury features require 2009+ history). The decomposition
and ceiling are computed on **2014–2025**, where 12-team PPR ADP pools are deep enough to be
meaningful. Population: QB/RB/WR/TE inside the draftable ADP range each season, roughly 150
players × 12 seasons ≈ 1,800 player-seasons for the decomposition, more for model training.

---

## The four hard gates

These are the ways this project could produce confidently wrong results. Each is a test, not a
guideline.

| # | Gate | Why it matters |
|---|---|---|
| **G1** | **Point-in-time ADP.** Admit a season only if the FFC `meta.end_date` precedes Week 1 kickoff from `load_schedules()`. | Verified: 2009 Non-PPR returns `end_date: 2010-06-20` — drafts held ten months *after* the season ended. Using that as "market expectation" is catastrophic leakage. Non-negotiable. |
| **G2** | **ID resolution ≥ 97%** of top-150-by-ADP rows resolve FFC name → `merge_name` → `mfl_id` → `gsis_id`. Unmatched rows emitted to a manual override table. | A silent join failure is the most likely path to a plausible-looking wrong answer. |
| **G3** | **Decomposition identity.** Unit test asserting the three terms sum to `Y − E[Y]` to floating-point tolerance, and the three variance shares sum to 1.0. | The core result is an algebraic identity, so it can be tested as one. |
| **G4** | **Walk-forward isolation.** Assert that for every fold, `max(train_seasons) < test_season` — including inside the rank→points mapping `f` and the games baseline `g`. | The mapping is the easiest place to leak, because it feels like a lookup table rather than a fitted model. It is a fitted model. |

`ingest_manifest` records source URL, fetch time, row count, and sha256 per pull. nflverse
retroactively corrects historical stats, so today's 2019 table is not byte-identical to 2019's.

---

## Warehouse (DuckDB, single file)

```
dim_player           (player_key PK, gsis_id, mfl_id, name, merge_name, position, birthdate,
                      draft_year, draft_round)
fact_player_week     (player_key, season, week, team, opponent, active, <raw stat counters>)
fact_injury_report   (player_key, season, week, status, designation, body_part)
fact_adp             (season, format, teams, player_key, adp, stdev, times_drafted,
                      window_start, window_end, is_pre_kickoff)
dim_season           (season, week1_kickoff)

market_baseline      (season, adp_rank, position, exp_total, exp_games, exp_ppg)
decomposition        (season, player_key, Y, G, P, exp_*, term_availability,
                      term_production, term_interaction)
variance_shares      (season, position, share_availability, share_production,
                      share_interaction, market_r2, n)
predictions          (model, season, player_key, target, predicted, actual)
skill_summary        (model, season, position, mse_model, mse_baseline, skill)
ingest_manifest      (dataset, source_url, fetched_at, row_count, sha256)
```

Counters, not points — points are a pure function of (counters × scoring profile), so persisting
counters keeps other scoring formats available for free later. v1 reports PPR only.

**No Postgres.** There is no mutable state in this project; every table above is read-only
analytical output. A single DuckDB file shipped as a release asset is the correct store, and adding
a Postgres container would be decoration. Easy to add later if the app grows a feature that writes.

---

## The app — minimal, three endpoints, one page

```
apps/web (React + TS, one page)  ──►  FastAPI  ──►  DuckDB (read-only file)
```

```
GET /decomposition?season=&position=   → variance shares + market R² + n
GET /ceiling                            → headline bound, skill per component
GET /players/{gsis_id}/seasons/{season} → expected vs realized, three-way split
```

One page, three things on it: the variance breakdown, a scatter of market-expected vs realized
total coloured by games played (the visual punchline — the vertical spread *is* the unforecastable
part), and a player lookup showing any individual season's split.

All queries hit precomputed tables, so p95 is a few milliseconds and no caching layer is needed.
Docker Compose locally; Fly.io or Render for the API; Vercel or Cloudflare Pages for the web app.
`uv` for env management. Free-tier viable.

---

## Units of work

| UoW | Scope | Gates |
|---|---|---|
| **1** | Data foundation — ingest four sources, ID crosswalk, DuckDB build, manifest | G1, G2 |
| **2** | Decomposition — market baseline, three-way split, variance shares | G3, G4 |
| **3** | Predictability — availability + production models, walk-forward, ceiling | G4 |
| **4** | App — three endpoints, one page, deploy | — |

UoW 1 is the largest by a wide margin. UoW 2 is a few hundred lines and produces the headline
result, so **the project has a defensible finding before either model is written.** That ordering is
intentional: if the decomposition shows availability dominates and the market already tracks
production well, UoW 3 gets rescoped rather than built on spec.

## Repo layout

```
docs/
  00-question.md  10-method.md  20-data-sources.md  30-findings.md
src/ffceiling/
  ingest/    nflverse.py  adp_ffc.py  ids.py  manifest.py
  warehouse/ ddl.sql  build.py
  analysis/  baseline.py  decompose.py
  models/    availability.py  production.py  walkforward.py
  api/       main.py
  cli.py
apps/web/    tests/    pyproject.toml    README.md
```

---

## What was dropped from the previous plan, and why

| Dropped | Reason |
|---|---|
| Draft simulator, opponent model, Plackett–Luce calibration | No drafting means none of it is needed |
| Policy ladder Tiers 0–3, Monte Carlo rollouts, backward induction | The decision layer was a second project |
| Committed-vs-clairvoyant lineup problem | Evaporates — the unit of analysis is a player-season, not a roster |
| Quantile models, Monte Carlo composition, games-played distribution | Point predictions suffice for a variance bound |
| Play-by-play, NGS, PFR advanced, snaps, combine, contracts, FTN | Not needed for these two targets; removing pbp removes all memory pressure |
| Common random numbers, paired bootstrap, hindsight oracle | Artifacts of policy comparison. The *ceiling* is the oracle idea, kept in a cheaper form |
| Postgres | No mutable state exists |
| 10 units of work → 4 | Direct consequence of the above |

**Kept, because they were right regardless:** counters over points, walk-forward CV only,
point-in-time ADP gating, the ID-resolution gate, the ingest manifest, and no LLM anywhere near
the prediction path — an LLM has memorized these seasons, so asking it to project 2019 is asking
it to recall 2019.

---

## Honest risks

**The result may be undramatic.** The likely finding is that availability is a large share of
variance and only weakly predictable. That is a real, useful, slightly deflationary result. It is
worth stating up front that "the ceiling is low" is the *expected* outcome, not a failure — the
project is designed so that outcome still yields a publishable number.

**Novelty is in the synthesis, not the parts.** Injury rates by position, and year-over-year
fantasy inconsistency, have both been written about. The three-way variance decomposition against a
point-in-time market baseline, combined with a walk-forward predictability bound, is what has not
been cleanly published. Do not overclaim beyond that.

**Sample is small for season-level claims.** Twelve seasons means roughly twelve independent draws
of season-level shocks. Player-season sample is ~1,800, which is fine for the decomposition and
thin for the models. Report per-season shares with wide intervals; bootstrap blocked by season, not
by player.

**`E[P] = f(r) / g(r, position)` is a modelling choice, not a fact.** The market does not publish a
per-game expectation, so this construction imputes one. A sensitivity check — recomputing shares
under an alternative split — belongs in UoW 2.

## Next step

Approve this, then UoW 1 goes through the AI-DLC Construction gates in `CLAUDE.md`. The previous
plan is preserved at [plan-archive-draft-engine.md](plan-archive-draft-engine.md) — its data
investigation section stays useful, since the nflverse and FFC findings were verified live and
still hold.
