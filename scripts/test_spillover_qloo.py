"""Decision test: does Qloo's in-country affinity add anything to the Netflix-history baseline?

Same split as backtest_spillover.py. To bound API use, the blend is fit on the most recent
TRAIN_SAMPLE training events and scored on TEST_SAMPLE test events; both models are scored on
that same test subset. Leakage note: Qloo's current data postdates these breakouts, so a lift
here is an upper bound; the forward test on live breakouts is the real proof.
"""
import json
import logging
import random
from concurrent.futures import ThreadPoolExecutor
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from aftershock.netflix import (  # noqa: E402
    HistoryBaseline, breakout_events, first_entries, load_rows, title_categories,
)
from aftershock.qloo import Qloo, QlooError, norm  # noqa: E402
from backtest_spillover import evaluate, HORIZON, TEST_WEEKS, RAW  # noqa: E402

TRAIN_SAMPLE = 300
TEST_SAMPLE = 200
BATCH = 50
OUT = ROOT / "data" / "results" / "spillover_qloo_test.json"
log = logging.getLogger("spillover_qloo")


def resolve_title(client, event):
    entity_type = "urn:entity:movie" if event["category"].startswith("Films") else "urn:entity:tv_show"
    name = event["title"][0]
    for hit in client.search(name, types=entity_type):
        if norm(hit.get("name", "")) == norm(name):
            return hit["entity_id"]
    return None


def country_affinities(client, entity_ids, country_name):
    """Affinity of each entity in one country. Entities absent from the response get no value."""
    found = {}
    for start in range(0, len(entity_ids), BATCH):
        batch = entity_ids[start:start + BATCH]
        params = {"signal.location.query": country_name, "filter.results.entities": ",".join(batch), "take": len(batch)}
        for entity_type in ("urn:entity:tv_show", "urn:entity:movie"):
            body = client.get("/v2/insights", {"filter.type": entity_type, **params})
            for entity in body.get("results", {}).get("entities", []):
                found[entity["entity_id"]] = entity["query"]["affinity"]
    return found


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rows = load_rows(RAW)
    countries = sorted({r["country_iso2"] for r in rows})
    country_names = {r["country_iso2"]: r["country_name"] for r in rows}
    last_week = date.fromisoformat(max(r["week"] for r in rows))
    events = breakout_events(first_entries(rows), title_categories(rows), max_origin=3)
    observed_by = last_week - timedelta(weeks=HORIZON)
    cutoff = last_week - timedelta(weeks=TEST_WEEKS + HORIZON)
    train_all = [e for e in events if e["origin_week"] < cutoff]
    test_all = [e for e in events if cutoff <= e["origin_week"] <= observed_by]

    model = HistoryBaseline(horizon=HORIZON).fit(train_all, countries)
    train = sorted(train_all, key=lambda e: e["origin_week"])[-TRAIN_SAMPLE:]
    test = random.Random(7).sample(test_all, min(TEST_SAMPLE, len(test_all)))

    client = Qloo(call_budget=2500)
    entity_of = {}
    for event in train + test:
        try:
            entity_of[event["title"]] = resolve_title(client, event)
        except QlooError as err:
            log.warning("resolve failed for %s: %s", event["title"][0], err)
            entity_of[event["title"]] = None
    resolved = sorted({e for e in entity_of.values() if e})
    log.info("resolved %d of %d titles; live calls so far %d", len(resolved), len(entity_of), client.live_calls)

    # Calls take seconds each; five in flight keeps the client's 4 req/s pacing busy.
    with ThreadPoolExecutor(max_workers=5) as pool:
        affinity = dict(zip(countries, pool.map(lambda code: country_affinities(client, resolved, country_names[code]), countries)))
    log.info("affinity calls done; live calls %d; month remaining %s", client.live_calls, client.month_remaining)

    def extras_for(event):
        entity = entity_of.get(event["title"])
        values = {c: affinity[c].get(entity) for c in countries} if entity else {}
        present = [v for v in values.values() if v is not None]
        mean = sum(present) / len(present) if present else 0.0
        # Relative pull: how much more this country likes the title than the title's average country.
        return {c: {"qloo_relative": (values[c] - mean) if values.get(c) is not None else 0.0,
                    "qloo_present": 1.0 if values.get(c) is not None else 0.0} for c in countries}

    blended = HistoryBaseline(horizon=HORIZON).fit(train_all, countries)
    blended.fit_blend(train, [extras_for(e) for e in train])

    def blend_scorer(event, candidates):
        return blended.predict(event, candidates, extra=extras_for(event))

    table = [
        evaluate("history baseline", model.predict, test, countries),
        evaluate("history + Qloo", blend_scorer, test, countries),
    ]
    resolved_test = [e for e in test if entity_of.get(e["title"])]
    table_resolved = [
        evaluate("history baseline (resolved only)", model.predict, resolved_test, countries),
        evaluate("history + Qloo (resolved only)", blend_scorer, resolved_test, countries),
    ]
    print(f"test events {len(test)} (resolved {len(resolved_test)}), train blend events {len(train)}")
    print(f"{'model':36s} {'AUC':>7s} {'Brier':>8s} {'top-5':>7s}")
    for row in table + table_resolved:
        print(f"{row['model']:36s} {row['auc']:7.4f} {row['brier']:8.4f} {row['top5_precision']:7.4f}")
    print(f"blend weights: {blended.blend}")
    print(f"live calls {client.live_calls}, month remaining {client.month_remaining}")
    # How often Qloo returned an in-country value at all: the reason the blend cannot add much.
    pairs = len(resolved) * len(countries)
    present = sum(1 for c in countries for e in resolved if affinity[c].get(e) is not None)
    OUT.write_text(json.dumps({"metrics": table + table_resolved, "test_events": len(test),
                               "resolved_test": len(resolved_test), "live_calls": client.live_calls,
                               "qloo_value_coverage": {"title_country_pairs": pairs, "with_value": present,
                                                       "share": round(present / pairs, 4) if pairs else None}},
                              indent=2))


if __name__ == "__main__":
    main()
