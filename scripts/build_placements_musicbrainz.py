"""Build data/placements.csv from MusicBrainz (core data CC0) and Wikidata (CC0).

A song is "placed" in a title if it is a track on the title's official song soundtrack release
in MusicBrainz (release-group secondary type Soundtrack; a songs album such as "Music from the
...", "Soundtrack from the ...", "The Album", "Mixtape"; never an instrumental score).
Release date is the title's own release date (season premiere or film release), never the album's:
either the date carried over from the earlier placements.csv, or the earliest day-precision
P577 (publication date) / P580 (start time) on the title's Wikidata item. Per-title sources are
written to data/placements_sources.csv.

Filtering of tracks: tracks credited to the score composer or to the show's cast are dropped (a
per-title list plus a generic rule: an artist credited on 30% or more of a release's tracks is
the composer or the cast, not a licensed placement); score-like track titles (main title, end
title, score, interlude, skit, instrumental) are dropped. Covers recorded for a show are kept as
credited to the performing artist (no per-cover Wikipedia check was made).

MusicBrainz is called at most 1 request/second with a descriptive User-Agent; responses are
cached under .cache/musicbrainz/. Cap: 1,500 requests.
"""
import csv
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _mb  # noqa: E402

OUT = ROOT / "data" / "placements.csv"
SOURCES = ROOT / "data" / "placements_sources.csv"
WD_CACHE = ROOT / ".cache" / "wikidata"
COLUMNS = ["show", "show_type", "platform", "release_date", "song", "artist", "song_year", "scene_note", "source_url"]

# (show, type, platform, MusicBrainz release-group id, date spec, artists to exclude)
# date spec: "csv:YYYY-MM-DD" (carried over from the previous placements.csv), "wd:Q..." (item),
# "wdfilm:<search>|<year>" (Wikidata search for a film), "wdseason:<label>" (Wikidata season label).
TITLES = [
    ("Stranger Things 4 (Volume 1)", "tv_show", "Netflix", "da0590e4-5cc6-44a6-a210-21da6f914fc5", "csv:2022-05-27", []),
    ("Heartstopper (Season 2)", "tv_show", "Netflix", "5c141051-2c94-411e-920a-349dd186319a", "csv:2023-08-03", []),
    ("Saltburn", "movie", "Prime Video", "3986d08e-2a86-49e9-85e8-3e02762ac6c3", "csv:2023-12-22", []),
    ("Barbie", "movie", "Cinema", "866df188-ec18-448d-add1-e15e756e4f01", "csv:2023-07-21", ["Ryan Gosling"]),
    ("Guardians of the Galaxy Vol. 3", "movie", "Cinema", "8537a325-991d-4619-80bd-d2117ab043e3", "csv:2023-05-05", []),
    ("The Holdovers", "movie", "Cinema", "e9ecd0dc-2f78-4745-b081-99aee2a3c8f6", "csv:2023-10-27", ["Mark Orton"]),
    ("Deadpool & Wolverine", "movie", "Cinema", "21c26877-783a-41eb-8211-8baa14b2ec7e", "csv:2024-07-25", ["Hugh Jackman"]),
    ("Beetlejuice Beetlejuice", "movie", "Cinema", "c596f1b4-d0c3-42b8-a3be-04a504d0bf37", "csv:2024-09-06", ["Danny Elfman"]),
    ("Twisters", "movie", "Cinema", "1e789e3f-3fc8-4991-8e68-938b90121ca3", "csv:2024-07-19", []),
    ("F1", "movie", "Cinema", "bcaf4c17-e1c3-4c47-a691-c243a0753ac0", "csv:2025-06-22", []),
    ("Materialists", "movie", "Cinema", "46aaea39-81f7-4ff9-8ef6-e44ace5d6ae2", "csv:2025-06-13", ["Daniel Pemberton"]),
    ("The Devil Wears Prada 2", "movie", "Cinema", "a45fa107-0b0f-4146-91ed-c78336c054ac", "csv:2026-05-01", []),
    ("Virgin River (Season 3)", "tv_show", "Netflix", "340934a1-b646-406e-a2da-665c5c798230", "wd:Q115668406", ["Jeff Garber"]),
    ("Euphoria (Season 2)", "tv_show", "HBO", "502491f2-8d08-4866-88cf-4e72fbe0844c", "wd:Q110496915", ["Labrinth", "Zendaya"]),
    ("Nobody Wants This (Season 2)", "tv_show", "Netflix", "ba5f97ea-4b10-4cab-96be-ff457418c06f", "wd:Q131274407", []),
    ("Stranger Things 5 (Volume 1)", "tv_show", "Netflix", "1b85007c-df60-4479-971e-2f3b47612f34", "wd:Q113712509", []),
    ("Emily in Paris (Season 5)", "tv_show", "Netflix", "4ecb19b8-4595-4b24-ada5-dfb09f6af1c4", "wd:Q130335118", ["Ashley Park", "Gabriel Mann"]),
    ("To All the Boys: Always and Forever", "movie", "Netflix", "a3fb0eaa-77a4-4d29-b75b-8c94ffeae1d2", "wd:Q85321374", []),
    ("They Cloned Tyrone", "movie", "Netflix", "c9977784-58d5-44f9-b623-6241a2d033d6", "wd:Q104902025", []),
    ("Cruella", "movie", "Cinema", "f3328080-a80d-42a4-be4d-56061e9aec08", "wdfilm:Cruella|2021", []),
    ("Free Guy", "movie", "Cinema", "40b3ea9e-42e0-4ea6-a04a-51d086c6f2f4", "wdfilm:Free Guy|2021", []),
    ("The Suicide Squad", "movie", "Cinema", "9a2202c1-7a7d-400b-bbc5-7daba4dc4612", "wdfilm:The Suicide Squad|2021", []),
    ("Last Night in Soho", "movie", "Cinema", "11d40299-5e83-462e-90ea-b6beed2358eb", "wdfilm:Last Night in Soho|2021", []),
    ("House of Gucci", "movie", "Cinema", "957122ba-a1f8-47b9-9f3d-119c36d6c859", "wdfilm:House of Gucci|2021", []),
    ("Licorice Pizza", "movie", "Cinema", "2441ac5c-7192-4687-b792-70383af69e8b", "wdfilm:Licorice Pizza|2021", []),
    ("Fast X", "movie", "Cinema", "b50c3b75-0666-4cf9-bbbe-266567e7e107", "wdfilm:Fast X|2023", []),
    ("The Idea of You", "movie", "Prime Video", "e2bbe298-956f-4680-8f00-24c2d7b1d1b6", "wdfilm:The Idea of You|2024", []),
    ("Priscilla", "movie", "Cinema", "627684d5-0452-4a03-9eab-869af12a4a19", "wdfilm:Priscilla|2023", []),
    ("Sinners", "movie", "Cinema", "da48070c-89ad-49be-a7ed-6ae4c87cad19", "wdfilm:Sinners|2025", []),
    ("A Minecraft Movie", "movie", "Cinema", "56c55597-4e13-4683-8c31-9917b69b3912", "wdfilm:A Minecraft Movie|2025", []),
    ("The Garfield Movie", "movie", "Cinema", "77ef07cb-987b-4924-a124-90ce67a78906", "wdfilm:The Garfield Movie|2024", []),
    ("Space Jam: A New Legacy", "movie", "Cinema", "a5400ae9-8db9-4471-9e9c-3f7c84438dd0", "wdfilm:Space Jam: A New Legacy|2021", []),
    ("Fast & Furious 9", "movie", "Cinema", "b7dc15c9-a306-4b93-88a1-71a28d5dd42d", "wdfilm:F9|2021", []),
    ("Arcane (Season 1)", "tv_show", "Netflix", "43141177-7606-44cc-abdb-fa6a2b9275a2", "wdseason:Arcane, season 1", []),
    ("Yellowjackets (Season 2)", "tv_show", "Showtime", "3460d159-d1ae-422a-a9a5-3ee2e8bc8513", "wdseason:Yellowjackets, season 2", []),
    ("The Marvelous Mrs. Maisel (Season 4)", "tv_show", "Prime Video", "556cb08d-6140-436a-a649-08d00e1f79bf", "wdseason:The Marvelous Mrs. Maisel, season 4", []),
    ("The Marvelous Mrs. Maisel (Season 5)", "tv_show", "Prime Video", "dfaa2483-b23e-45fc-bfd4-943de5d590c3", "wdseason:The Marvelous Mrs. Maisel, season 5", []),
]

SKIP_TITLE = re.compile(r"\b(main title|end title|end credits|score|interlude|skit|instrumental|theme from)\b", re.I)
WD_API = "https://www.wikidata.org/w/api.php"


def wd_get(**params) -> dict:
    params["format"] = "json"
    key = re.sub(r"[^A-Za-z0-9]+", "_", json.dumps(params, sort_keys=True))[:150]
    f = WD_CACHE / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    time.sleep(0.4)
    r = httpx.get(WD_API, params=params, headers={"User-Agent": _mb.UA}, timeout=30)
    r.raise_for_status()
    WD_CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(r.json()), encoding="utf-8")
    return r.json()


def wd_dates(qid: str) -> list[str]:
    """Day-precision P577 / P580 values of an item, earliest first."""
    claims = wd_get(action="wbgetentities", ids=qid, props="claims")["entities"][qid]["claims"]
    days = []
    for prop in ("P577", "P580"):
        for c in claims.get(prop, []):
            v = c["mainsnak"].get("datavalue", {}).get("value", {})
            if v.get("precision", 0) >= 11:
                days.append(v["time"][1:11])
    return sorted(set(days))


def wd_search(term: str, year: str | None) -> str | None:
    for hit in wd_get(action="wbsearchentities", search=term, language="en", limit=10, type="item")["search"]:
        desc = (hit.get("description") or "").lower()
        if year is None:
            if hit.get("label", "").casefold() == term.casefold() and "season" in desc:
                return hit["id"]
        elif year in desc and "film" in desc and "soundtrack" not in desc and "album" not in desc:
            return hit["id"]
    return None


def resolve_date(spec: str) -> tuple[str, str] | None:
    kind, _, value = spec.partition(":")
    if kind == "csv":
        return value, "previous placements.csv release_date"
    if kind == "wd":
        qid = value
    elif kind == "wdfilm":
        term, year = value.split("|")
        qid = wd_search(term, year)
    else:
        qid = wd_search(value, None)
    days = wd_dates(qid) if qid else []
    return (days[0], f"Wikidata {qid} P577/P580 earliest") if days else None


def clean_song(title: str) -> str:
    title = re.sub(r"\s*[-–]\s*(from|taken from)\b.*$", "", title, flags=re.I)
    title = re.sub(r"\s*\((?:from|single version|mono|stereo|remaster(?:ed)?|\d{4} remaster(?:ed)?)[^)]*\)", "", title, flags=re.I)
    return title.strip()


def credit_names(track: dict) -> list[str]:
    return [a["artist"]["name"] if "artist" in a else a["name"] for a in track["artist-credit"]]


def credit_text(track: dict) -> str:
    return "".join(a["name"] + a.get("joinphrase", "") for a in track["artist-credit"]).strip()


def best_release(rg: str) -> dict:
    releases = _mb.get("release", **{"release-group": rg, "limit": 100})["releases"]
    official = [r for r in releases if r.get("status") == "Official"] or releases

    def tracks(r):
        return sum(m.get("track-count", 0) for m in r.get("media", []))
    return sorted(official, key=lambda r: (-tracks(r), r.get("date") or "9999"))[0]


def tracks_for(rg: str, exclude: list[str]) -> tuple[list[tuple[str, str]], str]:
    best = best_release(rg)
    release = _mb.get(f"release/{best['id']}", inc="recordings+artist-credits")
    tracks = [t for m in release["media"] for t in m["tracks"]]
    counts = Counter(n.casefold() for t in tracks for n in set(credit_names(t)))
    dominant = {n for n, c in counts.items() if len(tracks) >= 4 and c / len(tracks) >= 0.3}
    banned = {e.casefold() for e in exclude} | dominant
    seen, rows = set(), []
    for t in tracks:
        names = [n.casefold() for n in credit_names(t)]
        if any(n in banned or re.search(r"\bcast\b", n) for n in names) or SKIP_TITLE.search(t["title"]):
            continue
        song, artist = clean_song(t["title"]), credit_text(t)
        if (song.casefold(), artist.casefold()) in seen:
            continue
        seen.add((song.casefold(), artist.casefold()))
        rows.append((song, artist))
    return rows, f"https://musicbrainz.org/release/{best['id']}"


def main() -> None:
    rows, sources = [], []
    for show, show_type, platform, rg, date_spec, exclude in TITLES:
        resolved = resolve_date(date_spec)
        if resolved is None:
            print(f"DROPPED (no sourced release date): {show}", file=sys.stderr)
            continue
        date, date_source = resolved
        songs, url = tracks_for(rg, exclude)
        if not songs:
            print(f"DROPPED (no licensed song rows left after filtering): {show}", file=sys.stderr)
            continue
        for song, artist in songs:
            rows.append({"show": show, "show_type": show_type, "platform": platform, "release_date": date,
                         "song": song, "artist": artist, "song_year": "", "scene_note": "", "source_url": url})
        sources.append({"show": show, "release_date": date, "date_source": date_source,
                        "musicbrainz_release_group": f"https://musicbrainz.org/release-group/{rg}",
                        "musicbrainz_release": url, "songs": len(songs)})
        print(f"{show:42s} {date} {len(songs):3d} songs  ({date_source})")
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    with SOURCES.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sources[0]))
        w.writeheader()
        w.writerows(sources)
    big = [s for s in sources if s["songs"] >= 4]
    print(f"rows {len(rows)}; titles {len(sources)}; with >=4 songs {len(big)}; 2024+ {sum(s['release_date'] >= '2024-01-01' for s in big)}")
    print(f"MusicBrainz requests: {_mb.stats}")


if __name__ == "__main__":
    main()
