"""MCP server: gives any MCP agent (Claude Desktop, Claude Code, others) AFTERSHOCK's tools.

Run locally over stdio: .venv/Scripts/python -m aftershock.mcp_server
The tools are product-specific (not a pass-through to Qloo); the Qloo key stays in this
process's environment and never appears in an MCP config.
"""
import json
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from aftershock.qloo import Qloo
from aftershock.ripple import MAX_SONGS, score_placements

ROOT = Path(__file__).resolve().parent.parent
STORMS = ROOT / "data" / "private" / "storms.json"

server = MCPServer(
    name="aftershock",
    instructions="Forecast where a breakout Netflix title spreads next (countries) and which songs placed in a show "
                 "will spike. Forecasts are probabilities from Netflix history plus Qloo taste data, not certainties.",
)


def _storms():
    if not STORMS.exists():
        return []
    return json.loads(STORMS.read_text(encoding="utf-8"))["storms"]


@server.tool(description="List this week's breakouts: titles that entered the Netflix Top 10 in 1 to 3 countries.")
def list_storms() -> list[dict]:
    return [s["summary"] for s in _storms()]


@server.tool(description="Country spillover forecast for one breakout, by storm id from list_storms.")
def spillover_forecast(storm_id: str) -> dict:
    for storm in _storms():
        if storm["summary"]["id"] == storm_id:
            return storm["detail"]["spillover"] | {"title": storm["summary"]["title"]}
    return {"error": f"no storm with id {storm_id!r}; call list_storms first"}


@server.tool(description=f"Score up to {MAX_SONGS} songs placed in a show or film for ripple potential "
                         "(taste fit of the show's audience x how unfamiliar the artist is to that audience). "
                         "songs is a list of [song, artist] pairs.")
def ripple_score(show: str, songs: list[list[str]]) -> dict:
    placements = [(pair[0], pair[1]) for pair in songs if len(pair) == 2][:MAX_SONGS]
    return score_placements(Qloo(call_budget=40), show, placements)


if __name__ == "__main__":
    server.run("stdio")
