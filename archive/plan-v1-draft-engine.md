# Fantasy Draft Decision Engine — AI-DLC Inception Phase

## Context

The goal is a legitimate data-science/ML project that answers a falsifiable question:

> **Can a model that jointly reasons about expected production, positional scarcity, roster
> construction, league settings, and remaining player supply make measurably better draft
> decisions than following ADP or expert consensus rankings?**

Not a ranking site. The deliverable is a **backtest with a defensible methodology**: simulate
drafts for historical seasons using only information available before Week 1, then score the
resulting rosters against what actually happened that season, and compare against baseline
drafting strategies under identical conditions.

The repo is currently empty (one initial commit, a `.gitattributes`). This plan covers the
**AI-DLC Inception phase only**: design artifacts plus one small, read-only *data feasibility
spike* that empirically proves or disproves the data assumptions before any substantial code is
written. Construction is a separate approval gate.

### Confirmed decisions

| Decision | Choice |
|---|---|
| League scope | 12-team PPR canonical spine; formats × sizes sweep as robustness |
| Positions modeled | QB/RB/WR/TE modeled; K/DST drafted from ADP (occupy real picks/slots) |
| Stack | FastAPI + Postgres + React/TS, Dockerized |
| Hardware | **8 GB RAM, no GPU** — hard constraint, drives several architecture choices |
| Decision layer | Tiered ladder with ablations, Tier 3 gated on a compute benchmark |

---

## Data investigation — findings

All of the following was verified live against the actual APIs and docs, not assumed.

### nflverse — primary source. Confirmed sufficient.

Access via **`nflreadpy`** (nflverse org, MIT, Polars-native, Python). It is the maintained
Python port of `nflreadr`; `nfl_data_py` is the older third-party package and should not be used.
Data is CC-BY-4.0. All 23 loaders confirmed present with these coverage windows:

| Loader | Coverage | Role in project |
|---|---|---|
| `load_player_stats(summary_level="week")` | **1999+** | **Ground truth for realized fantasy points.** 148 cols |
| `load_team_stats()` | 1999+ | DST scoring, team context |
| `load_pbp()` | 1999+ | Derived features (red zone, air-yard depth, pace, expected TD) |
| `load_players()` / `load_ff_playerids()` | all | ID crosswalk (gsis/mfl/pfr/pff/espn/yahoo/fantasypros/sleeper + `merge_name`) |
| `load_rosters_weekly()` | 2002+ | Roster churn → target/carry vacancy features |
| `load_depth_charts()` | 2001+ | Depth position at draft time |
| `load_injuries()` | 2009+ | Availability model |
| `load_snap_counts()` | 2012+ | Snap share, route participation proxy |
| `load_nextgen_stats()` | 2016+ | Separation, air yards, rush efficiency |
| `load_pfr_advstats()` | 2018+ | Advanced receiving/rushing |
| `load_draft_picks()` | **1980+** | Draft capital for rookies |
| `load_combine()` | all | Rookie athletic profile |
| `load_schedules()` | all | **Bye weeks** (essential), coaches, Vegas lines |
| `load_contracts()` | all | OverTheCap — contract-year / investment signal |
| `load_ff_opportunity()` | 2006+ | Expected points — **benchmark only, see leakage note** |
| `load_ff_rankings(type="all")` | archive, depth TBD | FantasyPros ECR baseline |
| `load_ftn_charting()` | 2022+ | **Excluded from v1** — see licensing note |

`load_player_stats` already returns the pre-aggregated player-week table with
`fantasy_points`, `fantasy_points_ppr`, `targets`, `target_share`, `air_yards_share`, `wopr`,
`racr`, `pacr`, EPA columns, per-play threshold counts, full kicking (`fg_made` by distance
bucket, `pat_made`) and full defensive counters. **This means we rarely need raw play-by-play** —
a major win on 8 GB.

> Note: the legacy `player_stats` nflverse release was deprecated 2025-08-01 in favour of
> `stats_player`. `nflreadpy.load_player_stats()` targets the new release. Do not hardcode the
> old asset paths.

### ADP — the critical non-nflverse dependency. Solved.

nflverse has **no ADP**, and ADP is required twice over: as the baseline to beat, and as the
opponent model that makes simulated drafts realistic.

**Fantasy Football Calculator's free REST API is the answer.**
`GET https://fantasyfootballcalculator.com/api/v1/adp/{format}?teams={n}&year={y}&position=all`

- Formats: `ppr`, `half-ppr`, `standard`, `2qb`, plus dynasty/rookie. Sizes: 8/10/12/14. Years: **2007–2026.**
- Per player: `adp`, `adp_formatted` (round.pick), `stdev`, `high`, `low`, `times_drafted`, `bye`, `position`, `team`.
  The `stdev`/`high`/`low` fields are what make a *probabilistic* opponent model and
  survival-probability estimates possible at all.
- Crucially, the response `meta` block exposes `start_date` / `end_date` for the draft window,
  which gives us an **auditable point-in-time gate**. Verified 12-team PPR windows:

| Season | Window | Drafts | Players |
|---|---|---|---|
| 2012 | Sep 4–5 | 303 | 90 |
| 2014 | Aug 31–Sep 1 | 635 | 173 |
| 2016 | Sep 1–2 | 956 | 170 |
| 2019 | Sep 2–4 | 2,167 | 176 |
| 2021 | Aug 31–Sep 1 | 1,709 | 176 |
| 2024 | Aug 31–Sep 1 | 1,371 | 175 |
| 2025 | Aug 25–Sep 1 | 8,470 | 200 |

All tight, all pre-kickoff. **But the gate is not optional** — a low-volume cell
(2009 Non-PPR) returned `end_date: 2010-06-20`, i.e. drafts held *ten months after the season
ended*. Using that as a "draft-time" baseline would be catastrophic leakage. Rule: admit a cell
only if `end_date < Week 1 kickoff` from `load_schedules()`.

**Backtest window: 2014–2025 (12 seasons).** 2012–2013 pools are too thin (90 players won't
fill a 180-pick draft).

### Rejected: MyFantasyLeague ADP as primary

MFL's ADP export (`api.myfantasyleague.com/{year}/export?TYPE=adp`) is attractive because its
`id` field is `mfl_id`, the primary key of `ff_playerids` — a clean join with no name matching —
and it returns deeper pools (340–413 players). **But its documented `TIME` cutoff parameter does
not work.** Verified: `TIME=1562025600` (July 2 2019) and `TIME=1567382400` (Sept 2 2019)
returned byte-identical results (3,575 drafts, 1,211 picks, 369 players, same top 3). And 2010
returns zero drafts. So it offers no point-in-time control and shallow history. **Demoted to a
secondary cross-check** for pool depth in deep leagues, with the bleed caveat documented.

### Gaps, accepted with mitigations

| Gap | Mitigation |
|---|---|
| No free historical **projections** | ADP *is* market consensus (the aggregate of everyone's projections) and is the stated target to beat. ECR archive via `load_ff_rankings(type="all")` is a secondary baseline — **archive depth is unverified**, so it is best-effort, not load-bearing. |
| No **college production** for rookies | Rookie model uses draft capital + combine + landing-spot vacancy, which carries most of the preseason signal. CollegeFootballData API (free key, Patreon tiers for heavy use) is a v2 add. |
| No **preseason** Vegas win totals | `load_schedules()` lines are game-time, not draft-time. Proxy team quality with prior-season pbp aggregates + coaching change. |
| `load_ff_opportunity()` **leaks** | Its xgboost was trained on 2006–2020 pbp, so its outputs encode future knowledge for any pre-2021 backtest. **Re-derive expected points in-house with walk-forward training; use ffopportunity only to validate the reimplementation.** |
| FTN charting is **CC-BY-SA 4.0** | Copyleft share-alike on a deployed app is a licensing hazard, and 2022+ coverage can't support a 2014–2025 backtest anyway. Excluded from v1. |

---

## Ten architectural decisions

These are the load-bearing choices; everything downstream follows.

1. **Store stat counters, never fantasy points.** Points are a pure function of
   (counters × scoring profile). Persisting counters makes arbitrary league settings free and
   avoids a combinatorial explosion of derived tables.

2. **Realized-season evaluation is a table lookup, not a simulation.** When scoring a *completed*
   backtest draft, the season already happened — outcomes are known. Build a dense
   `realized_points[player_idx, week]` matrix per (season, scoring profile); score a roster with
   a masked top-k per week in numpy. Only the *policy's internal lookahead* needs stochastic
   outcomes. **This is the single biggest reason the project fits in 8 GB and runs in hours
   instead of days.**

3. **Team value = Σ_weeks (best legal starting lineup that week)**, not the sum of season
   projections. Only the weekly formulation handles bye collisions, games missed, and FLEX
   substitution — and those are exactly what roster construction is about.

4. **Model scoring-agnostic per-game component rates, then compose.** Predict volume and
   efficiency components (targets/g, carries/g, yards/target, TD rate, …) rather than points
   directly, then compose into points under any scoring profile. One model serves PPR, Half, and
   Standard; more data-efficient and more interpretable. Direct-points models kept as a benchmark.

5. **Distributional predictions, not point projections.** LightGBM multi-quantile
   (τ ∈ {.05,.1,.25,.5,.75,.9,.95}) plus a **separate games-played model**, composed by Monte
   Carlo. Draft decisions depend on risk and upside, and distributions let us *test* calibration
   (PIT, interval coverage, CRPS) rather than just point error.

6. **Two model variants + a residual target.** A **market-free** model (no ADP/ECR features) and
   a **market-augmented** one, plus a model predicting *actual minus market-implied*. This is the
   direct answer to "do we add information beyond ADP?" — the actual research question.

7. **Walk-forward CV only.** Train on seasons `< t`, predict `t`, expanding window. Random K-fold
   would leak across seasons and is the classic way these projects fool themselves.

8. **No LLM in the prediction path — and a hard reason.** Beyond GBMs dominating on tabular data
   at this scale (~6k relevant player-seasons), **an LLM has memorized the 2014–2024 NFL seasons.
   Asking it to "project" 2019 is asking it to recall 2019.** That makes an honest historical
   backtest impossible. LLMs are confined to non-predictive surfaces (natural-language
   explanation of a recommendation the model already made).

9. **Out-of-core by default.** Polars `scan_parquet` + DuckDB with `SET memory_limit='2GB'`.
   Play-by-play processed **one season at a time with column projection** (~25 of 372 columns) —
   47–48k plays/season verified, so 27 seasons × 372 cols would be ~3.8 GB in memory but is
   ~250 MB pruned. No single pipeline step may exceed 2 GB peak RSS. No PyTorch anywhere.

10. **Paired evaluation with common random numbers.** Every policy in a given cell faces the
    *identical* sequence of opponent draws. Paired comparison kills most of the variance, which
    matters enormously given how noisy fantasy outcomes are.

---

## The decision layer — tiered ladder

Prediction gives each player a distribution. The decision layer turns distributions into a pick,
and it is where the project's contribution lives. Built as a ladder so the ablation reveals
*which rung earns the edge*:

- **Tier 0 — Greedy projections.** Take the highest predicted total. Deliberately naive control.
- **Tier 1 — Roster-aware VOR.** Value = marginal improvement to *my* expected starting lineup,
  with replacement level derived from league settings (starter demand per position given teams,
  slots, FLEX rules). Handles positional scarcity and roster construction. Nearly free to compute.
- **Tier 2 — Availability-aware / opportunity cost.** Adds P(player survives to my next pick),
  fitted from the ADP `adp`/`stdev`/`high`/`low` distribution. Trades value against
  scarcity-in-time. Still analytic and cheap (<50 ms).
- **Tier 2.5 — Backward-induction lookahead.** Dynamic program over remaining rounds × roster
  states using the *distribution of best-available-by-position* implied by ADP survival. Captures
  most of the lookahead benefit at `O(rounds × states)` instead of `O(candidates × rollouts × picks)`.
  **This is the pragmatic answer to the 8 GB / no-GPU constraint.**
- **Tier 3 — Monte Carlo lookahead.** For each candidate: draft them, roll the rest of the draft
  forward many times (opponents from the ADP model, self from Tier 2), simulate the season from
  *predicted* distributions, take the argmax expected outcome. **Gated on spike check S6.**
  Vectorized numpy with integer arrays, common random numbers, and successive halving to drop
  dominated candidates early; Numba JIT on the inner loop if the benchmark demands it.

Baselines to beat: ADP-follow, ADP + positional-need heuristic, ECR-follow (where archive
allows), static VOR on prior-season points, random.

Plus a **hindsight oracle** that drafts with perfect knowledge. It bounds how much edge even
exists, which converts a bare "+3%" into the far more honest "*captured 18% of the achievable
edge*."

---

## Opponent model — and how we validate it

If simulated opponents are unrealistic, the whole backtest is theatre. Model each opponent pick
as a Plackett–Luce / softmax draw over available players weighted by ADP rank, constrained by
plausible positional need (nobody drafts a 4th QB in round 6), with temperature calibrated per
(format, size, season).

**Validation gate:** run many simulated drafts and check that the *emergent* per-player mean draft
position and standard deviation reproduce FFC's observed `adp` and `stdev`. That is a concrete,
falsifiable test that the opponent model is faithful.

---

## Evaluation protocol

**Unit of analysis:** a cell = (season, format, league size, draft slot, seed). Our policy occupies
one slot; all other seats run the ADP opponent model. Every policy is replayed against the same
seeded opponent draws.

**Prediction-layer metrics** (is the model any good?)
Spearman/Kendall τ vs realized (overall and within position) · top-N precision (of predicted top-24
RBs, how many finished top 24) · MAE/RMSE · **CRPS** (proper scoring rule) · calibration via PIT
histogram and 80/90% interval coverage · **all benchmarked against ADP-implied rank and ECR.**

**Decision-layer metrics** (do better predictions produce better teams?)
Realized starting-lineup points · **head-to-head regular-season win %** in the simulated league
using real weekly scores · playoff-qualification and championship rates · final rank distribution ·
paired Δ vs ADP baseline with **block-bootstrap CIs blocked by season**.

**Headline output:** the ablation ladder (Tier 0 → 3) with confidence intervals and the oracle
bound.

**Statistical honesty, stated up front.** Twelve seasons means the effective independent sample for
season-level shocks is ~12, so season-level effects must be reported with wide intervals and no
p-hacking across the format sweep. Power comes from the cross-product of formats × sizes × slots ×
seeds *and* from the paired design — never from pretending correlated cells are independent.

---

## Warehouse schema (DuckDB + Parquet lake)

```
dim_player          (player_key PK, gsis_id, mfl_id, pfr_id, name, merge_name, position,
                     birthdate, draft_year, draft_round, draft_pick, college)
dim_team, dim_season, dim_week
dim_scoring_profile (profile_id, per-stat coefficients)
dim_league_settings (settings_id, teams, roster slots, flex rules, rounds, profile_id)

fact_player_week    (player_key, season, week, season_type, team, opponent, <raw counters>)
fact_team_week      (team, season, week, <team + DST counters>)
fact_snap_counts, fact_depth_chart, fact_injury_report, fact_ngs, fact_pfr_adv
fact_adp            (source, format, teams, season, player_key, adp, stdev, high, low,
                     times_drafted, window_start, window_end, is_pre_kickoff)
fact_ecr            (source, scrape_date, season, player_key, ecr, sd, best, worst)

feature_player_season (player_key, season, as_of_date, <~100 point-in-time features>)
pred_player_season    (model_id, season, player_key, quantile, value)
model_registry        (model_id, kind, train_seasons, hyperparams, git_sha, artifact_uri, metrics)

sim_draft   (sim_id, season, format, teams, slot, policy_id, seed)
sim_pick    (sim_id, pick_no, team_slot, player_key)
sim_result  (sim_id, team_slot, policy_id, realized_points, wins, rank, made_playoffs, champion)
experiment, experiment_cell   -- eval harness bookkeeping
ingest_manifest (dataset, source_url, fetched_at, row_count, sha256)
```

`ingest_manifest` is what makes runs reproducible and makes "did the upstream data change?"
answerable — relevant because **nflverse retroactively corrects historical stats**, so today's
2019 table is not byte-identical to 2019's 2019 table.

---

## Feature spec (all `as_of` = season kickoff)

**Player:** age, position, experience · prior 1/2/3-season per-game component rates · trailing
target share, air-yards share, WOPR, RACR · red-zone touches/targets · snap share, route
participation (2016+) · efficiency (YPC, YPT, EPA/play) · **TD rate vs expected TD rate**
(regression-to-mean signal) · games missed last 1–3 seasons · injury-report frequency and severity.

**Team context:** pass rate over expectation · plays/game (pace) · red-zone trips · O-line proxy
(sack rate, adjusted line yards from pbp) · QB quality for pass catchers · team change ·
**head-coach change** · and **target/carry vacancy** — the summed prior-season target and carry
share of departed teammates, computed by diffing `load_rosters_weekly`. Vacancy is one of the
strongest known preseason signals and must be in v1.

**Market:** ADP, ADP stdev, ECR, ECR sd — present only in the market-augmented variant.

**Rookies:** draft round/pick, combine metrics, landing-spot vacancy, team offense quality.

---

## Deployment architecture

```
apps/web (React + TS)  ──►  FastAPI  ──►  Postgres      (mutable draft-room state)
                                     └─►  DuckDB (RO)   (analytics + precomputed value tables)
                                     └─►  model artifacts (LightGBM boosters)

GitHub Actions cron ──► refresh nflverse + ADP ──► retrain ──► publish DuckDB + artifacts as release asset
```

**Latency budget:** precompute per-(format, size) value tables offline. At request time run a
*bounded* lookahead with a hard wall-clock budget, degrading Tier 3 → Tier 2.5 → Tier 2 if
exceeded. Target p95 < 1.5 s for `/recommend`. The tiered ladder is therefore not just a research
artifact — it is the production fallback chain.

**API surface:** `POST /leagues` · `POST /drafts` · `POST /drafts/{id}/picks` ·
`GET /drafts/{id}/recommendations` (ranked, each with marginal value, P(available next pick),
replacement baseline, risk band, and an explicit **"vs. what ADP would say"** diff) ·
`GET /players/{id}/projection` · `GET /experiments` (exposes the backtest results as a first-class
surface, since the research *is* the product's credibility).

**Infra:** Docker Compose locally; Fly.io or Render for the API; Neon or Supabase for Postgres;
Vercel or Cloudflare Pages for the web app. `uv` for env management. All free-tier viable.

---

## Repo layout

```
docs/aidlc/
  00-intent.md
  inception/    10-requirements.md  11-user-stories.md  12-units-of-work.md
                13-data-feasibility-report.md        ← generated by the spike
  construction/ 20-logical-architecture.md  21-domain-model.md  22-data-sources.md
                23-warehouse-schema.md  24-feature-spec.md  25-model-spec.md
                26-simulation-protocol.md  27-evaluation-protocol.md  28-leakage-controls.md
  operations/   30-deployment-architecture.md
src/fdraft/
  ingest/   nflverse.py  adp_ffc.py  ids.py  manifest.py
  scoring/  profiles.py  engine.py
  warehouse/ ddl.sql  build.py
  features/  models/  sim/{draft,opponents,season}.py  eval/  api/  cli.py
spikes/data_feasibility/
  s1_nflverse_coverage.py  s2_adp_windows.py  s3_id_resolution.py
  s4_pool_depth.py  s5_signal_floor.py  s6_compute_budget.py
apps/web/   tests/   pyproject.toml   README.md
```

---

## Units of Work (AI-DLC)

| UoW | Scope | Bolt |
|---|---|---|
| 1 | Data foundation — ingest, manifest, ID resolution, warehouse | 1 |
| 2 | Scoring engine — settings → points, property-tested | 1 |
| 3 | Feature pipeline + leakage test suite | 2 |
| 4 | Outcome models — component rates, games played, composition, walk-forward CV | 2 |
| 5 | Draft simulator — opponent model, array rollouts, realized-season evaluator | 3 |
| 6 | Policy ladder — Tiers 0–3 | 3 |
| 7 | Experiment harness — paired CRN grid, bootstrap, ablation, oracle | 3 |
| 8 | FastAPI service | 4 |
| 9 | React draft-room app | 4 |
| 10 | Ops — CI, cron refresh, deploy, monitoring | 4 |

---

## Scope of THIS phase

Design docs above, written to `docs/aidlc/`, **plus one read-only spike** — the empirical gate
that must pass before Construction starts. This is the "make sure the data is sound first" ask.

| # | Check | Gate |
|---|---|---|
| **S1** | Pull every loader; record min/max season, row counts, null rates on key columns, peak RSS, wall time | player_stats weekly 1999–2025; snap_counts through 2025 (release description reads "Last Updated 2022" — **verify**); injuries 2009–2025; **no step > 2 GB peak RSS** |
| **S2** | FFC ADP across {ppr, half-ppr, standard, 2qb} × {8,10,12,14} × 2007–2025; record every `meta` window | Emit the admissibility matrix under `end_date < Week 1 kickoff`. Expect 12-team 2014–2025 to pass |
| **S3** | FFC names → `ff_playerids.merge_name` → `mfl_id` → `gsis_id` → player_stats | **≥97%** of top-150-by-ADP rows resolve; emit unmatched list → manual override table. Handle DST (team abbr) and K separately |
| **S4** | Per admissible cell: `picks_required = size × rounds` vs `players_available` | 100% for the canonical config; document shortfalls (14-team × 15 rounds = 210 picks vs ~200 available **will** fall short) |
| **S5** | **Signal floor.** Spearman(ADP rank, realized points) per season/position; same for trivial baselines (prior-season PPG); compute the oracle gap | Informational, and **the most important output of the whole phase** — it tells us how efficient the market already is and how much headroom exists *before* building anything |
| **S6** | Micro-benchmark the array-based rollout + realized-season lineup evaluator | **≥5,000 rollouts/sec/core**, and full canonical grid (12 seasons × 12 slots × 20 seeds × 5 policies) projected **< 6 h single-threaded**. Tier 3 is descoped to Tier 2.5 if this fails |

The spike touches no production code paths, writes only to `spikes/` output and the report, and
is intended to run in well under an hour on the target machine.

---

## Verification

1. `uv run python -m spikes.data_feasibility.run_all` → writes
   `docs/aidlc/inception/13-data-feasibility-report.md` with every number above, plus a
   PASS/FAIL line per gate.
2. **Read S5 first.** If ADP's Spearman against realized points is already very high and trivial
   baselines are close behind, the honest conclusion may be that the achievable edge is small —
   and the project should then be framed around *quantifying and explaining* market efficiency,
   which is still a real result. That reframing decision belongs to you, before Construction, not
   after.
3. Confirm S2's admissibility matrix matches the 2014–2025 assumption; if fewer cells pass,
   the backtest window shrinks and the eval power section needs revising.
4. Confirm S3's match rate. A silent ID-join failure is the single most likely way this project
   produces confidently wrong results, so this gate is non-negotiable.
5. Review S6's projection against your patience. It decides whether Tier 3 ships in v1.
6. Review the design docs; **Mob Elaboration** on anything contested; then approve Bolt 1
   (UoW-1 + UoW-2) as the first Construction increment.

## Open items carried into Construction

- `load_ff_rankings(type="all")` archive depth — unverified. Determines whether the ECR baseline
  exists at all. ADP baseline does not depend on it.
- `load_schedules()` betting-line and coach column names — unverified (docs render dynamically).
  Not load-bearing; bye weeks are the only critical field.
- `load_snap_counts()` currency through 2025 — release description suggests staleness.
- v1 assumes **no waivers, trades, or in-season management.** This isolates draft quality, which
  is the question, but caps external validity and must be stated in any write-up.