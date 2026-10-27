"""HTTP API for AFTERSHOCK. Serves precomputed storms, the scorecard, replays and live RIPPLE scoring.

Live Qloo calls happen only in /api/ripple and /api/scout, capped per visitor; everything else is read from files
the forecast job writes. The Qloo key stays in the server environment.
"""
import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles

from aftershock import titles as title_index
from aftershock.qloo import CACHE_DIR, Qloo, QlooError
from aftershock.ripple import MAX_SONGS, score_placements
from aftershock.sync_scout import MAX_QLOO_CALLS, public_ripple, scout

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / "data" / "private"
PUBLIC_DATA = ROOT / "data" / "public"
TITLES = PRIVATE / "titles.json"
RIPPLE_PER_HOUR = 10
RIPPLE_PER_DAY = 300  # live scorings per server process per day, all visitors
MAX_FIELD = 120
WIKI_FIRST_DAY = date(2015, 8, 1)  # Wikimedia per-article pageviews start in July 2015

app = FastAPI(title="AFTERSHOCK", docs_url=None, redoc_url=None)
_ripple_hits = defaultdict(deque)
_daily = {"day": None, "count": 0}


def _load(path):
    if not path.exists():
        raise HTTPException(503, f"{path.name} has not been generated yet")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "qloo_key": bool(os.environ.get("QLOO_API_KEY")),
            "cache_entries": len(list(CACHE_DIR.glob("*.json"))) if CACHE_DIR.exists() else 0}


def _hero(items):
    """Clearest worked example: highest top-forecast probability among storms whose top forecast country has a
    title-specific launch-kit row with at least one hotspot place. None when no storm qualifies."""
    best = None
    for item in items:
        summ, detail = item["summary"], item["detail"]
        top = summ.get("top_forecast")
        if not top:
            continue
        row = next((r for r in detail.get("launch_kit", []) if r.get("code") == top["code"]), None)
        places = ((row or {}).get("hotspots") or {}).get("places") or []
        if not row or row.get("generic") or not places or not any((row.get("kit") or {}).values()):
            continue
        if best is None or top["probability"] > best[0]:
            best = (top["probability"], summ, row, top, places)
    if best is None:
        return None
    _, summ, row, top, places = best

    def fresh(domain, n):
        seen = {c.casefold() for c in (row.get("control") or {}).get(domain, [])}
        return [e["name"] for e in (row["kit"].get(domain) or []) if e["name"].casefold() not in seen][:n]

    return {"id": summ["id"], "title": summ["title"], "origin_countries": summ["origin_countries"],
            "country": top["name"], "code": top["code"], "probability": top["probability"], "why": top.get("why"),
            "artists": fresh("artist", 3), "brands": fresh("brand", 2), "places": places[:3],
            "specificity": row.get("specificity")}


MAP_TOP_TITLES = 3


def _week_map(items):
    """Per country, the chance that at least one of this week's breakouts arrives (1 - product of (1 - p) over
    storms) and the 3 likeliest. Only each storm's published forecast rows count, so it is a floor."""
    none, top, origins = defaultdict(lambda: 1.0), defaultdict(list), set()
    for item in items:
        summ = item["summary"]
        origins.update(o["code"] for o in summ["origin_countries"])
        for fc in item["detail"].get("spillover", {}).get("forecasts", []):
            none[fc["code"]] *= 1 - fc["probability"]
            top[fc["code"]].append((fc["probability"], summ["id"], summ["title"], fc["name"]))
    countries = []
    chance = {code: 1 - q for code, q in none.items()}
    for code in sorted(chance, key=lambda c: -chance[c]):
        best = sorted(top[code], key=lambda t: -t[0])[:MAP_TOP_TITLES]
        countries.append({"code": code, "name": best[0][3], "chance": round(chance[code], 4),
                          "top": [{"id": i, "title": t, "p": p} for p, i, t, _ in best]})
    return {"origins": sorted(origins), "countries": countries}


@app.get("/api/storms")
def storms():
    data = _load(PRIVATE / "storms.json")
    def kit_rows(s):
        return [r for r in s["detail"].get("launch_kit", []) if r.get("kit") and any(r["kit"].values())]

    return {"week": data["week"], "hero": _hero(data["storms"]), "map": _week_map(data["storms"]), "storms": [
        s["summary"] | {"has_kit": bool(kit_rows(s)), "kit_specific": any(not r.get("generic") for r in kit_rows(s))}
        for s in data["storms"]]}


@app.get("/api/storms/{storm_id}")
def storm(storm_id: str):
    for item in _load(PRIVATE / "storms.json")["storms"]:
        if item["summary"]["id"] == storm_id:
            return item["detail"]
    raise HTTPException(404, f"no storm with id {storm_id!r}")


MAX_TITLE_QUERY = 80


@app.get("/api/title")
def netflix_title(name: str = Query(..., min_length=1, max_length=MAX_TITLE_QUERY)):
    """When and where a title charted in Netflix's Top 10 (since 2024), and where it may chart next.
    Reads files only: no Qloo call, so no live-lookup slot is used."""
    return title_history(name)


def title_history(name):
    loaded = title_index.load(TITLES)
    if loaded is None:
        raise HTTPException(503, f"{TITLES.name} has not been generated yet")
    storms = _load(PRIVATE / "storms.json")["storms"] if (PRIVATE / "storms.json").exists() else []
    found = title_index.history(loaded, name, storms)
    if found is None:
        raise HTTPException(404, f"Not in Netflix's Top 10 since {loaded[0]['since'][:4]} in any country")
    return found


@app.get("/api/ripples")
def ripples():
    """New releases whose soundtracks were scored as of release day, with the early Wikipedia read."""
    data = _load(PRIVATE / "storms.json")
    return {"ripples": [{k: r[k] for k in ("id", "show", "show_type", "platform", "release_date")} |
                        {"songs": len(r["songs"]), "top_song": r["songs"][0] if r["songs"] else None,
                         "locked_at": r.get("locked_at"), "lockable": r.get("lockable"),
                         "not_locked_reason": r.get("not_locked_reason")} for r in data.get("ripples", [])]}


@app.get("/api/ripples/{ripple_id}")
def ripple_title(ripple_id: str):
    for item in _load(PRIVATE / "storms.json").get("ripples", []):
        if item["id"] == ripple_id:
            return public_ripple(item)
    raise HTTPException(404, f"no scored release with id {ripple_id!r}")


@app.get("/api/scorecard")
def scorecard():
    body = _load(PRIVATE / "scorecard.json")
    experiment = ROOT / "data" / "results" / "kit_experiment.json"
    if experiment.exists():
        body = {**body, "kit_experiment": _kit_experiment(json.loads(experiment.read_text(encoding="utf-8")))}
    return body


def _kit_experiment(raw):
    """The pre-registered Qloo-versus-LLM kit result, reduced to what the scorecard shows."""
    spec, ground = raw.get("title_specificity") or {}, raw.get("llm_grounding") or {}
    return {"verdict": spec.get("verdict"), "qloo": spec.get("qloo"), "llm": spec.get("llm"),
            "p_qloo_greater": spec.get("p_qloo_greater"), "scored_pairs": raw.get("scored_pairs"),
            "grounding_share": ground.get("share_resolving_in_qloo"), "model": raw.get("model")}


@app.get("/api/replays")
def replays():
    return _load(PUBLIC_DATA / "replays.json")


def _visitor(request):
    """First address in X-Forwarded-For (the client, behind a proxy), else the socket peer."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _split_song(chunk):
    """"song | artist" (first "|"), else "song by artist" split on the LAST " by "."""
    if "|" in chunk:
        return tuple(part.strip() for part in chunk.split("|", 1))
    cut = chunk.lower().rfind(" by ")
    if cut < 0:
        raise HTTPException(422, f"each song must be 'song|artist' or 'song by artist'; got {chunk[:MAX_FIELD]!r}")
    return chunk[:cut].strip(), chunk[cut + 4:].strip()


def _parse_songs(songs):
    placements = []
    for chunk in filter(None, (c.strip() for c in songs.split(";"))):
        song, artist = _split_song(chunk)
        if not song or not artist or len(song) > MAX_FIELD or len(artist) > MAX_FIELD:
            raise HTTPException(422, f"song and artist must each be 1 to {MAX_FIELD} characters")
        placements.append((song, artist))
    if not placements or len(placements) > MAX_SONGS:
        raise HTTPException(422, f"send 1 to {MAX_SONGS} songs; got {len(placements)}")
    return placements


def _take_live_slot(request):
    """Shared per-visitor hourly and per-process daily limit for every endpoint that calls Qloo live."""
    hits = _ripple_hits[_visitor(request)]
    now = time.time()
    while hits and now - hits[0] > 3600:
        hits.popleft()
    if len(hits) >= RIPPLE_PER_HOUR:
        raise HTTPException(429, f"limit is {RIPPLE_PER_HOUR} live scorings per hour per visitor")
    today = date.today()
    if _daily["day"] != today:
        _daily.update(day=today, count=0)
    if _daily["count"] >= RIPPLE_PER_DAY:
        raise HTTPException(429, f"daily limit of {RIPPLE_PER_DAY} live scorings across all visitors is used up; try again tomorrow")
    hits.append(now)
    _daily["count"] += 1


@app.get("/api/ripple")
def ripple(request: Request, show: str = Query(..., min_length=1, max_length=MAX_FIELD),
           songs: str = Query(..., min_length=3, max_length=MAX_SONGS * (2 * MAX_FIELD + 2)),
           as_of: date | None = None):
    placements = _parse_songs(songs)
    if as_of and not (WIKI_FIRST_DAY <= as_of <= date.today()):
        raise HTTPException(422, f"as_of must be between {WIKI_FIRST_DAY} and today; got {as_of}")
    _take_live_slot(request)
    try:
        return public_ripple(score_placements(Qloo(call_budget=40), show, placements, as_of=as_of))
    except QlooError as err:
        log.warning("ripple scoring failed: %s", err)
        raise HTTPException(502, "Qloo did not answer this request; try again in a minute") from err


@app.get("/api/scout")
def sync_scout(request: Request, show: str = Query(..., min_length=1, max_length=MAX_FIELD)):
    """Qloo-sourced candidate artists for a show, ranked by age gap. Same limiter as /api/ripple."""
    name = show.strip()
    if not name:
        raise HTTPException(422, "show must not be blank")
    _take_live_slot(request)
    try:
        return scout(Qloo(call_budget=MAX_QLOO_CALLS), name)
    except QlooError as err:
        log.warning("sync scout failed: %s", err)
        raise HTTPException(502, "Qloo did not answer this request; try again in a minute") from err


# Local runs serve the frontend too; on Vercel, public/ is served by the platform.
if (ROOT / "public").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "public", html=True), name="site")
