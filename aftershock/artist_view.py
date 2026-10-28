"""Artist view: the same weekly data as the launch briefs, read from the artist's side.

For every artist that appears this week as a Qloo-confirmed pick for a title's audience (`plan.confirmed`, domain
artist) or in an event idea, one entry per (title, country): where the title is breaking out, the chance it charts
there within the horizon, the cities where the title's audience and the artist's audience both concentrate (when an
event idea exists), whether Qloo's own kit also named the artist and whether Qloo confirmed the AI's suggestion.
Nothing here is new data: it re-indexes rows the weekly run already holds. No Qloo or model call.
"""
import hashlib
import re
import unicodedata

from aftershock.launch_brief import _join, _pct
from aftershock.launch_kit import name_key

NOT_FOUND = "No artist called {slug} appears in this week's forecasts."


def slugify(name):
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def _ident(name):
    return name_key(name) or name.casefold().strip()


def _slug_for(name, taken):
    """URL-safe slug; a name with no Latin letters, or one that collides with another artist, gets a short hash."""
    slug = slugify(name)
    if not slug or taken.get(slug, _ident(name)) != _ident(name):
        slug = f"{slug or 'artist'}-{hashlib.sha1(_ident(name).encode('utf-8')).hexdigest()[:6]}"
    taken[slug] = _ident(name)
    return slug


def build(items):
    """{"artists": [...]} from storm items ([{summary, detail}], as in storms.json), most breakouts first, then the
    best chance. Each artist: {name, slug, breakouts (list, best chance first), countries}."""
    found = {}  # ident -> {"name", "by": {(storm id, code): entry}}
    for item in items:
        detail = item["detail"]
        forecasts = {f["code"]: f for f in detail.get("spillover", {}).get("forecasts") or []}
        horizon = (detail.get("spillover") or {}).get("horizon_weeks", 4)
        origins = _join([o["name"] for o in detail.get("origin_countries") or []]) or "its home markets"
        season = detail.get("season")
        title = detail["title"] + (f" {season}" if season else "")
        for row in detail.get("launch_kit") or []:
            fc = forecasts.get(row.get("code"))
            if not fc:
                continue
            kit_names = {name_key(e["name"]) for e in (row.get("kit") or {}).get("artist") or [] if e.get("name")}
            seen = {}  # ident -> {name, confirmed, both, cities}
            for c in ((row.get("plan") or {}).get("confirmed") or []):
                if c.get("domain") == "artist" and c.get("name"):
                    e = seen.setdefault(_ident(c["name"]), {"name": c["name"], "confirmed": False, "both": False, "cities": []})
                    e["confirmed"], e["both"] = True, e["both"] or bool(c.get("both"))
            for ev in row.get("events") or []:
                if ev.get("artist") and ev.get("cities"):
                    e = seen.setdefault(_ident(ev["artist"]), {"name": ev["artist"], "confirmed": False, "both": False, "cities": []})
                    e["cities"] = list(dict.fromkeys(e["cities"] + list(ev["cities"])))
            for ident, e in seen.items():
                entry = {"storm_id": detail.get("id") or item["summary"]["id"], "title": title, "code": row["code"],
                         "country": fc["name"], "origin": origins, "chance": fc["probability"],
                         "chance_label": _pct(fc["probability"]), "horizon_weeks": horizon,
                         "cities": e["cities"], "countrywide": bool(row.get("generic")),
                         "in_qloo_kit": e["both"] or ident in kit_names,
                         "qloo_confirmed": e["confirmed"]}
                slot = found.setdefault(ident, {"name": e["name"], "by": {}})
                slot["by"][(entry["storm_id"], entry["code"])] = entry
    taken, artists = {}, []
    for ident, slot in sorted(found.items(), key=lambda kv: kv[1]["name"].casefold()):
        breakouts = sorted(slot["by"].values(), key=lambda b: (b["countrywide"], -b["chance"]))
        countries = list(dict.fromkeys(b["country"] for b in breakouts))
        artists.append({"name": slot["name"], "slug": _slug_for(slot["name"], taken), "breakouts": breakouts,
                        "countries": countries, "countrywide_only": all(b["countrywide"] for b in breakouts)})
    artists.sort(key=lambda a: (a["countrywide_only"], -len(a["breakouts"]), -a["breakouts"][0]["chance"], a["name"].casefold()))
    return {"artists": artists}


def listing(index, week):
    return {"week": week, "artists": [{"name": a["name"], "slug": a["slug"], "breakouts": len(a["breakouts"]),
                                       "countries": a["countries"], "countrywide_only": a["countrywide_only"]} for a in index["artists"]]}


def detail(index, week, slug):
    """One artist's page body, or None when no artist has this slug."""
    a = next((x for x in index["artists"] if x["slug"] == slug), None)
    return None if a is None else {"week": week, **a}
