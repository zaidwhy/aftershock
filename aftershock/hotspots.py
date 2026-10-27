"""Hotspots: where inside a country the title's audience concentrates.

One Qloo `urn:heatmap` insights call per country returns ~1,800 geohash cells with an affinity
rank. The top CELLS by affinity are kept as [lat, lon, weight]; the top PLACES are named by
reverse-geocoding the strongest cells that are at least MIN_SEPARATION_KM apart (OpenStreetMap
Nominatim, one request per second, cached on disk). Any failure returns what was gathered so far.
"""
import hashlib
import json
import logging
import math
import re
import time
from pathlib import Path

import httpx

from aftershock.qloo import QlooError

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".cache" / "nominatim"
USER_AGENT = "aftershock/0.1 (https://github.com/zaidwhy/aftershock; zaidsyed7021@gmail.com)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
MAX_CELLS = 120
MAX_PLACES = 3
MIN_SEPARATION_KM = 60
MAX_GEOCODE_TRIES = 8  # candidate cells tried per country before giving up on naming more places
_last_request = [0.0]


def distance_km(a, b):
    """Great-circle distance between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def top_cells(body, limit=MAX_CELLS):
    """[[lat, lon, weight 0..1], ...] for the highest-affinity cells; weight 1 is the best cell, falling linearly with position."""
    cells = []
    for item in (body.get("results") or {}).get("heatmap") or []:
        loc, query = item.get("location") or {}, item.get("query") or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None or lon is None:
            continue
        cells.append((float(lat), float(lon), query.get("affinity"), query.get("affinity_rank")))
    if not cells:
        return []
    # Higher affinity first (many cells tie at 1.0); affinity_rank (1 = best) breaks ties.
    cells.sort(key=lambda c: (-(c[2] if c[2] is not None else -1), -(c[3] if c[3] is not None else -1)))
    cells = cells[:limit]
    n = len(cells)
    return [[round(lat, 4), round(lon, 4), round(1 - i / n, 3)] for i, (lat, lon, _, _) in enumerate(cells)]


PLACE_FIELDS = ("city", "town", "municipality", "village", "county", "state_district", "state")
# Administrative words OpenStreetMap appends to a place name. Matched as whole words at the end or start
# of the name, so "Mexico City" and "Kingston upon Hull" stay as they are.
ADMIN_SUFFIX = re.compile(
    r"(?:\s+|^)(?:Metropolitan\s+Municipality|Municipal\s+Corporation|City\s+Corporation|Municipality|Upazila|District|Ward)$",
    re.IGNORECASE)
ADMIN_PREFIX = re.compile(r"^(?:Municipality|Municipal\s+Corporation)\s+of\s+", re.IGNORECASE)


def clean_place_name(name):
    """The place name without administrative wording; the original when stripping would empty it."""
    out = name.strip()
    for _ in range(2):
        out = ADMIN_SUFFIX.sub("", out).strip(" ,-")
    out = ADMIN_PREFIX.sub("", out).strip(" ,-")
    return out or name.strip()


def place_from_address(address):
    """The most local named place in a Nominatim address: city, town, municipality, village, and only then
    county, state_district or state; administrative suffixes removed. None when there is none."""
    for field in PLACE_FIELDS:
        if address.get(field):
            return clean_place_name(address[field])
    return None


def nominatim_name(lat, lon, cache_dir=None):
    """City, town or county name for a point, or None. Cached on disk; 1 live request per second."""
    cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
    key = hashlib.sha256(f"{lat:.3f},{lon:.3f},en".encode()).hexdigest()[:24]
    cached = cache_dir / f"{key}.json"
    if cached.exists():
        body = json.loads(cached.read_text(encoding="utf-8"))
    else:
        wait = 1.1 - (time.monotonic() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.monotonic()
        resp = httpx.get(NOMINATIM_URL, params={"format": "jsonv2", "zoom": 10, "lat": lat, "lon": lon, "accept-language": "en"},
                         headers={"User-Agent": USER_AGENT}, timeout=20.0)
        resp.raise_for_status()
        body = resp.json()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(body), encoding="utf-8")
    return place_from_address(body.get("address") or {})


def name_places(cells, geocode=nominatim_name, count=MAX_PLACES):
    """Names of up to `count` distinct places, strongest cells first, each at least
    MIN_SEPARATION_KM from the ones already chosen. A geocode failure stops naming, never raises."""
    chosen, names, tries = [], [], 0
    for lat, lon, _ in cells:
        if len(names) >= count or tries >= MAX_GEOCODE_TRIES:
            break
        if any(distance_km((lat, lon), c) < MIN_SEPARATION_KM for c in chosen):
            continue
        tries += 1
        try:
            name = geocode(lat, lon)
        except (httpx.HTTPError, ValueError, OSError) as err:
            log.warning("geocode failed at %.3f,%.3f: %s", lat, lon, err)
            break
        chosen.append((lat, lon))
        if name and name not in names:
            names.append(name)
    return names


def hotspots(client, entity_id, country_name, geocode=nominatim_name):
    """{"cells": [[lat, lon, weight], ...], "places": [name, ...]}; empty when nothing could be fetched."""
    if not entity_id:
        return {"cells": [], "places": []}
    try:
        body = client.get("/v2/insights", {"filter.type": "urn:heatmap", "signal.interests.entities": entity_id,
                                           "filter.location.query": country_name})
    except (QlooError, httpx.HTTPError) as err:
        log.warning("heatmap failed for %s: %s", country_name, err)
        return {"cells": [], "places": []}
    cells = top_cells(body)
    return {"cells": cells, "places": name_places(cells, geocode) if cells else []}
