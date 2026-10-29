"""Launch brief: the visible steps an agent takes from a forecast to a plan for one title in one country.

Everything here is deterministic and reads one storm detail (the JSON the weekly run writes): no model call and no
Qloo call at request time. The weekly run adds one optional field per kit row, `brief_summary`, a two-sentence
summary that Gemini writes from the brief's own facts and that is checked here against those facts (every name and
number must appear in them); otherwise a template sentence is used. `attach` puts the finished brief on each row.
"""
import json
import logging
import os
import re

from aftershock import llm_kits
from aftershock.grounded_plan import clean_rows
from aftershock.launch_kit import name_key

log = logging.getLogger(__name__)

MIN_CONFIRMED = 3  # fewer Qloo-confirmed AI picks than this and the brief uses Qloo's own kit
KIT_FIRST_SPECIFICITY = 0.6  # a kit at least this different from the country's taste leads the partners
KIT_LEAD_DOMAINS = ("tv_show", "movie", "artist")  # the data line names the first of these in Qloo's order
# Platforms every audience uses: naming one as a partner to approach says nothing about this title's viewers, and a
# local ad or label move built around one is not actionable. Dropped from brand partners and moves.
PLATFORM_BRANDS = {"Spotify", "Netflix", "YouTube", "Apple Music", "Amazon Prime Video", "Disney+", "TikTok",
                   "Instagram", "Facebook", "Google", "Amazon"}
CITIES = 3
PICKS_PER_DOMAIN = 3
BRIEFS_PER_CALL = 15
MAX_CALLS = 6
BACKTEST_AUC = 0.817
# data/results/lead_time.json: of the 131 top-3 picks that charted in the backtest, 117 did so one week after the breakout week.
LEAD_CHARTED, LEAD_ONE_WEEK = 131, 117
# data/results/spillover_backtest.json: 758 of 76,760 held-out country-breakout pairs charted within the horizon, so a
# bare "14%" reads as weak unless it is set against the roughly 1% a typical country gets.
BASE_CHARTED, BASE_PAIRS = 758, 76760
DOMAIN_LABELS = {"artist": "Artists", "tv_show": "TV shows", "movie": "Films", "brand": "Brands"}
# Artists and brands are who you approach; shows and films say what the audience watches (creative and ad targeting).
PARTNER_DOMAINS = ("artist", "brand")
SUMMARY_AI = "ai, checked"
SUMMARY_TEMPLATE = "template"

# Words a checked summary may use capitalised without them being in the brief's facts.
ALLOWED_CAPS = {"the", "this", "that", "it", "its", "a", "an", "in", "for", "with", "at", "on", "to", "and", "but",
                "start", "approach", "begin", "lead", "open", "pair", "target", "expect", "focus", "launch", "because",
                "there", "here", "if", "as", "by", "from", "of", "qloo", "netflix", "ai", "gemini", "kits", "kit",
                "partners", "cities", "chance", "rank", "audience", "second", "third", "most", "likely", "no", "not", "do", "avoid", "treat", "use"}
_WORD = re.compile(r"[^\W\d_][\w'.-]*", re.UNICODE)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_warned = []


def _row(detail, code):
    return next((r for r in detail.get("launch_kit") or [] if r.get("code") == code and r.get("kit")
                 and any(r["kit"].values())), None)


def scale_line(probability):
    """The chance set against the backtest's base rate, or None when it is not at least twice that rate."""
    base = BASE_CHARTED / BASE_PAIRS
    if probability < 2 * base:
        return None
    return (f"For scale: a typical country charts a given breakout about {_pct(base)} of the time "
            f"({BASE_CHARTED:,} of {BASE_PAIRS:,} held-out country-breakout pairs), so {_pct(probability)} is about "
            f"{round(probability / base)} times that.")


def _pct(p):
    pct = p * 100
    return f"{pct:.1f}%" if pct < 10 else f"{round(pct)}%"


def _join(items):
    items = list(items)
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def uses_plan(row):
    """True when the brief's partners lead with Qloo-confirmed AI picks (at least MIN_CONFIRMED were confirmed)."""
    return len(((row.get("plan") or {}).get("confirmed")) or []) >= MIN_CONFIRMED


def kit_first(row):
    """True when the kit row is title-specific (not countrywide, specificity at least KIT_FIRST_SPECIFICITY) and has
    names: then Qloo's own kit leads the partners and AI-confirmed names follow."""
    spec = row.get("specificity")
    return (not row.get("generic") and spec is not None and spec >= KIT_FIRST_SPECIFICITY
            and any((row.get("kit") or {}).values()))


def kit_lead(row):
    """"Qloo's kit for this audience is led by A, B and C." from the first three TV shows, films or artists in
    Qloo's order (shows first); None when the kit is not led by title-specific names."""
    if not kit_first(row):
        return None
    names = [e["name"] for d in KIT_LEAD_DOMAINS for e in (row["kit"].get(d) or []) if e.get("name")][:3]
    return f"Qloo's kit for this audience is led by {_join(names)}." if names else None


_PLATFORM_KEYS = {name_key(n) for n in PLATFORM_BRANDS}


def _is_platform(name):
    return name_key(name) in _PLATFORM_KEYS


def partner_artists(row):
    """The brief's artist partners for a kit row, in brief order: [{name, source, also_in_qloo_kit}], at most
    PICKS_PER_DOMAIN. Live events reuses this so the artists checked are the artists the brief names."""
    group = next((g for g in _partners(row, uses_plan(row)) if g["domain"] == "artist"), None)
    return group["picks"] if group else []


def partner_names(row, domain, n):
    """The first n partner names of one domain, in the order the brief shows them (the home example uses this so
    home and brief agree)."""
    group = next((g for g in _partners(row, uses_plan(row)) if g["domain"] == domain), None)
    return [p["name"] for p in group["picks"]][:n] if group else []


def _partners(row, use_plan):
    """By domain, up to PICKS_PER_DOMAIN picks (platform brands never). A title-specific kit (`kit_first`) leads with
    Qloo's own kit, then the AI picks Qloo confirmed that the kit did not already name, up to PICKS_PER_DOMAIN more.
    Otherwise, with a usable plan, Qloo-confirmed AI picks come first (marked when Qloo's own kit also named them) and
    a domain with none falls back to Qloo's kit."""
    confirmed = ((row.get("plan") or {}).get("confirmed") or []) if use_plan else []
    lead_kit = kit_first(row)
    out = []
    for domain, label in DOMAIN_LABELS.items():
        keep = (lambda n: not _is_platform(n)) if domain == "brand" else (lambda n: True)
        kit_picks = [{"name": e["name"], "source": "qloo_kit", "also_in_qloo_kit": True}
                     for e in (row["kit"].get(domain) or []) if keep(e["name"])]
        ai_picks = [{"name": c["name"], "source": "ai_confirmed", "also_in_qloo_kit": bool(c.get("both"))}
                    for c in confirmed if c.get("domain") == domain and keep(c["name"])]
        if lead_kit and kit_picks:
            seen = {name_key(p["name"]) for p in kit_picks[:PICKS_PER_DOMAIN]}
            picks = kit_picks[:PICKS_PER_DOMAIN] + [p for p in ai_picks if name_key(p["name"]) not in seen][:PICKS_PER_DOMAIN]
        else:
            picks = ai_picks[:PICKS_PER_DOMAIN] or kit_picks[:PICKS_PER_DOMAIN]
        if picks:
            out.append({"domain": domain, "label": label, "picks": picks,
                        "group": "partner" if domain in PARTNER_DOMAINS else "watches"})
    return out


# A bare "14%" reads as weak; the rank says what it means: of all countries, this is where it is second likeliest to go.
_ORDINAL = {1: "", 2: "second ", 3: "third ", 4: "fourth ", 5: "fifth "}


def rank_phrase(rank, of_countries):
    """'the most likely', 'the second most likely', ... next country; past fifth, 'number 7 of 15'."""
    if rank in _ORDINAL:
        return f"the {_ORDINAL[rank]}most likely next country (of {of_countries})"
    return f"number {rank} of {of_countries} likely next countries"


def template_summary(b):
    partners = [g["picks"][0]["name"] for g in b["partners"] if g["picks"] and g.get("group") == "partner"]
    where = f" Start in {_join(b['cities'])}." if b["cities"] else ""
    pair = f" Approach {_join(partners[:3])}." if partners else ""
    return (f"{b['country']} is {rank_phrase(b['rank'], b['of_countries'])} for {b['title']}: a {b['chance_label']} "
            f"chance of charting within {b['horizon_weeks']} weeks.{where}{pair}")


def _moves(title, country, chance_label, horizon, cities, partners, event_ideas, lead_kit=False):
    """One move per buyer, each doable within about a week, built only from the brief's own facts: [{buyer, text}].
    A move is left out when its facts do not exist (no brand move without a Qloo-confirmed brand, no artist move
    without an activation idea, no cities means no label, artist or brand move). Wording states steps, never outcomes."""
    moves = []
    artists = next((g["picks"] for g in partners if g["domain"] == "artist"), [])
    if event_ideas:
        idea = event_ideas[0]
        label_artist, label_cities = idea["artist"], idea["cities"]
    elif artists and cities:
        label_artist, label_cities = artists[0]["name"], cities
    else:
        label_artist = label_cities = None
    if label_artist:
        moves.append({"buyer": "Label", "text": f"Push {label_artist}'s catalogue to listeners in {_join(label_cities)} "
                      f"this week; Qloo links them to {title}'s viewers in {country}."})
    if event_ideas:
        idea = event_ideas[0]
        moves.append({"buyer": "Artist", "text": f"{idea['artist']}: a post, a DJ set or a playlist push aimed at "
                      f"{_join(idea['cities'])} this week, while {title} is charting; Qloo's maps show your audience "
                      "and this title's overlap there."})
    brands = next((g["picks"] for g in partners if g["domain"] == "brand"), [])
    brand = next((p["name"] for p in brands if p["source"] == "ai_confirmed" or lead_kit), None)
    if brand and cities:
        moves.append({"buyer": "Brand marketer", "text": f"Run local ads in {_join(cities)} next to {title} while it "
                      f"charts; Qloo's data for this audience {'lists' if lead_kit else 'confirms'} {brand}."})
    moves.append({"buyer": "Distributor", "text": f"Prepare {country} promotion "
                  f"now: {chance_label} chance it charts there within {horizon} weeks; in our backtest, {LEAD_ONE_WEEK} of "
                  f"the {LEAD_CHARTED} forecast picks that charted did so one week after the breakout week."})
    return moves


def brief(detail, code):
    """{"steps": [...], "brief": {...}} for one title in one forecast country, or None when the storm has no
    launch-kit row for that country. Each step is {key, title, found, decision?}."""
    code = (code or "").upper()
    clean_rows(detail)
    row = _row(detail, code)
    forecasts = detail.get("spillover", {}).get("forecasts") or []
    fc = next((f for f in forecasts if f["code"] == code), None)
    if not row or not fc:
        return None
    title, country = detail["title"], fc["name"]
    horizon = detail["spillover"].get("horizon_weeks", 4)
    rank = forecasts.index(fc) + 1
    origins = _join([o["name"] for o in detail.get("origin_countries") or []]) or "its home markets"
    steps = [{"key": "forecast", "title": "Forecast where it goes next",
              "found": f"{title} is breaking out in {origins}; Netflix history makes {country} "
                       f"{rank_phrase(rank, len(forecasts))}, with a {_pct(fc['probability'])} chance of charting "
                       f"it within {horizon} weeks.",
              "note": "The country ranking comes from where past breakouts from the same origin spread (Netflix "
                          "history only), so titles from the same origin get similar rankings. Qloo is what makes "
                          "the plan specific to this title."}]

    kit = row["kit"]
    names = sum(len(v) for v in kit.values())
    domains = sum(1 for v in kit.values() if v)
    generic, spec = bool(row.get("generic")), row.get("specificity")
    spec_text = "" if spec is None else f" ({round(spec * 100)}% different from what the whole country likes)"
    if generic:
        found = (f"Qloo lists {names} names across {domains} domains for this audience in {country}, but the list "
                 f"mostly matches what people there like in general{spec_text}: a countrywide kit.")
    else:
        found = (f"Qloo lists {names} names across {domains} domains that this title's audience in {country} "
                 f"over-indexes on, and the list differs from the country's general taste{spec_text}: a title-specific kit.")
    kit_step = {"key": "qloo_kit", "title": "Ask Qloo what this audience likes", "found": found}
    if generic:
        kit_step["decision"] = "A countrywide kit cannot show this title is special here, so the brief says so."
    steps.append(kit_step)

    plan = row.get("plan")
    confirmed = (plan or {}).get("confirmed") or []
    dropped = (plan or {}).get("dropped") or {}
    n_conf, not_placed, unknown = len(confirmed), dropped.get("not_placed", 0), dropped.get("not_in_qloo", 0)
    use_plan = uses_plan(row)
    if plan:
        steps.append({"key": "ai_proposals", "title": "Let an AI propose more names",
                      "found": f"{plan.get('model') or 'The model'} proposed {n_conf + not_placed + unknown} names for "
                               f"this audience in {country}."})
        check = {"key": "qloo_check", "title": "Check each AI name against Qloo",
                 "found": f"{n_conf} confirmed by Qloo for this audience, {not_placed} known to Qloo but not among "
                          f"its picks for these viewers here, {unknown} with no Qloo data yet."}
    else:
        steps.append({"key": "ai_proposals", "title": "Let an AI propose more names",
                      "found": f"No AI picks were made for {country} this week."})
        check = {"key": "qloo_check", "title": "Check each AI name against Qloo", "found": "There was nothing to check."}
    if (plan or {}).get("rejected"):
        check["rejected"] = [dict(r) for r in plan["rejected"]]
    if not plan:
        check["decision"] = "There is no AI plan for this country, so the brief uses Qloo's own kit."
    elif not use_plan:
        check["decision"] = f"Qloo confirmed fewer than {MIN_CONFIRMED} AI picks, so the brief uses Qloo's own kit."
    elif kit_first(row):
        check["decision"] = (f"Qloo's own kit is {round(spec * 100)}% different from the country's general taste, so the "
                             f"brief leads with it; the {n_conf} AI picks Qloo confirmed follow as extra names.")
    elif generic:
        check["decision"] = ("The kit mostly matches the country's general taste, so the brief leans on the AI "
                             "picks Qloo confirmed.")
    else:
        check["decision"] = (f"Qloo confirmed {n_conf} AI picks and the kit is not clearly title-specific "
                             f"(under {round(KIT_FIRST_SPECIFICITY * 100)}% different from the country's taste), so the "
                             "brief puts the AI picks ahead of Qloo's own kit.")
    steps.append(check)

    cities = list((row.get("hotspots") or {}).get("places") or [])[:CITIES]
    city_step = {"key": "cities", "title": "Find where the audience lives",
                 "found": (f"Qloo's audience map for this title in {country} peaks around {_join(cities)}." if cities
                           else f"Qloo returned no named places for this title in {country}.")}
    if not cities:
        city_step["decision"] = "With no named places, the brief does not suggest cities."
    steps.append(city_step)

    events = [e for e in row.get("events") or [] if e.get("artist") and e.get("cities")]
    checked = row.get("events_checked") or 0
    event_cities = list(dict.fromkeys(c for e in events for c in e["cities"]))
    event_step = {"key": "events", "title": "Match artists to cities for quick activations"}
    if events:
        event_step["found"] = (f"Qloo's audience maps for {checked} {'artist' if checked == 1 else 'artists'} overlap this "
                               f"title's audience in {len(event_cities)} {'city' if len(event_cities) == 1 else 'cities'}.")
    else:
        event_step["found"] = (f"Qloo's audience maps for {checked} {'artist' if checked == 1 else 'artists'} were "
                               "compared with this title's audience." if checked else
                               "No artist audience maps were compared with this title's audience.")
        event_step["decision"] = "No artist's audience overlaps the title's cities, so the brief lists no quick-turn activation idea."
    steps.append(event_step)

    avoid = []
    if generic:
        avoid.append(f"Do not say this audience is distinctive in {country}: the kit mostly matches the country's "
                     "general taste.")
    avoid.append(f"Do not present the {_pct(fc['probability'])} as a promise: it is a history-only estimate.")
    avoid.append("This week's moves are steps that fit in a week, not predictions that they will work.")
    if not use_plan:
        avoid.append("Do not call the partners AI-checked: this brief uses Qloo's own kit.")
    if events:
        avoid.append("Activation ideas are where audiences overlap, not ticket-demand forecasts.")
    evidence = [f"The forecast uses Netflix history only; its backtest ROC AUC is {BACKTEST_AUC}.",
                "The kits have not been validated against outcomes: nothing shows these partners change viewing."]
    if use_plan:
        evidence.append("AI picks are checked only for whether Qloo links them to this audience, not for sales or views.")
    partners = _partners(row, use_plan)
    lead = kit_first(row)
    out = {"title": title, "country": country, "code": code, "storm_id": detail.get("id"), "rank": rank,
           "of_countries": len(forecasts), "chance": fc["probability"], "chance_label": _pct(fc["probability"]),
           "horizon_weeks": horizon,
           "headline": f"{country} is {rank_phrase(rank, len(forecasts))} for {title}: a {_pct(fc['probability'])} "
                       f"chance of charting within {horizon} weeks.",
           "scale": scale_line(fc["probability"]),
           "kit_scope": "countrywide" if generic else "title-specific",
           "partner_basis": "qloo_kit_first" if lead and use_plan else "ai_confirmed" if use_plan else "qloo_kit",
           "kit_lead": kit_lead(row),
           "window": (f"Window: about one week ({LEAD_ONE_WEEK} of the {LEAD_CHARTED} forecast countries that charted "
                      "did so one week after the breakout)"),
           "cities": cities, "partners": partners,
           "event_ideas": [{"artist": e["artist"], "cities": list(e["cities"]),
                            "text": f"{e['artist']} in {_join(e['cities'])}: both audiences concentrate there."}
                           for e in events],
           "avoid": avoid, "evidence": evidence}
    out["moves"] = _moves(title, country, out["chance_label"], horizon, cities, partners, out["event_ideas"], lead)
    summary = row.get("brief_summary") or {}
    # A stored AI summary was checked against the facts of the run that wrote it; one that no longer fits today's
    # partner order (for instance it names a platform brand now dropped) gives way to the template.
    stored = summary.get("text") if validate_summary(summary.get("text"), out) else None
    out["summary"] = stored or template_summary(out)
    out["summary_source"] = summary.get("source") if stored else SUMMARY_TEMPLATE
    steps.append({"key": "brief", "title": "Assemble the brief",
                  "found": f"Brief ready: {len(partners)} partner groups, {len(cities)} cities, "
                           f"{len(avoid)} {'caveat' if len(avoid) == 1 else 'caveats'} on what not to claim."})
    return {"steps": steps, "brief": out}


def attach(detail):
    """Give every kit row that can have one a `brief` field (in place); returns detail."""
    for row in detail.get("launch_kit") or []:
        try:
            made = brief(detail, row.get("code"))
        except (KeyError, TypeError, IndexError, ValueError) as err:  # a malformed older archive row has no brief
            log.warning("no launch brief for %s %s: %s", detail.get("id"), row.get("code"), err)
            continue
        if made:
            row["brief"] = made
    return detail


def _facts_text(b):
    parts = [b["title"], b["country"], b["headline"], " ".join(b["cities"]), b["kit_scope"], b.get("kit_lead") or ""]
    for group in b["partners"]:
        parts.append(group["label"] + " " + " ".join(p["name"] for p in group["picks"]))
    parts += [e["text"] for e in b.get("event_ideas") or []]
    parts += b["avoid"] + b["evidence"]
    parts.append(f"{b['rank']} of {b['of_countries']} {b['chance_label']} {b['horizon_weeks']} weeks")
    return " ".join(parts)


def validate_summary(text, b):
    """True when `text` is a short summary whose every capitalised word appears in the brief's facts (or is a plain
    sentence opener from ALLOWED_CAPS) and whose every number appears in the facts."""
    if not isinstance(text, str) or not text.strip() or len(text) > 600:
        return False
    facts = _facts_text(b)
    known = {w.casefold().strip(".'-") for w in _WORD.findall(facts)}
    for word in _WORD.findall(text):
        if word[0].isupper() and word.casefold().strip(".'-") not in known | ALLOWED_CAPS:
            return False
    return set(_NUMBER.findall(text)) <= set(_NUMBER.findall(facts))


PROMPT = """Write a two-sentence summary for each launch brief below. Use ONLY the facts given: no other names, places,
numbers or claims. Sentence one: the title, the country and the chance. Sentence two: where to start and who to
approach. Plain words, no hype.
Return JSON: {{"summaries": [{{"id": <id>, "summary": "<two sentences>"}}]}}.
Briefs:
{items}"""


def _prompt_line(i, b):
    partners = "; ".join(f"{g['label']}: " + ", ".join(p["name"] for p in g["picks"]) for g in b["partners"]
                         if g.get("group") == "partner")
    return json.dumps({"id": i, "title": b["title"], "country": b["country"], "chance": b["chance_label"],
                       "rank": f"{b['rank']} of {b['of_countries']}", "weeks": b["horizon_weeks"],
                       "cities": b["cities"], "partners": partners, "kit": b["kit_scope"]}, ensure_ascii=False)


def add_summaries(storms):
    """Set `brief_summary` {text, source} on every kit row in `storms` ([{detail}]). Gemini writes the summaries in
    batches of BRIEFS_PER_CALL (at most MAX_CALLS calls); each is validated against the brief's own facts and the
    template is used when it fails, when the model is unreachable, or without GEMINI_API_KEY. Returns the number of
    rows whose summary came from the model."""
    todo = []
    for storm in storms:
        detail = storm["detail"]
        for row in detail.get("launch_kit") or []:
            row.pop("brief_summary", None)
            row.pop("brief", None)
            made = brief(detail, row.get("code"))
            if made:
                todo.append((row, made["brief"]))
    if not todo:
        return 0
    if not os.environ.get("GEMINI_API_KEY"):
        if not _warned:
            log.info("no GEMINI_API_KEY: launch brief summaries use the template")
            _warned.append(True)
        return 0
    accepted = 0
    for call, start in enumerate(range(0, len(todo), BRIEFS_PER_CALL)):
        if call >= MAX_CALLS:
            log.info("launch brief summaries: call cap reached, %d briefs keep the template", len(todo) - start)
            break
        batch = todo[start:start + BRIEFS_PER_CALL]
        lines = "\n".join(_prompt_line(i, b) for i, (_, b) in enumerate(batch))
        try:
            body = llm_kits.ask(PROMPT.format(items=lines))
            written = {int(r["id"]): r["summary"] for r in body.get("summaries", [])}
        except Exception as err:  # noqa: BLE001 - any failure means the template stays
            log.warning("launch brief summaries skipped for a batch, Gemini failed: %s", err)
            continue
        for i, (row, b) in enumerate(batch):
            text = written.get(i)
            if validate_summary(text, b):
                row["brief_summary"] = {"text": " ".join(text.split()), "source": SUMMARY_AI}
                accepted += 1
    log.info("launch brief summaries: %d of %d written by AI and checked", accepted, len(todo))
    return accepted
