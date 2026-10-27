"""Run the pre-registered launch-kit experiment (docs/EXPERIMENT_KITS.md) and write
data/results/kit_experiment.json. Four arms per title-country pair: Qloo title+country (the shipped
kit), Qloo country-only, LLM title+country, LLM country-only. Metrics are overlap counts, no LLM judge.

Run: .venv/Scripts/python scripts/experiment_kits.py
"""
import json
import logging
import random
import re
import sys
import time
import unicodedata
from collections import defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import find_dotenv, load_dotenv  # noqa: E402

load_dotenv(find_dotenv(usecwd=True))
from aftershock.launch_kit import DOMAINS, country_picks  # noqa: E402
from aftershock.llm_baseline import generate, calls as llm_calls  # noqa: E402
from aftershock.qloo import Qloo, QlooError, resolve  # noqa: E402

log = logging.getLogger("experiment_kits")
STORMS = ROOT / "data" / "private" / "storms.json"
OUT = ROOT / "data" / "results" / "kit_experiment.json"
MODEL = "gemini-3.5-flash"
PAIRS_PER_CALL = 20
COUNTRIES_PER_CALL = 21
GENERIC_OVERLAP = 0.6
FLIPS, SEED = 10_000, 7
MAX_SEARCHES = 1_500

TITLE_PROMPT = """For each item below, a {kind_note} has just become popular in a country. For each item, list the 5
names in each category that THIS title's audience in THAT country particularly likes (more than the average
person there): "artist" (music artists), "tv_show", "movie", "brand". Use real, specific names only.
Return JSON: {{"results": [{{"id": <id>, "artist": [5 names], "tv_show": [5], "movie": [5], "brand": [5]}}]}}.
Items:
{items}"""

COUNTRY_PROMPT = """For each country below, list the 5 names in each category that people in that country
particularly like (more than people elsewhere): "artist" (music artists), "tv_show", "movie", "brand".
Use real, specific names only. Return JSON: {{"results": [{{"id": <id>, "artist": [5 names], "tv_show": [5],
"movie": [5], "brand": [5]}}]}}.
Countries:
{items}"""


def key(name):
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def keys(names):
    return {key(n) for n in names if key(n)}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else None


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


def load_pairs():
    storms = json.loads(STORMS.read_text(encoding="utf-8"))["storms"]
    pairs = []
    for storm in storms:
        detail = storm["detail"]
        names = {f["code"]: f["name"] for f in detail["spillover"]["forecasts"]}
        for row in detail.get("launch_kit") or []:
            if row.get("kit"):
                pairs.append({"id": len(pairs), "storm": storm["summary"]["id"], "title": detail["title"],
                              "kind": "film" if detail["category"].lower().startswith("film") else "TV show",
                              "code": row["code"], "country": names[row["code"]],
                              "Q": {d: [p["name"] for p in row["kit"].get(d, [])] for d in DOMAINS}})
    return pairs


def llm_title_kits(pairs):
    kits = {}
    for start in range(0, len(pairs), PAIRS_PER_CALL):
        batch = pairs[start:start + PAIRS_PER_CALL]
        items = "\n".join(f'{p["id"]}: the {p["kind"]} "{p["title"]}" in {p["country"]}' for p in batch)
        body = ask(TITLE_PROMPT.format(kind_note="Netflix film or TV show", items=items))
        for row in body.get("results", []):
            kits[int(row["id"])] = {d: row.get(d, [])[:5] for d in DOMAINS}
    return kits


def llm_country_kits(countries):
    kits = {}
    ordered = sorted(countries)
    for start in range(0, len(ordered), COUNTRIES_PER_CALL):
        batch = ordered[start:start + COUNTRIES_PER_CALL]
        items = "\n".join(f"{i}: {c}" for i, c in enumerate(batch, start))
        body = ask(COUNTRY_PROMPT.format(items=items))
        for row in body.get("results", []):
            kits[ordered[int(row["id"])]] = {d: row.get(d, [])[:5] for d in DOMAINS}
    return kits


def specificity(title_kit, country_kit):
    """1 - Jaccard per domain, averaged over domains where both sides answered."""
    values = [1 - jaccard(keys(title_kit[d]), keys(country_kit[d])) for d in DOMAINS
              if title_kit.get(d) and country_kit.get(d)]
    return sum(values) / len(values) if values else None


def sign_flip_p(diffs):
    rng = random.Random(SEED)
    observed = sum(diffs) / len(diffs)
    hits = sum(1 for _ in range(FLIPS)
               if sum(d if rng.random() < 0.5 else -d for d in diffs) / len(diffs) >= observed)
    return (hits + 1) / (FLIPS + 1)


def distinctness(pairs, arm):
    by_country = defaultdict(list)
    for p in pairs:
        if p.get(arm):
            by_country[p["code"]].append(p[arm])
    values = []
    for kits in by_country.values():
        for a, b in combinations(kits, 2):
            per = [1 - jaccard(keys(a[d]), keys(b[d])) for d in DOMAINS if a.get(d) and b.get(d)]
            if per:
                values.append(sum(per) / len(per))
    return (sum(values) / len(values), len(values)) if values else (None, 0)


def grounding(client, pairs):
    """Share of LLM picks that resolve to a Qloo entity of the right type by exact normalized name."""
    cache, resolved, total = {}, 0, 0
    for p in pairs:
        p["L_grounded"] = {}
        for domain, entity_type in DOMAINS.items():
            kept = []
            for name in p["L"].get(domain, []):
                k = (domain, key(name))
                if k not in cache:
                    if len(cache) >= MAX_SEARCHES:
                        continue
                    try:
                        cache[k] = resolve(client, name, entity_type) is not None
                    except QlooError:
                        continue
                total += 1
                resolved += cache[k]
                if cache[k]:
                    kept.append(name)
            p["L_grounded"][domain] = kept
    return resolved / total if total else None, total, len(cache)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    pairs = load_pairs()
    client = Qloo(call_budget=MAX_SEARCHES + 400)
    countries = {p["country"] for p in pairs}
    qc = {c: {d: country_picks(client, c, t) for d, t in DOMAINS.items()} for c in sorted(countries)}
    lt = llm_title_kits(pairs)
    lc = llm_country_kits(countries)
    for p in pairs:
        p["Qc"], p["L"], p["Lc"] = qc[p["country"]], lt.get(p["id"]), lc.get(p["country"])
    complete = [p for p in pairs if p["L"] and p["Lc"]]
    log.info("pairs %d, complete %d", len(pairs), len(complete))

    for p in complete:
        p["spec_Q"] = specificity(p["Q"], p["Qc"])
        p["spec_L"] = specificity(p["L"], p["Lc"])
    scored = [p for p in complete if p["spec_Q"] is not None and p["spec_L"] is not None]
    diffs = [p["spec_Q"] - p["spec_L"] for p in scored]
    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None  # noqa: E731

    ground_share, ground_total, searches = grounding(client, complete)
    grounded = [p for p in scored if all(p["L_grounded"].get(d) for d in DOMAINS)]
    for p in grounded:
        p["spec_Lg"] = specificity(p["L_grounded"], p["Lc"])
    gdiffs = [p["spec_Q"] - p["spec_Lg"] for p in grounded if p["spec_Lg"] is not None]

    p_qloo = sign_flip_p(diffs) if diffs else None
    p_llm = sign_flip_p([-d for d in diffs]) if diffs else None
    verdict = ("Qloo more title-specific" if p_qloo is not None and p_qloo < 0.05 else
               "LLM more title-specific" if p_llm is not None and p_llm < 0.05 else "no difference shown")
    generic = [p for p in pairs if specificity(p["Q"], qc[p["country"]]) is not None
               and specificity(p["Q"], qc[p["country"]]) <= 1 - GENERIC_OVERLAP]
    dq, nq = distinctness(complete, "Q")
    dl, nl = distinctness(complete, "L")

    result = {
        "registered": "docs/EXPERIMENT_KITS.md",
        "model": MODEL,
        "pairs": len(pairs), "complete_pairs": len(complete), "scored_pairs": len(scored),
        "title_specificity": {"qloo": mean([p["spec_Q"] for p in scored]), "llm": mean([p["spec_L"] for p in scored]),
                              "mean_diff_qloo_minus_llm": mean(diffs), "p_qloo_greater": p_qloo,
                              "p_llm_greater": p_llm, "verdict": verdict},
        "title_specificity_grounded_llm_only": {"pairs": len(gdiffs), "qloo": mean([p["spec_Q"] for p in grounded]),
                                                "llm_grounded": mean([p["spec_Lg"] for p in grounded if p["spec_Lg"] is not None]),
                                                "mean_diff": mean(gdiffs)},
        "cross_title_distinctness": {"qloo": round(dq, 3) if dq is not None else None,
                                     "llm": round(dl, 3) if dl is not None else None, "title_pairs": nq},
        "llm_grounding": {"share_resolving_in_qloo": round(ground_share, 3) if ground_share is not None else None,
                          "picks_checked": ground_total, "distinct_searches": searches},
        "generic_kits": {"rule": f"overlap with Qloo country-only kit >= {GENERIC_OVERLAP}",
                         "count": len(generic), "of": len(pairs)},
        "calls": {"qloo_live": client.live_calls, "llm_live": llm_calls["live"],
                  "llm_cached": llm_calls["cached"]},
        "per_pair": [{"storm": p["storm"], "code": p["code"], "spec_qloo": round(p["spec_Q"], 3),
                      "spec_llm": round(p["spec_L"], 3)} for p in scored],
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    generic_private = ROOT / "data" / "private" / "kit_generic.json"
    generic_private.write_text(json.dumps({f'{p["storm"]}|{p["code"]}': round(specificity(p["Q"], qc[p["country"]]), 3)
                                           for p in pairs if specificity(p["Q"], qc[p["country"]]) is not None}),
                               encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "per_pair"}, indent=2))


if __name__ == "__main__":
    main()
