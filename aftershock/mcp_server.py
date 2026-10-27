"""MCP server: gives any MCP agent (Claude Desktop, Claude Code, others) AFTERSHOCK's tools.

Run locally over stdio: .venv/Scripts/python -m aftershock.mcp_server
The tools are product-specific (not a pass-through to Qloo); the Qloo key stays in this
process's environment and never appears in an MCP config.
"""
import json
import time
from datetime import date
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from aftershock.qloo import Qloo
from aftershock.ripple import MAX_SONGS, score_placements
from aftershock.sync_scout import MAX_QLOO_CALLS, TOP_N, scout

WIKI_FIRST_DAY = date(2015, 8, 1)  # Wikimedia per-article pageviews start in July 2015
RIPPLE_PER_HOUR = 20
SCOUT_PER_HOUR = 6
_ripple_calls: list[float] = []
_scout_calls: list[float] = []

ROOT = Path(__file__).resolve().parent.parent
STORMS = ROOT / "data" / "private" / "storms.json"

server = MCPServer(
    name="aftershock",
    instructions="Two forecasts. SPILLOVER: for a title that entered Netflix's Top 10 in 1 to 3 countries, the "
                 "probability that each other country charts it within 4 weeks, from Netflix history only (backtest "
                 "ROC AUC 0.817 on 829 breakouts; Qloo added no lift). Qloo supplies only the partners list. RIPPLE: "
                 "for songs placed in a show, a score in [0,1] that is the Qloo age gap between the artist's audience "
                 "and the show's; it is a ranking signal with modest evidence (2024+ releases, 9 shows, Spearman 0.28), "
                 "not a spike prediction. Prior Wikipedia views and Qloo taste fit are context only. Probabilities are "
                 "not certainties.",
)


def _storms():
    if not STORMS.exists():
        return []
    return json.loads(STORMS.read_text(encoding="utf-8"))["storms"]


@server.tool(description="List this week's breakouts: titles that entered the Netflix Top 10 in 1 to 3 countries.")
def list_storms() -> list[dict]:
    return [s["summary"] for s in _storms()]


@server.tool(description="SPILLOVER forecast for one breakout, by storm id from list_storms: a probability for each "
                         "other country charting the title within 4 weeks, from Netflix history only.")
def spillover_forecast(storm_id: str) -> dict:
    for storm in _storms():
        if storm["summary"]["id"] == storm_id:
            return storm["detail"]["spillover"] | {"title": storm["summary"]["title"]}
    return {"error": f"no storm with id {storm_id!r}; call list_storms first"}


@server.tool(description="Launch kit for one forecast country of a breakout, by storm id from list_storms and a "
                         "country code or name from its spillover forecasts: what the title's audience there "
                         "over-indexes on in Qloo's artist, tv_show, movie and brand domains (up to 5 names each, "
                         "in Qloo's order) and hotspot_places, the up-to-three places in that country where the audience "
                         "concentrates most (OpenStreetMap names). It does not change the probabilities.")
def launch_kit(storm_id: str, country: str) -> dict:
    for storm in _storms():
        if storm["summary"]["id"] != storm_id:
            continue
        wanted = country.strip().lower()
        names = {f["code"].lower(): f["name"] for f in storm["detail"]["spillover"]["forecasts"]}
        for row in storm["detail"].get("launch_kit") or []:
            if wanted in (row["code"].lower(), names.get(row["code"].lower(), "").lower()):
                return {"title": storm["summary"]["title"], "country": names.get(row["code"].lower(), row["code"]),
                        "launch_kit": row["kit"], "hotspot_places": (row.get("hotspots") or {}).get("places", [])}
        return {"error": f"no launch kit for {country!r}; kits cover the top three forecast countries with Qloo data"}
    return {"error": f"no storm with id {storm_id!r}; call list_storms first"}


@server.tool(description=f"RIPPLE: score up to {MAX_SONGS} songs placed in a show or film. The score is the Qloo "
                         "age gap in [0,1]: how far each artist's audience sits from the show's by age band. Prior "
                         "Wikipedia views and taste fit are returned as context only. songs is a list of [song, artist] "
                         "pairs. as_of (YYYY-MM-DD, optional) changes only the Wikipedia context window; Qloo audiences "
                         f"are today's. Limited to {RIPPLE_PER_HOUR} calls per hour.")
def ripple_score(show: str, songs: list[list[str]], as_of: str | None = None) -> dict:
    when = None
    if as_of is not None:
        try:
            when = date.fromisoformat(as_of)
        except ValueError:
            return {"error": f"as_of must be YYYY-MM-DD; got {as_of!r}"}
        if not (WIKI_FIRST_DAY <= when <= date.today()):
            return {"error": f"as_of must be between {WIKI_FIRST_DAY} and today; got {as_of}"}
    now = time.time()
    _ripple_calls[:] = [t for t in _ripple_calls if now - t < 3600]
    if len(_ripple_calls) >= RIPPLE_PER_HOUR:
        return {"error": f"ripple_score is limited to {RIPPLE_PER_HOUR} calls per hour per server process; try again later"}
    _ripple_calls.append(now)
    placements = [(pair[0], pair[1]) for pair in songs if len(pair) == 2][:MAX_SONGS]
    return score_placements(Qloo(call_budget=40), show, placements, as_of=when)


@server.tool(description=f"Sync Scout: for a show or film, up to {TOP_N} artists from Qloo's taste neighbourhood for that "
                         "title, ranked by the Qloo age gap (how far the artist's audience sits from the show's by age "
                         "band, 0 to 1). It ranks artists, not scenes or songs. The gap tracked real song spikes but not "
                         "a placebo in our backtest; the evidence is modest and in-sample, not a hit predictor. Each row "
                         "has name, entity_id, gap, taste_rank (Qloo's taste order) and a why line. Takes about 15 "
                         f"seconds uncached and uses up to {MAX_QLOO_CALLS} Qloo calls. Limited to {SCOUT_PER_HOUR} calls per hour.")
def sync_scout(show: str) -> dict:
    name = show.strip()
    if not name or len(name) > 120:
        return {"error": "show must be 1 to 120 characters"}
    now = time.time()
    _scout_calls[:] = [t for t in _scout_calls if now - t < 3600]
    if len(_scout_calls) >= SCOUT_PER_HOUR:
        return {"error": f"sync_scout is limited to {SCOUT_PER_HOUR} calls per hour per server process; try again later"}
    _scout_calls.append(now)
    return scout(Qloo(call_budget=MAX_QLOO_CALLS), name)


if __name__ == "__main__":
    server.run("stdio")
