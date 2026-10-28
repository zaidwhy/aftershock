"""Metro names: hotspot places named for the city a marketer would recognise, not the suburb the cell sits in.

Reverse geocoding a heatmap cell (aftershock/hotspots.py) names whatever OpenStreetMap calls that spot: Lidingö for a
cell inside Stockholm's metro area, Mississauga for Toronto's. Qloo lists each country's destinations with a
`popularity` (0 to 1: big cities high, villages low), so a hotspot is relabelled with the most popular destination
within RADIUS_KM of its cell, and falls back to the OpenStreetMap name when none is that close. The destinations come
from data/private/metro_names.json (scripts/build_metro_names.py; gitignored, Qloo-derived). Read-time and idempotent:
a relabelled name's cell resolves to the same destination again. Without the file nothing is relabelled.
"""
import json
import logging
from pathlib import Path

from aftershock.hotspots import clean_place_name, distance_km

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
METRO_FILE = ROOT / "data" / "private" / "metro_names.json"
# Measured on this week's 143 named hotspot cells with destinations at popularity >= 0.5: suburbs that should take the city's
# name sit 4 to 35 km from it (Lidingo 4, Vantaa 16, Stjordal 26, Taoyuan 35), while real towns that 50 km would swallow sit
# 40 to 50 km away (Neuchatel -> Bern 40, Val de Bagnes -> Zermatt 42, Tainan -> Kaohsiung 50).
RADIUS_KM = 35
_loaded = {}  # path -> (mtime, {country code: [(name, lat, lon, popularity)]})


def load(path=None):
    """{country code: [(name, lat, lon, popularity), ...]} from the metro file; {} when it is missing or unreadable."""
    path = Path(path) if path else METRO_FILE
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    cached = _loaded.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        raw = json.loads(path.read_text(encoding="utf-8")).get("countries") or {}
        metros = {code: [(n, float(la), float(lo), float(p)) for n, la, lo, p in rows] for code, rows in raw.items()}
    except (OSError, ValueError, TypeError) as err:  # a damaged file costs the relabel, not the page
        log.warning("could not read %s: %s", path, err)
        return {}
    _loaded[path] = (mtime, metros)
    return metros


def metro_for(cell, destinations, radius_km=RADIUS_KM):
    """The most popular destination within `radius_km` of `cell` ([lat, lon]), the nearer one on a tie; None when
    there is none."""
    best = None
    for name, lat, lon, popularity in destinations:
        km = distance_km(cell, (lat, lon))
        if km <= radius_km and (best is None or (-popularity, km) < best[0]):
            best = ((-popularity, km), name)
    return best[1] if best else None


def relabel(places, place_cells, destinations, radius_km=RADIUS_KM):
    """([names], [cells], {old name: new name}) for one country's hotspots: each place whose cell has a destination
    within the radius takes its name, the rest keep theirs, and a name that repeats (Lidingö and Stockholm both
    becoming Stockholm) keeps its first cell. `place_cells[i]` is the cell `places[i]` was named from; without one
    per place (an older row) nothing can be relabelled and the places come back as they are."""
    if len(place_cells) != len(places) or not destinations:
        return list(places), list(place_cells), {}
    names, cells, renamed = [], [], {}
    for old, cell in zip(places, place_cells):
        new = metro_for(cell, destinations, radius_km) or old
        renamed[old] = new
        if new not in names:
            names.append(new)
            cells.append(cell)
    return names, cells, renamed


def relabel_row(row, metros=None):
    """Relabel one launch-kit row's hotspots and event-idea cities in place (the row's `code` picks the country).
    Administrative wording is stripped first: a name with no destination nearby still reads well, and an event city
    finds the place it came from."""
    hot = row.get("hotspots") or {}
    metros = load() if metros is None else metros
    renamed = {}
    if hot.get("places"):
        places = [clean_place_name(n) for n in hot["places"]]
        hot["places"], cells, renamed = relabel(places, hot.get("place_cells") or [], metros.get(row.get("code")) or [])
        if hot.get("place_cells"):
            hot["place_cells"] = cells
    for event in row.get("events") or []:
        if event.get("cities"):
            cities = (renamed.get(clean_place_name(c)) or clean_place_name(c) for c in event["cities"])
            event["cities"] = list(dict.fromkeys(cities))
