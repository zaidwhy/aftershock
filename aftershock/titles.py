"""Netflix title index: when and where any title charted, plus a lookup that tolerates typos.

The index is built by scripts/run_forecasts.py and read by the API and the MCP server.
"""
import difflib
import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

INDEX_SINCE = date(2024, 1, 1)
BASE = date(2020, 1, 1)  # the file stores weeks as days since this date, grouped by week, to stay small
MAX_OTHERS = 4
NEXT_COUNTRIES = 8
MIN_RATIO = 0.85  # fuzzy matches below this similarity are rejected ("The Sopranos" must not find "The Orphans")
SEASON_WORDS = re.compile(r"\b(season|series|part|volume|vol|book|chapter)\s+\d+\b|\blimited series\b")
_cache = {}


def normalise(text):
    """Case, accent and punctuation-insensitive form of a title."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold().replace("&", " and ")).strip()


def season_number(text):
    found = re.search(r"\bseason\s+(\d+)\b", normalise(text))
    return int(found.group(1)) if found else None


def strip_seasons(text):
    return re.sub(r"\s+", " ", SEASON_WORDS.sub(" ", normalise(text))).strip()


def season_label(show, season):
    if season == "N/A":
        return None
    label = (season[len(show):].lstrip(": ").strip() or season) if season.startswith(show) else season
    return f"Season {label}" if label.isdigit() else label  # Netflix writes some as "Show 5"


def build_index(rows, model, countries, names, last_week, storm_keys, horizon, since=INDEX_SINCE):
    """One record per (show, season) that charted since `since`; see module docstring."""
    from aftershock.netflix import first_entries, title_categories  # local: keeps import order simple
    first, categories = first_entries(rows), title_categories(rows)
    recent = {}
    for row in rows:
        if date.fromisoformat(row["week"]) >= since:
            recent[(row["show_title"], row["season_title"])] = True
    spreading_from = last_week - timedelta(weeks=horizon)
    records = []
    for key in sorted(recent):
        show, season = key
        entries = sorted(first[key].items(), key=lambda kv: (kv[1], kv[0]))
        first_week = entries[0][1]
        label = season_label(show, season)
        by_week = {}
        for country, week in entries:
            by_week.setdefault((week - BASE).days, []).append(country)
        record = {"s": show, "k": "f" if categories[key].startswith("Films") else "t",
                  "c": [[days, ",".join(codes)] for days, codes in by_week.items()]}
        if label:
            record["n"] = label
        if first_week >= spreading_from and key not in storm_keys:
            origins = [c for c, w in entries if w == first_week]
            if len(origins) <= 3:
                event = {"title": key, "category": categories[key], "origin_countries": origins}
                charted = {c for c, _ in entries}
                candidates = [c for c in countries if c not in charted]
                probs = model.predict(event, candidates)
                ranked = sorted(candidates, key=lambda c: -probs[c])[:NEXT_COUNTRIES]
                record["f"] = {"origin": origins, "next": [
                    {"code": c, "name": names[c], "probability": round(probs[c], 4),
                     "why": _why(model, origins, c, names)} for c in ranked]}
            else:
                record["x"] = "already charting widely"
        records.append(record)
    return {"week": str(last_week), "since": str(since), "horizon_weeks": horizon, "base": str(BASE), "titles": records}


def _why(model, origins, target, names):
    parts = []
    for origin in origins:
        trials, joins = model._pair_trials[origin, target], model._pair_joins[origin, target]
        if trials:
            parts.append(f"{names[target]} joined {joins} of {trials} past breakouts that started in {names[origin]}")
    return "; ".join(parts) or None


def load(path):
    """Parsed index with a normalised-name lookup table, cached until the file changes."""
    path = Path(path)
    if not path.exists():
        return None
    stamp = (str(path), path.stat().st_mtime_ns)
    if stamp not in _cache:
        data = json.loads(path.read_text(encoding="utf-8"))
        by_show, week = {}, date.fromisoformat(data["week"])
        horizon = timedelta(weeks=data["horizon_weeks"])
        for raw in data["titles"]:
            rec = _expand(raw, date.fromisoformat(data["base"]))
            rec["still_spreading"] = date.fromisoformat(rec["first_week"]) >= week - horizon
            by_show.setdefault(normalise(rec["show"]), []).append(rec)
        _cache.clear()
        _cache[stamp] = (data, by_show)
    return _cache[stamp]


def _expand(raw, base):
    countries = [[code, str(base + timedelta(days=days))] for days, codes in raw["c"] for code in codes.split(",")]
    rec = {"title": f"{raw['s']}: {raw['n']}" if raw.get("n") else raw["s"], "show": raw["s"], "season": raw.get("n"),
           "kind": "film" if raw["k"] == "f" else "tv", "first_week": countries[0][1], "countries": countries}
    if "f" in raw:
        rec["forecast"] = raw["f"]
    if "x" in raw:
        rec["forecast_note"] = raw["x"]
    return rec


def _pick_season(records, wanted):
    if wanted is not None:
        for rec in records:
            if season_number(rec["season"] or "") == wanted:
                return rec
    return max(records, key=lambda r: r["first_week"])


def lookup(loaded, name):
    """(best record, [other records]) for a typed name, or (None, []). Allowed: exact, whole-word substring, or
    a fuzzy match with difflib ratio >= MIN_RATIO on the normalised title."""
    _, by_show = loaded
    wanted_season = season_number(name)
    query = strip_seasons(name)
    if len(query) < 2:
        return None, []
    ordered = []
    if query in by_show:
        ordered.append(query)
    else:
        loose = [k for k in by_show if len(query) >= 3 and f" {query} " in f" {k} "]
        ordered += sorted(loose, key=lambda k: (not k.startswith(query), len(k)))
    for k in difflib.get_close_matches(query, list(by_show), n=MAX_OTHERS + 2, cutoff=MIN_RATIO):
        if k not in ordered:
            ordered.append(k)
    if not ordered:
        return None, []
    best = _pick_season(by_show[ordered[0]], wanted_season)
    others = [r for r in sorted(by_show[ordered[0]], key=lambda r: r["first_week"], reverse=True) if r is not best]
    for k in ordered[1:]:
        others.append(_pick_season(by_show[k], None))
    return best, others[:MAX_OTHERS]


def storm_ids(storms):
    """{(show, season label): storm id} from the storms list in storms.json."""
    return {(item["netflix_title"][0], season_label(*item["netflix_title"])): item["summary"]["id"] for item in storms}


def history(loaded, name, storms):
    """The lookup response for a typed name, or None when nothing matches."""
    best, others = lookup(loaded, name.strip())
    if best is None:
        return None
    data, out = loaded[0], {k: best[k] for k in ("title", "show", "season", "kind", "first_week", "countries", "still_spreading")}
    if "forecast" in best:
        out["forecast"] = best["forecast"] | {"horizon_weeks": data["horizon_weeks"]}
    if "forecast_note" in best:
        out["forecast_note"] = best["forecast_note"]
    out["storm_id"] = storm_ids(storms).get((best["show"], best["season"]))
    out["others"] = [{k: o[k] for k in ("title", "kind", "first_week")} for o in others]
    return out
