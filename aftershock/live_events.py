"""Live events: in which cities do a title's audience and an artist's audience both concentrate?

A promoter whose show is breaking out in a country asks "which artist, in which city?". An LLM can name artists
but cannot say where in a country their audience lives. Qloo's heatmap can, for the show and for each artist. So
for one launch-kit row we take the artists the launch brief already names as partners (`launch_brief.partner_artists`,
at most MAX_ARTISTS), fetch each artist's heatmap in the same country, and call a show city an event city for that
artist when one of the artist's strongest cells lies within OVERLAP_KM of the show cell that city's name came from
(`hotspots.place_cells`). The result is where two audiences overlap, not a ticket-demand forecast.

Cost: one heatmap call per artist (cached on disk like every Qloo call) plus a name search for AI-confirmed
artists whose entity id is not on the kit. Any Qloo or network failure gives fewer artists, never an exception.
"""
import logging

import httpx

from aftershock.hotspots import distance_km, heat_cells
from aftershock.launch_brief import partner_artists
from aftershock.launch_kit import name_key
from aftershock.qloo import QlooError, resolve

log = logging.getLogger(__name__)

MAX_ARTISTS = 3
OVERLAP_KM = 30  # a show place and an artist cell this close count as the same city
ARTIST_TOP_CELLS = 5  # an artist's strongest cells that count as "where their audience concentrates"; at 30 cells and 60 km, 114 of 176 ideas named every show city


def overlap_cities(places, place_cells, artist_cells, km=OVERLAP_KM, top=ARTIST_TOP_CELLS):
    """The names in `places` (strongest first) whose show cell (`place_cells[i]`) lies within `km` of one of the
    artist's `top` strongest cells (`artist_cells` is [[lat, lon, weight], ...], strongest first)."""
    strongest = artist_cells[:top]
    return [name for name, cell in zip(places, place_cells)
            if any(distance_km(cell, (c[0], c[1])) <= km for c in strongest)]


def _entity_id(client, name, kit_artists):
    for entity in kit_artists:
        if entity.get("entity_id") and name_key(entity.get("name") or "") == name_key(name):
            return entity["entity_id"]
    hit = resolve(client, name, "urn:entity:artist")
    return (hit or {}).get("entity_id")


def events_for_row(client, row, country_name):
    """{"events": [{"artist", "cities"}], "events_checked": n} for one launch-kit row; artists with no overlapping
    city are dropped from `events` but still counted in `events_checked`."""
    hs = row.get("hotspots") or {}
    places, place_cells = hs.get("places") or [], hs.get("place_cells") or []
    events, checked = [], 0
    if not places or len(place_cells) < len(places):
        return {"events": events, "events_checked": checked}
    kit_artists = (row.get("kit") or {}).get("artist") or []
    for pick in partner_artists(row)[:MAX_ARTISTS]:
        try:
            entity_id = _entity_id(client, pick["name"], kit_artists)
        except (QlooError, httpx.HTTPError) as err:
            log.warning("live events: could not resolve %r: %s", pick["name"], err)
            continue
        if not entity_id:
            continue
        cells = heat_cells(client, entity_id, country_name)
        if not cells:
            continue
        checked += 1
        cities = overlap_cities(places, place_cells, cells)
        if cities:
            events.append({"artist": pick["name"], "cities": cities})
    return {"events": events, "events_checked": checked}


def add_events(client, storms):
    """Set `events` and `events_checked` on every launch-kit row in `storms` ([{detail}]) that has named hotspots
    with their cells. Returns the number of rows with at least one event idea."""
    with_events = rows = 0
    for storm in storms:
        detail = storm["detail"]
        country = {f["code"]: f["name"] for f in detail["spillover"]["forecasts"]}
        for row in detail.get("launch_kit") or []:
            row.pop("events", None)
            row.pop("events_checked", None)
            if row.get("code") not in country or not (row.get("hotspots") or {}).get("place_cells"):
                continue
            row.update(events_for_row(client, row, country[row["code"]]))
            rows += 1
            with_events += bool(row["events"])
    log.info("live events: %d of %d launch-kit rows have an event idea", with_events, rows)
    return with_events
