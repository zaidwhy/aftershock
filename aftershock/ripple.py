"""RIPPLE: which songs placed in a show will spike.

A placement pulls a song into the spotlight when the show's audience would like the artist
(taste fit) but does not already know them (the artist's audience sits in other age bands).
score = fit x age_gap, both in [0, 1].
"""
import logging
import re

from aftershock.qloo import QlooError, resolve

log = logging.getLogger(__name__)

AGE_BANDS = ["24_and_younger", "25_to_29", "30_to_34", "35_to_44", "45_to_54", "55_and_older"]
MAX_SONGS = 8


def age_profile(client, entity_id):
    body = client.insights(filter__type="urn:demographics", signal__interests__entities=entity_id)
    rows = body.get("results", {}).get("demographics") or []
    age = rows[0]["query"]["age"] if rows else {}
    return {band: float(age.get(band, 0.0)) for band in AGE_BANDS}


def age_gap(show_age, artist_age):
    """How unfamiliar the artist is to the show's core audience, in [0, 1].

    Weights are the show's positive over-index per band; familiarity is the artist's
    over-index averaged with those weights (range -1..1), so gap = (1 - familiarity) / 2.
    """
    weights = {b: max(show_age[b], 0.0) for b in AGE_BANDS}
    total = sum(weights.values())
    if total == 0:
        return 0.5
    familiarity = sum(weights[b] * artist_age[b] for b in AGE_BANDS) / total
    return max(0.0, min(1.0, (1.0 - familiarity) / 2.0))


def taste_fit(client, show_id, artist_ids):
    """Affinity of the show's audience for each artist. Qloo rescales affinity within a
    response, so values are comparable inside one show only."""
    body = client.insights(filter__type="urn:entity:artist", signal__interests__entities=show_id,
                           filter__results__entities=",".join(artist_ids), take=len(artist_ids))
    return {e["entity_id"]: float(e["query"]["affinity"]) for e in body.get("results", {}).get("entities", [])
            if e.get("query", {}).get("affinity") is not None}


def resolve_show(client, name, types):
    """Release labels like "Stranger Things 4 (Volume 1)" are not Qloo names; try the bare title too."""
    bare = re.sub(r"\s*\(.*?\)", "", name).strip()
    for candidate in dict.fromkeys([name, bare, re.sub(r"\s+\d+$", "", bare)]):
        hit = resolve(client, candidate, types)
        if hit:
            return hit
    return None


def score_placements(client, show_name, placements, show_type=None):
    """placements: [(song, artist)]. Returns the API `ripple` shape plus resolution flags."""
    if len(placements) > MAX_SONGS:
        raise ValueError(f"at most {MAX_SONGS} songs per request, got {len(placements)}")
    types = show_type or "urn:entity:tv_show,urn:entity:movie"
    show = resolve_show(client, show_name, types)
    if not show:
        return {"resolved": False, "show": show_name, "songs": []}
    show_age = age_profile(client, show["entity_id"])
    artists = {}
    for _, artist in placements:
        if artist not in artists:
            hit = resolve(client, artist, "urn:entity:artist")
            artists[artist] = hit["entity_id"] if hit else None
    known = sorted({a for a in artists.values() if a})
    fit = taste_fit(client, show["entity_id"], known) if known else {}
    songs = []
    for song, artist in placements:
        artist_id = artists.get(artist)
        if not artist_id:
            songs.append({"song": song, "artist": artist, "resolved": False})
            continue
        try:
            artist_age = age_profile(client, artist_id)
        except QlooError as err:
            log.warning("demographics failed for %s: %s", artist, err)
            songs.append({"song": song, "artist": artist, "resolved": False})
            continue
        gap = age_gap(show_age, artist_age)
        song_fit = fit.get(artist_id)
        songs.append({
            "song": song, "artist": artist, "resolved": song_fit is not None,
            "fit": song_fit, "age_gap": round(gap, 3), "artist_age": artist_age,
            "score": round(song_fit * gap, 3) if song_fit is not None else None,
        })
    songs.sort(key=lambda s: -(s.get("score") or -1))
    return {"resolved": True, "show": show["name"], "show_entity": show["entity_id"],
            "show_age": show_age, "songs": songs}
