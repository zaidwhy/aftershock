"""Sync Scout: artists a show's taste neighbourhood likes whose audience sits outside the show's generation.

The mechanism behind a song spike from a placement is an audience the show reaches that the song
had not. Qloo's age gap (aftershock.ripple.age_gap) is the one signal that survived the placebo
control (README section 3); taste fit did not predict anything, so taste only supplies the candidate
pool and its order is reported as context. Output carries derived gaps and age-band names only.
"""
import logging

from aftershock.qloo import QlooError
from aftershock.ripple import AGE_BANDS, age_gap, age_profile, resolve_show

log = logging.getLogger(__name__)

CANDIDATES = 50
TOP_N = 12
MAX_QLOO_CALLS = 60
SHOW_TYPES = ("urn:entity:tv_show", "urn:entity:movie")
BAND_LABELS = {"24_and_younger": "24 and younger", "25_to_29": "25 to 29", "30_to_34": "30 to 34",
               "35_to_44": "35 to 44", "45_to_54": "45 to 54", "55_and_older": "55 and older"}


def top_band(profile):
    return max(AGE_BANDS, key=lambda b: profile[b])


def why(show_age, artist_age):
    artist_band, show_band = top_band(artist_age), top_band(show_age)
    if artist_band == show_band:
        return (f"Audience over-indexes on the same age band as the show's ({BAND_LABELS[show_band]}); "
                "the gap comes from the rest of the age profile.")
    return f"Audience over-indexes on ages {BAND_LABELS[artist_band]}; the show's on ages {BAND_LABELS[show_band]}."


def candidates(client, show_id):
    body = client.insights(filter__type="urn:entity:artist", signal__interests__entities=show_id, take=CANDIDATES)
    rows = body.get("results", {}).get("entities", [])
    return [(e["entity_id"], e.get("name", "")) for e in rows if e.get("entity_id")]


def scout(client, show_name):
    """Returns {"resolved": bool, "show": ..., "artists": [...]}; never raw affinity or demographics."""
    show = None
    for kind in SHOW_TYPES:
        show = resolve_show(client, show_name, kind)
        if show:
            break
    if not show:
        return {"resolved": False, "show": show_name, "reason": "Qloo does not know a show or film by this name",
                "artists": []}
    show_age = age_profile(client, show["entity_id"])
    if show_age is None:
        return {"resolved": False, "show": show["name"], "reason": "Qloo has no audience profile for this title",
                "artists": []}
    pool = candidates(client, show["entity_id"])
    rows, truncated = [], False
    for rank, (entity_id, name) in enumerate(pool, start=1):
        try:
            artist_age = age_profile(client, entity_id)
        except QlooError as err:
            log.warning("scout stopped at candidate %d: %s", rank, err)
            truncated = True
            break
        if artist_age is None:
            continue
        rows.append({"name": name, "entity_id": entity_id, "gap": round(age_gap(show_age, artist_age), 3),
                     "taste_rank": rank, "why": why(show_age, artist_age)})
    rows.sort(key=lambda r: (-r["gap"], r["taste_rank"]))
    return {"resolved": True, "show": show["name"], "show_entity": show["entity_id"], "candidates": len(pool),
            "profiled": len(rows), "truncated": truncated, "artists": rows[:TOP_N]}
