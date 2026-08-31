"""Rebuild the player pool with NO arbitrary cap, so 15-round rosters fit.

The earlier top-150 cut was mine, not the data's. FFC returns more, and start/sit needs
bench depth or every rule gets forced into identical lineups.
"""
from __future__ import annotations
import sys, time
from pathlib import Path
import httpx, nflreadpy as nfl, polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ffeval.ingest.ids import SKILL_POSITIONS
from ffeval.ingest.resolve import build_crosswalk, resolve, season_activity

SEASONS = range(2014, 2026)
URL = "https://fantasyfootballcalculator.com/api/v1/adp/ppr"
OUT = Path(__file__).parent / "out" / "pool_full.parquet"

xw = build_crosswalk(nfl.load_ff_playerids())
st = nfl.load_player_stats(seasons=list(SEASONS), summary_level="week").filter(
    pl.col("season_type") == "REG")
act = season_activity(st)

frames = []
print(f"{'yr':<6}{'all':>6}{'skill':>7}{'joined':>8}{'rate':>8}")
for y in SEASONS:
    r = httpx.get(URL, params={"teams": 12, "year": y, "position": "all"}, timeout=30)
    r.raise_for_status()
    raw = pl.DataFrame(r.json()["players"]).with_columns(season=pl.lit(y))
    skill = raw.filter(pl.col("position").is_in(SKILL_POSITIONS)).sort("adp")
    res = resolve(skill, xw, act, y)
    ok = res.filter(pl.col("gsis_id").is_not_null())
    print(f"{y:<6}{raw.height:>6}{skill.height:>7}{ok.height:>8}{ok.height/skill.height:>7.1%}")
    frames.append(ok.select(
        "season", "name", "position", "team", "adp", "stdev", "gsis_id",
        pl.col("ppr").fill_null(0.0).alias("ppr_total"),
        pl.col("weeks").fill_null(0).alias("games")))
    time.sleep(0.4)

df = pl.concat(frames).with_columns(
    pos_rank=pl.col("adp").rank("ordinal").over("season", "position").cast(pl.Int32),
    ppg=pl.when(pl.col("games") > 0).then(pl.col("ppr_total") / pl.col("games")).otherwise(0.0),
)
df.write_parquet(OUT)
print(f"\nwrote {OUT}  rows={df.height}")
print(df.group_by("season").agg(pl.len().alias("n")).sort("season")
        .with_columns(enough_for_180=pl.col("n") >= 180))
