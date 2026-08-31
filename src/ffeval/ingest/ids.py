"""Name normalization and ID resolution.

FFC's ADP feed identifies players by display name only. nflverse keys on `gsis_id`.
The bridge is `ff_playerids.merge_name`, so FFC names must be normalized to exactly
the same convention.

Rules inferred from ff_playerids (name -> merge_name):
    lowercase; drop '.' and '''; KEEP '-'; strip trailing Jr/Sr/II/III/IV/V.
        "T.J. Parker"        -> "tj parker"
        "Le'Veon Moss"       -> "leveon moss"
        "Omar Cooper Jr."    -> "omar cooper"
        "Chris Brazzell II"  -> "chris brazzell"
        "Dani Dennis-Sutton" -> "dani dennis-sutton"   (hyphen preserved)

Two hazards this module exists to handle, both found empirically:

1. Suffix stripping creates COLLISIONS. "Frank Gore Jr." normalizes to "frank gore",
   same as his father. Resolving by name alone silently picked the son for 2014-2015
   seasons and scored a Hall-of-Fame back as zero. Collisions must be broken by
   checking which candidate actually has production in the target season.

2. FFC uses nicknames that nflverse does not: "Hollywood Brown" is Marquise Brown,
   "Gabe Davis" is Gabriel Davis. These need an explicit alias table.

Position is deliberately NOT part of the join key: sources disagree (Cordarrelle
Patterson is WR to FFC, RB to nflverse in some years) and a position mismatch would
silently drop a real player.
"""

from __future__ import annotations

import re

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
_DROP = re.compile(r"[.']")
_WS = re.compile(r"\s+")


def merge_name(name: str) -> str:
    """Normalize a display name to the nflverse `merge_name` convention."""
    if name is None:
        return ""
    s = _DROP.sub("", name).lower().strip()
    parts = _WS.sub(" ", s).split(" ")
    while len(parts) > 2 and parts[-1] in _SUFFIXES:
        parts.pop()
    return " ".join(parts)


# FFC display name (normalized) -> nflverse merge_name.
#
# APPEND-ONLY. Every entry below was produced by checks/g2_verify_aliases.py, which
# proposes candidates from (team, season, position) roster evidence rather than string
# similarity. Never add an alias from memory: a wrong one silently credits another
# player's season to this row, which is strictly worse than leaving it unmatched.
#
# "support" = seasons where the candidate independently topped the evidence ranking.
ALIASES: dict[str, str] = {
    # support 4/4, avg 175.5 PPR (next best 2 @ 89.8); FFC teams BAL,BAL,ARI,ARI,KC
    # trace Marquise Brown's actual career path. No string heuristic finds this one.
    "hollywood brown": "marquise brown",
    # support 3/3, avg 153.0 PPR (next best 2 @ 73.6)
    "gabe davis": "gabriel davis",
    # support 2/2, avg 92.6 PPR vs boston scott 2 @ 32.0; diminutive of Kenneth
    "kenny gainwell": "kenneth gainwell",
    # support 1, 113.4 PPR, top TEN candidate; Chig is short for Chigoziem
    "chig okonkwo": "chigoziem okonkwo",
    # support 2/2; reversed direction - FFC uses the LONGER name, nflverse the shorter
    "joshua palmer": "josh palmer",
    # support 1, 112.7 PPR (top of 3 LAC WRs), 9 weeks matches his 2015 stint.
    # NOTE: distinct from "steven johnson" (LB) in the crosswalk. Safe while only the
    # 2015 SD/LAC row uses this key; re-verify if another Steve Johnson enters a pool.
    "steve johnson": "stevie johnson",
}


def canonical_name(name: str) -> str:
    """Normalize, then apply the alias table."""
    m = merge_name(name)
    return ALIASES.get(m, m)


# FFC team abbreviations that differ from nflverse.
TEAM_FIXES = {
    "JAC": "JAX",
    "ARZ": "ARI",
    "BLT": "BAL",
    "CLV": "CLE",
    "HST": "HOU",
    "SL": "LA",
    "SD": "LAC",
    "OAK": "LV",
}

# Positions modeled. FFC also returns PK/DEF; DEF is a team rather than a player and
# never resolves to a gsis_id, so it is handled separately.
SKILL_POSITIONS = ("QB", "RB", "WR", "TE")
