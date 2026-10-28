"""Ask AFTERSHOCK: a deterministic intent router. A plain question goes to the tools the product already has
(title lookup, this week's storms, the Qloo launch kit, Sync Scout, song check). No language model is involved,
so it can only report what those tools return; anything it cannot parse gets a list of what it can answer.

`answer(question, ctx)` returns {intent, steps, answer, links}. ctx is a dict:
  storms: the storm items from storms.json (summary + detail)    week: the week label
  titles: titles.load(...) result or None                        week_map: callable returning the week map
  live:   None, or an object with take() / ripple(show, placements) / scout(show) that raise LiveError
Beyond the data tools it answers about the product itself (FEATURES), why a title is missing or forecast where it is,
who it is for, and small talk. Every number in those answers comes from ctx or from the fixed facts in FEATURES.
"""
import difflib
import re
from urllib.parse import quote

from aftershock import titles as title_index
from aftershock.ripple import MAX_SONGS

MAX_QUESTION = 200
MAX_FIELD = 120
SHOW_NEXT = 5
KIT_DOMAINS = ("artist", "tv_show", "movie", "brand")

ALIASES = {"usa": "US", "united states": "US", "america": "US", "uk": "GB", "britain": "GB",
           "great britain": "GB", "england": "GB", "united kingdom": "GB", "uae": "AE", "emirates": "AE",
           "korea": "KR", "russia": "RU", "turkey": "TR", "czech republic": "CZ", "holland": "NL",
           "ivory coast": "CI", "vietnam": "VN", "burma": "MM", "trinidad": "TT", "trinidad and tobago": "TT",
           "czechia": "CZ", "czech": "CZ", "south korea": "KR", "the netherlands": "NL", "u s": "US", "u s a": "US",
           "u k": "GB", "u a e": "AE"}
# Names for aliased countries that no storm or forecast mentions yet, so "Trinidad" still resolves to a country.
ALIAS_NAMES = {"US": "United States", "GB": "United Kingdom", "AE": "United Arab Emirates", "KR": "South Korea",
               "RU": "Russia", "TR": "Turkey", "CZ": "Czechia", "NL": "Netherlands", "CI": "Ivory Coast",
               "VN": "Vietnam", "MM": "Myanmar", "TT": "Trinidad and Tobago"}
STOP = set("""what should which where will would did does do is are has have can could go goes going next chart charts
charted spread spreads spreading head heading headed to in for with pair partner partners brand brands artist artists
launch kit market markets forecast forecasts a an of and find me tell about how far it by on at get reach reaches this
after likely be there song songs music travel travels land lands good best top who when why please give picks pick
suggest recommend s whats""".split())
COUNTRY_OK = set("""what is are heading coming arriving arrive arrives going go trending popular new this week now
next here there breaking out spreading to the in for from will be which titles shows show films netflix s whats""".split())
KIT_WORDS = re.compile(r"\b(pair|pairs|pairing|partner|partners|brand|brands|artist|artists|launch|market|marketing"
                       r"|promote|promotion|collab|collaborate|kit)\b")
SONGS_FOR = re.compile(r"\b(?:songs?|artists?|music|musicians?|tracks?|soundtrack|singers?)\s+(?:for|to go with|to pair with"
                       r"|that fit|that suit|that match|suited to)\s+(?P<show>.+)$", re.I)
SONG_CHECK = re.compile(r"^(?:(?:check|score|compare|try|test|rate)\s+)?(?P<songs>.+?\s+by\s+.+?)\s+(?:for|in)\s+(?P<show>.+)$", re.I)
HELP = ("I can answer: where a title goes next (\"Where will {title_example} go next?\"), what to pair a breakout with in a "
        "country (\"What should {kit_example} pair with in {kit_country}?\"), artists for a show (\"Find songs for Stranger "
        "Things\"), whether a song reaches a new crowd (\"Running Up That Hill by Kate Bush for Stranger Things\"), and "
        "what is heading to a country (\"What is heading to Brazil?\").")
# "Where will X go next?" and its variants: the asker clearly wants a forecast for X, even when X never charted.
WHERE_NEXT = re.compile(r"^(?:where\s+(?:will|would|could|does|is|might)\s+|where'?s\s+)(?P<title>.+?)\s+"
                        r"(?:go|going|head|heading|chart|charting|travel|traveling|travelling|spread|spreading|land)"
                        r"(?:\s+next)?\s*\??$", re.I)
SUGGEST = 3
# Words around a title in a forecast question ("plan a launch for X in Sweden", "is X a breakout"). They are stripped
# from both ends of the question, never from the middle, so "Where the Crawdads Sing" keeps its "the".
INTENT = STOP | set("""plan planning breakout breakouts breaking countries country doing hit hits trend trending popular
chart charting forecasted travelling traveling expand expands expanding market fit fits fans fan""".split())
NOT_ABOUT_A_TITLE = {"who", "why"}  # "who will win the world cup" is not a question about a title
MAX_TITLE_WORDS = 6
DID_YOU_MEAN_CUTOFF = 0.8


def _help(ctx):
    """HELP with this week's featured plan as the pairing example, so the example is always a real breakout."""
    lead = _lead(ctx)
    return HELP.format(title_example=lead[0] if lead else "Squid Game",
                       kit_example=lead[0] if lead else "Nightwatch: Demons Are Forever",
                       kit_country=lead[1] if lead else "Sweden")


def _breakout_links(ctx):
    ranked = sorted(ctx["storms"], key=lambda i: -((i["summary"].get("top_forecast") or {}).get("probability") or 0))
    return [{"label": i["summary"]["title"], "href": f"#/storm/{i['summary']['id']}"} for i in ranked[:SUGGEST]]


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
        name = names.get(code) or ALIAS_NAMES.get(code)
        if name and _norm(alias) not in table:
            table[_norm(alias)] = (code, name)
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


def _unknown_title(raw, country):
    """The title a forecast-style question is about when nothing matched: the question's words with the country phrase
    removed and intent words trimmed off both ends, as typed. None when nothing title-like is left."""
    words = raw.split()
    if not words or _norm(words[0]) in NOT_ABOUT_A_TITLE:
        return None
    if country:
        phrase = country[2]
        for start in range(len(words)):
            hit = next((n for n in range(1, 5) if start + n <= len(words)
                        and " ".join(_norm(w) for w in words[start:start + n]).strip() == phrase), None)
            if hit:
                del words[start:start + hit]
                break

    def intent(word):
        pieces = _norm(word).split()
        return bool(pieces) and all(p in INTENT for p in pieces)

    while words and intent(words[0]):
        words.pop(0)
    while words and intent(words[-1]):
        words.pop()
    name = " ".join(words).strip(" ,;:\"'")
    if not name or len(name) > MAX_FIELD or len(words) > MAX_TITLE_WORDS or not re.search(r"[A-Za-z0-9]", name):
        return None
    return name


def _did_you_mean(ctx, name):
    """{title, href} for the closest title (storm titles first, then Netflix's Top 10 index) at ratio >= 0.8, or None.
    A storm links to its page; an index title has no page of its own, so href is None."""
    key = _norm(name)
    if len(key) < 3:
        return None
    pool = {}
    for item in ctx["storms"]:
        title = item["summary"]["title"]
        for variant in dict.fromkeys([_norm(title), _norm(title.split(":")[0])]):
            pool.setdefault(variant, (title, f"#/storm/{item['summary']['id']}"))
    loaded = ctx.get("titles")
    if loaded is not None:
        for k, recs in loaded[1].items():
            pool.setdefault(k, (recs[0]["show"], None))
    close = difflib.get_close_matches(key, sorted(pool), n=1, cutoff=DID_YOU_MEAN_CUTOFF)
    if not close:
        return None
    title, href = pool[close[0]]
    return {"title": title, "href": href}


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


def _no_forecast_reason(rec):
    if rec.get("forecast_note"):
        return "it is already charting in many countries."
    if not rec.get("still_spreading"):
        return "it first charted more than a month ago, so it is past the forecast window; the history shows where it has charted."
    return "there is too little history to forecast it."


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
        why = _no_forecast_reason(rec)
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


# ---- the product itself: features, "why" questions, who it is for, small talk ----------------------------------

def _feature(name, href, text, aliases, keys, loose, link_label=None, more=(), no_country=False):
    return {"name": name, "href": href, "text": text, "aliases": aliases, "keys": set(keys.split()),
            "loose": set(loose.split()), "link_label": link_label or name, "more": more, "no_country": no_country}


# Facts here are the only numbers the product-help answers may state; they are the project's measured results.
# aliases are normalised phrases; keys are words that name the feature (enough to route on); loose words only rank.
FEATURES = {
    "overview": _feature(
        "AFTERSHOCK", "#/",
        "AFTERSHOCK forecasts which country a Netflix breakout (a title that entered a country's Top 10 while not "
        "charting elsewhere) reaches next, then plans the launch there: an AI proposes partner names for that audience "
        "and Qloo confirms or rejects each one.",
        ("what is aftershock", "what s aftershock", "what is this", "what is this site", "what is this app",
         "what is this tool", "what does aftershock do", "what does this do", "what does this site do",
         "explain aftershock", "aftershock", "tell me about aftershock", "about aftershock", "what is it"),
        "aftershock", "netflix breakout breakouts", "Home page map", more=("plan",)),
    "plan": _feature(
        "Plan a launch", "#/plan",
        "Plan a launch runs 7 visible steps: the forecast, Qloo's launch kit, AI proposals, a Qloo check of each name, "
        "cities, matching artists to cities, and the brief. It ends in a downloadable Launch Brief.",
        ("plan a launch", "plan launch", "launch plan", "launch planner", "launch brief", "plan page"),
        "brief proposals planner download pdf", "plan launch partner partners brand brands kit step steps cities artists seven"),
    "release": _feature(
        "Plan a release", "#/release",
        "Plan a release is for something that is not on Netflix: an upcoming film, series, album, comedy special or "
        "tour. Qloo ranks countries and cities by audience affinity, then suggests venues and local taste.",
        ("plan a release", "plan release", "release plan", "release planner"),
        "venue venues album comedy special podcast documentary concert gig festival",
        "release film series tour music upcoming premiere audience affinity taste local cities"),
    "artists": _feature(
        "For artists", "#/artists",
        "For artists shows an artist where their next fans are this week.",
        ("for artists", "for artist", "artists page", "artist page"),
        "musician musicians singer singers band bands", "artist artists fans"),
    "scorecard": _feature(
        "Scorecard", "#/scorecard",
        "The Scorecard has every test of the forecast, including the misses.",
        ("scorecard", "score card"),
        "scorecard misses miss wrong tests tested honest failures failed", "results right track record performance"),
    "ledger": _feature(
        "Ledger", "#/ledger",
        "The Ledger holds 3,240 forecasts that were locked before their outcomes were known. They are graded from 15 Nov.",
        ("ledger",),
        "ledger locked graded grade grading receipts predictions", "forecasts outcomes proof verify november nov"),
    "song_check": _feature(
        "Song check", "#/try",
        "Song check scores whether a song reaches a new crowd for a show: Qloo says who watches the show and who "
        "listens to each artist, then their age groups are compared. Ask it like \"Running Up That Hill by Kate Bush "
        "for Stranger Things\".",
        ("song check", "song checker", "check a song", "check songs"),
        "song songs track tracks", "check score crowd new"),
    "scout": _feature(
        "Sync Scout", "#/scout",
        "Sync Scout takes a show and asks Qloo which artists its fans like, then ranks them by how different their "
        "listeners' ages are, so you see who could bring the show a new audience.",
        ("sync scout", "scout"),
        "sync scout licensing licence license placement supervisor", "show artists music age"),
    "agent": _feature(
        "Weekly run", "#/agent",
        "Weekly run is the log of the automatic weekly job.",
        ("weekly run", "weekly job", "weekly log", "agent page", "the agent"),
        "weekly automatic automatically cron schedule scheduled job agent log", "run runs week updates update refresh often"),
    "globe": _feature(
        "Map", "#/",
        "The map on the home page shows this week's breakouts and where each is forecast to go next.",
        ("globe", "map", "world map", "the map", "the globe"),
        "globe map", "home world countries breakouts pins dots", "Home page map", no_country=True),
    "tour": _feature(
        "Guided tour", "#/",
        "The tour button replays the guided tour. Otherwise: the map on the home page shows this week's breakouts, "
        "Plan a launch builds the launch for one of them, and Plan a release does the same for your own film, "
        "series, album or comedy special.",
        ("guided tour", "take the tour", "take a tour", "give me a tour", "show me around", "walk me through",
         "walkthrough", "tutorial", "onboarding", "how do i use", "how to use", "getting started", "get started",
         "how do i start", "how does this work", "replay the tour", "start the tour", "tour button"),
        "tutorial walkthrough onboarding guided", "start use started begin help how guide", "Home page map",
        more=("plan", "release")),
    "qloo": _feature(
        "Qloo's role", "#/plan",
        "An AI alone named things Qloo could not back 71% of the time: of 1,615 names, 29% were backed, 37% were known "
        "but not placed with that audience, and 34% were not in Qloo. So the AI proposes and Qloo decides. Qloo also "
        "supplies the launch kit, the city heatmaps and the audience maps. The forecast itself uses Netflix history only.",
        ("qloo", "qloo s role", "role of qloo", "qloo role", "how does it use qloo", "how do you use qloo",
         "how is qloo used", "what does qloo do", "why qloo", "what is qloo"),
        "qloo taste affinity heatmap heatmaps", "ai gemini confirm reject partners audience audiences"),
    "forecast": _feature(
        "How the forecast works", "#/scorecard",
        "The forecast uses Netflix history only: ROC AUC 0.82 on 829 held-out breakouts. A breakout is a title that "
        "entered a country's Top 10 while not charting elsewhere.",
        ("how accurate", "accuracy", "how does the forecast work", "how does it forecast", "how do you forecast",
         "what is a breakout", "what is the forecast", "how good is the forecast", "roc auc", "auc",
         "how do you predict", "how does it predict"),
        "auc accurate accuracy model roc predict prediction algorithm held", "forecast breakout breakouts netflix history next",
        more=("ledger",)),
    "capabilities": _feature(
        "What I can answer", "#/",
        "I answer questions about this week's Netflix breakouts and where they go next, what to pair a breakout with "
        "in a country, artists for a show, whether a song reaches a new crowd, and what each page of the site does. "
        "For your own film, series, album or comedy special, ask where to release it and I will point you to Plan a release.",
        ("what can you do", "what do you do", "what can i ask", "what can i ask you", "what can this do",
         "what can aftershock do", "what can u do", "what are you", "who are you", "what can i do here", "help",
         "options", "example questions", "examples"),
        "", "", "Home page map", more=("plan", "release")),
}
QWORDS = {"what", "whats", "explain", "describe", "how", "tell", "give", "show", "define", "can", "does", "do", "is",
          "are", "walk", "take", "start", "replay", "open", "who", "wat", "wht", "where"}
SMALL_GREET = set("""hi hello hey hiya yo howdy sup thanks thank thx ty cheers bye goodbye cool nice great awesome ok okay
morning afternoon evening gm wow greetings""".split())
SMALL_FILL = set("""there you so much a lot very again aftershock bot assistant good all everyone team friend man dude
mate for the help that is it was helpful""".split())
SMALL_PHRASES = {"how are you", "how are you doing", "whats up", "what s up", "how s it going", "how is it going"}
KINDS = set("""album film movie series show special comedy tour song single ep podcast documentary book game standup stand up
music record concert gig festival band debut""".split())

RELEASE_VERB = r"(?:releas(?:e|ing)|launch(?:ing)?|premier(?:e|ing)|drop(?:ping)?|put(?:ting)?\s+out|tour(?:ing)?|debut(?:ing)?)"
FIRST_PERSON = (r"(?:i'?m|i\s+am|we'?re|we\s+are|i\s+will|i'?ll|we\s+will|i\s+want\s+to|we\s+want\s+to|i\s+plan\s+to"
                r"|we\s+plan\s+to|i\s+need\s+to|about\s+to)")
KIND_NOUN = "(?:" + "|".join(sorted((k for k in KINDS if " " not in k), key=len, reverse=True)) + ")"
ASKING = r"(?:wh\w+|which\s+\w+|what\s+\w+)"  # "where", "which countries", "what cities"
RELEASE_TRIGGERS = [
    re.compile(rf"\b{FIRST_PERSON}\s+{RELEASE_VERB}\b", re.I),  # "I'm launching X"
    re.compile(rf"\bwhere\s+(?:should|can|could|would|do|to)\s+(?:i|we)\s+{RELEASE_VERB}\b", re.I),
    re.compile(rf"\b{ASKING}\b.*\b(?:my|our)\s+(?:\w+\s+){{0,2}}{KIND_NOUN}\b", re.I),  # "where will my comedy special work"
    re.compile(rf"\b{RELEASE_VERB}\s+(?:my|our)\b", re.I),  # "release my film"
    re.compile(r"^plan\s+(?:a\s+)?release\b", re.I),
    # touring: "where should Kevin Hart tour", "plan a tour for X"; "tour" alone never means the site tour
    re.compile(r"\bwhere\b.*\b(?:tour|touring)\b", re.I),
    re.compile(r"^plan\s+(?:a\s+|the\s+|his\s+|her\s+|their\s+)?(?:world\s+|national\s+)?tour\b", re.I),
    re.compile(r"\b(?:which|what)\s+(?:countries|country|cities|city|markets?)\b.*\b(?:tour|touring)\b", re.I),
]
# The name a touring question is about, as typed; it is None for "I" and "we", which are handled by the generic path.
TOUR_SUBJECT = [
    re.compile(r"^wh\w+\s+(?:should|can|could|would|will|does|do|is)\s+(?P<n>.+?)\s+(?:go\s+on\s+tour|go\s+touring|tour|touring)\b", re.I),
    re.compile(r"^plan\s+(?:a\s+|the\s+)?(?:world\s+|national\s+)?tour\s+(?:for|of|with)\s+(?P<n>.+)$", re.I),
    re.compile(r"^(?:where\s+(?:will|would|should)\s+)?(?P<n>[^,]+?)'s\s+(?:world\s+)?tour\b", re.I),
]
COMEDY_WORDS = re.compile(r"\b(?:comedian|comedians|comic|comics|comedy|stand\s?-?\s?up|standup)\b", re.I)
MUSIC_WORDS = re.compile(r"\b(?:album|song|single|ep|music|band|concert|singer|rapper|tour|touring|gig|festival)\b", re.I)
FIRST_PERSON_WORDS = {"i", "we", "you", "it", "they"}
RELEASE_LEAD = set("for of my our called named titled new upcoming this next in to".split())
RELEASE_ARTICLES = {"a", "an", "the"}
RELEASE_TRAIL = set("""work works land lands resonate sell play perform soon abroad worldwide globally anywhere well there
year month week summer fall winter spring this next do does go over best""".split())

_TAIL = (r"(?:\s+(?:here|there|listed|shown|showing|included|anywhere"
         r"|(?:in|on|from)\s+(?:the\s+)?(?:\w+\s+)?(?:lists?|results?|app|site|page|map|globe|storms?|breakouts?|forecasts?|home\s?page)))?")
MISSING = [
    re.compile(rf"^(?:why|how\s+come)\s+(?:isn'?t|is\s+not|aren'?t|are\s+not|wasn'?t|was\s+not)\s+(?P<x>.+?){_TAIL}$", re.I),
    re.compile(rf"^(?:why|how\s+come)\s+(?:can'?t|cannot|can\s+not|couldn'?t|could\s+not|don'?t|do\s+not|won'?t)\s+"
               rf"(?:i|we|you)\s+(?:find|see|search|get|locate)\s+(?P<x>.+?){_TAIL}$", re.I),
    re.compile(r"^(?:why|how\s+come)\s+is\s+(?P<x>.+?)\s+(?:missing|absent|gone|not\s+(?:here|there|listed|shown|showing|"
               r"included|(?:on|in)\s+(?:the\s+)?\w+(?:\s+\w+)?))$", re.I),
    re.compile(r"^(?:i\s+)?(?:can'?t|cannot|couldn'?t|could\s+not|unable\s+to)\s+find\s+(?P<x>.+?)(?:\s+(?:anywhere|here|there))?$", re.I),
    re.compile(rf"^(?:i\s+)?(?:don'?t|do\s+not)\s+see\s+(?P<x>.+?){_TAIL}$", re.I),
    re.compile(r"^(?P<x>.+?)\s+(?:is|are)\s+(?:missing|not\s+(?:here|there|listed|showing|shown))$", re.I),
]
NOT_A_TITLE = {"it", "this", "that", "anything", "something", "one", "them", "things", "stuff", "what", "everything"}
WHY_BREAKING = re.compile(r"^(?:why|how\s+come)\s+(?:is|are|will|would|does|did|might|could|should)\s+(?P<x>.+?)\s+"
                          r"(?:breaking|break|going|go|goes|chart|charting|charted|heading|head|spread|spreading|travel|trending|"
                          r"trend|coming|come|reach|reaching|land|landing|popular|hit|hitting|likely|expected|tipped|predicted|"
                          r"forecast|forecasted|ranked|rank|first|next|top)\b(?P<rest>.*)$", re.I)
WHY_ANY = re.compile(r"^(?:why|how\s+come)\s+(?P<x>.+)$", re.I)
WHY_COUNTRY_OK = COUNTRY_OK | set("it so likely high next a top here there chosen picked pick first".split())
WHO_FOR = re.compile(r"\b(?:who\s+(?:is|s|are)\s+(?:this|it|aftershock|the\s+(?:product|tool|app|site))\s+for"
                     r"|who\s+(?:would|will|might|could|should|do|does|can)\s+(?:pay|buy|use|need|want|benefit)"
                     r"|who\s+(?:pays|uses|buys|needs|benefits)|who\s+(?:are|re)\s+(?:the|your|its)\s+(?:customers?|users?|clients?|audience|buyers?)"
                     r"|(?:target|ideal)\s+(?:customers?|users?|audience|market)|business\s+model|pricing"
                     r"|how\s+much\s+(?:does|is|would)\s+(?:it|this)\s+cost|(?:is|are)\s+(?:it|this)\s+free"
                     r"|who\s+is\s+this\s+built\s+for)\b")
WHO_MADE = re.compile(r"\b(?:who\s+(?:made|built|created|developed|designed|wrote|is\s+behind|s\s+behind|runs|owns)"
                      r"|who\s+are\s+(?:the\s+team|the\s+people|the\s+builders|the\s+makers)|about\s+(?:us|the\s+team)"
                      r"|the\s+team|(?:team|about)\s+page|the\s+builders)\b")
DATA_Q = re.compile(r"\b(?:privacy|cookies?|gdpr|tracking|personal\s+(?:data|information)|terms|legal|data\s+protection"
                    r"|(?:is|are)\s+my\s+(?:data|info|information|ip)|what\s+data|which\s+data|data\s+(?:do|does)\s+(?:you|it|this)"
                    r"|data\s+(?:sources?|stored|collected|retention|policy)|(?:do|does)\s+(?:you|it|this)\s+(?:store|track|collect|keep|save|log)"
                    r"|where\s+does\s+(?:the|your)\s+data\s+come|(?:what|where)\s+(?:is|are)\s+(?:the\s+)?(?:data\s+)?sources?)\b")
DATA_ANSWER = ("AFTERSHOCK has no accounts, collects no personal data and sets no cookies for tracking. Your IP address is used only in "
               "memory, to count recent live Qloo calls for the per-visitor rate limit, and it is not stored. The data comes from "
               "Netflix's public Top 10 lists, Qloo audience data (anonymous groups, cached privately and never published), "
               "Wikimedia pageviews, MusicBrainz and OpenStreetMap.")
WHO_IS = re.compile(r"^who\s+(?:is|was|are)\s+(?P<x>.+)$|^who'?s\s+(?P<y>.+)$", re.I)
FORECAST_CUE = re.compile(r"\b(?:forecast|forecasts|breakout|breakouts|chart|charts|charting|charted|spread|spreads|spreading"
                          r"|reach|reaches|travel|travels|launch|plan|pair|partner|partners|heading|countries|country|how\s+will|how\s+far)\b")
NAME_CONNECTORS = {"the", "of", "and", "de", "la", "le", "von", "van", "da", "di", "jr", "mc", "el"}
FANS_LIKE = re.compile(r"(?P<x>[^?]+?)\s+(?:fans|viewers|watchers|audience)\s+(?:in|from)\s+(?P<y>.+?)\s+"
                       r"(?:like|love|enjoy|prefer|want|buy|read|follow|stream|watch|listen|eat|play|are\s+into)\b", re.I)
FANS_LEAD = set("""what does do did would qloo think thinks say says know show tell me which are is so how about fans of
the data""".split()) - {"the"}
# The vocabulary that misspellings of feature words are repaired against ("scorcard", "ledgr").
REPAIR_WORDS = {w for f in FEATURES.values() for w in (*f["keys"], *(w for a in f["aliases"] for w in a.split())) if len(w) >= 5}


RECENT_YEARS = 5  # a breakout released longer ago than this is catalog, not a good first example


def _lead(ctx):
    """(title, country) of this week's example breakout, or None when ctx has no storms. The featured plan when there is
    one; else the likeliest storm released within RECENT_YEARS of the data week (catalog titles come last), with the
    country of its first launch-kit row or its top forecast."""
    featured = ctx.get("featured") or {}
    if featured.get("title") and featured.get("country"):
        return featured["title"], featured["country"]
    storms = ctx.get("storms") or []
    if not storms:
        return None
    try:
        data_year = int(str(ctx.get("week"))[:4])
    except (TypeError, ValueError):
        data_year = None

    def recent(item):
        year = (item["summary"].get("meta") or {}).get("year")
        return data_year is not None and isinstance(year, int) and data_year - year <= RECENT_YEARS

    ranked = sorted(storms, key=lambda i: -((i["summary"].get("top_forecast") or {}).get("probability") or 0))
    item = next((i for i in ranked if recent(i)), ranked[0])
    forecasts = item["detail"]["spillover"]["forecasts"]
    names = {f["code"]: f["name"] for f in forecasts}
    row = next((r for r in item["detail"].get("launch_kit", []) if r.get("kit") and any(r["kit"].values()) and r["code"] in names), None)
    country = names[row["code"]] if row else (forecasts[0]["name"] if forecasts else None)
    return (item["summary"]["title"], country) if country else None


def _examples(ctx):
    title, country = _lead(ctx) or ("", "Sweden")
    return ["Where will " + (title or "Squid Game") + " go next?",
            "What should " + (title or "Nightwatch: Demons Are Forever") + " pair with in " + country + "?",
            "What does Plan a launch do?"]


def _try(ctx):
    a, b, c = _examples(ctx)
    return f' Try asking "{a}", "{b}" or "{c}"'


def _guide(intent, steps, msg, links, **extra):
    """A plain-text answer (kind "help", which the page already renders) with its own links."""
    done = _done(intent, steps, {"kind": "help", "message": msg, **extra})
    done["links"] = links
    return done


def _flink(key, label=None):
    f = FEATURES[key]
    return {"label": label or f["link_label"], "href": f["href"]}


def _repair(norm):
    """Fix typos in feature words only: a token of 5+ letters that is not a feature word becomes its close feature word."""
    out = []
    for tok in norm.split():
        if len(tok) >= 5 and tok not in REPAIR_WORDS:
            close = difflib.get_close_matches(tok, sorted(REPAIR_WORDS), n=1, cutoff=0.84)
            tok = close[0] if close else tok
        out.append(tok)
    return " ".join(out)


def _since(ctx):
    return ctx["titles"][0]["since"][:4] if ctx.get("titles") else "2024"


def _small_talk(norm):
    words = norm.split()
    if norm in SMALL_PHRASES:
        return "Hi, I am doing fine, thanks."
    if not words or len(words) > 6 or not set(words) <= (SMALL_GREET | SMALL_FILL) or not set(words) & SMALL_GREET:
        return None
    if set(words) & {"thanks", "thank", "thx", "ty", "cheers"}:
        return "You are welcome."
    if set(words) & {"bye", "goodbye"}:
        return "Goodbye, come back any time."
    if set(words) & {"cool", "nice", "great", "awesome", "ok", "okay", "wow"}:
        return "Glad that helps."
    return "Hi, I am the AFTERSHOCK assistant."


def _feature_for(ctx, norm, names):
    """The FEATURES key a question asks about, or None. Longest alias wins. A bare feature name or a question-shaped
    sentence counts; a long statement that merely contains an alias ("plan a launch for X in Nepal") does not."""
    words = norm.split()
    hits = [(len(a.split()), k) for k, f in FEATURES.items() for a in f["aliases"] if _has(norm, a)]
    if not hits:
        return None
    asked = words[0] in QWORDS
    if not asked and len(words) > 4:
        return None
    if not asked and _storm_by_title(ctx["storms"], norm, [])[0]:
        return None  # a title that happens to be named like a feature word
    key = max(hits, key=lambda h: h[0])[1]
    if FEATURES[key]["no_country"] and find_country(norm, norm, names):
        return None  # "what is heading to Brazil on the map" is about Brazil
    return key


def _feature_answer(ctx, key, steps):
    f = FEATURES[key]
    topic = {"capabilities": "What the assistant can answer.", "tour": "How to use the site."}.get(key, f"Question about {f['name']}.")
    steps.append(_step("understand", None, True, topic))
    steps.append(_step("feature_help", key, True, f"Read the description of {f['name']} ({f['href']})."))
    msg = f["text"] + (_try(ctx) + "." if key == "capabilities" else "")
    links = [_flink(key)] + [_flink(k) for k in f["more"]]
    if key == "qloo":
        links += [_flink("forecast", "How the forecast works")]
    intent = {"qloo": "qloo_role", "tour": "tour", "capabilities": "capabilities", "overview": "overview"}.get(key, "feature_help")
    return _guide(intent, steps, msg, links, feature=key)


ROLE = r"(?:comedian|comic|singer|rapper|band|artist|musician|dj)"


def _strip_role(name):
    """"comedian Kevin Hart" and "Kevin Hart the comedian" name Kevin Hart; the role is read for the type instead."""
    out = re.sub(rf"^(?:the\s+)?{ROLE}\s+", "", name, flags=re.I)
    out = re.sub(rf"\s+(?:the\s+)?{ROLE}$", "", out, flags=re.I)
    return out.strip() or name


def _release_name(raw, names):
    """The title a release question names, as typed, or None when it only names a kind of thing ("my comedy special")."""
    # a touring question names the touring act ("where should Kevin Hart tour"), not what follows the verb
    subject = next((m for m in (pat.search(raw) for pat in TOUR_SUBJECT) if m), None)
    who = subject.group("n").strip(" ,;:\"'") if subject else ""
    if who and (_norm(who).split() or ["i"])[0] not in FIRST_PERSON_WORDS | {"my", "our"} and len(who) <= MAX_FIELD and len(who.split()) <= 6:
        return _strip_role(who)
    # "my" / "our" first: "release my album X" names X, and "my comedy tour" must not take "tour" as the verb
    m = re.search(r"\b(?:my|our)\s+(?P<n>.+)$", raw, re.I)
    popped = bool(m)
    m = m or re.search(rf"\b{RELEASE_VERB}\s+(?P<n>.+)$", raw, re.I)
    text = m.group("n") if m else ""
    place = re.search(r"\s+(?:in|across|around)\s+(?P<c>[A-Za-z .]+)$", text)
    if place and find_country(_norm(place.group("c")), place.group("c"), names):
        text = text[:place.start()]  # "... in Japan" says where, it is not part of the title
    words = text.split()
    while words:
        low = _norm(words[0])
        nxt = _norm(words[1]) if len(words) > 1 else ""
        if low in RELEASE_LEAD or (popped and low in KINDS) or (low in RELEASE_ARTICLES and (nxt in RELEASE_LEAD or nxt in KINDS)):
            popped = popped or low in RELEASE_LEAD or low in RELEASE_ARTICLES
            words.pop(0)
        else:
            break
    while words and _norm(words[-1]) in RELEASE_TRAIL:
        words.pop()
    name = " ".join(words).strip(" ,;:\"'")
    if not name or len(name) > MAX_FIELD or len(words) > 8 or not re.search(r"[A-Za-z0-9]", name):
        return None
    if all(w in KINDS or w in RELEASE_LEAD or w in RELEASE_TRAIL for w in _norm(name).split()):
        return None
    return name


def _release_kind(raw):
    """(kind, guessed) for the release page's type switch. Comedy words say comedy; music words (tour, album...) say music;
    a touring question with only "tour" to go on is a guess for music, and the answer admits it. (None, False) when
    nothing says."""
    if COMEDY_WORDS.search(raw):
        return "comedy", False
    if MUSIC_WORDS.search(raw):
        only_tour = not re.search(r"\b(?:album|song|single|ep|music|band|singer|rapper|concert)\b", raw, re.I)
        return "music", only_tour
    return None, False


def _release_answer(raw, steps, names):
    name = _release_name(raw, names)
    kind, guessed = _release_kind(raw.replace(name, " ")) if name else (None, False)  # a word in the title is not a signal
    about = f" about {name}" if name else ""
    steps.append(_step("understand", name, True, f"Release question{about}: this is not a Netflix breakout, so it goes to Plan a release."))
    steps.append(_step("route", "#/release", True, "Plan a release asks Qloo which countries and cities have the most audience affinity."))
    href = "#/release" + (f"?name={quote(name, safe='')}" if name else "") + (f"&kind={kind}" if kind else "")
    if not name:
        fill = " Type your title on that page."
    elif kind:
        fill = f" I have filled in {name} as {kind}." + (" That is a guess, so switch the type on that page if it is a comedy act, film or series." if guessed else "")
    else:
        fill = f" I have filled in {name} for you."
    msg = ("Plan a release is built for this. For an upcoming film, series, album, comedy special or tour, Qloo ranks countries "
           "and cities by audience affinity, then suggests venues and local taste." + fill)
    return _guide("release_plan", steps, msg, [{"label": "Plan a release" + (f" for {name}" if name else ""), "href": href}],
                  name=name)


def _missing_title(raw):
    for pat in MISSING:
        m = pat.match(raw)
        if m:
            x = m.group("x").strip(" ,;:\"'")
            if x and len(x.split()) <= MAX_TITLE_WORDS and len(x) <= MAX_FIELD and re.search(r"[A-Za-z0-9]", x) \
                    and _norm(x) not in NOT_A_TITLE:
                return x
    return None


def _missing_answer(ctx, x, steps):
    steps.append(_step("understand", x, True, f"Why {x} is not among this week's breakouts."))
    norm = _norm(x)
    item, _ = _storm_by_title(ctx["storms"], norm, [norm, norm[4:] if norm.startswith("the ") else norm])
    if item:
        t = item["summary"]["title"]
        steps.append(_step("week_storms", t, True, f"{t} is one of this week's breakouts."))
        return _guide("why_missing", steps, f"{t} is here: it is one of this week's breakouts, with a forecast of what comes next.",
                      [{"label": f"Full forecast for {t}", "href": f"#/storm/{item['summary']['id']}"}])
    rec = _history(ctx, x)
    if rec:
        places = {c for c, _ in rec["countries"]}
        last = max(w for _, w in rec["countries"])
        steps.append(_step("title_lookup", x, True, f"Found {rec['title']} in Netflix's Top 10 history since {_since(ctx)}, but not among this week's breakouts."))
        close = "" if _norm(x) in (_norm(rec["title"]), _norm(rec["show"])) else f"The closest title is {rec['title']}. "
        msg = (f"{close}{rec['title']} is in Netflix's Top 10 history (first charted {rec['first_week']}, last added a country "
               f"{last}, {len(places)} {'country' if len(places) == 1 else 'countries'} so far) but it is not one of this week's breakouts. "
               "A breakout has to start in one country while charting nowhere else; titles that launch worldwide chart everywhere "
               "at once, so there is nothing to forecast.")
        links = [{"label": f"Storm page for {rec['title']}", "href": f"#/storm/{rec['storm_id']}"}] if rec.get("storm_id") else []
        return _guide("why_missing", steps, msg, links + [{"label": "This week's storms", "href": "#/"}])
    steps.append(_step("title_lookup", x, False, f"{x} is not in Netflix's Top 10 in any country since {_since(ctx)}."))
    mean = _did_you_mean(ctx, x)
    if mean:
        steps.append(_step("did_you_mean", x, True, f"The closest title is {mean['title']}."))
    msg = (f"{x} has not been in Netflix's Top 10 in any country since {_since(ctx)}, so AFTERSHOCK has nothing on it."
           + (f" Did you mean {mean['title']}?" if mean else "")
           + " For a title on any platform, use Plan a release.")
    links = ([{"label": f"Storm page for {mean['title']}", "href": mean["href"]}] if mean and mean["href"] else [])
    return _guide("why_missing", steps, msg, links + [{"label": "Plan a release", "href": f"#/release?name={quote(x, safe='')}"}],
                  did_you_mean=mean)


def _stop(reason):
    return reason.rstrip(". ") + "."


def _why_rows(found, names):
    """(title, origin text, origin week, horizon, rows, storm id) for a resolved title; rows are empty without a forecast."""
    if found["storm"]:
        summ, detail = found["storm"]["summary"], found["storm"]["detail"]
        rows = [{"code": f["code"], "name": f["name"], "probability": f["probability"], "why": f.get("why")}
                for f in detail["spillover"]["forecasts"]]
        return (summ["title"], _origins(summ), summ["origin_week"], detail["spillover"].get("horizon_weeks"), rows, summ["id"],
                {c["code"] for c in summ["origin_countries"]})
    rec = found["history"]
    fc = rec.get("forecast") or {}
    origin = ", ".join(names.get(c, c) for c in fc.get("origin", [])) or "one country"
    rows = [{"code": n["code"], "name": n["name"], "probability": n["probability"], "why": n.get("why")} for n in fc.get("next", [])]
    return rec["title"], origin, rec["first_week"], fc.get("horizon_weeks"), rows, rec.get("storm_id"), set(fc.get("origin", []))


def _why_title_answer(found, country, steps, names):
    title, origin, week, horizon, rows, sid, origin_codes = _why_rows(found, names)
    focus = f" in {country[1]}" if country else ""
    steps.append(_step("understand", title, True, f"The reason behind the forecast for {title}{focus}."))
    links = [{"label": f"Full forecast for {title}", "href": f"#/storm/{sid}"}] if sid else []
    if not rows:
        reason = _no_forecast_reason(found["history"]) if found["history"] else "it has no forecast rows."
        steps.append(_step("forecast", title, False, f"No forecast for this title: {reason}"))
        return _guide("why_forecast", steps, f"There is no forecast for {title}, so there is nothing to explain: {reason}", links)
    row = next((r for r in rows if r["code"] == country[0]), None) if country else rows[0]
    others = ", ".join(f"{r['name']} ({pct(r['probability'])})" for r in rows[:3])
    if country and country[0] in origin_codes:
        # where it broke out is not a destination; saying "not in the forecast" would contradict the title's own origin
        steps.append(_step("forecast", title, True, f"{title} broke out in {country[1]}; read its next countries."))
        msg = (f"{title} broke out in {country[1]} (week of {week}), so that is where it started, not where it is heading. "
               f"Its likeliest next countries are {others}.")
        return _guide("why_forecast", steps, msg, links)
    if row is None:
        steps.append(_step("forecast", title, False, f"{country[1]} is not in the forecast for {title}."))
        msg = (f"{country[1]} is not in the forecast for {title}. It started in {origin} ({week}); the countries it is forecast to reach "
               f"next are {others}.")
        return _guide("why_forecast", steps, msg, links)
    rank = rows.index(row) + 1
    steps.append(_step("forecast", title, True, f"Read the forecast row for {row['name']}: {pct(row['probability'])}, number {rank} of {len(rows)}."))
    reason = _stop(f"Why: {row['why']}") if row["why"] else "No written reason is stored for this country."
    window = f" within {horizon} weeks" if horizon else ""
    msg = (f"{title} started in {origin} (week of {week}). {row['name']} has a {pct(row['probability'])} chance of being next{window}"
           f", number {rank} of {len(rows)}. {reason}")
    if rank == 1 and len(rows) > 1:
        after = ", ".join(f"{r['name']} ({pct(r['probability'])})" for r in rows[1:3])
        msg += f" After that: {after}."
    return _guide("why_forecast", steps, msg, links)


def _why_country_answer(ctx, country, steps):
    steps.append(_step("understand", country[1], True, f"Why {country[1]} is on this week's map."))
    wm = ctx["week_map"]()
    entry = next((c for c in wm["countries"] if c["code"] == country[0]), None)
    if entry is None:
        steps.append(_step("week_map", country[1], False, f"No breakout lists {country[1]} among its likeliest countries this week."))
        origin = " It is an origin country this week: breakouts start there rather than arrive." if country[0] in wm.get("origins", []) else ""
        return _guide("why_forecast", steps, f"No breakout lists {country[1]} among its likeliest countries this week.{origin}",
                      [{"label": "This week's storms", "href": "#/"}])
    steps.append(_step("week_map", country[1], True, f"Read this week's map: {country[1]} has a {pct(entry['chance'])} chance of at least one new breakout."))
    parts, links = [], []
    for t in entry.get("top", [])[:2]:
        storm = next((i for i in ctx["storms"] if i["summary"]["id"] == t["id"]), None)
        row = next((f for f in storm["detail"]["spillover"]["forecasts"] if f["code"] == country[0]), None) if storm else None
        reason = f": {_stop(row['why'])}" if row and row.get("why") else "."
        parts.append(f"{t['title']} ({pct(t['p'])}){reason}")
        links.append({"label": f"Full forecast for {t['title']}", "href": f"#/storm/{t['id']}"})
    msg = f"{country[1]} has a {pct(entry['chance'])} chance of getting at least one new breakout this week." + (
        " The strongest pull: " + " Then ".join(parts) if parts else "")
    return _guide("why_forecast", steps, msg, links or [{"label": "This week's storms", "href": "#/"}])


def _why_question(ctx, raw, names):
    """Answer "why is X breaking in Y", "why will X go to Y", "why Y", "why X"; None when it is some other "why"."""
    m = WHY_BREAKING.match(raw)
    if m:
        x, rest = m.group("x").strip(" \"'"), m.group("rest")
        country = find_country(_norm(rest), rest, names) if rest.strip() else None
        found = resolve_title(ctx, _norm(x), None)
        if found is None:
            steps = [_step("understand", x, True, f"The reason behind the forecast for {x}."),
                     _step("title_lookup", x, False, f"{x} is not in Netflix's Top 10 in any country since {_since(ctx)}.")]
            mean = _did_you_mean(ctx, x)
            return _guide("why_forecast", steps,
                          f"{x} has not been in Netflix's Top 10 in any country since {_since(ctx)}, so there is no forecast to explain."
                          + (f" Did you mean {mean['title']}?" if mean else ""),
                          [{"label": f"Storm page for {mean['title']}", "href": mean["href"]}] if mean and mean["href"] else [],
                          did_you_mean=mean)
        return _why_title_answer(found, country, [], names)
    m = WHY_ANY.match(raw)
    if not m:
        return None
    body = _norm(m.group("x"))
    storm_hit, phrase = _storm_by_title(ctx["storms"], body, [])
    country = find_country(_mask(body, phrase) if storm_hit else body, m.group("x"), names)
    if country and not [t for t in _mask(body, country[2]).split() if t not in WHY_COUNTRY_OK]:
        return _why_country_answer(ctx, country, [])
    found = resolve_title(ctx, body, country)
    return _why_title_answer(found, country, [], names) if found else None


def _name_like(raw, lower_ok):
    """True when the text reads as a person's or act's name: up to four words, no question or forecast words, and
    capitalised ("Cedric the Entertainer") unless it is one word or the asker wrote "who is ..." (lower_ok)."""
    words = raw.split()
    if not words or len(words) > 4 or not re.search(r"[A-Za-z]", raw):
        return False
    for w in words:
        n = _norm(w)
        if not n or (n in INTENT and n not in NAME_CONNECTORS) or any(ch.isdigit() for ch in n):
            return False
    if len(words) == 1 or lower_ok:
        return True
    return all(w[0].isupper() or _norm(w) in NAME_CONNECTORS for w in words)


def _unknown_name_answer(ctx, name, steps):
    """A name that is not a Netflix breakout or a Top 10 title: say what AFTERSHOCK tracks and offer Plan a release for it.
    Qloo is not called here; whether the name is a comedian, band or film is not knowable offline, so the type is a
    music default the answer says can be switched."""
    steps.append(_step("understand", name, True, f"{name} looks like a name, not a title AFTERSHOCK tracks."))
    steps.append(_step("title_lookup", name, False, f"{name} is not in Netflix's Top 10 in any country since {_since(ctx)}."))
    mean = _did_you_mean(ctx, name)
    if mean:
        steps.append(_step("did_you_mean", name, True, f"The closest title is {mean['title']}."))
    msg = (f"AFTERSHOCK tracks Netflix breakouts, and {name} is not one this week."
           + (f" Did you mean {mean['title']}?" if mean else "")
           + f" If {name} has a film, series, album, comedy special or tour coming up, Plan a release ranks countries and cities by "
             "Qloo audience affinity. I have filled in the name as music; switch the type on that page if it is a comedy act, film or series.")
    links = [{"label": f"Storm page for {mean['title']}", "href": mean["href"]}] if mean and mean["href"] else []
    links.append({"label": f"Plan a release for {name}", "href": f"#/release?name={quote(name, safe='')}&kind=music"})
    return _guide("unknown_name", steps, msg, links, name=name, did_you_mean=mean)


def _storm_loose(storms, x):
    """The storm whose title is x, x plus a subtitle ("Nightwatch" for "Nightwatch: Demons Are Forever"), or x without
    a leading "the"; None otherwise."""
    wanted = {x, x[4:] if x.startswith("the ") else x}
    hits = [i for i in storms
            if any(_norm(i["summary"]["title"]) == w or _norm(i["summary"]["title"].split(":")[0]) == w
                   or _norm(i["summary"]["title"]).startswith(w + " ") for w in wanted if w)]
    return _best_storm(hits) if hits else None


def _fans_like(ctx, raw, names):
    """"What does Qloo think Nightwatch fans in Sweden like": the launch kit for that title and country, or None when the
    question does not name both a known title and a country."""
    m = FANS_LIKE.search(raw)
    country = find_country(_norm(m.group("y")), m.group("y"), names) if m else None
    if not country:
        return None
    toks = _norm(m.group("x")).split()
    while toks and toks[0] in FANS_LEAD:
        toks.pop(0)
    x = " ".join(toks)
    storm = _storm_loose(ctx["storms"], x) if x else None
    found = {"storm": storm, "history": None, "phrase": x} if storm else (resolve_title(ctx, x, None) if x else None)
    if not found:
        return None
    title = _title_of(found)
    steps = [_step("understand", None, True, f"What {title} fans in {country[1]} like: the Qloo launch kit.")]
    if found["storm"]:
        return _done("launch_kit", steps, _kit_answer(found["storm"], country, steps))
    steps.append(_step("title_lookup", title, True, f"Found {title} in Netflix's Top 10 history, but it is not one of this week's breakouts."))
    note = f"{title} is not one of this week's breakouts, so there is no launch kit for it. Here is its Netflix history and forecast instead."
    return _done("launch_kit", steps, _title_answer(found["history"], country, steps, note=note))


def _meta(ctx, raw, norm):
    """The questions about the product rather than about one title; a done answer or None."""
    talk = _small_talk(norm)
    if talk:
        return _guide("small_talk", [_step("understand", None, True, "Small talk.")], talk + _try(ctx) + ".",
                      [_flink("plan"), _flink("release")])
    if DATA_Q.search(norm) and len(norm.split()) <= 9 and not _storm_by_title(ctx["storms"], norm, [])[0]:
        steps = [_step("understand", None, True, "Question about data and privacy."),
                 _step("data_policy", None, True, "Read the data and privacy summary.")]
        return _guide("data_privacy", steps, DATA_ANSWER, [{"label": "About and data sources", "href": "#/about"}])
    if WHO_FOR.search(norm):
        steps = [_step("understand", None, True, "Who AFTERSHOCK is for.")]
        msg = ("It is built for labels' catalogue teams, artist teams and managers, promoters and brand marketers who need to know "
               "which audience to reach next and who to partner with there. There are no customers and no prices yet.")
        return _guide("audience", steps, msg, [_flink("plan"), _flink("release")])
    if WHO_MADE.search(norm) or norm in ("about", "about aftershock team"):
        steps = [_step("understand", None, True, "Who made AFTERSHOCK.")]
        return _guide("about", steps, "AFTERSHOCK is built by Team Solstine (Zaid Ali Syed, Hasnat Shaikh, Shravni Gorde and Farhan Khan) for the Qloo hackathon. Contact: sidzaid72@gmail.com. More on the About page.", [{"label": "About the team", "href": "#/about"}])
    names = country_names(ctx["storms"], ctx.get("titles"))
    key = _feature_for(ctx, _repair(norm), names)
    if key:
        return _feature_answer(ctx, key, [])
    if any(p.search(raw) for p in RELEASE_TRIGGERS):
        return _release_answer(raw, [], names)
    x = _missing_title(raw)
    if x:
        return _missing_answer(ctx, x, [])
    if re.match(r"^(?:why|how\s+come)\b", raw, re.I):
        return _why_question(ctx, raw, names)
    return None


def _closest(norm, strong_only):
    """(score, feature key, matched words) for the feature sharing the most keywords with the question, or None.
    A naming word counts 3, a related word 1; a match needs a naming word or two related words."""
    toks = set(norm.split())
    best = None
    for key, f in FEATURES.items():
        named, related = toks & f["keys"], toks & f["loose"]
        score = 3 * len(named) + len(related)
        # one related word ("world" in "who will win the world cup") is coincidence, not a match
        if score >= (3 if strong_only else 2) and (named or not strong_only) and (best is None or score > best[0]):
            best = (score, key, sorted(named | related))
    return best


def _closest_answer(ctx, norm, best, steps):
    steps.append(_step("understand", None, False, "I could not match this to a title, a country or a song."))
    if best is None:
        steps.append(_step("title_lookup", norm, False, "No close match for the text in Netflix's Top 10 since 2024."))
        msg = ("I am not sure what you are asking. AFTERSHOCK forecasts which country a Netflix breakout reaches next and plans the "
               "launch there. I can answer questions like " + _try(ctx)[len(" Try asking "):] + ".")
        return _guide("none", steps, msg, [_flink("plan"), _flink("overview")])
    _, key, hit = best
    f = FEATURES[key]
    steps.append(_step("feature_match", ", ".join(hit), True, f"The closest feature is {f['name']} (matched: {', '.join(hit)})."))
    msg = f"I am not sure I caught that. The closest thing AFTERSHOCK does is {f['name']}. {f['text']}{_try(ctx)}."
    return _guide("closest_feature", steps, msg, [_flink(key)], feature=key)


def answer(question, ctx):
    raw = _clean(question)
    if not raw:
        return _fail("none", "The question was empty. " + _help(ctx))
    raw = raw[:MAX_QUESTION]
    norm = _norm(raw)
    if not norm:
        # Netflix's Top 10 data and Qloo list titles in Latin script, so "जब वी मेट" matches nothing
        return _fail("none", "I could not read that question. Titles are matched as Netflix lists them, in "
                             "the Latin alphabet: try \"Jab We Met\". " + _help(ctx))
    steps = []
    names = country_names(ctx["storms"], ctx.get("titles"))

    # "what do Nightwatch fans in Sweden like" is a launch-kit question even though it names no pairing word
    fans = _fans_like(ctx, raw, names)
    if fans:
        return fans

    # questions about the product itself come first: "what is the ledger" or "where should I release my album"
    # must not be read as a title, and a release question can contain "X by Y" that looks like a song check
    meta = _meta(ctx, raw.replace("’", "'").replace("‘", "'"), norm)
    if meta:
        return meta

    # a) song check: "<song> by <artist> for|in <show>"
    m = SONG_CHECK.match(raw)
    if m:
        songs, show = _parse_songs(m.group("songs")), m.group("show").strip(" \"'")
        if songs and show:
            if len(songs) > MAX_SONGS or any(len(x) > MAX_FIELD for s in songs for x in s) or len(show) > MAX_FIELD:
                return _fail("song_check", f"A song check takes 1 to {MAX_SONGS} songs, each name up to {MAX_FIELD} characters.")
            return _done("song_check", steps, _song_check(ctx, songs, show, steps))

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

    # a question that names a feature ("how do I download the brief") is not a title Netflix never charted
    if not WHERE_NEXT.match(raw):
        best = _closest(_repair(norm), strong_only=True)
        if best:
            return _closest_answer(ctx, norm, best, steps)

    # f) a forecast-style question about a title Netflix never charted: answer it as asked, suggest the nearest
    #    title, then point at this week's breakouts
    m = WHERE_NEXT.match(raw)
    name = m.group("title").strip(" \"'") if m and len(m.group("title")) <= MAX_FIELD else _unknown_title(raw, country)
    # Only text that asks for a forecast is treated as a Netflix title. A bare name ("Kevin Hart") gets the AFTERSHOCK-tracks
    # answer; anything else ("best pizza in new york") falls through to the generic help.
    if name and not (m or country or FORECAST_CUE.search(norm)):
        if _name_like(name, lower_ok=False):
            return _unknown_name_answer(ctx, name, steps)
        name = None
    if name:
        since = ctx["titles"][0]["since"][:4] if ctx.get("titles") else "2024"
        steps.append(_step("understand", None, True, f"Next countries for {name}."))
        steps.append(_step("title_lookup", name, False, f"{name} is not in Netflix's Top 10 in any country since {since}."))
        mean = _did_you_mean(ctx, name)
        if mean:
            steps.append(_step("did_you_mean", name, True, f"The closest title is {mean['title']}."))
        links = _breakout_links(ctx)
        picks = ", ".join(link["label"] for link in links)
        msg = f"{name} has not been in Netflix's Top 10 in any country since {since}, so there is no breakout to forecast."
        if mean:
            msg += f" Did you mean {mean['title']}?"
        if country:
            msg += f" For {country[1]}, ask \"What is heading to {country[1]}?\"."
        msg += " AFTERSHOCK follows titles that have just broken out on Netflix" + (f"; this week's include {picks}." if picks else ".")
        done = _done("forecast", steps, {"kind": "help", "message": msg, "did_you_mean": mean})
        done["links"] = ([{"label": f"Storm page for {mean['title']}", "href": mean["href"]}] if mean and mean["href"] else []) + links
        return done

    who = WHO_IS.match(raw)
    who_name = ((who.group("x") or who.group("y")).strip(" \"'") if who else "")
    if who_name and _name_like(who_name, lower_ok=True):
        return _unknown_name_answer(ctx, who_name, steps)

    # g) fallback: never a dead end; offer the closest feature, or an overview, with example questions
    return _closest_answer(ctx, norm, _closest(_repair(norm), strong_only=False), steps)
