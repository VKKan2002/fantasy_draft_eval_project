"""Weekly lineup construction and season scoring.

A roster is scored week by week, not by summing season totals. Only the weekly view
sees bye collisions, missed games, and FLEX substitution - which is exactly what
roster construction is about.

Two lineup rules, because the choice is NOT neutral:

  COMMITTED   - start players by a priority fixed before the season (draft order).
                No knowledge of that week's scores. What a passive manager does.
  CLAIRVOYANT - start whoever actually scored most that week. Perfect start/sit.

Clairvoyant silently over-rewards volatile depth. Two coin-flip players scoring 5 or
25: committing in advance averages 15, always picking the winner averages 20. That
phantom 5 grows with variance, and volatility is exactly what draft strategies differ
on - so reporting only clairvoyant would bias the headline. Both are computed.

Availability: a player is startable in a week iff the stats table has a row for them
that week. No row = bye or inactive. A row scoring 0.0 means they played and did
nothing, which IS startable.
"""

from __future__ import annotations

from .league import FLEX_ELIGIBLE, League


def best_lineup(
    available: list[tuple[str, str, float]],
    league: League,
    priority: dict[str, int] | None = None,
) -> tuple[float, list[tuple[str, str, float]]]:
    """Pick the best legal lineup from `available` = [(player_id, position, points)].

    priority=None      -> CLAIRVOYANT: rank by actual points this week.
    priority given     -> COMMITTED: rank by that fixed order (lower = start sooner).

    Returns (points scored, chosen players). Scoring always uses ACTUAL points; the
    rule only decides who takes the field.

    Filling dedicated slots before FLEX is optimal here: FLEX accepts a superset of
    RB/WR/TE, so taking the best at each dedicated position first can never block a
    better FLEX choice.
    """
    if priority is None:
        key = lambda p: -p[2]  # noqa: E731  best actual points first
    else:
        key = lambda p: priority.get(p[0], 10**6)  # noqa: E731  draft order

    pool = sorted(available, key=key)
    used: set[str] = set()
    chosen: list[tuple[str, str, float]] = []

    for pos, n in league.starters.items():
        picked = 0
        for p in pool:
            if picked == n:
                break
            if p[0] not in used and p[1] == pos:
                used.add(p[0])
                chosen.append(p)
                picked += 1

    for _ in range(league.flex):
        for p in pool:
            if p[0] not in used and p[1] in FLEX_ELIGIBLE:
                used.add(p[0])
                chosen.append(p)
                break

    return sum(p[2] for p in chosen), chosen


def score_season(
    roster: list[tuple[str, str]],
    week_points: dict[tuple[str, int], float],
    weeks: range,
    league: League,
    priority: dict[str, int] | None = None,
) -> list[float]:
    """Weekly points for one roster. `roster` = [(player_id, position), ...]."""
    out = []
    for wk in weeks:
        avail = [
            (pid, pos, week_points[(pid, wk)])
            for pid, pos in roster
            if (pid, wk) in week_points
        ]
        pts, _ = best_lineup(avail, league, priority)
        out.append(pts)
    return out


def weekly_detail(
    roster: list[tuple[str, str]],
    week_points: dict[tuple[str, int], float],
    weeks: range,
    league: League,
    priority: dict[str, int] | None = None,
) -> list[dict]:
    """Same as score_season but returns who started and how many were unavailable."""
    rows = []
    for wk in weeks:
        avail = [
            (pid, pos, week_points[(pid, wk)])
            for pid, pos in roster
            if (pid, wk) in week_points
        ]
        pts, chosen = best_lineup(avail, league, priority)
        rows.append(
            {
                "week": wk,
                "points": round(pts, 1),
                "available": len(avail),
                "out": len(roster) - len(avail),
                "started": chosen,
                "short": len(chosen) < league.n_starters,
            }
        )
    return rows
