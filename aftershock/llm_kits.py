"""The LLM side of a launch kit: ask Gemini what each title's audience in each country likes, in batches.

Shared by the pre-registered experiment (scripts/experiment_kits.py, which must keep producing the same
prompts so its cached answers still apply) and by the weekly plan (aftershock/grounded_plan.py), where the
LLM proposes names and Qloo checks them. The prompt text, batch size and model are part of the registered
experiment: change them and the cache no longer matches.
"""
import logging
import time

from aftershock.launch_kit import DOMAINS
from aftershock.llm_baseline import generate

log = logging.getLogger(__name__)

MODEL = "gemini-3.5-flash"
PAIRS_PER_CALL = 20
NAMES_PER_DOMAIN = 5

TITLE_PROMPT = """For each item below, a {kind_note} has just become popular in a country. For each item, list the 5
names in each category that THIS title's audience in THAT country particularly likes (more than the average
person there): "artist" (music artists), "tv_show", "movie", "brand". Use real, specific names only.
Return JSON: {{"results": [{{"id": <id>, "artist": [5 names], "tv_show": [5], "movie": [5], "brand": [5]}}]}}.
Items:
{items}"""


def ask(prompt, attempts=4):
    """Gemini's free tier answers 503 under load; wait and try again a few times, then give up loudly."""
    for attempt in range(attempts):
        try:
            return generate(MODEL, prompt)
        except RuntimeError as err:
            if "HTTP 503" not in str(err) and "HTTP 429" not in str(err) or attempt == attempts - 1:
                raise
            log.warning("Gemini busy (%s); retrying in %ds", str(err)[:60], 30 * (attempt + 1))
            time.sleep(30 * (attempt + 1))


def title_kits(pairs):
    """{pair id: {domain: [names]}} for pairs, each a dict with id, kind ("film" or "TV show"), title, country.
    Batches of PAIRS_PER_CALL per Gemini call; a pair the model skipped is absent."""
    kits = {}
    for start in range(0, len(pairs), PAIRS_PER_CALL):
        batch = pairs[start:start + PAIRS_PER_CALL]
        items = "\n".join(f'{p["id"]}: the {p["kind"]} "{p["title"]}" in {p["country"]}' for p in batch)
        body = ask(TITLE_PROMPT.format(kind_note="Netflix film or TV show", items=items))
        for row in body.get("results", []):
            kits[int(row["id"])] = {d: row.get(d, [])[:NAMES_PER_DOMAIN] for d in DOMAINS}
    return kits
