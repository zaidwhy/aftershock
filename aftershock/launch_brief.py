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

log = logging.getLogger(__name__)

MIN_CONFIRMED = 3  # fewer Qloo-confirmed AI picks than this and the brief uses Qloo's own kit
CITIES = 3
PICKS_PER_DOMAIN = 3
BRIEFS_PER_CALL = 15
MAX_CALLS = 6
BACKTEST_AUC = 0.817
DOMAIN_LABELS = {"artist": "Artists", "tv_show": "TV shows", "movie": "Films", "brand": "Brands"}
SUMMARY_AI = "ai, checked"
SUMMARY_TEMPLATE = "template"

# Words a checked summary may use capitalised without them being in the brief's facts.
ALLOWED_CAPS = {"the", "this", "that", "it", "its", "a", "an", "in", "for", "with", "at", "on", "to", "and", "but",
                "start", "approach", "begin", "lead", "open", "pair", "target", "expect", "focus", "launch", "because",
                "there", "here", "if", "as", "by", "from", "of", "qloo", "netflix", "ai", "gemini", "kits", "kit",
                "partners", "cities", "chance", "rank", "audience", "no", "not", "do", "avoid", "treat", "use"}
_WORD = re.compile(r"[^\W\d_][\w'.-]*", re.UNICODE)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_warned = []


def _row(detail, code):
    return next((r for r in detail.get("launch_kit") or [] if r.get("code") == code and r.get("kit")
                 and any(r["kit"].values())), None)


def _pct(p):
    pct = p * 100
    return f"{pct:.1f}%" if pct < 10 else f"{round(pct)}%"


def _join(items):
    items = list(items)
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _partners(row, use_plan):
    """By domain, up to PICKS_PER_DOMAIN picks. With a usable plan, Qloo-confirmed AI picks come first (marked when
    Qloo's own kit also named them); a domain with none falls back to Qloo's kit."""
    confirmed = ((row.get("plan") or {}).get("confirmed") or []) if use_plan else []
    out = []
    for domain, label in DOMAIN_LABELS.items():
        picks = [{"name": c["name"], "source": "ai_confirmed", "also_in_qloo_kit": bool(c.get("both"))}
                 for c in confirmed if c.get("domain") == domain][:PICKS_PER_DOMAIN]
        if not picks:
            picks = [{"name": e["name"], "source": "qloo_kit", "also_in_qloo_kit": True}
                     for e in (row["kit"].get(domain) or [])[:PICKS_PER_DOMAIN]]
        if picks:
            out.append({"domain": domain, "label": label, "picks": picks})
    return out


def template_summary(b):
    partners = [g["picks"][0]["name"] for g in b["partners"] if g["picks"]]
    where = f" Start in {_join(b['cities'])}." if b["cities"] else ""
    pair = f" Approach {_join(partners[:3])}." if partners else ""
    return (f"{b['title']} has a {b['chance_label']} chance of charting in {b['country']} within "
            f"{b['horizon_weeks']} weeks, rank {b['rank']} of {b['of_countries']}.{where}{pair}")


def brief(detail, code):
    """{"steps": [...], "brief": {...}} for one title in one forecast country, or None when the storm has no
    launch-kit row for that country. Each step is {key, title, found, decision?}."""
    code = (code or "").upper()
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
              "found": f"{title} is breaking out in {origins}; Netflix history gives {country} a {_pct(fc['probability'])} "
                       f"chance of charting it within {horizon} weeks, rank {rank} of {len(forecasts)} countries."}]

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
    use_plan = n_conf >= MIN_CONFIRMED
    if plan:
        steps.append({"key": "ai_proposals", "title": "Let an AI propose more names",
                      "found": f"{plan.get('model') or 'The model'} proposed {n_conf + not_placed + unknown} names for "
                               f"this audience in {country}."})
        check = {"key": "qloo_check", "title": "Check each AI name against Qloo",
                 "found": f"{n_conf} confirmed by Qloo for this audience, {not_placed} known to Qloo but not linked "
                          f"to this audience, {unknown} not found in Qloo."}
    else:
        steps.append({"key": "ai_proposals", "title": "Let an AI propose more names",
                      "found": f"No AI picks were made for {country} this week."})
        check = {"key": "qloo_check", "title": "Check each AI name against Qloo", "found": "There was nothing to check."}
    if not plan:
        check["decision"] = "There is no AI plan for this country, so the brief uses Qloo's own kit."
    elif not use_plan:
        check["decision"] = f"Qloo confirmed fewer than {MIN_CONFIRMED} AI picks, so the brief uses Qloo's own kit."
    elif generic:
        check["decision"] = ("The kit mostly matches the country's general taste, so the brief leans on the AI "
                             "picks Qloo confirmed.")
    else:
        check["decision"] = f"Qloo confirmed {n_conf} AI picks, so the brief puts them ahead of Qloo's own kit."
    steps.append(check)

    cities = list((row.get("hotspots") or {}).get("places") or [])[:CITIES]
    city_step = {"key": "cities", "title": "Find where the audience lives",
                 "found": (f"Qloo's audience map for this title in {country} peaks around {_join(cities)}." if cities
                           else f"Qloo returned no named places for this title in {country}.")}
    if not cities:
        city_step["decision"] = "With no named places, the brief does not suggest cities."
    steps.append(city_step)

    avoid = []
    if generic:
        avoid.append(f"Do not say this audience is distinctive in {country}: the kit mostly matches the country's "
                     "general taste.")
    avoid.append(f"Do not present the {_pct(fc['probability'])} as a promise: it is a history-only estimate.")
    if not use_plan:
        avoid.append("Do not call the partners AI-checked: this brief uses Qloo's own kit.")
    evidence = [f"The forecast uses Netflix history only; its backtest ROC AUC is {BACKTEST_AUC}.",
                "The kits have not been validated against outcomes: nothing shows these partners change viewing."]
    if use_plan:
        evidence.append("AI picks are checked only for whether Qloo links them to this audience, not for sales or views.")
    partners = _partners(row, use_plan)
    out = {"title": title, "country": country, "code": code, "storm_id": detail.get("id"), "rank": rank,
           "of_countries": len(forecasts), "chance": fc["probability"], "chance_label": _pct(fc["probability"]),
           "horizon_weeks": horizon,
           "headline": f"{title} has a {_pct(fc['probability'])} chance of charting in {country} within {horizon} "
                       f"weeks (rank {rank} of {len(forecasts)}).",
           "kit_scope": "countrywide" if generic else "title-specific",
           "partner_basis": "ai_confirmed" if use_plan else "qloo_kit",
           "cities": cities, "partners": partners, "avoid": avoid, "evidence": evidence}
    summary = row.get("brief_summary") or {}
    out["summary"] = summary.get("text") or template_summary(out)
    out["summary_source"] = summary.get("source") if summary.get("text") else SUMMARY_TEMPLATE
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
    parts = [b["title"], b["country"], b["headline"], " ".join(b["cities"]), b["kit_scope"]]
    for group in b["partners"]:
        parts.append(group["label"] + " " + " ".join(p["name"] for p in group["picks"]))
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
    partners = "; ".join(f"{g['label']}: " + ", ".join(p["name"] for p in g["picks"]) for g in b["partners"])
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
