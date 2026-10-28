"""Grounded plan: an LLM proposes names for a title's audience in a country, Qloo checks each one.

A pre-registered experiment (docs/EXPERIMENT_KITS.md, README section 3) found that a plain LLM gives launch
kits that are more title-specific than Qloo's own, but only 66% of its picks resolve to a Qloo entity at all.
So neither list is shown alone: the LLM supplies range, Qloo says which names it actually places with this
audience. Each proposed name gets one verdict:
- confirmed: Qloo has the entity and places it with this title's audience in this country
- not placed: Qloo knows the entity but does not place it with this audience here
- not in Qloo: no entity of that type with exactly that name (qloo.resolve's strict rule)
Per domain this is one filtered `/v2/insights` call (`filter.results.entities` restricts the answer to the
resolved ids). Affinity is used only to order confirmed names within a domain; it is never kept or shown.
Any failure gives fewer rows, never an exception.
"""
import logging
import os

import httpx

from aftershock import llm_kits
from aftershock.launch_kit import DOMAINS, name_key, repair_name
from aftershock.qloo import QlooError, norm, resolve

log = logging.getLogger(__name__)

MAX_NAMES_PER_DOMAIN = 5
MAX_NAME_CHARS = 120
INSIGHTS_TAKE = 50  # Qloo's maximum


def is_own_title(name, title):
    """True when `name` is the title itself or its franchise: the same normalized name as the title, or as the title's
    base name before ":" ("Nightwatch" for "Nightwatch: Demons Are Forever"). Naming the show for its own audience says
    nothing, so such a proposal is dropped, not checked and not counted."""
    if not title or not isinstance(name, str):
        return False
    key = norm(name, keep_subtitle=True)
    return bool(key) and key in {norm(title, keep_subtitle=True), norm(title)}


def clean_plan(plan, title):
    """A copy of a stored `plan` without names that are the title itself or its franchise, with `dropped` recounted
    from the remaining `rejected` list. A plan stored without `rejected` keeps its counts. Read-time, idempotent:
    no Qloo or model call."""
    if not plan:
        return plan
    confirmed = [c for c in plan.get("confirmed") or [] if not is_own_title(c.get("name"), title)]
    out = {**plan, "confirmed": confirmed}
    if "rejected" in plan:
        rejected = [r for r in plan["rejected"] or [] if not is_own_title(r.get("name"), title)]
        out["rejected"] = rejected
        out["dropped"] = {"not_placed": sum(r.get("verdict") == "not_placed" for r in rejected),
                          "not_in_qloo": sum(r.get("verdict") == "not_in_qloo" for r in rejected)}
    return out


def clean_rows(detail):
    """Apply `clean_plan` to every launch-kit row of a storm detail, in place; returns detail."""
    for row in detail.get("launch_kit") or []:
        if row.get("plan"):
            row["plan"] = clean_plan(row["plan"], detail.get("title"))
    return detail


def clean_names(names):
    """Up to MAX_NAMES_PER_DOMAIN distinct string names no longer than MAX_NAME_CHARS, in the given order."""
    out, seen = [], set()
    for name in names if isinstance(names, list) else []:
        if not isinstance(name, str):
            continue
        name = " ".join(name.split())
        if not name or len(name) > MAX_NAME_CHARS or name_key(name) in seen:
            continue
        seen.add(name_key(name))
        out.append(name)
        if len(out) == MAX_NAMES_PER_DOMAIN:
            break
    return out


def _placed_with_audience(client, title_entity_id, country_name, entity_type, entity_ids):
    """{entity_id: (affinity, Qloo's name)} for those of entity_ids that Qloo places with this audience; absent
    ones are not placed. The insights answer carries Qloo's canonical spelling ("JBL"), which /search can lack ("Jbl")."""
    body = client.get("/v2/insights", {"filter.type": entity_type, "signal.interests.entities": title_entity_id,
                                       "signal.location.query": country_name,
                                       "filter.results.entities": ",".join(entity_ids), "take": INSIGHTS_TAKE})
    placed = {}
    for entity in body.get("results", {}).get("entities", []):
        if entity.get("entity_id"):
            placed[entity["entity_id"]] = (float((entity.get("query") or {}).get("affinity") or 0.0),
                                           repair_name(entity["name"]) if entity.get("name") else None)
    return placed


def check_name(client, title_entity_id, country_name, domain, name):
    """The weekly plan's check for ONE typed name: resolve it by exact name in `domain`, then ask Qloo (the same
    filtered insights call as `ground`) whether it places that entity with this title's audience in this country.
    Returns {"verdict": "confirmed" | "not_placed" | "not_in_qloo", "name": the name as Qloo spells it (the typed
    name when Qloo does not know it)}. Qloo errors are raised, so the caller can say why nothing was checked."""
    entity_type = DOMAINS[domain]
    typed = " ".join(name.split())
    hit = resolve(client, typed, entity_type)
    if not hit or not hit.get("entity_id"):
        return {"verdict": "not_in_qloo", "name": typed}
    entity_id = hit["entity_id"]
    qloo_name = repair_name(hit.get("name") or typed)
    placed = _placed_with_audience(client, title_entity_id, country_name, entity_type, [entity_id])
    if entity_id in placed:
        return {"verdict": "confirmed", "name": placed[entity_id][1] or qloo_name}
    return {"verdict": "not_placed", "name": qloo_name}


def ground(client, title_entity_id, country_name, proposals, kit=None, title=None):
    """Check `proposals` ({domain: [names]}) against Qloo for one title and country. `kit` is Qloo's own launch
    kit for the same pair ({domain: [{name, entity_id?}]}) and marks confirmed picks it also named.
    Returns {"confirmed": [{domain, name, both}], "dropped": {not_placed, not_in_qloo},
    "rejected": [{domain, name, verdict}]} with confirmed names ordered by affinity within each domain, or None
    when nothing could be checked. `rejected` lists the AI's own names (not Qloo data) that did not pass, verdict
    "not_placed" or "not_in_qloo"."""
    if not title_entity_id:
        return None
    kit = kit or {}
    if title:
        proposals = {d: [n for n in clean_names(names) if not is_own_title(n, title)] for d, names in (proposals or {}).items()}
    confirmed, rejected, not_placed, not_in_qloo, checked = [], [], 0, 0, 0
    for domain, entity_type in DOMAINS.items():
        resolved = {}  # entity_id -> Qloo's name
        proposed = {}  # entity_id -> the name the AI proposed
        for name in clean_names((proposals or {}).get(domain)):
            try:
                hit = resolve(client, name, entity_type)
            except (QlooError, httpx.HTTPError) as err:
                log.warning("grounded plan: search for %s %r failed: %s", domain, name, err)
                continue
            if not hit or not hit.get("entity_id"):
                not_in_qloo += 1
                checked += 1
                rejected.append({"domain": domain, "name": name, "verdict": "not_in_qloo"})
            elif hit["entity_id"] not in resolved:
                resolved[hit["entity_id"]] = repair_name(hit.get("name") or name)
                proposed[hit["entity_id"]] = name
        if not resolved:
            continue
        try:
            placed = _placed_with_audience(client, title_entity_id, country_name, entity_type, list(resolved))
        except (QlooError, httpx.HTTPError) as err:
            log.warning("grounded plan: %s check failed for %s: %s", domain, country_name, err)
            continue
        checked += len(resolved)
        for entity_id in resolved:
            if entity_id not in placed:
                not_placed += 1
                rejected.append({"domain": domain, "name": proposed[entity_id], "verdict": "not_placed"})
        kit_ids = {e.get("entity_id") for e in kit.get(domain) or [] if e.get("entity_id")}
        kit_names = {name_key(e["name"]) for e in kit.get(domain) or [] if e.get("name")}
        for entity_id in sorted((i for i in resolved if i in placed), key=lambda i: -placed[i][0]):
            name = placed[entity_id][1] or resolved[entity_id]
            confirmed.append({"domain": domain, "name": name,
                              "both": entity_id in kit_ids or name_key(name) in kit_names})
    if not checked:
        return None
    return {"confirmed": confirmed, "dropped": {"not_placed": not_placed, "not_in_qloo": not_in_qloo},
            "rejected": rejected}


def add_plans(client, storms):
    """Give every launch-kit row in `storms` a `plan` field: Gemini proposes names for all rows in a few batched
    calls, then each row is checked against Qloo. Without GEMINI_API_KEY (the weekly GitHub Action has none),
    or if Gemini fails, rows are left as they are. Returns the number of rows that got a plan."""
    if not os.environ.get("GEMINI_API_KEY"):
        log.info("no GEMINI_API_KEY: skipping the AI plan; launch kits are unchanged")
        return 0
    pairs, rows, detail_title = [], {}, {}
    for storm in storms:
        detail = storm["detail"]
        country = {f["code"]: f["name"] for f in detail["spillover"]["forecasts"]}
        kind = "film" if detail["category"].lower().startswith("film") else "TV show"
        for row in detail.get("launch_kit") or []:
            if row.get("kit") and detail.get("qloo_entity") and row["code"] in country:
                pair = {"id": len(pairs), "title": detail["title"], "kind": kind, "country": country[row["code"]]}
                pairs.append(pair)
                rows[pair["id"]] = (detail["qloo_entity"], row)
                detail_title[pair["id"]] = detail["title"]
    if not pairs:
        return 0
    try:
        proposals = llm_kits.title_kits(pairs)
    except (RuntimeError, ValueError, KeyError, TypeError, httpx.HTTPError) as err:
        log.warning("AI plan skipped, Gemini failed: %s", err)
        return 0
    added = 0
    for pair in pairs:
        entity_id, row = rows[pair["id"]]
        plan = ground(client, entity_id, pair["country"], proposals.get(pair["id"]), row["kit"], detail_title[pair["id"]])
        if plan:
            row["plan"] = {**plan, "model": llm_kits.MODEL}
            added += 1
    log.info("AI plan: %d of %d launch-kit rows checked against Qloo", added, len(pairs))
    return added
