"""G2 - ID resolution gate.

FFC ADP name -> ff_playerids.merge_name -> gsis_id -> production in player_stats.

Two separate numbers, because only one of them is a bug:

  JOIN RATE  (hard gate, >=99%) - did the name map to a gsis_id?
      Failing means we lost a real player. That is a defect.

  PLAY RATE  (informational)    - did that id record regular-season snaps?
      Failing is usually true: holdouts, suspensions, season-ending injuries.
      Reported so absences stay visible, never as a pass/fail.

Run:  uv run python checks/g2_id_resolution.py
      uv run python checks/g2_id_resolution.py --suggest   # propose new aliases
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import nflreadpy as nfl
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ffeval.ingest.ids import SKILL_POSITIONS  # noqa: E402
from ffeval.ingest.resolve import (  # noqa: E402
    build_crosswalk,
    resolve,
    season_activity,
    suggest_aliases,
)

SEASONS = range(2014, 2026)
TOP_N = 150
JOIN_THRESHOLD = 0.99
ADP_URL = "https://fantasyfootballcalculator.com/api/v1/adp/ppr"


def fetch_adp(year: int, teams: int = 12) -> pl.DataFrame:
    r = httpx.get(
        ADP_URL, params={"teams": teams, "year": year, "position": "all"}, timeout=30
    )
    r.raise_for_status()
    return pl.DataFrame(r.json()["players"]).with_columns(season=pl.lit(year))


def main(suggest: bool = False) -> int:
    crosswalk = build_crosswalk(nfl.load_ff_playerids())
    stats = nfl.load_player_stats(seasons=list(SEASONS), summary_level="week")
    activity = season_activity(stats)

    print(f"{'yr':<6}{'top':>5}{'joined':>8}{'join%':>8}{'played':>8}{'play%':>8}"
          f"{'collis':>8}  gate")
    print("-" * 60)

    unresolved, absent = [], []
    tot = joined = played = collisions = 0

    for year in SEASONS:
        adp = fetch_adp(year)
        pool = (
            adp.filter(pl.col("position").is_in(SKILL_POSITIONS)).sort("adp").head(TOP_N)
        )
        res = resolve(pool, crosswalk, activity, year)

        n = res.height
        j = res.filter(pl.col("gsis_id").is_not_null())
        p = j.filter(pl.col("weeks").is_not_null())
        c = res.filter(pl.col("n_candidates") > 1).height

        tot += n
        joined += j.height
        played += p.height
        collisions += c

        jr = j.height / n
        ok = jr >= JOIN_THRESHOLD
        print(f"{year:<6}{n:>5}{j.height:>8}{jr:>7.1%}{p.height:>8}"
              f"{p.height / n:>7.1%}{c:>8}  {'PASS' if ok else 'FAIL'}")

        for r in res.filter(pl.col("gsis_id").is_null()).to_dicts():
            unresolved.append({k: r[k] for k in ("name", "position", "team", "adp", "season")})
        for r in j.filter(pl.col("weeks").is_null()).to_dicts():
            absent.append({k: r[k] for k in ("name", "position", "team", "adp", "season")})
        time.sleep(0.4)

    jr = joined / tot
    print("-" * 60)
    print(f"{'ALL':<6}{tot:>5}{joined:>8}{jr:>7.1%}{played:>8}{played / tot:>7.1%}"
          f"{collisions:>8}  {'PASS' if jr >= JOIN_THRESHOLD else 'FAIL'}")
    print(f"\nJOIN rate  {jr:.2%}  (gate >= {JOIN_THRESHOLD:.0%})   <- defects")
    print(f"PLAY rate  {played / tot:.2%}  (informational)      <- real absences")
    print(f"Collisions broken by production: {collisions}")

    out = Path(__file__).parent / "out"
    out.mkdir(exist_ok=True)

    if absent:
        a = pl.DataFrame(absent).sort("adp")
        a.write_csv(out / "g2_absent.csv")
        print(f"\n{a.height} drafted-but-never-played -> checks/out/g2_absent.csv")
        print("(expected: holdouts, suspensions, preseason injuries)")
        with pl.Config(tbl_rows=6, fmt_str_lengths=22):
            print(a.head(6))

    if unresolved:
        u = pl.DataFrame(unresolved).sort("adp")
        u.write_csv(out / "g2_unresolved.csv")
        print(f"\n{u.height} UNRESOLVED (defects) -> checks/out/g2_unresolved.csv")
        with pl.Config(tbl_rows=20, fmt_str_lengths=22):
            print(u)
        if suggest:
            s = suggest_aliases(u, crosswalk)
            if s.height:
                s.write_csv(out / "g2_alias_suggestions.csv")
                print("\nAlias candidates (VERIFY each before adding to ids.ALIASES):")
                with pl.Config(tbl_rows=40, fmt_str_lengths=44):
                    print(s.select("ffc_name", "normalized", "season", "candidates"))
    else:
        print("\nNo unresolved names.")

    return 0 if jr >= JOIN_THRESHOLD else 1


if __name__ == "__main__":
    raise SystemExit(main(suggest="--suggest" in sys.argv))
