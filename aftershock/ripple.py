"""RIPPLE: which songs placed in a show will spike.

A placement pulls a song into the spotlight when the show puts it in front of an audience it has
not reached. The score is the Qloo age gap: how far the artist's audience sits from the show's
audience by age band, in [0, 1] (Qloo demographics for both).

Why only the gap (scripts/test_ripple.py, scripts/test_ripple_controls.py; 195 artists, 24 shows):
- Obscurity (low Wikipedia views before release) correlates with the spike, but it "predicts" a
  placebo spike measured entirely before release almost as well (0.19 vs 0.27; 0.28 vs 0.29 on
  2024+ releases): it is mostly regression to the mean, so it is shown as context, not scored.
- The age gap does not predict the placebo (-0.13) but does predict the real spike (0.08 overall,
  0.28 on 2024+); real minus placebo is significant (permutation p 0.04 overall, 0.03 on 2024+).
- Qloo taste fit predicted nothing (0.00) and is shown as context only.
"""
import logging
import math
import re
from datetime import date, timedelta

from aftershock import wiki
from aftershock.qloo import QlooError, resolve

log = logging.getLogger(__name__)

AGE_BANDS = ["24_and_younger", "25_to_29", "30_to_34", "35_to_44", "45_to_54", "55_and_older"]
MAX_SONGS = 8
BASELINE_DAYS = (60, 8)  # same window as the backtest: days -60..-8 before the reference date


def age_profile(client, entity_id):
    """Age-band over-index, or None when Qloo has no demographic data for the entity
    (an all-zero profile would otherwise read as a real, perfectly average audience)."""
    body = client.insights(filter__type="urn:demographics", signal__interests__entities=entity_id)
    rows = body.get("results", {}).get("demographics") or []
    age = rows[0]["query"].get("age") if rows else None
    if not age or not any(age.get(band) for band in AGE_BANDS):
        return None
    return {band: float(age.get(band, 0.0)) for band in AGE_BANDS}


def resolve_artist(client, artist):
    """Placement credits list collaborators ("Mumford and Sons, Chris Stapleton"); fall back to the first."""
    hit = resolve(client, artist, "urn:entity:artist")
    if hit:
        return hit
    first = re.split(r",| feat\.? | featuring | & | x ", artist, maxsplit=1)[0].strip()
    return resolve(client, first, "urn:entity:artist") if first != artist else None


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


def prior_attention(song, artist, as_of):
    """Mean daily Wikipedia views before as_of, for the song's article or else the artist's.
    Returns (views, article) or (None, None) when neither has an article."""
    article = wiki.resolve_article(song, artist) or wiki.resolve_artist_article(artist)
    if not article:
        return None, None
    start, end = as_of - timedelta(days=BASELINE_DAYS[0]), as_of - timedelta(days=BASELINE_DAYS[1])
    series = wiki.daily_views(article, start, end)
    return sum(series.values()) / len(series), article


def score_placements(client, show_name, placements, show_type=None, as_of=None, max_songs=MAX_SONGS):
    """placements: [(song, artist)]. Returns the API `ripple` shape plus resolution flags.
    max_songs caps visitor requests; the weekly job scores whole soundtracks."""
    if len(placements) > max_songs:
        raise ValueError(f"at most {max_songs} songs per request, got {len(placements)}")
    as_of = as_of or date.today()
    show = resolve_show(client, show_name, show_type or "urn:entity:tv_show,urn:entity:movie")
    if not show:
        return {"resolved": False, "show": show_name, "songs": []}
    show_age = age_profile(client, show["entity_id"])
    if show_age is None:
        return {"resolved": False, "show": show["name"], "reason": "Qloo has no audience profile for this title", "songs": []}
    artists = {}
    for _, artist in placements:
        if artist not in artists:
            hit = resolve_artist(client, artist)
            artists[artist] = hit["entity_id"] if hit else None
    known = sorted({a for a in artists.values() if a})
    fit = taste_fit(client, show["entity_id"], known) if known else {}
    songs = []
    for song, artist in placements:
        row = {"song": song, "artist": artist, "resolved": False}
        artist_id = artists.get(artist)
        if artist_id:
            try:
                artist_age = age_profile(client, artist_id)
                row.update(resolved=True, fit=fit.get(artist_id))
                if artist_age is not None:
                    row.update(artist_age=artist_age, age_gap=round(age_gap(show_age, artist_age), 3))
            except QlooError as err:
                log.warning("demographics failed for %s: %s", artist, err)
        views, article = prior_attention(song, artist, as_of)
        row.update(prior_daily_views=round(views, 1) if views is not None else None, wiki_article=article,
                   obscurity=round(-math.log(views + 1), 3) if views is not None else None)
        songs.append(row)
    for s in songs:
        s["score"] = s.get("age_gap")
    songs.sort(key=lambda s: -(s["score"] if s["score"] is not None else -1))
    return {"resolved": True, "show": show["name"], "show_entity": show["entity_id"], "show_age": show_age,
            "as_of": str(as_of), "songs": songs}
