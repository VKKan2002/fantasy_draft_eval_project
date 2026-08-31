"""Resolve FFC ADP rows to nflverse gsis_ids.

Two-stage, because the two failure modes are different and only one is a bug:

  Stage 1 (join integrity) - does the name map to a gsis_id at all?
      A failure here IS a bug. The player exists; we simply cannot find them.

  Stage 2 (availability)   - does that gsis_id have regular-season rows that year?
      A failure here is usually the TRUTH. Le'Veon Bell held out all of 2018;
      Ray Rice never played in 2014. Those are real zeros, not join errors.

Conflating the two makes the gate unpassable, since some drafted players genuinely
never play. Stage 1 carries the hard threshold; stage 2 is reported for information.

Collisions are broken by production: suffix stripping maps "Frank Gore Jr." and
"Frank Gore" to the same key, so when several gsis_ids share a name the one with
actual snaps in the target season wins.
"""

from __future__ import annotations

import polars as pl

from .ids import canonical_name


def build_crosswalk(ff_playerids: pl.DataFrame) -> pl.DataFrame:
    """merge_name -> every candidate gsis_id (collisions preserved, not silently cut)."""
    return (
        ff_playerids.filter(pl.col("gsis_id").is_not_null())
        .select("merge_name", "gsis_id", "position", "draft_year")
        .unique(subset=["merge_name", "gsis_id"])
    )


def season_activity(stats: pl.DataFrame) -> pl.DataFrame:
    """Per (season, player_id): games with a snap and total PPR points.

    Used to break name collisions and to report genuine absences.
    """
    return (
        stats.filter(pl.col("season_type") == "REG")
        .group_by("season", "player_id")
        .agg(
            pl.len().alias("weeks"),
            pl.col("fantasy_points_ppr").sum().alias("ppr"),
        )
    )


def resolve(
    adp: pl.DataFrame,
    crosswalk: pl.DataFrame,
    activity: pl.DataFrame,
    season: int,
) -> pl.DataFrame:
    """Attach gsis_id to each ADP row for one season.

    Returns the input columns plus:
        gsis_id     - resolved id, or null if the name did not map (stage-1 failure)
        n_candidates- how many ids shared this name (>1 means a collision was broken)
        weeks, ppr  - production that season; null means no rows (stage-2 absence)
    """
    act = activity.filter(pl.col("season") == season).select("player_id", "weeks", "ppr")

    cand = (
        adp.with_columns(
            merge_name=pl.col("name").map_elements(canonical_name, return_dtype=pl.String)
        )
        .join(crosswalk.select("merge_name", "gsis_id"), on="merge_name", how="left")
        .join(act, left_on="gsis_id", right_on="player_id", how="left")
    )

    # Rank candidates per ADP row: played that season first, then most production.
    # A row whose name never mapped keeps a single null-gsis_id candidate.
    return (
        cand.with_columns(
            n_candidates=pl.col("gsis_id").n_unique().over("name", "adp"),
            _rank=pl.struct(
                pl.col("weeks").fill_null(-1),
                pl.col("ppr").fill_null(-1.0),
            ),
        )
        .sort("_rank", descending=True)
        .unique(subset=["name", "adp"], keep="first", maintain_order=True)
        .drop("_rank")
    )


def suggest_aliases(
    unmatched: pl.DataFrame, crosswalk: pl.DataFrame, max_suggestions: int = 3
) -> pl.DataFrame:
    """For names that did not resolve, propose crosswalk candidates from evidence.

    Matching heuristic, in order of confidence:
      1. same surname AND first initial   (Hollywood/Marquise Brown, Gabe/Gabriel Davis)
      2. same surname only
    Never applies a suggestion automatically - a human confirms before it enters ALIASES.
    """
    xw = crosswalk.select("merge_name").unique().with_columns(
        surname=pl.col("merge_name").str.split(" ").list.last(),
        initial=pl.col("merge_name").str.slice(0, 1),
    )
    rows = []
    for r in unmatched.to_dicts():
        key = canonical_name(r["name"])
        parts = key.split(" ")
        if not parts:
            continue
        surname, initial = parts[-1], key[:1]
        hits = xw.filter(pl.col("surname") == surname)
        strong = hits.filter(pl.col("initial") == initial)["merge_name"].to_list()
        weak = [n for n in hits["merge_name"].to_list() if n not in strong]
        rows.append(
            {
                "ffc_name": r["name"],
                "normalized": key,
                "position": r.get("position"),
                "season": r.get("season"),
                "adp": r.get("adp"),
                "candidates": ", ".join((strong + weak)[:max_suggestions]) or "(none)",
            }
        )
    return pl.DataFrame(rows) if rows else pl.DataFrame()
