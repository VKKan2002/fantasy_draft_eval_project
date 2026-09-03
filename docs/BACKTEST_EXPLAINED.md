# How the backtest works

The measured numbers live in [FINDINGS.md](FINDINGS.md) and the design decisions in
[DESIGN.md](DESIGN.md). This file explains the *method* behind the headline finding, in
plain language, for someone who has not read the code.

**The question it answers:** how much room is there for a smart start/sit tool to beat a
simple one?

**The answer:** 2.9 points a week out of about 96. Which is why this project claims to
save you time rather than win you games.

---

## Step 1 — One fantasy team, one week

```
  You have 10 players. Only 7 can play. Who sits?

  Three different coaches decide, using the SAME team:

  +----------------+  +----------------+  +----------------+
  |  COACH DICE    |  |  COACH RULE    |  |  COACH CHEAT   |
  |                |  |                |  |                |
  |  picks names   |  |  10 lines of   |  |  ALREADY SAW   |
  |  out of a hat  |  |  simple math   |  |  Sunday's game |
  +----------------+  +----------------+  +----------------+
        the floor         the real test        the ceiling

  Then all three are scored with what ACTUALLY happened.
```

The coaches only decide **who takes the field**. Points are always the real points from
[nflverse](https://github.com/nflverse). That separation is what makes the comparison fair:
the only thing that varies between coaches is the lineup decision itself.

## Step 2 — Coach Rule is not allowed to peek

```
  Deciding week 5:

    week 1   week 2   week 3   week 4  ||  week 5   week 6
      OK       OK       OK       OK    ||   NO       NO
    \------- can see this --------/    ||  \--- blocked ---/
         (already happened)            ||   (hasn't happened)
```

Coach Rule's guess for each player mixes two things — what that player has averaged so far
this season, and what his draft position promised. The mix shifts as evidence accumulates:

| Games played so far | Weight on this season | Weight on draft position |
|---|---|---|
| 0 (week 1) | 0% | 100% |
| 1 | 25% | 75% |
| 3 | 50% | 50% |
| 6 | 67% | 33% |
| 12 | 80% | 20% |

Early on, one big game means almost nothing. Later, it means a lot. That is the whole rule
— the formula is `n / (n + 3)`, where `n` is games played, so one game of real evidence is
worth roughly three games' worth of preseason expectation.

The "draft position promised" half comes from
[src/ffeval/models/expected.py](../src/ffeval/models/expected.py): across all the *other*
seasons, what did the 5th running back drafted typically average per game? Smoothed across
neighbouring ranks, then forced never to rise for a later pick.

## Step 3 — Now do that 144 times

```
  12 seasons  x  12 teams per season  =  144 teams
  Every team, every week, all three coaches.

  Average points per season:

    COACH DICE   1,521  ####################
    COACH RULE   1,631  #####################+
    COACH CHEAT  1,681  ######################
    PERFECT      1,789  #######################+
```

The 144 teams come from simulating a 12-team snake draft in each season off that year's
real average draft position, taking the best player available subject to a roster target of
2 QB / 4 RB / 4 WR / 2 TE. Twelve draft slots per season means twelve different rosters, so
the comparison is not resting on one lucky team.

Coach Cheat knows each player's true ability *and* the matchup quality. Perfect Hindsight is
a separate, higher bar: it knows the actual score of every game before it is played.

## Step 4 — The answer

Score everyone as a percentage of Perfect Hindsight, then zoom in on 85–100%:

```
  85%                    91.2%        94%                 100%
   |                       |           |                   |
   v                       v           v                   v
  DICE                   SIMPLE      BEST                PERFECT
 (random)                 RULE      POSSIBLE            HINDSIGHT
                                    CHEATER

   \--------------------/ \---------/ \----------------------/
    a simple rule gets     THIS is     nobody gets this.
    you almost all the     all the     It is luck.
    way here               room a      40% of the gap
      41% of the gap       smart tool
                           could win
                           = 2.9 pts
                           a week
                           18% of the gap
```

**The punchline:** Coach Cheat knows how good every player really is and how good every
matchup is, and he beats ten lines of arithmetic by 3%.

The zoom is the argument. On a full 0–100% axis all four coaches look nearly identical,
which tells you nothing. Zoomed, the band a smart tool competes in is *narrower than the
band that is pure luck*. Any version of this chart without the zoom hides the finding —
which is roughly how tools in this category end up implying an edge nobody measured.

---

## Why the number can be trusted

Three properties of the code, each stopping a specific way this could have cheated:

**No future data.** `prior_games` filters to weeks strictly before the week being decided.
Coach Rule never sees a score that would not have been available on Sunday morning.

**Leave-one-season-out.** The draft-position curve used for 2019 is fit on the other eleven
seasons. Including 2019 would let that season's results inform its own projections.

**Draft data measured before kickoff.** Every season's ADP collection window was verified to
close before Week 1 — 12 of 12 pass, with 2015 clearing by a single day. The counter-example
that makes this non-optional: the 2009 non-PPR data was collected in June 2010, ten months
after that season ended.

One more, for reproducibility: the random coach uses a fixed seed and averages five shuffles,
so the floor is stable between runs rather than jittering.

## Running it yourself

```bash
uv run python checks/step1_build_pool.py   # 12 seasons of draft data -> real player IDs
uv run python checks/step1_baseline.py     # prints the capture-rate table
```

`checks/out/` is deliberately not committed, so a fresh clone rebuilds everything. Expect a
minute or two — the draft-data fetches pause between seasons so the free API is not hammered.

## Where the code is

| Piece | File |
|---|---|
| The backtest itself | [checks/step1_baseline.py](../checks/step1_baseline.py) |
| The winning rule | [checks/step1_baseline.py:113](../checks/step1_baseline.py#L113) `rule_shrunk` |
| Draft position -> expected points | [src/ffeval/models/expected.py](../src/ffeval/models/expected.py) |
| Lineup construction and scoring | [src/ffeval/scoring/lineup.py](../src/ffeval/scoring/lineup.py) |
| League settings, snake draft order | [src/ffeval/scoring/league.py](../src/ffeval/scoring/league.py) |
| How much of the gap is forecastable | [checks/step1b_ceiling.py](../checks/step1b_ceiling.py) |
| Whether matchups add anything | [checks/step1c_matchup.py](../checks/step1c_matchup.py) |
