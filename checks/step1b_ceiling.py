"""STEP 1b - How much of the remaining gap is even forecastable?

Step 1 said the best simple rule captures 91.3% and perfect hindsight is 100%. The 8.7%
gap is only worth chasing if some of it is FORECASTABLE rather than luck.

The discriminator: a rule that knows each player's TRUE full-season average - perfect
knowledge of how good a player is, but no knowledge of which week he explodes. That is
the best any projection model could ever be, because ability is the forecastable part and
week-to-week variance is not.

    best simple rule -> oracle-ability   = the room a better model could occupy
    oracle-ability   -> perfect hindsight = pure week-to-week luck, unreachable forever

Run: uv run python checks/step1b_ceiling.py
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
PTS, HIST = {}, {}
for r in st.select("season", "player_id", "week", "fantasy_points_ppr").to_dicts():
    s, pid, w = r["season"], r["player_id"], int(r["week"])
    v = float(r["fantasy_points_ppr"] or 0.0)
    PTS.setdefault(s, {})[(pid, w)] = v
    HIST.setdefault(s, {}).setdefault(pid, []).append((w, v))
for s in HIST:
    for pid in HIST[s]:
        HIST[s][pid].sort()

# true full-season PPG - HINDSIGHT on ability
TRUE_PPG = {s: {pid: sum(v for _, v in h) / len(h) for pid, h in HIST[s].items() if h}
            for s in HIST}
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
            "oracle_ability": score(roster, season, projector=oracle_ability),
            "perfect": score(roster, season, projector=None),
        })
res = pl.DataFrame(rows)
res.write_parquet(Path(__file__).parent / "out" / "step1b_results.parquet")

R, S, O, P = (res[c].mean() for c in ("random", "best_simple", "oracle_ability", "perfect"))
print(f"{res.height} roster-seasons\n")
print(f"{'level':<34}{'points':>9}{'capture':>10}")
print("-" * 53)
for lbl, v in [("random lineup (floor)", R), ("best simple rule", S),
               ("oracle: knows true ability", O), ("perfect hindsight (ceiling)", P)]:
    print(f"{lbl:<34}{v:>9.0f}{v / P:>9.1%}")

print(f"\nBreaking the {P - R:.0f}-point decision space into three parts:\n")
print(f"  simple rules earn                {S - R:>7.0f} pts  ({(S-R)/(P-R):>5.1%} of the space)")
print(f"  ROOM FOR A BETTER MODEL          {O - S:>7.0f} pts  ({(O-S)/(P-R):>5.1%} of the space)")
print(f"  pure week-to-week luck           {P - O:>7.0f} pts  ({(P-O)/(P-R):>5.1%} of the space)")

print(f"\nSo the entire addressable headroom is {O - S:.0f} points/season "
      f"({(O - S) / P:.2%} of total points).")

# paired significance, blocked by season
d = res.with_columns(gain=pl.col("oracle_ability") - pl.col("best_simple"))
per_season = d.group_by("season").agg(pl.col("gain").mean()).sort("season")
vals_str = ", ".join(f"{v:.0f}" for v in per_season["gain"].to_list())
print("\nPer-season addressable headroom (pts): " + vals_str)
print(f"mean {per_season['gain'].mean():.0f}, sd across seasons {per_season['gain'].std():.0f}")

boot = []
vals = per_season["gain"].to_list()
rb = random.Random(7)
for _ in range(4000):
    s = [vals[rb.randrange(len(vals))] for _ in vals]
    boot.append(sum(s) / len(s))
boot.sort()
print(f"95% CI (bootstrap blocked by season): "
      f"[{boot[100]:.0f}, {boot[-100]:.0f}] pts/season")
