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

from aftershock import artist_view
from aftershock import ask as ask_agent
from aftershock import launch_brief as brief_builder
from aftershock import release_plan as release_planner
from aftershock import titles as title_index
from aftershock.qloo import Qloo
from aftershock.ripple import MAX_SONGS, score_placements
from aftershock.sync_scout import MAX_QLOO_CALLS, TOP_N, public_ripple, scout

WIKI_FIRST_DAY = date(2015, 8, 1)  # Wikimedia per-article pageviews start in July 2015
RIPPLE_PER_HOUR = 20
SCOUT_PER_HOUR = 6
RELEASE_PER_HOUR = 6
_ripple_calls: list[float] = []
_scout_calls: list[float] = []
_release_calls: list[float] = []

ROOT = Path(__file__).resolve().parent.parent
STORMS = ROOT / "data" / "private" / "storms.json"
TITLES = ROOT / "data" / "private" / "titles.json"

server = MCPServer(
    name="aftershock",
    instructions="Two forecasts. SPILLOVER: for a title that entered Netflix's Top 10 in 1 to 3 countries, the "
                 "probability that each other country charts it within 4 weeks, from Netflix history only (backtest "
                 "ROC AUC 0.817 on 829 breakouts; Qloo added no lift). Qloo supplies the partners list and the launch kit, "
                 "and each kit row says how title-specific it is versus the country's taste. RIPPLE: "
                 "for songs placed in a show, a score in [0,1] that is the Qloo age gap between the artist's audience "
                 "and the show's; it is an explorer, not a predictor: on 24 shows the age gap did not predict song "
                 "spikes (p 0.40). Prior Wikipedia views are context only. Probabilities are not certainties.",
)


def _storms():
    if not STORMS.exists():
        return []
    return json.loads(STORMS.read_text(encoding="utf-8"))["storms"]


@server.tool(description="List this week's breakouts: titles that entered the Netflix Top 10 in 1 to 3 countries.")
def list_storms() -> list[dict]:
    return [s["summary"] for s in _storms()]


@server.tool(description="Netflix history of any title that charted in a Top 10 since 2024: the week it first entered a "
                         "Top 10 and where, every country it has since charted in (with the week), whether it is still "
                         "spreading, and for a recent title not among this week's breakouts the countries it is likely to "
                         "chart in next (history only). Matches ignore case, accents and 'Season N'. storm_id is set when "
                         "it is one of this week's breakouts (use spillover_forecast). No Qloo call.")
def netflix_history(title: str) -> dict:
    name = title.strip()
    if not name or len(name) > 80:
        return {"error": "title must be 1 to 80 characters"}
    loaded = title_index.load(TITLES)
    if loaded is None:
        return {"error": "titles.json has not been generated yet; run scripts/run_forecasts.py"}
    found = title_index.history(loaded, name, _storms())
    return found or {"error": f"Not in Netflix's Top 10 since {loaded[0]['since'][:4]} in any country"}


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
                         "concentrates most (OpenStreetMap names), plus specificity (0 to 1, how much the kit depends on the title "
                         "rather than the country) and generic (true when the kit mostly matches Qloo's country-only "
                         "taste). It does not change the probabilities.")
def launch_kit(storm_id: str, country: str) -> dict:
    for storm in _storms():
        if storm["summary"]["id"] != storm_id:
            continue
        wanted = country.strip().lower()
        names = {f["code"].lower(): f["name"] for f in storm["detail"]["spillover"]["forecasts"]}
        for row in storm["detail"].get("launch_kit") or []:
            if wanted in (row["code"].lower(), names.get(row["code"].lower(), "").lower()):
                return {"title": storm["summary"]["title"], "country": names.get(row["code"].lower(), row["code"]),
                        "launch_kit": row["kit"], "specificity": row.get("specificity"),
                        "generic": row.get("generic"), "hotspot_places": (row.get("hotspots") or {}).get("places", [])}
        return {"error": f"no launch kit for {country!r}; kits cover the top three forecast countries with Qloo data"}
    return {"error": f"no storm with id {storm_id!r}; call list_storms first"}


@server.tool(description="Launch brief for one breakout in one of its launch-kit countries, by storm id from list_storms and "
                         "a country code (such as TW) from its launch kits: the agent's steps (forecast, Qloo kit, AI "
                         "proposals, Qloo check, cities) with what each found and the rule it applied, then the brief: "
                         "headline, chance and rank, cities to start in, partners by domain (Qloo-confirmed AI picks "
                         "first, else Qloo's kit), what not to claim, evidence notes and a two-sentence summary with "
                         "its source. Reads files only; no Qloo or model call.")
def launch_brief(storm_id: str, country_code: str) -> dict:
    for storm in _storms():
        if storm["summary"]["id"] == storm_id:
            made = brief_builder.brief(storm["detail"], country_code.strip())
            return made or {"error": f"no launch kit for {country_code!r}; kits cover the top three forecast "
                                     "countries with Qloo data"}
    return {"error": f"no storm with id {storm_id!r}; call list_storms first"}


@server.tool(description="Artist opportunities this week: for an artist's name (as in a launch brief's partners or event "
                         "ideas), every breakout where Qloo links that artist to the title's audience in a forecast country: "
                         "title, origin, country, the chance the title charts there within 4 weeks, the cities where both "
                         "audiences concentrate (when an event idea exists), whether Qloo's own kit also named the artist and "
                         "whether Qloo confirmed the AI's suggestion. Audience overlap, not a forecast of streams or ticket "
                         "sales. Reads files only; no Qloo or model call.")
def artist_opportunities(artist_name: str) -> dict:
    name = artist_name.strip()
    if not name or len(name) > 120:
        return {"error": "artist_name must be 1 to 120 characters"}
    if not STORMS.exists():
        return {"error": "storms.json has not been generated yet; run scripts/run_forecasts.py"}
    data = json.loads(STORMS.read_text(encoding="utf-8"))
    index = artist_view.build(data["storms"])
    want = artist_view.slugify(name) or name.casefold()
    found = next((a for a in index["artists"] if a["slug"] == want or a["name"].casefold() == name.casefold()), None)
    if found is None:
        return {"error": artist_view.NOT_FOUND.format(slug=name)}
    return {"week": data["week"], **found}


@server.tool(description=f"RIPPLE: score up to {MAX_SONGS} songs placed in a show or film. The score is the Qloo "
                         "age gap in [0,1]: how far each artist's audience sits from the show's by age band. Prior "
                         "Wikipedia views are returned as context only; raw Qloo values are not returned. songs is a list of [song, artist] "
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
    return public_ripple(score_placements(Qloo(call_budget=40), show, placements, as_of=when))


@server.tool(description=f"Sync Scout: for a show or film, up to {TOP_N} artists from Qloo's taste neighbourhood for that "
                         "title, ranked by the Qloo age gap (how far the artist's audience sits from the show's by age "
                         "band, 0 to 1). It ranks artists, not scenes or songs. It is a discovery shortlist: the age gap "
                         "did not predict song spikes in our test, so it is not a hit predictor. Each row "
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


@server.tool(description="Plan a release: for a film, series, music act or comedian (kind is film, series, music or "
                         "comedy) about to release or tour, the countries where Qloo finds the audience (ranked by "
                         "Qloo destination affinity, a relative score and not a probability), for the top three the "
                         "cities where the audience concentrates (Qloo heatmap density over Qloo destinations), venues that fit those cities "
                         "(cinemas, concert halls and live-music venues, or comedy clubs, picked by Qloo venue tags), and "
                         "what that audience also likes in the top two countries. If Qloo does not know the name "
                         "(an unreleased title), pass up to 5 comparable titles in `like` and up to 3 stand in as the "
                         "audience; signal.used says which. Returns steps: every Qloo call made, with endpoint and "
                         f"params. Optional: region (any, asia, europe, americas, middle-east-africa, oceania) limits the countries; "
                         f"home (ISO2 code such as IN) leaves the home market out of the ranking; goal is tour, premiere "
                         f"or digital (digital makes no venue calls; default tour for music and comedy, premiere for "
                         f"film and series). Also returns scores, every country checked. Uses up to "
                         f"{release_planner.MAX_CALLS} Qloo calls, about 20 seconds uncached. "
                         f"Limited to {RELEASE_PER_HOUR} calls per hour.")
def release_plan(name: str, kind: str, like: list[str] | None = None, region: str = "any", home: str | None = None,
                 goal: str | None = None) -> dict:
    try:
        typed, kind, comparables = release_planner.validate(name, kind, like or [])
        region, home, goal, _ = release_planner.validate_options(kind, region, home, goal)
    except release_planner.ReleaseInputError as err:
        return {"error": str(err)}
    now = time.time()
    _release_calls[:] = [t for t in _release_calls if now - t < 3600]
    if len(_release_calls) >= RELEASE_PER_HOUR:
        return {"error": f"release_plan is limited to {RELEASE_PER_HOUR} calls per hour per server process; try again later"}
    _release_calls.append(now)
    return release_planner.plan_release(Qloo(call_budget=release_planner.MAX_CALLS), typed, kind, comparables,
                                        region=region, home=home, goal=goal)


class _McpLive:
    """Live tools for ask(): the same per-process limits as ripple_score and sync_scout."""

    def take(self):
        pass

    def ripple(self, show, songs):
        out = ripple_score(show, [list(p) for p in songs])
        if "error" in out:
            raise ask_agent.LiveError(out["error"])
        return out

    def scout(self, show):
        out = sync_scout(show)
        if "error" in out:
            raise ask_agent.LiveError(out["error"])
        return out


@server.tool(description="Ask a plain-language question and let AFTERSHOCK pick the tool, by fixed rules (no language "
                         "model). Handles: where a title goes next; a launch kit for a title in a country (\"What should "
                         "Fukrey Returns pair with in Bangladesh?\"); artists for a show; \"song by artist for show\"; what "
                         "is heading to a country. Returns {intent, steps (which tools it used and what each found), "
                         "answer, links}. Song and artist questions call Qloo live and share those tools' limits.")
def ask(question: str) -> dict:
    loaded = title_index.load(TITLES)
    storms = _storms()
    from aftershock import api  # local: the week map helper lives with the API
    week = json.loads(STORMS.read_text(encoding="utf-8"))["week"] if STORMS.exists() else None
    return ask_agent.answer(question[:ask_agent.MAX_QUESTION], {
        "storms": storms, "week": week, "titles": loaded, "live": _McpLive(), "week_map": lambda: api._week_map(storms)})


if __name__ == "__main__":
    server.run("stdio")
