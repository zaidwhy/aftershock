"""Ask AFTERSHOCK: a deterministic intent router. A plain question goes to the tools the product already has
(title lookup, this week's storms, the Qloo launch kit, Sync Scout, song check). No language model is involved,
so it can only report what those tools return; anything it cannot parse gets a list of what it can answer.

`answer(question, ctx)` returns {intent, steps, answer, links}. ctx is a dict:
  storms: the storm items from storms.json (summary + detail)    week: the week label
  titles: titles.load(...) result or None                        week_map: callable returning the week map
  live:   None, or an object with take() / ripple(show, placements) / scout(show) that raise LiveError
"""
import difflib
import re

from aftershock import titles as title_index
from aftershock.ripple import MAX_SONGS

MAX_QUESTION = 200
MAX_FIELD = 120
SHOW_NEXT = 5
KIT_DOMAINS = ("artist", "tv_show", "movie", "brand")

ALIASES = {"usa": "US", "united states": "US", "america": "US", "uk": "GB", "britain": "GB",
           "great britain": "GB", "england": "GB", "united kingdom": "GB", "uae": "AE", "emirates": "AE",
           "korea": "KR", "russia": "RU", "turkey": "TR", "czech republic": "CZ", "holland": "NL",
           "ivory coast": "CI", "vietnam": "VN", "burma": "MM"}
STOP = set("""what should which where will would did does do is are has have can could go goes going next chart charts
charted spread spreads spreading head heading headed to in for with pair partner partners brand brands artist artists
launch kit market markets forecast forecasts a an of and find me tell about how far it by on at get reach reaches this
after likely be there song songs music travel travels land lands good best top who when why please give picks pick
suggest recommend s whats""".split())
COUNTRY_OK = set("""what is are heading coming arriving arrive arrives going go trending popular new this week now
next here there breaking out spreading to the in for from will be which titles shows show films netflix""".split())
KIT_WORDS = re.compile(r"\b(pair|pairs|pairing|partner|partners|brand|brands|artist|artists|launch|market|marketing"
                       r"|promote|promotion|collab|collaborate|kit)\b")
SONGS_FOR = re.compile(r"\b(?:songs?|artists?|music|musicians?|tracks?|soundtrack|singers?)\s+(?:for|to go with|to pair with"
                       r"|that fit|that suit|that match|suited to)\s+(?P<show>.+)$", re.I)
SONG_CHECK = re.compile(r"^(?:(?:check|score|compare|try|test|rate)\s+)?(?P<songs>.+?\s+by\s+.+?)\s+(?:for|in)\s+(?P<show>.+)$", re.I)
HELP = ("I can answer: where a title goes next (\"Where will Squid Game go next?\"), what to pair a breakout with in a "
        "country (\"What should Fukrey Returns pair with in Bangladesh?\"), artists for a show (\"Find songs for Stranger "
        "Things\"), whether a song reaches a new crowd (\"Running Up That Hill by Kate Bush for Stranger Things\"), and "
        "what is heading to a country (\"What is heading to Brazil?\").")


class LiveError(Exception):
    """A live Qloo lookup was refused or failed; the message is safe to show."""


def pct(p):
    return "<1%" if p < 0.005 else f"{round(p * 100)}%"


def _norm(text):
    return title_index.normalise(text)


def _has(hay, needle):
    return bool(needle) and f" {needle} " in f" {hay} "


def _clean(question):
    text = re.sub(r"\s+", " ", (question or "").strip())
    return text.rstrip("?!. ").strip()


def _strip_stops(norm_text):
    tokens = norm_text.split()
    while tokens and tokens[0] in STOP:
        tokens.pop(0)
    while tokens and tokens[-1] in STOP:
        tokens.pop()
    return " ".join(tokens)


def country_names(storms, titles):
    """{code: name} from the storms' forecasts and origins and the title index's forecasts."""
    names = {}
    for item in storms:
        for c in item["summary"].get("origin_countries", []):
            names[c["code"]] = c["name"]
        for f in item["detail"].get("spillover", {}).get("forecasts", []):
            names[f["code"]] = f["name"]
    if titles:
        for rec in titles[0]["titles"]:
            for n in (rec.get("f") or {}).get("next", []):
                names.setdefault(n["code"], n["name"])
    return names


def find_country(norm_text, raw_text, names):
    """(code, name, matched normalised phrase) for a country named in the text, longest name first, else None.
    A bare upper-case ISO code counts only after 'in' or 'to' ("in BR")."""
    table = {_norm(n): (c, n) for c, n in names.items()}
    for alias, code in ALIASES.items():
        if code in names and _norm(alias) not in table:
            table[_norm(alias)] = (code, names[code])
    for key in sorted(table, key=len, reverse=True):
        if _has(norm_text, key):
            return table[key][0], table[key][1], key
    code = re.search(r"\b(?:in|to)\s+([A-Z]{2})\b", raw_text)
    if code and code.group(1) in names:
        return code.group(1), names[code.group(1)], code.group(1).lower()
    return None


def _mask(norm_text, phrase):
    return re.sub(r"\s+", " ", f" {norm_text} ".replace(f" {phrase} ", " ", 1)).strip()


def _best_storm(items):
    return max(items, key=lambda i: (i["summary"].get("top_forecast") or {}).get("probability", 0))


def _storm_by_title(storms, norm_text, candidates):
    """The storm named in the text: a whole-word title match (longest), else a close match (ratio >= MIN_RATIO)
    of a candidate phrase against the storm titles. Returns (item, matched phrase) or (None, None)."""
    keyed = [(_norm(i["summary"]["title"]), i) for i in storms]
    whole = [(k, i) for k, i in keyed if len(k) >= 2 and _has(norm_text, k)]
    if whole:
        k, _ = max(whole, key=lambda t: len(t[0]))
        return _best_storm([i for kk, i in whole if kk == k]), k
    for cand in candidates:
        close = difflib.get_close_matches(cand, sorted({k for k, _ in keyed}), n=1, cutoff=title_index.MIN_RATIO)
        if close:
            return _best_storm([i for k, i in keyed if k == close[0]]), close[0]
    return None, None


def _history(ctx, name):
    loaded = ctx.get("titles")
    if loaded is None or len(_norm(name)) < 2:
        return None
    return title_index.history(loaded, name, ctx["storms"])


def _from_history(ctx, rec, phrase):
    storm = next((i for i in ctx["storms"] if i["summary"]["id"] == rec.get("storm_id")), None)
    return {"storm": storm, "history": rec, "phrase": phrase}


def resolve_title(ctx, norm_text, country):
    """Find the title a question is about. Returns {storm, history, phrase} (either may be None) or None.
    Order: a storm named in the text; the stripped question against the Netflix index (strict match rule);
    a whole-word index title of 5+ characters inside the text (country words removed)."""
    base = _mask(norm_text, country[2]) if country else norm_text
    cands = [c for c in dict.fromkeys([_strip_stops(norm_text), _strip_stops(base)]) if c]
    if country and cands and cands[0] == country[2]:
        cands = cands[1:]  # "what is heading to Brazil" is about the country, not a film called Brazil
    item, phrase = _storm_by_title(ctx["storms"], norm_text, cands + [c[4:] for c in cands if c.startswith("the ")])
    if item:
        return {"storm": item, "history": None, "phrase": phrase}
    for cand in cands:
        rec = _history(ctx, cand)
        if rec:
            return _from_history(ctx, rec, cand)
    loaded = ctx.get("titles")
    if loaded is not None and base:
        keys = [k for k in loaded[1] if len(k) >= 5 and _has(base, k)]
        rec = _history(ctx, max(keys, key=len)) if keys else None
        if rec:
            return _from_history(ctx, rec, base)
    return None


def _step(tool, inp, ok, note):
    return {"tool": tool, "input": inp, "ok": ok, "note": note}


def _origins(summary):
    return ", ".join(c["name"] for c in summary["origin_countries"])


def _forecast_rows(detail, n=SHOW_NEXT):
    return [{"code": f["code"], "name": f["name"], "probability": f["probability"], "why": f.get("why")}
            for f in detail["spillover"]["forecasts"][:n]]


def _storm_answer(item, country, steps, note=None):
    summ, detail = item["summary"], item["detail"]
    forecasts = detail["spillover"]["forecasts"]
    focus = None
    if country:
        for rank, f in enumerate(forecasts, 1):
            if f["code"] == country[0]:
                focus = {"name": f["name"], "code": f["code"], "probability": f["probability"], "rank": rank}
        if focus is None:
            focus = {"name": country[1], "code": country[0], "probability": None, "rank": None}
    top = forecasts[0] if forecasts else None
    steps.append(_step("forecast", summ["title"], bool(top),
                       f"Read this week's forecast for {summ['title']}: most likely next is {top['name']} ({pct(top['probability'])})."
                       if top else f"{summ['title']} is a breakout this week but has no forecast rows."))
    meta = summ.get("meta") or {}
    kits = [r for r in detail.get("launch_kit", []) if r.get("kit") and any(r["kit"].values())]
    names = {f["code"]: f["name"] for f in forecasts}
    return {"kind": "storm", "id": summ["id"], "title": summ["title"], "season": summ.get("season"),
            "origin": _origins(summ), "origin_week": summ["origin_week"], "year": meta.get("year"),
            "genres": meta.get("genres") or [], "horizon_weeks": detail["spillover"].get("horizon_weeks"),
            "forecast": _forecast_rows(detail), "focus": focus, "note": note,
            "kit_countries": [names.get(r["code"], r["code"]) for r in kits],
            "locked_at": detail["spillover"].get("locked_at")}


def _fresh(row, domain, n=5):
    seen = {c.casefold() for c in (row.get("control") or {}).get(domain, [])}
    items = [e["name"] for e in (row["kit"].get(domain) or [])]
    return [x for x in items if x.casefold() not in seen][:n], [x for x in items if x.casefold() in seen][:n]


def _kit_answer(item, country, steps):
    summ, detail = item["summary"], item["detail"]
    forecasts = detail["spillover"]["forecasts"]
    rank, fc = next(((r, f) for r, f in enumerate(forecasts, 1) if f["code"] == country[0]), (None, None))
    row = next((r for r in detail.get("launch_kit", []) if r.get("code") == country[0]
                and r.get("kit") and any(r["kit"].values())), None)
    if row is None:
        covered = [f["name"] for f in forecasts[:3]]
        standing = (f"{country[1]} is #{rank} in its forecast ({pct(fc['probability'])})" if fc
                    else f"{country[1]} is not in its forecast list")
        steps.append(_step("qloo_launch_kit", f"{summ['title']} / {country[1]}", False,
                           f"No launch kit for {country[1]}: kits cover only a breakout's top 3 countries ({', '.join(covered)})."))
        return _storm_answer(item, country, steps,
                             note=f"{summ['title']} is a breakout this week, but there is no launch kit for {country[1]}. {standing}; "
                                  f"Qloo launch kits cover only the top 3 countries: {', '.join(covered)}. Here is the forecast instead.")
    steps.append(_step("forecast", summ["title"], fc is not None,
                       f"Looked up this week's forecast: {country[1]} {pct(fc['probability'])}." if fc
                       else f"{country[1]} is not in the forecast list."))
    spec = row.get("specificity")
    label = "unknown specificity" if spec is None else f"{'countrywide taste' if row.get('generic') else 'title-specific'} {round(spec * 100)}%"
    steps.append(_step("qloo_launch_kit", f"{summ['title']} / {country[1]}", True, f"Read the Qloo launch kit ({label})."))
    picks, common = {}, {}
    for d in KIT_DOMAINS:
        picks[d], common[d] = _fresh(row, d)
    hs = row.get("hotspots") or {}
    places = hs.get("places") or []
    steps.append(_step("qloo_hotspots", country[1], bool(places),
                       f"Added Qloo hotspots: {', '.join(places)}." if places else "Qloo named no hotspot places for this country."))
    meta = summ.get("meta") or {}
    return {"kind": "kit", "id": summ["id"], "title": summ["title"], "season": summ.get("season"),
            "origin": _origins(summ), "country": country[1], "code": country[0],
            "probability": fc["probability"] if fc else None, "rank": rank, "why": fc.get("why") if fc else None,
            "horizon_weeks": detail["spillover"].get("horizon_weeks"), "year": meta.get("year"),
            "specificity": spec, "generic": bool(row.get("generic")), "picks": picks, "common": common,
            "places": places, "cells": hs.get("cells") or []}


def _parse_songs(text):
    """[(song, artist)] from "A by X and B by Y, C by Z", or None. Commas and semicolons split songs; " and "
    splits only where both sides are complete "song by artist" pieces, so "Simon and Garfunkel" survives."""
    pieces = []
    for chunk in re.split(r"[;,]", text):
        cur = None
        for part in re.split(r"\s+and\s+", chunk.strip(), flags=re.I):
            if cur is None:
                cur = part
            elif " by " not in cur.lower() or " by " not in part.lower():
                cur = f"{cur} and {part}"
            else:
                pieces.append(cur)
                cur = part
        if cur:
            pieces.append(cur)
    out = []
    for piece in pieces:
        cut = piece.lower().rfind(" by ")
        if cut < 0:
            return None
        song, artist = piece[:cut].strip(" \"'"), piece[cut + 4:].strip(" \"'")
        if not song or not artist:
            return None
        out.append((song, artist))
    return out or None


def _live(ctx, steps, tool, inp, run, doing):
    live = ctx.get("live")
    if live is None:
        steps.append(_step(tool, inp, False, "Live Qloo lookups are not available here."))
        return None
    try:
        live.take()
        result = run(live)
    except LiveError as err:
        steps.append(_step(tool, inp, False, str(err)))
        return None
    steps.append(_step(tool, inp, True, doing))
    return result


def _history_step(ctx, steps, show):
    rec = _history(ctx, show)
    if rec:
        steps.append(_step("title_lookup", show, True, f"Found {rec['title']} in Netflix's Top 10 history (first charted {rec['first_week']})."))


def _song_check(ctx, songs, show, steps):
    one = f"{songs[0][0]} by {songs[0][1]}" if len(songs) == 1 else f"{len(songs)} songs"
    steps.insert(0, _step("understand", None, True, f"Song check: {one} for {show}."))
    _history_step(ctx, steps, show)
    result = _live(ctx, steps, "ripple_score", show, lambda live: live.ripple(show, songs),
                   "Asked Qloo who watches the show and who listens to each artist, then compared their age groups.")
    parsed = {"show": show, "songs": [{"song": s, "artist": a} for s, a in songs]}
    if result is None:
        return {"kind": "unavailable", "message": steps[-1]["note"], "parsed": parsed}
    return {"kind": "ripple", "ripple": result, "parsed": parsed}


def _scout(ctx, show, steps):
    steps.insert(0, _step("understand", None, True, f"Artists for {show} (Sync Scout)."))
    _history_step(ctx, steps, show)
    result = _live(ctx, steps, "sync_scout", show, lambda live: live.scout(show),
                   "Asked Qloo which artists the show's fans like, then ranked them by how different their listeners' ages are.")
    if result is None:
        return {"kind": "unavailable", "message": steps[-1]["note"], "show": show}
    return {"kind": "scout", "scout": result, "show": show}


def _title_answer(rec, country, steps, note=None):
    focus = None
    if country:
        charted = next((w for c, w in rec["countries"] if c == country[0]), None)
        nxt = next((n for n in (rec.get("forecast") or {}).get("next", []) if n["code"] == country[0]), None)
        if charted:
            focus = f"It has already charted in {country[1]} (first week {charted})."
        elif nxt:
            focus = f"{country[1]} is among its likeliest next countries: {pct(nxt['probability'])} within {rec['forecast']['horizon_weeks']} weeks."
        else:
            focus = f"{country[1]} is not among its likeliest next countries."
    if rec.get("forecast"):
        top = rec["forecast"]["next"][0]
        steps.append(_step("forecast", rec["title"], True, f"Read its Netflix-history forecast: most likely next is {top['name']} ({pct(top['probability'])})."))
    else:
        if rec.get("forecast_note"):
            why = "it is already charting in many countries."
        elif not rec.get("still_spreading"):
            why = "it first charted more than a month ago, so it is past the forecast window; the history shows where it has charted."
        else:
            why = "there is too little history to forecast it."
        steps.append(_step("forecast", rec["title"], False, "No forecast for this title: " + why))
        note = note or f"There is no forecast for {rec['title']}: {why}"
    return {"kind": "title", "history": rec, "focus": focus, "note": note}


def _country_answer(ctx, country, steps):
    steps.insert(0, _step("understand", None, True, f"What is heading to {country[1]} this week."))
    wm = ctx["week_map"]()
    entry = next((c for c in wm["countries"] if c["code"] == country[0]), None)
    if entry is None:
        steps.append(_step("week_map", country[1], False, f"No breakout lists {country[1]} among its likeliest countries this week."))
    else:
        steps.append(_step("week_map", country[1], True,
                           f"Read this week's map: {country[1]} has a {pct(entry['chance'])} chance of getting at least one new breakout."))
    return {"kind": "country", "name": country[1], "code": country[0], "week": ctx.get("week"),
            "origin": country[0] in wm.get("origins", []), "chance": entry["chance"] if entry else None,
            "top": [{"id": t["id"], "title": t["title"], "p": t["p"]} for t in (entry or {}).get("top", [])]}


def _links(a):
    kind = a["kind"]
    if kind in ("kit", "storm"):
        return [{"label": f"Full forecast for {a['title']}", "href": f"#/storm/{a['id']}"}]
    if kind == "title" and a["history"].get("storm_id"):
        return [{"label": "Storm page", "href": f"#/storm/{a['history']['storm_id']}"}]
    if kind in ("ripple", "unavailable") and "parsed" in a:
        return [{"label": "Song check page", "href": "#/try"}]
    if kind == "scout":
        return [{"label": "Sync Scout page", "href": "#/scout"}]
    if kind == "country":
        return [{"label": "This week's storms", "href": "#/"}]
    return []


def _done(intent, steps, ans):
    if not steps or steps[0]["tool"] != "understand":
        steps.insert(0, _step("understand", None, True, intent.replace("_", " ").capitalize() + "."))
    for i, s in enumerate(steps, 1):
        s["n"] = i
    return {"intent": intent, "steps": steps, "answer": ans, "links": _links(ans)}


def _fail(intent, msg):
    return _done(intent, [_step("understand", None, False, msg)], {"kind": "help", "message": msg})


def _title_of(found):
    return found["storm"]["summary"]["title"] if found["storm"] else found["history"]["title"]


def answer(question, ctx):
    raw = _clean(question)
    if not raw:
        return _fail("none", "The question was empty. " + HELP)
    raw = raw[:MAX_QUESTION]
    norm = _norm(raw)
    if not norm:
        # Netflix's Top 10 data and Qloo list titles in Latin script, so "जब वी मेट" matches nothing
        return _fail("none", "I could not read that question. Titles are matched as Netflix lists them, in "
                             "the Latin alphabet: try \"Jab We Met\". " + HELP)
    steps = []

    # a) song check: "<song> by <artist> for|in <show>"
    m = SONG_CHECK.match(raw)
    if m:
        songs, show = _parse_songs(m.group("songs")), m.group("show").strip(" \"'")
        if songs and show:
            if len(songs) > MAX_SONGS or any(len(x) > MAX_FIELD for s in songs for x in s) or len(show) > MAX_FIELD:
                return _fail("song_check", f"A song check takes 1 to {MAX_SONGS} songs, each name up to {MAX_FIELD} characters.")
            return _done("song_check", steps, _song_check(ctx, songs, show, steps))

    names = country_names(ctx["storms"], ctx.get("titles"))
    storm_hit, storm_phrase = _storm_by_title(ctx["storms"], norm, [])
    country = find_country(_mask(norm, storm_phrase) if storm_hit else norm, raw, names)
    wants_kit = bool(KIT_WORDS.search(norm))

    # c) songs or artists for a show (live)
    m = SONGS_FOR.search(raw)
    if m and not (wants_kit and country and storm_hit):
        show = m.group("show").strip(" \"'")
        if country:
            show = re.sub(r"\s+(?:in|to)\s+[A-Za-z .]+$", "", show)
        if show and len(show) <= MAX_FIELD:
            return _done("artists_for_show", steps, _scout(ctx, show, steps))

    found = resolve_title(ctx, norm, country)

    # b) launch kit: a pairing word, a title and "in <country>"
    if wants_kit and country and found:
        title = _title_of(found)
        steps.append(_step("understand", None, True, f"Launch kit for {title} in {country[1]}."))
        if found["storm"]:
            return _done("launch_kit", steps, _kit_answer(found["storm"], country, steps))
        steps.append(_step("title_lookup", title, True, f"Found {title} in Netflix's Top 10 history, but it is not one of this week's breakouts."))
        note = f"{title} is not one of this week's breakouts, so there is no launch kit for it. Here is its Netflix history and forecast instead."
        return _done("launch_kit", steps, _title_answer(found["history"], country, steps, note=note))

    # A pairing question naming a place we do not know ("in Narnia") would otherwise be answered as if the
    # place had not been asked about; say so in the steps before falling back to the forecast.
    unknown_place = re.search(r"\bin\s+([A-Za-z][A-Za-z .'-]{1,40})$", raw) if wants_kit and found and not country else None
    if unknown_place:
        steps.append(_step("understand", unknown_place.group(1), False,
                           f"I don't know a country called {unknown_place.group(1)}, so here is the forecast for every country instead."))

    # d) next countries, spread, forecast, or where a title has charted
    if found:
        title = _title_of(found)
        aside = f", with a look at {country[1]}" if country else ""
        steps.append(_step("understand", None, True, f"Next countries for {title}{aside}."))
        if found["storm"]:
            return _done("forecast", steps, _storm_answer(found["storm"], country, steps))
        steps.append(_step("title_lookup", title, True, f"Looked up {title} in Netflix's Top 10 history since {ctx['titles'][0]['since'][:4]}."))
        return _done("title_lookup", steps, _title_answer(found["history"], country, steps))

    # e) a country alone
    if country and not [t for t in _mask(norm, country[2]).split() if t not in COUNTRY_OK]:
        return _done("country", steps, _country_answer(ctx, country, steps))

    # f) fallback
    steps.append(_step("understand", None, False, "I could not match this to a title, a country or a song."))
    steps.append(_step("title_lookup", raw, False, "No close match for the text in Netflix's Top 10 since 2024."))
    return _done("none", steps, {"kind": "help", "message": "I could not tell what you are asking. " + HELP})
