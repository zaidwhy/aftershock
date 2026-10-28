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
from aftershock.qloo import QlooError, resolve

log = logging.getLogger(__name__)

MAX_NAMES_PER_DOMAIN = 5
MAX_NAME_CHARS = 120
INSIGHTS_TAKE = 50  # Qloo's maximum


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
    """{entity_id: affinity} for those of entity_ids that Qloo places with this audience; absent ones are not placed."""
    body = client.get("/v2/insights", {"filter.type": entity_type, "signal.interests.entities": title_entity_id,
                                       "signal.location.query": country_name,
                                       "filter.results.entities": ",".join(entity_ids), "take": INSIGHTS_TAKE})
    placed = {}
    for entity in body.get("results", {}).get("entities", []):
        if entity.get("entity_id"):
            placed[entity["entity_id"]] = float((entity.get("query") or {}).get("affinity") or 0.0)
    return placed


def ground(client, title_entity_id, country_name, proposals, kit=None):
    """Check `proposals` ({domain: [names]}) against Qloo for one title and country. `kit` is Qloo's own launch
    kit for the same pair ({domain: [{name, entity_id?}]}) and marks confirmed picks it also named.
    Returns {"confirmed": [{domain, name, both}], "dropped": {not_placed, not_in_qloo}} with confirmed names
    ordered by affinity within each domain, or None when nothing could be checked."""
    if not title_entity_id:
        return None
    kit = kit or {}
    confirmed, not_placed, not_in_qloo, checked = [], 0, 0, 0
    for domain, entity_type in DOMAINS.items():
        resolved = {}  # entity_id -> Qloo's name
        for name in clean_names((proposals or {}).get(domain)):
            try:
                hit = resolve(client, name, entity_type)
            except (QlooError, httpx.HTTPError) as err:
                log.warning("grounded plan: search for %s %r failed: %s", domain, name, err)
                continue
            if not hit or not hit.get("entity_id"):
                not_in_qloo += 1
                checked += 1
            elif hit["entity_id"] not in resolved:
                resolved[hit["entity_id"]] = repair_name(hit.get("name") or name)
        if not resolved:
            continue
        try:
            placed = _placed_with_audience(client, title_entity_id, country_name, entity_type, list(resolved))
        except (QlooError, httpx.HTTPError) as err:
            log.warning("grounded plan: %s check failed for %s: %s", domain, country_name, err)
            continue
        checked += len(resolved)
        not_placed += sum(1 for entity_id in resolved if entity_id not in placed)
        kit_ids = {e.get("entity_id") for e in kit.get(domain) or [] if e.get("entity_id")}
        kit_names = {name_key(e["name"]) for e in kit.get(domain) or [] if e.get("name")}
        for entity_id in sorted((i for i in resolved if i in placed), key=lambda i: -placed[i]):
            name = resolved[entity_id]
            confirmed.append({"domain": domain, "name": name,
                              "both": entity_id in kit_ids or name_key(name) in kit_names})
    if not checked:
        return None
    return {"confirmed": confirmed, "dropped": {"not_placed": not_placed, "not_in_qloo": not_in_qloo}}


def add_plans(client, storms):
    """Give every launch-kit row in `storms` a `plan` field: Gemini proposes names for all rows in a few batched
    calls, then each row is checked against Qloo. Without GEMINI_API_KEY (the weekly GitHub Action has none),
    or if Gemini fails, rows are left as they are. Returns the number of rows that got a plan."""
    if not os.environ.get("GEMINI_API_KEY"):
        log.info("no GEMINI_API_KEY: skipping the AI plan; launch kits are unchanged")
        return 0
    pairs, rows = [], {}
    for storm in storms:
        detail = storm["detail"]
        country = {f["code"]: f["name"] for f in detail["spillover"]["forecasts"]}
        kind = "film" if detail["category"].lower().startswith("film") else "TV show"
        for row in detail.get("launch_kit") or []:
            if row.get("kit") and detail.get("qloo_entity") and row["code"] in country:
                pair = {"id": len(pairs), "title": detail["title"], "kind": kind, "country": country[row["code"]]}
                pairs.append(pair)
                rows[pair["id"]] = (detail["qloo_entity"], row)
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
        plan = ground(client, entity_id, pair["country"], proposals.get(pair["id"]), row["kit"])
        if plan:
            row["plan"] = {**plan, "model": llm_kits.MODEL}
            added += 1
    log.info("AI plan: %d of %d launch-kit rows checked against Qloo", added, len(pairs))
    return added
