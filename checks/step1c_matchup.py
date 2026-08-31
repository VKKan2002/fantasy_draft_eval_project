"""STEP 1c - Does WEEK-SPECIFIC information have any room?

Step 1b's oracle knew each player's true season-long ability. That is the ceiling for
"rank players better", and it was only 40 pts/season above the best simple rule.

But that oracle is STATIC. It cannot know that this week a player faces the worst defense
in the league, or that the starter ahead of him is out. That week-specific information is
exactly what an LLM reading news is supposed to supply - and it lives in the 118-point
band Step 1b labelled "luck", which was too dismissive.

So: give a rule PERFECT hindsight on matchup quality and see if it beats the ability
oracle. If perfect matchup knowledge is worth almost nothing, the week-specific band is
mostly noise and the agent has nowhere to work. If it is worth a lot, the agent's thesis
survives.

Run: uv run python checks/step1c_matchup.py
"""
from __future__ import annotations
import random, sys
from pathlib import Path
import nflreadpy as nfl
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ffeval.models.expected import fit_expected_points
from ffeval.scoring.league import League, snake_pick_numbers
from ffeval.scoring.lineup import best_lineup

df = pl.read_parquet(Path(__file__).parent / "out" / "pool_full.parquet")
SEASONS = sorted(df["season"].unique().to_list())
LEAGUE = League(rounds=12)
TARGET = {"QB": 2, "RB": 4, "WR": 4, "TE": 2}
RNG = random.Random(20260830)

st = nfl.load_player_stats(seasons=SEASONS, summary_level="week").filter(
    pl.col("season_type") == "REG")
WK = {r["season"]: range(1, int(r["mx"]) + 1)
      for r in st.group_by("season").agg(pl.col("week").max().alias("mx")).to_dicts()}

PTS, HIST, OPP = {}, {}, {}
for r in st.select("season", "player_id", "week", "fantasy_points_ppr",
                   "opponent_team", "position").to_dicts():
    s, pid, w = r["season"], r["player_id"], int(r["week"])
    v = float(r["fantasy_points_ppr"] or 0.0)
    PTS.setdefault(s, {})[(pid, w)] = v
    HIST.setdefault(s, {}).setdefault(pid, []).append((w, v))
    OPP.setdefault(s, {})[(pid, w)] = r["opponent_team"]
for s in HIST:
    for pid in HIST[s]:
        HIST[s][pid].sort()

TRUE_PPG = {s: {pid: sum(v for _, v in h) / len(h) for pid, h in HIST[s].items() if h}
            for s in HIST}

# Defense factor with FULL HINDSIGHT: how much did each defense allow to each position,
# relative to the league average that season? >1 = generous matchup.
dfac = {}
agg = (st.group_by("season", "opponent_team", "position")
         .agg(pl.col("fantasy_points_ppr").mean().alias("allowed")))
lg = (st.group_by("season", "position")
        .agg(pl.col("fantasy_points_ppr").mean().alias("lg_avg")))
fac = agg.join(lg, on=["season", "position"]).with_columns(
    f=pl.when(pl.col("lg_avg") > 0).then(pl.col("allowed") / pl.col("lg_avg")).otherwise(1.0))
for r in fac.to_dicts():
    dfac[(r["season"], r["opponent_team"], r["position"])] = float(r["f"])

CURVE = {s: fit_expected_points(
    df.select("season", "position", "pos_rank", pl.col("ppg").alias("ppr_total")), s)
    for s in SEASONS}

def build_rosters(season):
    pool = (df.filter(pl.col("season") == season).sort("adp")
              .select("gsis_id", "name", "position", "pos_rank").to_dicts())
    oc = {}
    for s in range(1, LEAGUE.teams + 1):
        for pn in snake_pick_numbers(s, LEAGUE.teams, LEAGUE.rounds):
            oc[pn] = s
    ros = {s: [] for s in range(1, LEAGUE.teams + 1)}
    taken = set()
    for pick in range(1, LEAGUE.picks + 1):
        slot = oc[pick]
        have = {}
        for p in ros[slot]:
            have[p["position"]] = have.get(p["position"], 0) + 1
        for p in pool:
            if p["gsis_id"] in taken or have.get(p["position"], 0) >= TARGET[p["position"]]:
                continue
            ros[slot].append(p); taken.add(p["gsis_id"]); break
    return ros

def shrunk(season, p, week, k=3.0):
    h = [v for w, v in HIST[season].get(p["gsis_id"], []) if w < week]
    prior = CURVE[season](p["position"], int(p["pos_rank"]))
    if not h:
        return prior
    n = len(h); w_ = n / (n + k)
    return w_ * (sum(h) / n) + (1 - w_) * prior

def oracle_ability(season, p, week):
    return TRUE_PPG[season].get(p["gsis_id"], 0.0)

def oracle_ability_matchup(season, p, week):
    """Ability oracle x perfect knowledge of how generous this week's defense was."""
    base = TRUE_PPG[season].get(p["gsis_id"], 0.0)
    o = OPP[season].get((p["gsis_id"], week))
    return base * dfac.get((season, o, p["position"]), 1.0)

def shrunk_matchup(season, p, week):
    """Realistic rule + perfect matchup knowledge, to isolate matchup's own value."""
    o = OPP[season].get((p["gsis_id"], week))
    return shrunk(season, p, week) * dfac.get((season, o, p["position"]), 1.0)

def score(roster, season, projector=None, randomize=False):
    tot = 0.0
    for wk in WK[season]:
        avail = [(p["gsis_id"], p["position"], PTS[season][(p["gsis_id"], wk)])
                 for p in roster if (p["gsis_id"], wk) in PTS[season]]
        if not avail:
            continue
        if randomize:
            o = [a[0] for a in avail]; RNG.shuffle(o)
            prio = {pid: i for i, pid in enumerate(o)}
        elif projector is None:
            prio = None
        else:
            pr = sorted(((projector(season, p, wk), p["gsis_id"]) for p in roster
                         if (p["gsis_id"], wk) in PTS[season]), reverse=True)
            prio = {pid: i for i, (_, pid) in enumerate(pr)}
        tot += best_lineup(avail, LEAGUE, prio)[0]
    return tot

rows = []
for season in SEASONS:
    for slot, roster in build_rosters(season).items():
        rows.append({
            "season": season, "slot": slot,
            "random": sum(score(roster, season, randomize=True) for _ in range(5)) / 5,
            "best_simple": score(roster, season, projector=shrunk),
            "simple_plus_matchup": score(roster, season, projector=shrunk_matchup),
            "oracle_ability": score(roster, season, projector=oracle_ability),
            "oracle_abil_matchup": score(roster, season, projector=oracle_ability_matchup),
            "perfect": score(roster, season, projector=None),
        })
res = pl.DataFrame(rows)
res.write_parquet(Path(__file__).parent / "out" / "step1c_results.parquet")

cols = ["random", "best_simple", "simple_plus_matchup", "oracle_ability",
        "oracle_abil_matchup", "perfect"]
M = {c: res[c].mean() for c in cols}
P, R, S = M["perfect"], M["random"], M["best_simple"]

print(f"{res.height} roster-seasons\n")
print(f"{'level':<38}{'points':>9}{'capture':>10}{'vs simple':>11}")
print("-" * 68)
labels = {
    "random": "random lineup (floor)",
    "best_simple": "best simple rule",
    "simple_plus_matchup": "simple + PERFECT matchup knowledge",
    "oracle_ability": "oracle: true season ability",
    "oracle_abil_matchup": "oracle ability + perfect matchup",
    "perfect": "perfect hindsight (ceiling)",
}
for c in cols:
    print(f"{labels[c]:<38}{M[c]:>9.0f}{M[c]/P:>9.1%}{M[c]-S:>+11.0f}")

print("\nWhat each kind of information is worth, per season:")
print(f"  better static projections (ability)      {M['oracle_ability']-S:>+7.0f} pts")
print(f"  perfect matchup knowledge alone          {M['simple_plus_matchup']-S:>+7.0f} pts")
print(f"  both together                            {M['oracle_abil_matchup']-S:>+7.0f} pts")
print(f"  everything else (irreducible weekly luck){P-M['oracle_abil_matchup']:>+7.0f} pts")
print(f"\n  total decision space (random->perfect)   {P-R:>7.0f} pts")

def ci(col):
    per = res.group_by("season").agg((pl.col(col) - pl.col("best_simple")).mean().alias("g"))
    vals = per["g"].to_list()
    rb = random.Random(11); b = []
    for _ in range(4000):
        s = [vals[rb.randrange(len(vals))] for _ in vals]
        b.append(sum(s) / len(s))
    b.sort()
    return sum(vals)/len(vals), b[100], b[-100]

print("\n95% CI on gain over the best simple rule (bootstrap blocked by season):")
for c in ("simple_plus_matchup", "oracle_ability", "oracle_abil_matchup"):
    m, lo, hi = ci(c)
    print(f"  {labels[c]:<36} {m:>+6.0f}  [{lo:>+5.0f}, {hi:>+5.0f}]")
