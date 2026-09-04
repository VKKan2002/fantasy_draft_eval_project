# Findings

Sections 1-7 measured on 2026-08-30, section 8 on 2026-09-03, all against live data. Each number names the script that
produces it, so all of it is reproducible rather than remembered.

Seasons 2014–2025, 12-team PPR, point-in-time ADP only.

---

## 1. Data integrity

`checks/g2_id_resolution.py`, `checks/g2_verify_aliases.py`

| Check | Result |
|---|---|
| FFC ADP name → `gsis_id` | **100%** of 2,065 player-seasons |
| Name collisions broken by production | **81** |
| Nickname aliases needed | **6** |
| Drafted players who never played | 15 (0.8%) — genuine, not join failures |

**Two bugs the gate caught.** Both would have produced plausible wrong answers rather than
crashing, which is the dangerous kind.

*Collisions.* Suffix stripping maps "Frank Gore Jr." and "Frank Gore" to the same key. The
first version silently kept whichever row came first, crediting a Hall-of-Fame back's
season to his son. This happened **81 times** across different players. Fixed by breaking
ties on who actually recorded snaps in the target season.

*Nicknames.* FFC's display names don't always match nflverse. Six cases, and no string
heuristic finds the important one — "Hollywood Brown" is Marquise Brown. Solved by
proposing candidates from `(team, season, position)` roster evidence instead: Marquise
Brown had 4 seasons of support at 175.5 avg PPR against a next-best 2 at 89.8, and the FFC
team path BAL→BAL→ARI→ARI→KC matches his actual career.

**Rule adopted:** never add an alias from memory. A wrong alias credits one player's season
to another, which is worse than leaving the row unmatched.

**Availability vs join failure must be separated.** Le'Veon Bell held out all of 2018; Ray
Rice and Josh Gordon were suspended; A.J. Green, Jerick McKinnon and Gus Edwards had
season-ending injuries. Those are true zeros. Counting them as join failures makes the gate
unpassable, which is what the first version did.

## 2. ADP is measured before kickoff — but verify every season

Every FFC ADP window closed before Week 1: **12/12 seasons pass.** 2015 clears by a single
day (Sep 9 window end vs Sep 10 kickoff), which is why this is checked and not assumed.

The counter-example that makes it non-optional: the 2009 Non-PPR cell returns
`end_date: 2010-06-20` — drafts held ten months *after* the season ended. Using that as
"draft-time market consensus" would be catastrophic leakage.

**Rule:** admit a season only if `meta.end_date < Week 1 kickoff` from `load_schedules()`.

## 3. The draft market is efficient (abandoned direction, kept for the record)

| Measure | ADP | "Rank by last season's points" |
|---|---|---|
| Within-position Spearman vs realized | **0.634** | 0.528 |
| Seasons won | **12 / 12** | 0 |

ADP beats the naive baseline in every season by a mean of +0.105. The market is doing real
work, so "build a better projection model" is a poor bet.

**Methodological trap worth remembering.** Pooled across positions, ADP scores only 0.375
and *loses* to the naive baseline. That is Simpson's paradox: QBs average 252 PPR against
TEs at 147, so ranking everyone by raw points inherits the position ordering for free. ADP
deliberately deviates from raw points to price scarcity — QBs are drafted latest despite
scoring most.

Checking what that "winning" baseline would actually draft: **nine quarterbacks in the
first fifteen picks of 2022.** You can start one.

**Lesson: correlation with realized points cannot evaluate a draft strategy.** A strategy
can score better on a spreadsheet and lose every week, because correlation is blind to
roster constraints.

## 4. Start/sit headroom — the decisive measurement

`checks/step1_baseline.py`, `step1b_ceiling.py`, `step1c_matchup.py` · 144 team-seasons

| Who sets the lineup | Points/season | Captured |
|---|---|---|
| Random | 1,521 | 85.1% |
| Best simple rule — season average shrunk toward preseason rank | **1,631** | **91.2%** |
| + perfect matchup knowledge | 1,645 | 92.0% |
| Cheater who knows true player ability | 1,671 | 93.4% |
| **Cheater with perfect ability AND matchup** | **1,681** | **94.0%** |
| Perfect hindsight | 1,789 | 100% |

The 267-point decision space splits three ways:

| Component | Points | Share |
|---|---|---|
| Simple rules already capture | 110 | 41% |
| Addressable by better information | **49** | **18%** |
| Irreducible week-to-week luck | 108 | 40% |

**Perfect information is worth 49 points a season — 2.9 points a week out of ~96.**
95% CI [44, 54], bootstrapped blocked by season.

Rule comparison (all within 35 points of each other):

| Rule | Captured |
|---|---|
| shrink to preseason rank | 91.2% |
| season average | 91.0% |
| 50/50 blend | 90.9% |
| last 3 games | 90.6% |
| preseason ADP only, never updated | 90.0% |
| last 1 game | 89.3% |

Two things fall out. Ignoring in-season data entirely costs only 23 points. And **chasing
last week's performance is worse than ignoring everything** — the recency rule finishes
last.

**Detectability.** The per-team-season sd of the gain is 38.6 points, so:

| To detect | Team-seasons needed |
|---|---|
| Perfect information (+49) | 5 |
| A very good system (+25) | 19 |
| A realistic system (+15) | **53** |

A live single-season test gives you **one**. So a start/sit system's edge cannot be
validated by using it for a season, regardless of whether it works.

## 5. Lineup scoring has a bias worth knowing about

`src/ffeval/scoring/lineup.py`

Scoring a roster with hindsight-optimal weekly lineups inflates results. Two coin-flip
players scoring 5 or 25: committing in advance averages 15, always starting the one who
boomed averages 20. The phantom 5 scales with variance.

Measured on a real 2019 roster: **committed 1,422 points vs clairvoyant 1,644 — a 15.6%
premium** that no real manager can earn.

Because volatility preference is exactly what strategies differ on, reporting only the
clairvoyant number biases any comparison. Both rules are always computed.

## 6. Data source notes

**nflreadpy 0.1.5** (not `nfl_data_py`). 25 loaders. All 12 seasons of weekly player stats
= 217,490 rows, 155 MB, 1.6 s to load, 223 MB peak RSS. Pre-aggregated, so play-by-play is
never needed — which removes all memory pressure on 8 GB.

A row exists only if the player was active. **No row = bye or inactive; a 0.0 row means he
played and scored nothing.** That distinction is the availability signal.

Regular season runs weeks 1–17 through 2020 and 1–18 from 2021.

**FFC ADP API** — free, no key: `GET fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year={y}&position=all`
Returns `adp`, `stdev`, `high`, `low`, `times_drafted`, `bye`, plus a `meta` block with the
draft window. Skill-position pool depth by season: 146 (2022) to 206 (2025).

**Available for the live agent**, all verified present:

- 2026 schedule already published, Week 1 on **September 9–10, 2026**
- `spread_line`, `total_line`, moneylines, `roof`, `surface`, `temp`, `wind`, coaches
- `load_injuries()` 2009+: `report_status` (Out/Questionable/Doubtful) plus
  `practice_status` and injury descriptions

Note the asymmetry: betting lines are set at game time, which is leakage for a draft-time
model but perfectly legitimate for a Sunday-morning lineup decision.

## 7. How to tell in advance whether a project can be evaluated

The meta-lesson. Four questions, applied before building:

1. Do you learn the right answer quickly and unambiguously?
2. How many **independent** observations do you get?
3. Is the baseline you're beating actually bad?
4. Is the effect large relative to the noise?

Fantasy football fails 2, 3 and 4. Twelve seasons is twelve independent draws, ADP is
already good, and the effects are a few points against a 180-point spread.

Four project directions died on this, all of which would have been visible in an hour of
checking rather than a day of building.

## 8. The deterministic claim checker — the auditor's floor

`src/ffeval/audit/evaluate.py --baseline` · 1 packet (Josh Allen, 2025 week 3), 30 labelled
claims

Before building an LLM auditor, a regex that only reads numbers was measured against the same
labelled set. It extracts every number from a sentence and asks whether the packet contains it.

| | this checker | always say "supported" |
|---|---|---|
| Recall on unfaithful claims | **33%** (5 of 15) | 0% |
| False alarms on supported claims | 10% (1 of 10) | 0% |
| Exact agreement | **43%** | 33% |

The second column is the degenerate auditor that answers "supported" to everything. It is
printed beside every result because at an 8% unfaithful rate it would score 92% accuracy while
catching nothing. Any accuracy figure reported without it is uninterpretable.

**Confusion matrix** (rows = label, columns = what the checker said):

| | supported | contradicted | not_in_packet | not_a_claim |
|---|---|---|---|---|
| supported | 5 | 1 | 0 | 4 |
| contradicted | 0 | 3 | 0 | 4 |
| not_in_packet | 0 | 2 | 0 | 6 |
| not_a_claim | 0 | 0 | 0 | 5 |

Three things fall out, and none were visible from the summary numbers alone.

**Every miss is an abstention, not a wrong answer.** All ten missed bad claims were returned as
`not_a_claim` — the checker found no digits and declined to rule. It abstains on 19 of 30
sentences, 14 of which were real claims. So its weakness is **coverage, not accuracy**: when it
commits, it is mostly right.

**The `not_in_packet` column is structurally empty.** The checker can only express "numbers
match" or "numbers do not match", so it can never say "this may be true but is absent from the
evidence." Eight of the fifteen bad claims need exactly that verdict. That is not a
performance gap, it is an expressiveness gap.

**Easy and hard claims must be scored separately.** Recall was **100%** on the 11 natural claims
and **29%** on the 19 adversarial ones. Pooled, that reads as an unremarkable 33% and hides both
halves — that the checker is perfect on numeric claims and blind to direction flips and
true-but-absent ones.

Two known defects were left unpatched so the matrix would show their cost rather than hide it.
Incidental numbers are treated as claims: *"Allen scored 38.76 points in week 1"* is flagged
because no packet fact equals 1, which is the single false alarm. And small integers match
promiscuously — the packet stores a defensive rank of 2, so *"week 2"* matched it by
coincidence, making one catch luck rather than reasoning.

**What this sets up.** The LLM auditor has a floor of 33% recall and a specific job: rule on
sentences containing no numbers, and be able to answer `not_in_packet`. If it cannot, it adds
almost nothing over free regex, and one run will say so.

**Limit worth stating:** the 30 labels were written by Claude. The number above is unaffected —
a regex is not a model — but an LLM auditor scored against these labels would be partly
circular. See the `_provenance` block in `eval/cases/2025_w03_allen.json`.
