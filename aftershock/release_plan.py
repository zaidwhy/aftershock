"""Plan a release: where is the audience for a film, series, album or comedian's tour, which venues fit, and what
to pair it with locally? Qloo answers all three, so every step here is a Qloo call and the plan carries the trail.

The audience is one Qloo signal (the title, or up to three comparables when Qloo does not know an unreleased title).
Countries are ranked by calling the destination insights once per candidate country and keeping that country's best
destination affinity: without the country filter Qloo returns mostly the signal's home country. Destination affinity is
travel-flavoured (it favours resorts and old towns), so it ranks countries only. Where the audience lives inside each
of the top countries is the launch kits' heatmap (`aftershock.hotspots`) read through the same destinations: each real,
named destination is scored by the heatmap weight within DENSITY_KM of it, so the cities are places Qloo gave
coordinates for and the heatmap decides which of them the audience favours. Reverse geocoding (OpenStreetMap) is only
the fallback for a country where no destination has heatmap cells nearby. Venues come from Qloo's place insights
filtered by venue tag, around the strongest of those cities (unfiltered place results are gyms and villas). Local
taste is the signal's audience in the top two countries. Calls run in small thread pools: the Qloo client paces them at 4 per second, so threads only overlap
network waits. Affinity is Qloo's relative score, never a probability, and nothing here is a forecast of ticket
or stream numbers.

Every call goes through `_Trace`, which counts it against MAX_CALLS (cache hits included, so a plan costs the same
every time) and records endpoint and params for `steps`. The API key travels in a header and never appears there.
"""
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

import httpx

from aftershock import hotspots as audience_map
from aftershock.qloo import QlooError, norm

log = logging.getLogger(__name__)

MAX_FIELD = 120
MAX_LIKE = 5  # comparables accepted; the first MAX_USED_LIKE that Qloo resolves are the signal
MAX_USED_LIKE = 3
MAX_CALLS = 45
WORKERS = 8  # the Qloo client paces and locks its requests (4 a second); threads only overlap the network waits

# Big streaming and touring markets with diaspora spread, name as Qloo's location query spells it.
CANDIDATES = {"US": "United States", "GB": "United Kingdom", "CA": "Canada", "AU": "Australia", "IN": "India",
              "AE": "United Arab Emirates", "SA": "Saudi Arabia", "DE": "Germany", "FR": "France", "ES": "Spain",
              "IT": "Italy", "NL": "Netherlands", "SE": "Sweden", "BR": "Brazil", "MX": "Mexico", "AR": "Argentina",
              "JP": "Japan", "KR": "South Korea", "ID": "Indonesia", "PH": "Philippines", "NG": "Nigeria",
              "ZA": "South Africa", "TR": "Turkey", "SG": "Singapore"}
DESTINATION_TAKE = 15  # the country's destinations: the best affinity ranks the country, the rest are city candidates
MIN_POPULARITY = 0.4  # Qloo's destination popularity; see _candidates
CITIES_PER_COUNTRY = 3
DENSITY_KM = 40  # a candidate city's audience density is the heatmap weight within this distance
MERGE_KM = 15  # candidates this close are one city (Tokyo, Minato and Shinjuku; Mexico City and its old name)
MIN_RELATIVE_DENSITY = 0.1  # a city under a tenth of the country's best density is noise (Srinagar 0.1 against Manali 5.4)
HEATMAP_COUNTRIES = 3
GEOCODE_BUDGET_S = 10  # Nominatim allows 1 request per second; past this the cells stay and the names are dropped
VENUE_CITIES = 3
VENUE_ATTEMPTS = 4  # worst case 6 searches + 24 countries + 3 heatmaps + 4 venues + 6 taste = 43, under MAX_CALLS
VENUES_PER_CITY = 5
VENUE_RADIUS_M = 20000
TASTE_COUNTRIES = 2
TASTE_TAKE = 5
TASTE_DOMAINS = (("tv_show", "urn:entity:tv_show"), ("movie", "urn:entity:movie"), ("artist", "urn:entity:artist"))

# Search types per kind: a comedian is a person in Qloo and their specials are tv_shows; a film or series
# comparable may be either ("The Bridge" is a series even when the release is a film). Night clubs are not a
# music tag here: in probes they returned restaurants and hotels. `urn:tag:setting:qloo:music_venue` exists as
# a tag but matches no place.
KINDS = {
    "film": {"types": "urn:entity:movie,urn:entity:tv_show", "label": "film", "venue": "cinemas",
             "tags": ("urn:tag:category:place:movie_theater",)},
    "series": {"types": "urn:entity:tv_show,urn:entity:movie", "label": "series", "venue": "cinemas",
               "tags": ("urn:tag:category:place:movie_theater",)},
    "music": {"types": "urn:entity:artist", "label": "music", "venue": "concert halls and live-music venues",
              "tags": ("urn:tag:category:place:concert_hall", "urn:tag:category:place:live_music_venue")},
    "comedy": {"types": "urn:entity:person,urn:entity:tv_show", "label": "comedy", "venue": "comedy clubs",
               "tags": ("urn:tag:category:place:comedy_club",)},
}
VENUE_NOTE = ("Qloo lists venues by its own place ranking within the tag, not by this audience: adding the audience "
              "signal cut a probe list to a single venue, so it is left out. Tags are Qloo's and loose; a few results "
              "are bars, banquet halls or hotels that carry the venue tag. For film and series these are cinemas, "
              "not screening events.")


class ReleaseInputError(ValueError):
    """A bad field; the message names the field and its limit."""


class _CapReached(Exception):
    """The plan has used its MAX_CALLS."""


def _clean(text):
    return " ".join(str(text or "").split())


def split_like(text):
    return [part for part in re.split(r"[;,|]", text or "") if part.strip()]


def validate(name, kind, like=()):
    """(name, kind, [comparables]) with whitespace folded, or ReleaseInputError naming the field and its limit."""
    name = _clean(name)
    if not 1 <= len(name) <= MAX_FIELD:
        raise ReleaseInputError(f"name must be 1 to {MAX_FIELD} characters")
    if kind not in KINDS:
        raise ReleaseInputError(f"kind must be one of {', '.join(KINDS)}; got {_clean(kind)[:MAX_FIELD]!r}")
    if isinstance(like, str):
        like = split_like(like)
    names = [_clean(item) for item in like if _clean(item)]
    if len(names) > MAX_LIKE:
        raise ReleaseInputError(f"like must have at most {MAX_LIKE} comparables; got {len(names)}")
    if any(len(item) > MAX_FIELD for item in names):
        raise ReleaseInputError(f"each like comparable must be 1 to {MAX_FIELD} characters")
    return name, kind, names


class _Trace:
    """Counts every Qloo call against the cap and records it for the steps trail (thread-safe)."""

    def __init__(self, client, cap=MAX_CALLS):
        self.client, self.cap, self.calls, self.log = client, cap, 0, []
        self._lock = threading.Lock()

    def _take(self, stage, path, params, order):
        with self._lock:
            if self.calls >= self.cap:
                raise _CapReached()
            self.calls += 1
            entry = {"stage": stage, "order": order, "endpoint": path, "params": dict(params), "ok": True}
            self.log.append(entry)
        return entry

    def get(self, stage, path, params, order=0):
        entry = self._take(stage, path, params, order)
        try:
            return self.client.get(path, params)
        except (QlooError, httpx.HTTPError):
            entry["ok"] = False
            raise

    def search(self, stage, query, types, order=0, take=5):
        entry = self._take(stage, "/search", {"query": query, "types": types, "take": take}, order)
        try:
            return self.client.search(query, types=types, take=take)
        except (QlooError, httpx.HTTPError):
            entry["ok"] = False
            raise

    def stage(self, name):
        return sorted((e for e in self.log if e["stage"] == name), key=lambda e: e["order"])


def _fatal(err):
    """A refused key or a rate limit will not recover on the next call, so it ends the plan."""
    if not isinstance(err, QlooError):
        return False
    return err.status in (401, 403, 429) or "QLOO_API_KEY is not set" in str(err)


def _find(trace, name, types, order):
    """The search hit named `name`, or None. Exact name, or Qloo's "Name, Occupation" form for people ("Zakir
    Khan, Comedian"); a hit whose name only starts with `name` is not a match, since /search always returns its
    nearest hit ("Zakir Khan: Tathastu" for "Zakir Khan")."""
    want = norm(name, keep_subtitle=True)
    hits = trace.search("resolve", name, types, order=order)
    for hit in hits:
        if norm(hit.get("name", ""), keep_subtitle=True) == want:
            return hit
    for hit in hits:
        if "," in hit.get("name", "") and norm(hit["name"].split(",", 1)[0], keep_subtitle=True) == want:
            return hit
    return None


def _entity(hit):
    types = hit.get("types") or []
    return {"name": hit.get("name"), "id": hit.get("entity_id"), "type": types[0] if types else None}


def _summarise(entries):
    """One step's calls as (params every call shares, {param: [value per call]} for those that differ)."""
    shared, varies = {}, {}
    for key in dict.fromkeys(k for e in entries for k in e["params"]):
        values = [e["params"].get(key) for e in entries]
        if all(v == values[0] for v in values):
            shared[key] = values[0]
        else:
            varies[key] = values
    return shared, varies


def _step(trace, stage, tool, note, ok=True):
    entries = trace.stage(stage)
    shared, varies = _summarise(entries)
    step = {"tool": tool, "endpoint": entries[0]["endpoint"] if entries else None, "params": shared,
            "ok": bool(entries) and ok and all(e["ok"] for e in entries), "note": note, "calls": len(entries)}
    if varies:
        step["varies"] = varies
    return step


def _candidates(body, code):
    """The country's destinations as city candidates [{name, lat, lon, affinity, popularity}], those with a
    popularity of at least MIN_POPULARITY (a missing one passes). Qloo's destination affinity is travel-flavoured and
    its top row is often a village or resort (Larrabetzu, Dalyan, Lichfield); popularity separates those from
    cities: measured on 1,860 candidates, those places sit at 0.003 to 0.38 while Jaipur, Nagoya and Patna sit at
    0.42 to 0.48. It cannot remove famous resorts (Whistler 0.90, Agra 0.77), which the heatmap density handles."""
    rows = []
    for entity in (body.get("results") or {}).get("entities") or []:
        geo = (entity.get("properties") or {}).get("geocode") or {}
        affinity, loc = (entity.get("query") or {}).get("affinity"), entity.get("location") or {}
        popularity = entity.get("popularity")
        # Qloo also lists time zones as destinations ("Europe/Madrid"); a slash never appears in a city name.
        if (geo.get("country_code") != code or affinity is None or not entity.get("name") or "/" in entity["name"]
                or loc.get("lat") is None or loc.get("lon") is None
                or (popularity is not None and popularity < MIN_POPULARITY)):
            continue
        rows.append({"name": entity["name"], "lat": loc["lat"], "lon": loc["lon"], "affinity": round(float(affinity), 3),
                     "popularity": popularity if popularity is not None else MIN_POPULARITY})
    return rows


def _rank_countries(trace, signal_ids, countries, keep):
    """(the `keep` countries with the highest destination affinity, best first, countries asked, countries with
    nothing). Each country is {code, name, score, candidates}; score is its best candidate's affinity, so a village
    below the popularity floor cannot lift a country."""
    def one(item):
        order, (code, name) = item
        try:
            body = trace.get("countries", "/v2/insights",
                             {"filter.type": "urn:entity:destination", "signal.interests.entities": signal_ids,
                              "filter.geocode.country_code": code, "take": DESTINATION_TAKE}, order=order)
        except _CapReached:
            log.warning("release plan: call cap reached before %s", code)
            return None
        except (QlooError, httpx.HTTPError) as err:
            if _fatal(err):
                raise
            log.warning("release plan: no destinations for %s: %s", code, err)
            return None
        rows = _candidates(body, code)
        if not rows:
            return None
        return {"code": code, "name": name, "score": max(r["affinity"] for r in rows), "candidates": rows}

    with ThreadPoolExecutor(max_workers=WORKERS) as workers:
        results = list(workers.map(one, enumerate(countries.items())))
    ranked = sorted((r for r in results if r), key=lambda c: (-c["score"], c["name"]))
    return ranked[:keep], len(results), sum(1 for r in results if r is None)


class _TracedClient:
    """The client interface `aftershock.hotspots.heat_cells` expects (just `get`), routed through the trace so the
    heatmap call is counted and shown in steps."""

    def __init__(self, trace, stage, order):
        self.trace, self.stage, self.order = trace, stage, order

    def get(self, path, params):
        return self.trace.get(self.stage, path, params, order=self.order)


def _heat(trace, signal_ids, country_name, order):
    """Top heatmap cells of the signal's audience in a country ([] on failure or when the plan's call cap is spent)."""
    try:
        return audience_map.heat_cells(_TracedClient(trace, "cities", order), signal_ids, country_name)
    except _CapReached:
        log.warning("release plan: call cap reached before the heatmap for %s", country_name)
        return []


class _Geocode:
    """Reverse geocoding with a time budget. Nominatim is a free service at 1 request per second, so when it is
    slow or down the plan keeps the heatmap cells and goes without names rather than waiting. On Vercel the cache
    sits in /tmp, the only writable place (qloo.py does the same for its own cache)."""

    def __init__(self, base=None, budget=None):
        if base is None:
            base = (partial(audience_map.nominatim_name, cache_dir=Path("/tmp/nominatim-cache"))
                    if os.environ.get("VERCEL") else audience_map.nominatim_name)
        self.base = base
        self.deadline = time.monotonic() + (GEOCODE_BUDGET_S if budget is None else budget)

    def __call__(self, lat, lon):
        if time.monotonic() > self.deadline:
            raise OSError("geocoding time budget spent")
        return self.base(lat, lon)


def _pick_cities(candidates, cells):
    """Up to CITIES_PER_COUNTRY {name, lat, lon, affinity, density} for the candidates the heatmap favours: density
    is the sum of cell weights within DENSITY_KM, candidates with none (or under MIN_RELATIVE_DENSITY of the best) are
    dropped, near-duplicates are merged into
    the most popular one (taking the higher density), and ties go to the higher destination affinity."""
    def density(c):
        return sum(w for lat, lon, w in cells if audience_map.distance_km((c["lat"], c["lon"]), (lat, lon)) <= DENSITY_KM)

    merged = []  # [representative, density]
    for c in sorted(candidates, key=lambda c: -c["popularity"]):
        here = density(c)
        near = next((m for m in merged if audience_map.distance_km((c["lat"], c["lon"]), (m[0]["lat"], m[0]["lon"])) <= MERGE_KM), None)
        if near:
            near[1] = max(near[1], here)
        else:
            merged.append([c, here])
    best = max((m[1] for m in merged), default=0)
    merged = [m for m in merged if m[1] > 0 and m[1] >= MIN_RELATIVE_DENSITY * best]
    merged.sort(key=lambda m: (-m[1], -m[0]["affinity"]))
    return [{"name": c["name"], "lat": c["lat"], "lon": c["lon"], "affinity": c["affinity"], "density": round(d, 1)}
            for c, d in merged[:CITIES_PER_COUNTRY]]


def _place_hotspots(countries, cells_by_country, geocode):
    """Set `hotspots` {cells, places, place_cells} (the launch kits' shape) and `cities` on each country. The places
    are `_pick_cities`; only a country where no destination has cells nearby is named by reverse geocoding the
    strongest cells (at most MAX_PLACES, sequential: Nominatim allows one request a second). Returns the countries
    that needed the fallback."""
    fallback, geo = [], None
    for country, cells in zip(countries, cells_by_country):
        candidates = country.pop("candidates", [])
        cities = _pick_cities(candidates, cells) if cells else []
        if cities:
            country["cities"] = cities
            country["hotspots"] = {"cells": cells, "places": [c["name"] for c in cities],
                                   "place_cells": [[c["lat"], c["lon"]] for c in cities]}
        elif cells:
            geo = geo or _Geocode(geocode)
            # _name_places_located is private to hotspots but is exactly "name these cells and keep each one's cell".
            located = audience_map._name_places_located(cells, geo, audience_map.MAX_PLACES)
            country["hotspots"] = {"cells": cells, "places": [n for n, _, _ in located],
                                   "place_cells": [[la, lo] for _, la, lo in located]}
            fallback.append(country["name"])
        else:
            country["hotspots"] = {"cells": [], "places": []}
    return fallback


def _country_lines(ranked, asked):
    """Set `summary` on each country: one sentence made only from its own numbers and place names."""
    lead = ranked[0]
    for i, country in enumerate(ranked):
        if i == 0:
            text = (f"{country['name']} leads: Qloo's destination affinity {country['score']:.2f}, the highest of "
                    f"the {asked} countries checked.")
        else:
            text = (f"{country['name']}: Qloo's destination affinity {country['score']:.2f}, "
                    f"{lead['score'] - country['score']:.2f} below {lead['name']}.")
        places = (country.get("hotspots") or {}).get("places") or []
        if places:
            text += f" Qloo's audience map peaks around {_join(places)}."
        country["summary"] = text


def _join(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _tag_names(entity, wanted):
    """Up to three tag names for a place: the venue tag it was filtered on first, then its other place tags."""
    wanted_keys = {t.rsplit(":", 1)[-1] for t in wanted}
    tags = sorted(entity.get("tags") or [], key=lambda t: (t.get("id") or "").rsplit(":", 1)[-1] not in wanted_keys)
    names = []
    for tag in tags:
        tid, label = tag.get("id") or "", (tag.get("name") or "").strip()
        if label and ("category:place:" in tid or "genre:place:" in tid) and label not in names:
            names.append(label)
    return names[:3]


def _venue(entity, wanted):
    loc = entity.get("location") or {}
    out = {"name": entity.get("name"), "lat": loc.get("lat"), "lon": loc.get("lon"), "tags": _tag_names(entity, wanted)}
    address = _clean((entity.get("properties") or {}).get("address"))
    if address:
        out["address"] = address
    return out


def _venue_call(trace, wanted, city, order):
    """{city, country, venues} for one city (venues may be empty), or None when the call failed or hit the cap."""
    try:
        body = trace.get("venues", "/v2/insights",
                         {"filter.type": "urn:entity:place", "filter.tags": ",".join(wanted),
                          "filter.location": f"POINT({city['lon']} {city['lat']})",
                          "filter.location.radius": VENUE_RADIUS_M, "take": VENUES_PER_CITY}, order=order)
    except _CapReached:
        log.warning("release plan: call cap reached before venues near %s", city["name"])
        return None
    except (QlooError, httpx.HTTPError) as err:
        if _fatal(err):
            raise
        log.warning("release plan: no venues near %s: %s", city["name"], err)
        return None
    rows = [_venue(e, wanted) for e in (body.get("results") or {}).get("entities") or [] if e.get("name")]
    return {"city": city["name"], "country": city["country"], "venues": rows}


def _venues(trace, kind, cities):
    """([{city, country, venues}] for up to VENUE_CITIES cities that have venues, [names of cities with none]).
    The strongest VENUE_CITIES cities are asked together; a small town can have no tagged venue, so each empty one
    is replaced by the next city down, up to VENUE_ATTEMPTS calls in all."""
    wanted = KINDS[kind]["tags"]
    first = cities[:VENUE_CITIES]
    with ThreadPoolExecutor(max_workers=WORKERS) as workers:
        found = list(workers.map(lambda item: _venue_call(trace, wanted, item[1], item[0]), enumerate(first)))
    for order, city in enumerate(cities[VENUE_CITIES:VENUE_ATTEMPTS], start=len(first)):
        if sum(1 for f in found if f and f["venues"]) >= VENUE_CITIES:
            break
        found.append(_venue_call(trace, wanted, city, order))
    done = [f for f in found if f and f["venues"]]
    return done, [f["city"] for f in found if f and not f["venues"]]


def _is_signal(entity, signal):
    ids = {e["id"] for e in signal if e.get("id")}
    names = {norm(e["name"], keep_subtitle=True) for e in signal if e.get("name")}
    return entity.get("entity_id") in ids or norm(entity.get("name", ""), keep_subtitle=True) in names


def _taste_call(trace, signal, country, domain, urn, order, countries):
    """The names Qloo lists for this audience in one country and domain, signal dropped; None when the call failed."""
    try:
        body = trace.get("taste", "/v2/insights",
                         {"filter.type": urn, "signal.interests.entities": ",".join(e["id"] for e in signal),
                          "signal.location.query": countries.get(country["code"], country["name"]),
                          "take": TASTE_TAKE + len(signal)}, order=order)
    except _CapReached:
        log.warning("release plan: call cap reached before %s taste for %s", domain, country["code"])
        return None
    except (QlooError, httpx.HTTPError) as err:
        if _fatal(err):
            raise
        log.warning("release plan: no %s taste for %s: %s", domain, country["code"], err)
        return None
    found = [e["name"] for e in (body.get("results") or {}).get("entities") or []
             if e.get("name") and not _is_signal(e, signal)]
    return found[:TASTE_TAKE]


def _start_taste(workers, trace, signal, ranked, countries):
    """Start the taste calls for the top countries in the pool; `_collect_taste` gathers them."""
    jobs = []
    for index, country in enumerate(ranked[:TASTE_COUNTRIES]):
        for slot, (domain, urn) in enumerate(TASTE_DOMAINS):
            order = index * len(TASTE_DOMAINS) + slot
            jobs.append((country, domain, workers.submit(_taste_call, trace, signal, country, domain, urn, order,
                                                         countries)))
    return jobs


def _collect_taste(jobs):
    """[{code, country, tv_show: [name], movie: [name], artist: [name]}] for the top countries, signal entities dropped."""
    rows = {}
    for country, domain, future in jobs:
        row = rows.setdefault(country["code"], {"code": country["code"], "country": country["name"]})
        names = future.result()
        if names is not None:
            row[domain] = names
    return list(rows.values())


def _refuse(trace, name, kind, reason, steps):
    return {"resolved": False, "name": name, "kind": kind, "reason": reason, "steps": steps, "calls": trace.calls,
            "try": ["the title or artist name as Wikipedia, Spotify or Netflix spells it",
                    f"up to {MAX_USED_LIKE} comparable {KINDS[kind]['label']} titles or acts Qloo knows, in `like`"]}


def _resolve_signal(trace, name, kind, like):
    """([entity], "title" | "comparables" | None): the title if Qloo knows it, else the first comparables it does."""
    types = KINDS[kind]["types"]
    hit = _find(trace, name, types, 0)
    if hit:
        return [_entity(hit)], "title"
    signal = []
    for i, other in enumerate(like, start=1):
        found = _find(trace, other, types, i)
        if found and found.get("entity_id") not in {e["id"] for e in signal}:
            signal.append(_entity(found))
        if len(signal) >= MAX_USED_LIKE:
            break
    return signal, "comparables" if signal else None


def plan_release(client, name, kind, like=(), countries=None, n_countries=8, geocode=None):
    """The plan for one release: {resolved, name, kind, signal, countries, venues, local_taste, steps, calls, caveats}.
    `signal.used` says whether Qloo knew the title or the comparables stood in for it; with neither it returns
    {resolved: False, reason, try, steps} and nothing is guessed. ReleaseInputError for a bad field; QlooError
    only when Qloo refuses the key or rate-limits (a country or venue call that fails is skipped and shows in steps).
    `geocode(lat, lon)` names heatmap cells (OpenStreetMap by default)."""
    name, kind, like = validate(name, kind, like)
    countries = dict(countries or CANDIDATES)
    n_countries = max(1, min(int(n_countries), len(countries)))
    cfg = KINDS[kind]
    trace = _Trace(client)
    steps = []

    signal, used = _resolve_signal(trace, name, kind, like)
    if used == "title":
        note = f"Qloo knows {signal[0]['name']!r}; its audience is the signal."
    elif used == "comparables":
        note = (f"Qloo does not know {name!r} (unreleased or spelled differently), so {len(signal)} comparable"
                f"{'s' if len(signal) != 1 else ''} stand in: {', '.join(e['name'] for e in signal)}.")
    elif like:
        note = f"Qloo knows neither {name!r} nor any of the {len(like)} comparables."
    else:
        note = f"Qloo does not know {name!r}, and no comparables were given."
    steps.append(_step(trace, "resolve", "qloo_search", note, ok=used is not None))
    if not signal:
        return _refuse(trace, name, kind, note, steps)
    ids = ",".join(e["id"] for e in signal)

    ranked, asked, empty = _rank_countries(trace, ids, countries, n_countries)
    if not ranked:
        steps.append(_step(trace, "countries", "qloo_destinations",
                           f"Qloo returned no destinations for this audience in any of {asked} countries.", ok=False))
        return _refuse(trace, name, kind, "Qloo has no destination affinity for this audience", steps)
    steps.append(_step(trace, "countries", "qloo_destinations",
                       f"Destination calls, one per country, rank the {asked} countries by Qloo's best destination "
                       f"affinity there and supply the city candidates (they are not shown as cities unless the heatmap favours "
                       f"them); kept {len(ranked)}." + (f" {empty} returned nothing." if empty else "")))

    # The heatmaps and the taste calls are independent, so they share a pool; Nominatim naming then runs one
    # request at a time on this thread while the taste calls finish.
    top = ranked[:HEATMAP_COUNTRIES]
    with ThreadPoolExecutor(max_workers=WORKERS) as workers:
        heat = [workers.submit(_heat, trace, ids, c["name"], order) for order, c in enumerate(top)]
        taste_jobs = _start_taste(workers, trace, signal, ranked, countries)
        fallback = _place_hotspots(top, [h.result() for h in heat], geocode)
        taste = _collect_taste(taste_jobs)
    for country in ranked[HEATMAP_COUNTRIES:]:
        country.pop("candidates", None)
    _country_lines(ranked, asked)
    mapped = [c["name"] for c in top if c["hotspots"]["places"]]
    steps.append(_step(trace, "cities", "qloo_heatmap",
                       f"Heatmap calls, one per top country, say where the audience concentrates. Cities are the "
                       f"destinations from the step above (popularity at least {MIN_POPULARITY}), each scored by the "
                       f"heatmap weight within {DENSITY_KM} km and merged within {MERGE_KM} km; no Nominatim "
                       f"lookup was needed there. Cities in {', '.join(mapped) or 'no country'}."
                       + (f" No destination had heatmap cells nearby in {', '.join(fallback)}, so its strongest cells "
                          f"were named by OpenStreetMap reverse geocoding (not Qloo)." if fallback else ""),
                       ok=any(c["hotspots"]["cells"] for c in top)))

    # Venue anchors: each top country's strongest city first, then the next one down in each, so a city
    # with no tagged venue is replaced rather than leaving a country empty. A country whose cells could not be
    # named is anchored on its strongest cell.
    rows = []
    for c in top:
        hs = c["hotspots"]
        if hs["places"]:
            rows.append([{"name": p, "country": c["name"], "lat": cell[0], "lon": cell[1]}
                         for p, cell in zip(hs["places"], hs["place_cells"])])
        elif hs["cells"]:
            lat, lon = hs["cells"][0][:2]
            rows.append([{"name": f"the strongest cell ({lat:.2f}, {lon:.2f})", "country": c["name"],
                          "lat": lat, "lon": lon}])
    pool = [row[i] for i in range(audience_map.MAX_PLACES) for row in rows if i < len(row)][:VENUE_ATTEMPTS]
    venues, bare = _venues(trace, kind, pool) if pool else ([], [])
    steps.append(_step(trace, "venues", "qloo_places",
                       f"Venue calls look for {cfg['venue']} within {VENUE_RADIUS_M // 1000} km of the strongest "
                       f"cities; found {sum(len(v['venues']) for v in venues)} in "
                       f"{', '.join(v['city'] for v in venues) or 'none'}."
                       + (f" Qloo lists none near {', '.join(bare)}." if bare else ""), ok=bool(venues)))
    steps.append(_step(trace, "taste", "qloo_insights",
                       f"Taste calls ask Qloo what this audience also likes in "
                       f"{', '.join(r['country'] for r in taste) or 'the top countries'}, leaving out the signal itself.",
                       ok=bool(taste)))

    caveats = ["Qloo affinity is a relative score for how closely a place's taste matches the signal, not a "
               "probability and not a forecast of ticket or stream numbers.",
               "Countries are ranked by destination affinity, which is travel-flavoured and is a country's single best "
               "destination, so a small country with one strong destination can outrank a large one. The cities "
               "inside a country are Qloo destinations ranked by how much of Qloo's audience heatmap lies within "
               f"{DENSITY_KM} km; a country the heatmap barely touches shows few or odd cities.", VENUE_NOTE]
    if used == "comparables":
        caveats.append("The title itself is not in Qloo, so this is the audience of the comparables, not of the release.")
    if trace.calls >= trace.cap:
        caveats.append(f"The plan hit its {trace.cap}-call cap; later steps may be shorter than usual.")
    return {"resolved": True, "name": name, "kind": kind, "signal": {"used": used, "entities": signal},
            "countries": ranked, "countries_checked": asked, "venues": venues, "local_taste": taste,
            "steps": steps, "calls": trace.calls, "caveats": caveats}
