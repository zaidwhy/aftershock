"""Launch kit: what a title's audience in one country over-indexes on, across Qloo domains.

SPILLOVER says where a title will chart next; the kit says what to do there. Each domain is one
`/v2/insights` call with the title as the interest signal and the country as the location.

Domains were chosen by probing 4 titles x 2 countries (data/results/launch_kit_probe.json):
- kept: artist, tv_show, movie, brand. They returned five results every time, differed between
  titles in the same country, and were sensible for the country.
- dropped: podcast (70% of results identical across different titles in one country, so it ignores
  the title), book (manga volumes and children's books for unrelated films), place (venues from other
  countries, e.g. Tokyo shops for Taiwan, Paris and Barcelona for Luxembourg).
Qloo's order within a response is the only use of affinity; values are not kept or shown.
"""
import logging
import re
import unicodedata

import httpx

from aftershock.qloo import QlooError

log = logging.getLogger(__name__)

# Output key -> Qloo entity type, in display order.
DOMAINS = {
    "artist": "urn:entity:artist",
    "tv_show": "urn:entity:tv_show",
    "movie": "urn:entity:movie",
    "brand": "urn:entity:brand",
}
PER_DOMAIN = 5
GENERIC_AT_OR_BELOW = 0.4  # specificity; overlap of 0.6 or more with the country-only kit (docs/EXPERIMENT_KITS.md)


def repair_name(name):
    """Some Qloo names arrive as UTF-8 read as Mac Roman ("Dise√±o" for "Diseño"). Reverse that only
    when the round trip yields valid UTF-8; correct names fail the round trip and come back unchanged."""
    try:
        repaired = name.encode("mac_roman").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name
    return repaired


def country_picks(client, country_name, entity_type):
    """What a whole country over-indexes on, with no title signal: the control that shows how much of a
    launch kit comes from the title and how much from the country (docs/EXPERIMENT_KITS.md)."""
    body = client.get("/v2/insights", {"filter.type": entity_type, "signal.location.query": country_name,
                                       "take": PER_DOMAIN})
    return [repair_name(e["name"]) for e in body.get("results", {}).get("entities", []) if e.get("name")][:PER_DOMAIN]


def name_key(name):
    """Lower-cased, accents and punctuation stripped, for comparing names across lists."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


def specificity(kit_names, control_names):
    """Mean over domains (both lists non-empty) of 1 - Jaccard(kit, control). None when no domain qualifies.
    kit_names and control_names map domain -> [names]. 0 means the kit is the country's taste, 1 the title's."""
    scores = []
    for domain, names in kit_names.items():
        control = control_names.get(domain) or []
        if not names or not control:
            continue
        a, b = {name_key(n) for n in names}, {name_key(n) for n in control}
        scores.append(1 - len(a & b) / len(a | b))
    return sum(scores) / len(scores) if scores else None


def domain_picks(client, entity_id, country_name, entity_type):
    """Up to PER_DOMAIN entities of one type the title's audience in a country over-indexes on."""
    body = client.get("/v2/insights", {"filter.type": entity_type, "signal.interests.entities": entity_id,
                                       "signal.location.query": country_name, "take": PER_DOMAIN})
    picks = []
    for entity in body.get("results", {}).get("entities", []):
        if not entity.get("name"):
            continue
        pick = {"name": repair_name(entity["name"])}
        if entity.get("entity_id"):
            pick["entity_id"] = entity["entity_id"]
        picks.append(pick)
        if len(picks) == PER_DOMAIN:
            break
    return picks


def launch_kit(client, entity_id, country_name, domains=DOMAINS):
    """{domain: [{name, entity_id?}, ...]} for the domains that returned something. An unresolved
    title or a failed domain call gives a smaller kit, never an error."""
    if not entity_id:
        return {}
    kit = {}
    for domain, entity_type in domains.items():
        try:
            picks = domain_picks(client, entity_id, country_name, entity_type)
        except (QlooError, httpx.HTTPError) as err:
            log.warning("launch kit %s failed for %s: %s", domain, country_name, err)
            continue
        if picks:
            kit[domain] = picks
    return kit
