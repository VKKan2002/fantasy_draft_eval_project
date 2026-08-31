"""Minimal MCP server: one tool, get_player_form.

Run it directly and it waits on stdin for JSON-RPC messages:
    uv run python mcp_server/server.py

You will not see anything happen. That is correct — it is a program waiting to be
spoken to. Use mcp_server/demo_client.py to talk to it.
"""

import nflreadpy as nfl
import polars as pl
from mcp.server.mcpserver import MCPServer

# 1. The server object. The name is how clients identify it.
mcp = MCPServer(name="nfl-fantasy")

# 2. Load data ONCE at startup, not per call. The server is a long-lived process,
#    so a 1.5s load happens one time instead of on every question.
#    2025 because 2026 has not been played yet.
SEASON = 2025
STATS = nfl.load_player_stats(seasons=[SEASON], summary_level="week").filter(
    pl.col("season_type") == "REG"
)

players = STATS.group_by("player_id", "player_display_name", "position", "team").agg()



# 3. The decorator is the whole trick. It reads the function's name, its type hints,
#    and its docstring, and turns all of that into the tool schema the model sees.
@mcp.tool()
def get_player_form(player_name: str, weeks: int = 3) -> dict:
    """Recent fantasy production for one NFL player.

    Use this to see whether a player has been performing well lately. Returns their
    most recent games with PPR points scored, plus an average.

    Args:
        player_name: Full or partial player name, e.g. "Josh Allen" or "Allen".
        weeks: How many of their most recent games to return.
    """
    hits = STATS.filter(
        pl.col("player_display_name").str.to_lowercase().str.contains(
            player_name.lower(), literal=True
        )
    )

    # 4. Failures RETURN a value, they do not raise. The model has to be able to read
    #    what went wrong and pick a different action.
    if hits.height == 0:
        return {"error": "not_found", "message": f"No player matching {player_name!r}"}

    names = hits["player_display_name"].unique().to_list()
    if len(names) > 1:
        return {
            "error": "ambiguous",
            "message": f"{len(names)} players match {player_name!r}. Ask again with one.",
            "candidates": sorted(names)[:10],
        }

    games = hits.sort("week", descending=True).head(weeks)
    pts = games["fantasy_points_ppr"].to_list()

    # 5. Every answer carries where it came from and what it covers, so the agent can
    #    cite it and so a stale answer is visible rather than silent.
    return {
        "player": names[0],
        "position": games["position"][0],
        "team": games["team"][0],
        "games": [
            {"week": int(w), "opponent": o, "ppr_points": round(p, 1)}
            for w, o, p in zip(
                games["week"].to_list(), games["opponent_team"].to_list(), pts
            )
        ],
        "average_ppr": round(sum(pts) / len(pts), 1) if pts else 0.0,
        "source": "nflverse player_stats (weekly, regular season)",
        "as_of": f"{SEASON} season, through week {int(STATS['week'].max())}",
    }


# 6. stdio is the default transport: read JSON from stdin, write JSON to stdout.
if __name__ == "__main__":
    mcp.run()
