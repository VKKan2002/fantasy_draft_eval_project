"""Propose aliases from team/season/position evidence, not name similarity.

FFC gives each ADP row a team. So for an unresolved name we can ask a much stronger
question than "which crosswalk name looks similar?":

    who actually played that position, for that team, in that season,
    and is not already claimed by another ADP row?

That catches full nickname substitutions ("Hollywood Brown" -> Marquise Brown) which
no string heuristic will ever find, and it self-verifies: a candidate is only proposed
because roster evidence already places them there.

Run: uv run python checks/g2_verify_aliases.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import nflreadpy as nfl
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ffeval.ingest.ids import SKILL_POSITIONS, TEAM_FIXES  # noqa: E402
from ffeval.ingest.resolve import build_crosswalk, resolve, season_activity  # noqa: E402

SEASONS = range(2014, 2026)
TOP_N = 150
ADP_URL = "https://fantasyfootballcalculator.com/api/v1/adp/ppr"


def fetch_adp(year: int, teams: int = 12) -> pl.DataFrame:
    r = httpx.get(
        ADP_URL, params={"teams": teams, "year": year, "position": "all"}, timeout=30
    )
    r.raise_for_status()
    return pl.DataFrame(r.json()["players"]).with_columns(season=pl.lit(year))


def main() -> int:
    xw = build_crosswalk(nfl.load_ff_playerids())
    stats = nfl.load_player_stats(seasons=list(SEASONS), summary_level="week").filter(
        pl.col("season_type") == "REG"
    )
    activity = season_activity(stats)

    roster = (
        stats.group_by("season", "player_id", "position", "team")
        .agg(pl.len().alias("weeks"), pl.col("fantasy_points_ppr").sum().alias("ppr"))
        .join(
            xw.select("gsis_id", "merge_name").unique(subset=["gsis_id"]),
            left_on="player_id",
            right_on="gsis_id",
            how="left",
        )
    )

    proposals = []
    for year in SEASONS:
        adp = fetch_adp(year)
        pool = adp.filter(pl.col("position").is_in(SKILL_POSITIONS)).sort("adp").head(TOP_N)
        res = resolve(pool, xw, activity, year)

        claimed = set(res.filter(pl.col("gsis_id").is_not_null())["gsis_id"].to_list())
        miss = res.filter(pl.col("gsis_id").is_null())

        for r in miss.to_dicts():
            team = TEAM_FIXES.get(r["team"], r["team"])
            cands = (
                roster.filter(
                    (pl.col("season") == year)
                    & (pl.col("team") == team)
                    & (pl.col("position") == r["position"])
                    & (~pl.col("player_id").is_in(list(claimed)))
                )
                .sort("ppr", descending=True)
                .head(3)
            )
            for c in cands.to_dicts():
                proposals.append(
                    {
                        "ffc_name": r["name"],
                        "season": year,
                        "pos": r["position"],
                        "ffc_team": r["team"],
                        "adp": r["adp"],
                        "candidate": c["merge_name"],
                        "gsis_id": c["player_id"],
                        "weeks": c["weeks"],
                        "ppr": round(c["ppr"] or 0, 1),
                    }
                )
        time.sleep(0.4)

    if not proposals:
        print("Nothing unresolved.")
        return 0

    p = pl.DataFrame(proposals)
    out = Path(__file__).parent / "out"
    out.mkdir(exist_ok=True)
    p.write_csv(out / "g2_alias_proposals.csv")

    print("Proposals from team/season/position evidence")
    print("(same candidate recurring across seasons for one ffc_name = strong)\n")
    with pl.Config(tbl_rows=60, fmt_str_lengths=20):
        print(
            p.sort("ffc_name", "season").select(
                "ffc_name", "season", "pos", "ffc_team", "candidate", "weeks", "ppr"
            )
        )

    print("\nTop candidate per name, with cross-season support:")
    best = (
        p.group_by("ffc_name", "candidate")
        .agg(
            pl.len().alias("seasons_supporting"),
            pl.col("ppr").mean().round(1).alias("avg_ppr"),
        )
        .sort(["ffc_name", "seasons_supporting"], descending=[False, True])
    )
    with pl.Config(tbl_rows=40, fmt_str_lengths=22):
        print(best)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
