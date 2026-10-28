"""HTTP API for AFTERSHOCK. Serves precomputed storms, the scorecard, replays and live RIPPLE scoring.

Live Qloo calls happen only in /api/ripple, /api/scout and /api/check, capped per visitor; everything else is read from files
the forecast job writes. The Qloo key stays in the server environment.
"""
import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import date
from typing import Literal
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles

from aftershock import artist_view
from aftershock import grounded_plan
from aftershock import ask as ask_agent
from aftershock import launch_brief
from aftershock import storm_archive
from aftershock import titles as title_index
from aftershock.qloo import CACHE_DIR, Qloo, QlooError
from aftershock.ripple import MAX_SONGS, score_placements
from aftershock.sync_scout import MAX_QLOO_CALLS, public_ripple, scout

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / "data" / "private"
PUBLIC_DATA = ROOT / "data" / "public"
TITLES = PRIVATE / "titles.json"
ARCHIVE = PRIVATE / "storm_archive"
RIPPLE_PER_HOUR = 10
RIPPLE_PER_DAY = 300  # live scorings per server process per day, all visitors
MAX_FIELD = 120
WIKI_FIRST_DAY = date(2015, 8, 1)  # Wikimedia per-article pageviews start in July 2015

app = FastAPI(title="AFTERSHOCK", docs_url=None, redoc_url=None)
_ripple_hits = defaultdict(deque)
_daily = {"day": None, "count": 0}


def _load_storms():
    """storms.json with names that are the title itself or its franchise removed from every AI plan (read time; the
    weekly run's file is untouched)."""
    data = _load(PRIVATE / "storms.json")
    for item in data.get("storms", []):
        grounded_plan.clean_rows(item.get("detail") or {})
    return data


def _load(path):
    if not path.exists():
        raise HTTPException(503, f"{path.name} has not been generated yet")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "qloo_key": bool(os.environ.get("QLOO_API_KEY")),
            "cache_entries": len(list(CACHE_DIR.glob("*.json"))) if CACHE_DIR.exists() else 0}


def _featured_hero(items, featured):
    """(summary, row, forecast, places) for the featured plan's title and country, so the home example and the
    "Plan a launch" button show the same case; None when that row is missing or has no places."""
    item = next((i for i in items if i["summary"]["id"] == featured.get("id")), None)
    if not item:
        return None
    row = next((r for r in item["detail"].get("launch_kit", []) if r.get("code") == featured.get("code")), None)
    top = next((f for f in item["detail"].get("spillover", {}).get("forecasts", []) if f["code"] == featured.get("code")), None)
    places = ((row or {}).get("hotspots") or {}).get("places") or []
    return (item["summary"], row, top, places) if row and top and places else None


def _hero(items, featured=None):
    """Clearest worked example: the featured plan when there is one (its Qloo-confirmed names, as in its brief);
    otherwise the highest top-forecast probability among storms whose top forecast country has a title-specific
    launch-kit row with at least one hotspot place. None when no storm qualifies."""
    picked = _featured_hero(items, featured) if featured else None
    if picked:
        summ, row, top, places = picked
        confirmed = (row.get("plan") or {}).get("confirmed") or []
        meta = summ.get("meta") or {}
        origin_year = int(summ["origin_week"][:4]) if summ.get("origin_week") else None
        return {"id": summ["id"], "title": summ["title"], "origin_countries": summ["origin_countries"],
                "year": meta.get("year"), "genres": meta.get("genres") or [],
                "just_added": bool(meta.get("year") and origin_year and origin_year - meta["year"] > 1),
                "country": top["name"], "code": top["code"], "probability": top["probability"], "why": top.get("why"),
                "artists": [c["name"] for c in confirmed if c["domain"] == "artist"][:3],
                "brands": [c["name"] for c in confirmed if c["domain"] == "brand"][:2],
                "places": places[:3], "specificity": row.get("specificity")}
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

    meta = summ.get("meta") or {}
    origin_year = int(summ["origin_week"][:4]) if summ.get("origin_week") else None
    return {"id": summ["id"], "title": summ["title"], "origin_countries": summ["origin_countries"],
            "year": meta.get("year"), "genres": meta.get("genres") or [],
            "just_added": bool(meta.get("year") and origin_year and origin_year - meta["year"] > 1),
            "country": top["name"], "code": top["code"], "probability": top["probability"], "why": top.get("why"),
            "artists": fresh("artist", 3), "brands": fresh("brand", 2), "places": places[:3],
            "specificity": row.get("specificity")}


FEATURED_MIN_CONFIRMED = 3
FEATURED_RECENT_YEARS = 5
FEATURED_FALLBACK_SEARCH = 8


def _rank_key(item):
    return -((item["summary"].get("top_forecast") or {}).get("probability") or -1)


def _country_name(item, code):
    fc = next((f for f in item["detail"].get("spillover", {}).get("forecasts", []) if f["code"] == code), {})
    return fc.get("name"), fc.get("probability")


def featured_plan(items, week):
    """The plan the site opens on: {id, code, title, country}, or None when no storm has a launch-kit row.
    Among title-specific kit rows with at least FEATURED_MIN_CONFIRMED Qloo-confirmed AI picks and at least one
    event idea, prefer titles released within FEATURED_RECENT_YEARS of the data week (meta.year), then most
    confirmed picks, then the country's chance. Otherwise the older rule: among the week's FEATURED_FALLBACK_SEARCH
    likeliest storms, the first title-specific row with enough confirmed picks, else the top storm's first kit row."""
    try:
        data_year = int(str(week)[:4])
    except (TypeError, ValueError):
        data_year = None
    ranked = sorted(items, key=_rank_key)

    def usable(item):
        return [r for r in item["detail"].get("launch_kit", []) if r.get("kit") and any(r["kit"].values())
                and _country_name(item, r["code"])[0]]

    def pick(item, row):
        return {"id": item["summary"]["id"], "code": row["code"], "title": item["summary"]["title"],
                "country": _country_name(item, row["code"])[0]}

    def confirmed(row):
        return len((row.get("plan") or {}).get("confirmed") or [])

    candidates = []
    for item in ranked:
        year = (item["summary"].get("meta") or {}).get("year")
        recent = bool(data_year and isinstance(year, int) and data_year - year <= FEATURED_RECENT_YEARS)
        for row in usable(item):
            has_events = any(e.get("artist") and e.get("cities") for e in row.get("events") or [])
            if not row.get("generic") and confirmed(row) >= FEATURED_MIN_CONFIRMED and has_events:
                candidates.append(((recent, confirmed(row), _country_name(item, row["code"])[1] or 0), item, row))
    if candidates:
        _, item, row = max(candidates, key=lambda c: c[0])
        return pick(item, row)
    fallback = None
    for item in ranked[:FEATURED_FALLBACK_SEARCH]:
        rows = usable(item)
        grounded = next((r for r in rows if not r.get("generic") and confirmed(r) >= FEATURED_MIN_CONFIRMED), None)
        if grounded:
            return pick(item, grounded)
        if fallback is None and rows:
            fallback = pick(item, rows[0])
    return fallback


def summary_label(summary, all_summaries):
    """A name that tells storms apart: the title plus its season, plus category and year when two storms would
    still read the same (a film and a series called "Money Trap")."""
    def base(s):
        return s["title"] + (f" {s['season']}" if s.get("season") else "")

    label = base(summary)
    if sum(1 for s in all_summaries if base(s) == label) > 1:
        year = (summary.get("meta") or {}).get("year")
        label += f" ({summary.get('category', '').lower()}{', ' + str(year) if year else ''})"
    return label


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
    data = _load_storms()
    def kit_rows(s):
        return [r for r in s["detail"].get("launch_kit", []) if r.get("kit") and any(r["kit"].values())]

    summaries = [s["summary"] for s in data["storms"]]
    featured = featured_plan(data["storms"], data["week"])
    return {"week": data["week"], "hero": _hero(data["storms"], featured), "map": _week_map(data["storms"]),
            "featured_plan": featured, "storms": [
        s["summary"] | {"has_kit": bool(kit_rows(s)), "kit_specific": any(not r.get("generic") for r in kit_rows(s)),
                        "label": summary_label(s["summary"], summaries)}
        for s in data["storms"]]}


@app.get("/api/storms/{storm_id}")
def storm(storm_id: str):
    current = PRIVATE / "storms.json"
    # A missing current week (fresh clone, or between runs) still lets archived storm links resolve.
    for item in _load_storms()["storms"] if current.exists() else []:
        if item["summary"]["id"] == storm_id:
            return launch_brief.attach(item["detail"])
    found = storm_archive.find(ARCHIVE, storm_id)
    if found:
        return launch_brief.attach(found[1] | {"archived_week": found[0]})
    raise HTTPException(404, f"No breakout called {storm_id} in any week we have forecast.")


@app.get("/api/brief")
def brief(storm_id: str = Query(..., alias="storm", min_length=1, max_length=MAX_FIELD),
          country: str = Query(..., min_length=2, max_length=MAX_FIELD)):
    """The launch brief for one breakout in one of its launch-kit countries (country is a code such as TW):
    the agent's steps and the finished brief. Reads files only; no Qloo or model call."""
    detail = storm(storm_id)
    made = launch_brief.brief(detail, country.strip())
    if made is None:
        raise HTTPException(404, f"No launch kit for {country} on {detail['title']}; kits cover the top three "
                                 "forecast countries with Qloo data.")
    return made


def _artist_index():
    data = _load_storms()
    return artist_view.build(data["storms"]), data["week"]


@app.get("/api/artists")
def artists():
    """Artists that appear this week as Qloo-confirmed picks or in event ideas: name, slug, breakouts, countries."""
    index, week = _artist_index()
    return artist_view.listing(index, week)


@app.get("/api/artists/{slug}")
def artist(slug: str):
    """One artist's breakouts this week: where each title is going, the chance, cities and Qloo's evidence."""
    index, week = _artist_index()
    found = artist_view.detail(index, week, slug)
    if found is None:
        raise HTTPException(404, artist_view.NOT_FOUND.format(slug=slug[:MAX_FIELD]))
    return found


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
    storms = _load_storms()["storms"] if (PRIVATE / "storms.json").exists() else []
    found = title_index.history(loaded, name, storms)
    if found is None:
        raise HTTPException(404, f"No close match in Netflix's Top 10 since {loaded[0]['since'][:4]}")
    return found


@app.get("/api/ripples")
def ripples():
    """New releases whose soundtracks were scored as of release day, with the early Wikipedia read."""
    data = _load_storms()
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
    grounded = ROOT / "data" / "results" / "grounded_plan.json"
    if grounded.exists():
        body = {**body, "grounded_plan": _grounded_plan(json.loads(grounded.read_text(encoding="utf-8")))}
    lead = ROOT / "data" / "results" / "lead_time.json"
    if lead.exists():
        body = {**body, "lead_time": _lead_time(json.loads(lead.read_text(encoding="utf-8")))}
    return body


def _lead_time(raw):
    """The held-out lead-time measurement, reduced to what the scorecard and home page show (titles and countries only)."""
    keep = ("breakouts", "hit_breakouts", "hit_rate", "picks", "picks_charted", "per_pick_precision", "lead_weeks")
    return {"horizon_weeks": raw.get("horizon_weeks"), "top_k": raw.get("top_k"), "test_events": raw.get("test_events"),
            "breakouts_that_spread_at_all": raw.get("breakouts_that_spread_at_all"),
            "model": {k: (raw.get("model") or {}).get(k) for k in keep},
            "baseline": {k: (raw.get("baseline") or {}).get(k) for k in keep},
            "baseline_most_common_picks": raw.get("baseline_most_common_picks"),
            "case_study_rule": raw.get("case_study_rule"), "case_studies": raw.get("case_studies") or []}


def _grounded_plan(raw):
    """The exploratory grounded-plan result, reduced to what the scorecard shows. `unbacked_share` is the share of the
    LLM's named picks that Qloo did not confirm (not placed with the audience, or not in Qloo at all)."""
    counts, spec = raw.get("verdict_counts") or {}, raw.get("title_specificity_same_pairs") or {}
    total = sum(counts.values())
    return {"status": raw.get("status"), "pairs": raw.get("pairs"), "picks_checked": raw.get("picks_checked") or total,
            "unbacked_share": (1 - counts.get("confirmed", 0) / total) if total else None,
            "counts": {k: counts.get(k, 0) for k in ("confirmed", "not_placed", "not_in_qloo")} if total else None,
            "specificity_plan": spec.get("grounded_plan_confirmed_only"), "specificity_llm": spec.get("llm_all_picks"),
            "specificity_pairs": spec.get("pairs")}


def _kit_experiment(raw):
    """The pre-registered Qloo-versus-LLM kit result, reduced to what the scorecard shows."""
    spec, ground = raw.get("title_specificity") or {}, raw.get("llm_grounding") or {}
    grounded = raw.get("title_specificity_grounded_llm_only") or {}
    return {"verdict": spec.get("verdict"), "qloo": spec.get("qloo"), "llm": spec.get("llm"),
            "p_qloo_greater": spec.get("p_qloo_greater"), "scored_pairs": raw.get("scored_pairs"),
            "grounding_share": ground.get("share_resolving_in_qloo"), "model": raw.get("model"),
            "grounded_pairs": grounded.get("pairs"), "grounded_qloo": grounded.get("qloo"),
            "grounded_llm": grounded.get("llm_grounded")}


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


def qloo_failure(err):
    """Status code and visitor-facing message for a failed live Qloo lookup. A refused key will not
    recover by retrying, so it says so and points at the parts of the site that need no live call."""
    if err.status in (401, 403) or "QLOO_API_KEY is not set" in str(err):
        reason = "Qloo refused the API key" if err.status else "no Qloo API key is set"
        return 503, (f"Live Qloo lookups are switched off right now ({reason}). The weekly "
                     "forecasts, launch kits, hotspots and map on this site still work.")
    if err.status == 429:
        return 503, "Qloo is rate-limiting live lookups; try again in a few minutes."
    return 502, "Qloo did not answer this request; try again in a minute"


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
        raise HTTPException(*qloo_failure(err)) from err


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
        raise HTTPException(*qloo_failure(err)) from err


MAX_NAME = 80


@app.get("/api/check")
def check(request: Request, storm_id: str = Query(..., alias="storm", min_length=1, max_length=MAX_FIELD),
          country: str = Query(..., min_length=2, max_length=MAX_FIELD),
          domain: Literal["artist", "brand", "tv_show", "movie"] = Query(...),
          name: str = Query(..., min_length=1, max_length=MAX_NAME)):
    """Check one typed name for a title's audience in one of its launch-kit countries, the way the weekly plan checks
    each AI name: {verdict: confirmed | not_placed | not_in_qloo, name as Qloo spells it}. Live; same limiter as
    /api/ripple."""
    typed = " ".join(name.split())
    if not typed:
        raise HTTPException(422, "name must not be blank")
    detail = storm(storm_id)
    code = country.strip().upper()
    row = next((r for r in detail.get("launch_kit") or [] if r.get("code", "").upper() == code and r.get("kit")), None)
    countries = {f["code"].upper(): f["name"] for f in detail.get("spillover", {}).get("forecasts", [])}
    if not row or not detail.get("qloo_entity") or code not in countries:
        raise HTTPException(404, f"No launch kit for {country} on {detail['title']}; kits cover the top three "
                                 "forecast countries with Qloo data.")
    _take_live_slot(request)
    try:
        return grounded_plan.check_name(Qloo(call_budget=8), detail["qloo_entity"], countries[code], domain, typed)
    except QlooError as err:
        log.warning("name check failed: %s", err)
        raise HTTPException(*qloo_failure(err)) from err


class _Live:
    """Live Qloo tools for the ask router: the shared limiter and the same calls as /api/ripple and /api/scout."""

    def __init__(self, request):
        self.request = request

    def take(self):
        try:
            _take_live_slot(self.request)
        except HTTPException as err:
            raise ask_agent.LiveError(err.detail) from err

    def ripple(self, show, songs):
        try:
            return public_ripple(score_placements(Qloo(call_budget=40), show, songs))
        except QlooError as err:
            log.warning("ask: ripple scoring failed: %s", err)
            raise ask_agent.LiveError(qloo_failure(err)[1]) from err

    def scout(self, show):
        try:
            return scout(Qloo(call_budget=MAX_QLOO_CALLS), show)
        except QlooError as err:
            log.warning("ask: sync scout failed: %s", err)
            raise ask_agent.LiveError(qloo_failure(err)[1]) from err


def ask_context(live=None):
    path = PRIVATE / "storms.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"week": None, "storms": []}
    for item in data["storms"]:
        grounded_plan.clean_rows(item.get("detail") or {})
    return {"storms": data["storms"], "week": data["week"], "titles": title_index.load(TITLES), "live": live,
            "week_map": lambda: _week_map(data["storms"])}


@app.get("/api/ask")
def ask(request: Request, q: str = Query(..., min_length=1, max_length=ask_agent.MAX_QUESTION)):
    """A plain question routed to AFTERSHOCK's tools by fixed rules (no language model). Only the song and artist
    routes call Qloo live, and they use the same per-visitor limit as /api/ripple."""
    return ask_agent.answer(q, ask_context(_Live(request)))


# Local runs serve the frontend too; on Vercel, public/ is served by the platform.
if (ROOT / "public").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "public", html=True), name="site")
