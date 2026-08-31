"""The money graphic: how big is the start/sit decision space, and who can reach what."""
from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import polars as pl

res = pl.read_parquet(Path(__file__).parent / "out" / "step1c_results.parquet")
M = {c: res[c].mean() for c in
     ["random", "best_simple", "simple_plus_matchup", "oracle_ability",
      "oracle_abil_matchup", "perfect"]}
R, S, P = M["random"], M["best_simple"], M["perfect"]

fig, ax = plt.subplots(1, 2, figsize=(13.5, 5.0))

# ---- panel 1: the ladder
levels = [
    ("Random lineup", R, "#b91c1c"),
    ("Best simple rule\n(shrink to preseason)", S, "#1d4ed8"),
    ("+ perfect matchup info", M["simple_plus_matchup"], "#0891b2"),
    ("Perfect player-ability info", M["oracle_ability"], "#047857"),
    ("Perfect ability + matchup\n(ceiling for ANY model)", M["oracle_abil_matchup"], "#15803d"),
    ("Perfect hindsight\n(impossible)", P, "#525252"),
]
names = [l[0] for l in levels]
vals = [l[1] for l in levels]
cols = [l[2] for l in levels]
y = range(len(levels))
ax[0].barh(list(y), vals, color=cols, height=0.62)
ax[0].set_yticks(list(y)); ax[0].set_yticklabels(names, fontsize=8.5)
ax[0].invert_yaxis()
ax[0].set_xlim(1450, 1830)
ax[0].set_xlabel("Points scored per season")
for i, v in enumerate(vals):
    ax[0].text(v + 6, i, f"{v:.0f}   {v/P:.1%}", va="center", fontsize=8.5)
ax[0].axvline(S, color="#1d4ed8", ls=":", lw=1.2, alpha=0.7)
ax[0].set_title("A simple rule already captures 91% of what's achievable", fontsize=10.5)
ax[0].grid(axis="x", alpha=0.15)

# ---- panel 2: the decision space, split by what could reach it
parts = [
    ("Simple rules\nalready capture this", S - R, "#1d4ed8"),
    ("Reachable with PERFECT\nability + matchup info", M["oracle_abil_matchup"] - S, "#15803d"),
    ("Week-to-week luck\nno information can touch", P - M["oracle_abil_matchup"], "#a3a3a3"),
]
left = 0.0
for label, w, c in parts:
    ax[1].barh([0], [w], left=[left], color=c, height=0.42)
    ax[1].text(left + w / 2, 0, f"{w:.0f} pts\n{w/(P-R):.0%}",
               ha="center", va="center", fontsize=10,
               color="white" if c != "#a3a3a3" else "#262626", fontweight="bold")
    left += w
ax[1].set_yticks([])
ax[1].set_xlim(0, P - R)
ax[1].set_xlabel(f"The entire decision space = {P-R:.0f} points/season")
ax[1].set_title("Only 49 of 267 points are addressable by better information",
                fontsize=10.5)
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in parts]
ax[1].legend(handles, [p[0].replace("\n", " ") for p in parts],
             loc="upper center", bbox_to_anchor=(0.5, -0.22), frameon=False, fontsize=8.5)

fig.suptitle("Step 1: how much room is there for a smarter start/sit assistant?",
             fontsize=13, y=1.02)
fig.tight_layout()
# tracked figure: it backs a claim in plan.md and docs/FINDINGS.md, so it lives
# in docs/ rather than the gitignored checks/out/
out = Path(__file__).resolve().parents[1] / "docs" / "step1_headroom.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
print("wrote", out)
print(f"addressable = {M['oracle_abil_matchup']-S:.0f} pts/season "
      f"= {(M['oracle_abil_matchup']-S)/17:.1f} pts/week")
