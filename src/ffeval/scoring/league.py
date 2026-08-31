"""League configuration.

No K or DST slots in v1: they are drafted at the end, close to random, and DST is a
team rather than a player (a different join). Excluding them removes real plumbing for
almost no loss of validity - but it does mean roster sizes here are smaller than a
typical real league's.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Dedicated starting slots, then FLEX which accepts any of RB/WR/TE.
FLEX_ELIGIBLE = ("RB", "WR", "TE")


@dataclass(frozen=True)
class League:
    teams: int = 12
    rounds: int = 13
    # position -> number of dedicated starting slots
    starters: dict[str, int] = field(
        default_factory=lambda: {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
    )
    flex: int = 1
    # Max drafted per position, so every roster can actually field a lineup.
    # Without caps, a strict ADP-follow team can end up with 3 QBs and 1 TE.
    caps: dict[str, int] = field(
        default_factory=lambda: {"QB": 2, "RB": 6, "WR": 6, "TE": 2}
    )

    @property
    def picks(self) -> int:
        return self.teams * self.rounds

    @property
    def n_starters(self) -> int:
        return sum(self.starters.values()) + self.flex


def snake_pick_numbers(slot: int, teams: int, rounds: int) -> list[int]:
    """Overall pick numbers belonging to `slot` (1-indexed) in a snake draft.

    Round 1 runs 1..teams, round 2 reverses, and so on.
        slot 5 of 12 -> [5, 20, 29, 44, 53, ...]
    """
    out = []
    for r in range(1, rounds + 1):
        if r % 2 == 1:
            out.append((r - 1) * teams + slot)
        else:
            out.append(r * teams - slot + 1)
    return out
