"""Sync Scout: artists a show's taste neighbourhood likes whose audience sits outside the show's generation.

This is a discovery shortlist, not a predictor. The idea is an audience the show reaches that the song
had not, measured by Qloo's age gap (aftershock.ripple.age_gap); in our licensed-data test the age gap
did not predict which songs spiked (README section 3). Taste only supplies the candidate pool and its
order is reported as context. Output carries derived gaps and age-band names only.
"""
import logging

from aftershock.qloo import QlooError, suggest
from aftershock.ripple import AGE_BANDS, age_gap, age_profile, resolve_show

log = logging.getLogger(__name__)

CANDIDATES = 50
TOP_N = 12
MAX_QLOO_CALLS = 60
SHOW_TYPES = ("urn:entity:tv_show", "urn:entity:movie")
BAND_LABELS = {"24_and_younger": "24 and younger", "25_to_29": "25 to 29", "30_to_34": "30 to 34",
               "35_to_44": "35 to 44", "45_to_54": "45 to 54", "55_and_older": "55 and older"}


def leaning_bands(profile):
    """Bands the audience over-indexes on, strongest first. Audiences can lean two ways at once
    (Wednesday's leans both 24 and younger and 55 and older), so naming one band would mislead."""
    bands = sorted((b for b in AGE_BANDS if profile[b] > 0), key=lambda b: -profile[b])
    return bands or [max(AGE_BANDS, key=lambda b: profile[b])]


def band_list(bands):
    labels = [BAND_LABELS[b] for b in bands]
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]


def public_ripple(result):
    """A score_placements result without raw Qloo values: no taste fit and no per-band over-index numbers.
    The age profiles become the band names each side leans to (show_leans, and leans per song)."""
    out = {k: v for k, v in result.items() if k != "show_age"}
    if result.get("show_age"):
        out["show_leans"] = leaning_bands(result["show_age"])
    out["songs"] = [{**{k: v for k, v in s.items() if k not in ("fit", "artist_age")},
                     **({"leans": leaning_bands(s["artist_age"])} if s.get("artist_age") else {})}
                    for s in result.get("songs", [])]
    return out


def why(show_age, artist_age):
    artist_bands, show_bands = leaning_bands(artist_age), leaning_bands(show_age)
    shared = [b for b in artist_bands if b in show_bands]
    text = f"Audience leans {band_list(artist_bands)}; the show's leans {band_list(show_bands)}."
    if not shared:
        return text + " No overlap."
    return text + f" Overlap only at {band_list(shared)}."


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
        try:
            hint = suggest(client, show_name, ",".join(SHOW_TYPES))
        except QlooError as err:
            log.warning("suggestion lookup failed for %r: %s", show_name, err)
            hint = None
        return {"resolved": False, "show": show_name, "reason": "Qloo does not know a show or film by this name",
                "suggestion": hint, "artists": []}
    show_age = age_profile(client, show["entity_id"])
    if show_age is None:
        return {"resolved": False, "show": show["name"], "reason": "Qloo has no audience profile for this title",
                "no_profile": True, "artists": []}
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
                     "taste_rank": rank, "leans": leaning_bands(artist_age), "why": why(show_age, artist_age)})
    rows.sort(key=lambda r: (-r["gap"], r["taste_rank"]))
    return {"resolved": True, "show": show["name"], "show_entity": show["entity_id"], "show_leans": leaning_bands(show_age), "candidates": len(pool),
            "profiled": len(rows), "truncated": truncated, "artists": rows[:TOP_N]}
