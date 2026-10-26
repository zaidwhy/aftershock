"""Weekly forecast job: refresh Netflix data, forecast this week's breakouts, lock them in the
ledger, grade earlier forecasts, and write the files the API serves.

Run: .venv/Scripts/python scripts/run_forecasts.py [--no-refresh] [--no-qloo] [--no-lock]
"""
import argparse
import csv
import json
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aftershock import ledger  # noqa: E402
from aftershock.netflix import (  # noqa: E402
    HistoryBaseline, breakout_events, first_entries, load_rows, roc_auc, title_categories,
)
from aftershock.qloo import Qloo, QlooError, norm  # noqa: E402
from aftershock.ripple import score_placements  # noqa: E402

RAW = ROOT / "data" / "raw" / "all-weeks-countries.tsv"
NETFLIX_URL = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"
PRIVATE = ROOT / "data" / "private"
RESULTS = ROOT / "data" / "results"
LIVE_PLACEMENTS = ROOT / "data" / "placements_live.csv"
HORIZON = 4
SHOW_TOP = 15
LOCK_TOP = 10
MAX_STORMS = 40
log = logging.getLogger("run_forecasts")


def refresh_netflix():
    RAW.parent.mkdir(parents=True, exist_ok=True)
    resp = httpx.get(NETFLIX_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    if not resp.text.startswith("country_name"):
        raise RuntimeError("Netflix TSV did not have the expected header; not overwriting")
    RAW.write_text(resp.text, encoding="utf-8")
    log.info("refreshed Netflix data: %d bytes", len(resp.text))


def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", f"{title[0]} {'' if title[1] == 'N/A' else title[1]}".lower()).strip("-")[:80]


def why_text(model, event, target, names):
    parts = []
    for origin in event["origin_countries"]:
        trials, joins = model._pair_trials[origin, target], model._pair_joins[origin, target]
        if trials:
            parts.append(f"{names[target]} joined {joins} of {trials} past breakouts that started in {names[origin]}")
    return "; ".join(parts) or f"no past breakouts from these origins; uses {names[target]}'s general rate"


def resolve_title(client, event):
    entity_type = "urn:entity:movie" if event["category"].startswith("Films") else "urn:entity:tv_show"
    for hit in client.search(event["title"][0], types=entity_type):
        if norm(hit.get("name", "")) == norm(event["title"][0]):
            return hit["entity_id"]
    return None


def qloo_relative_all(client, entity_ids, countries, names):
    """{entity: {country: affinity minus the entity's mean across countries}}, one batched call
    per country and entity type (Qloo returns only entities it holds for that type)."""
    ids = ",".join(entity_ids)

    def one_country(code):
        found = []
        for entity_type in ("urn:entity:tv_show", "urn:entity:movie"):
            try:
                body = client.get("/v2/insights", {"filter.type": entity_type, "signal.location.query": names[code],
                                                   "filter.results.entities": ids, "take": len(entity_ids)})
            except QlooError as err:
                log.warning("affinity failed in %s: %s", code, err)
                continue
            found += [(e["entity_id"], e["query"]["affinity"]) for e in body.get("results", {}).get("entities", [])]
        return code, found

    by_entity = {}
    # Calls take seconds each; five in flight keeps the client's 4 req/s pacing busy.
    with ThreadPoolExecutor(max_workers=5) as pool:
        for code, found in pool.map(one_country, countries):
            for entity, value in found:
                by_entity.setdefault(entity, {})[code] = value
    relative = {}
    for entity, values in by_entity.items():
        mean = sum(values.values()) / len(values)
        relative[entity] = {c: v - mean for c, v in values.items()}
    return relative


def partners(client, entity_id, country_name):
    """Artists this title's audience in one country over-indexes on."""
    try:
        body = client.get("/v2/insights", {"filter.type": "urn:entity:artist", "signal.interests.entities": entity_id,
                                           "signal.location.query": country_name, "take": 3})
        return [e["name"] for e in body.get("results", {}).get("entities", [])]
    except QlooError as err:
        log.warning("partners failed: %s", err)
        return []


def live_placements():
    if not LIVE_PLACEMENTS.exists():
        return {}
    by_show = {}
    with LIVE_PLACEMENTS.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_show.setdefault(norm(row["show"]), []).append((row["song"], row["artist"]))
    return by_show


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def grade(rows, last_week):
    """Grade locked spillover forecasts whose horizon has passed."""
    first = first_entries(rows)
    graded, hits, pending = [], 0, 0
    for record in ledger.read():
        if record.get("kind") != "spillover":
            continue
        origin = date.fromisoformat(record["origin_week"])
        if origin + timedelta(weeks=HORIZON) > last_week:
            pending += 1
            continue
        weeks = first.get(tuple(record["title"]), {})
        joined_week = weeks.get(record["target"])
        hit = bool(joined_week and origin < date.fromisoformat(joined_week) <= origin + timedelta(weeks=HORIZON))
        hits += hit
        graded.append({"probability": record["probability"], "hit": hit})
    return graded, hits, pending


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-refresh", action="store_true")
    parser.add_argument("--no-qloo", action="store_true")
    parser.add_argument("--no-lock", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if not args.no_refresh:
        try:
            refresh_netflix()
        except (httpx.HTTPError, RuntimeError) as err:
            log.warning("Netflix refresh failed, using the cached file: %s", err)
    rows = load_rows(RAW)
    countries = sorted({r["country_iso2"] for r in rows})
    names = {r["country_iso2"]: r["country_name"] for r in rows}
    last_week = date.fromisoformat(max(r["week"] for r in rows))
    events = breakout_events(first_entries(rows), title_categories(rows), max_origin=3)
    observed = [e for e in events if e["origin_week"] <= last_week - timedelta(weeks=HORIZON)]
    storms_now = [e for e in events if e["origin_week"] == last_week][:MAX_STORMS]
    model = HistoryBaseline(horizon=HORIZON).fit(observed, countries)
    log.info("last week %s: %d breakouts this week, model fit on %d events", last_week, len(storms_now), len(observed))

    client = None if args.no_qloo else Qloo(call_budget=4000)
    placements = live_placements()
    storms, to_lock = [], []
    entity_of = {e["title"]: resolve_title(client, e) for e in storms_now} if client else {}
    known = sorted({v for v in entity_of.values() if v})
    # In-country affinity covered 1.8% of title-country pairs and added no AUC, so it is not fetched.
    affinity = {}
    for event in storms_now:
        candidates = [c for c in countries if c not in event["origin_countries"]]
        probabilities = model.predict(event, candidates)
        entity_id = entity_of.get(event["title"])
        relative = affinity.get(entity_id, {})
        ranked = sorted(candidates, key=lambda c: -probabilities[c])[:SHOW_TOP]
        forecasts = [{
            "code": c, "name": names[c], "probability": round(probabilities[c], 4),
            "history_probability": round(probabilities[c], 4),
            "qloo_relative": round(relative[c], 3) if c in relative else None,
            # Qloo's in-country affinity did not improve this forecast in the backtest
            # (scripts/test_spillover_qloo.py), so it is shown as context, not used in the probability.
            "why": why_text(model, event, c, names),
        } for c in ranked]
        ripple = None
        songs = placements.get(norm(event["title"][0]))
        if client and songs:
            try:
                ripple = score_placements(client, event["title"][0], songs[:8])
            except QlooError as err:
                log.warning("ripple failed for %s: %s", event["title"][0], err)
        partner_rows = [{"code": c, "artists": partners(client, entity_id, names[c])} for c in ranked[:3]] if entity_id else []
        storm_id = slug(event["title"])
        summary = {"id": storm_id, "title": event["title"][0], "season": None if event["title"][1] == "N/A" else event["title"][1],
                   "category": event["category"], "origin_week": str(event["origin_week"]),
                   "origin_countries": [{"code": c, "name": names[c]} for c in event["origin_countries"]],
                   "qloo_entity": entity_id, "has_ripple": bool(ripple),
                   "top_forecast": forecasts[0] if forecasts else None}
        storms.append({"summary": summary, "detail": {**summary, "spillover": {"horizon_weeks": HORIZON, "forecasts": forecasts},
                                                      "ripple": ripple, "partners": partner_rows}})
        to_lock += [{"kind": "spillover", "title": list(event["title"]), "origin_week": str(event["origin_week"]),
                     "target": f["code"], "probability": f["probability"]} for f in forecasts[:LOCK_TOP]]
        if ripple:
            to_lock += [{"kind": "ripple", "title": list(event["title"]), "origin_week": str(event["origin_week"]),
                         "target": f"{s['song']} | {s['artist']}", "score": s["score"]} for s in ripple["songs"] if s.get("score") is not None]

    already = {(tuple(r["title"]), r["origin_week"]) for r in ledger.read()}
    fresh = [f for f in to_lock if (tuple(f["title"]), f["origin_week"]) not in already]
    if fresh and not args.no_lock:
        written = ledger.append(fresh)
        lock_ids = {(tuple(w["title"]), w["origin_week"]): (w["locked_at"], w["hash"]) for w in written}
    else:
        lock_ids = {}
    for record in ledger.read():
        lock_ids.setdefault((tuple(record["title"]), record["origin_week"]), (record["locked_at"], record["hash"]))
    for storm in storms:
        key = (tuple([storm["summary"]["title"], storm["summary"]["season"] or "N/A"]), storm["summary"]["origin_week"])
        if key in lock_ids:
            storm["detail"]["spillover"]["locked_at"], storm["detail"]["spillover"]["ledger_id"] = lock_ids[key]

    graded, hits, pending = grade(rows, last_week)
    backtest = _read_json(RESULTS / "spillover_backtest.json")
    qloo_test = _read_json(RESULTS / "spillover_qloo_test.json")
    ripple_test = _read_json(RESULTS / "ripple_test.json")
    metric = lambda table, name: next((m["auc"] for m in table.get("metrics", []) if m["model"] == name), None)  # noqa: E731
    records = ledger.read()
    graded_ripple = [r for r in records if r["kind"] == "ripple"]
    scorecard = {
        "spillover": {"locked": sum(1 for r in records if r["kind"] == "spillover"), "graded": len(graded),
                      "hits": hits, "pending": pending,
                      "auc": roc_auc([g["probability"] for g in graded], [int(g["hit"]) for g in graded])
                      if graded and 0 < hits < len(graded) else None,
                      "baseline_auc": None},
        "ripple": {"locked": len(graded_ripple), "graded": 0, "spearman": None, "baseline_spearman": None},
        "backtest": {
            "spillover": {"history_auc": metric(backtest, "history baseline"),
                          "qloo_auc": metric(qloo_test, "history + Qloo"),
                          "history_auc_same_subset": metric(qloo_test, "history baseline")},
            "ripple": {"n": ripple_test.get("n", 0), "spearman": ripple_test.get("spearman"),
                       "baseline_spearman": ripple_test.get("baseline_spearman")},
        },
        "ledger_url": "https://github.com/zaidwhy/aftershock/blob/main/ledger/forecasts.jsonl",
        "ledger_intact": ledger.verify() is None,
        "data_week": str(last_week),
    }
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (PRIVATE / "storms.json").write_text(json.dumps({"week": str(last_week), "storms": storms}, indent=1), encoding="utf-8")
    (PRIVATE / "scorecard.json").write_text(json.dumps(scorecard, indent=1), encoding="utf-8")
    log.info("wrote %d storms; locked %d new forecasts; graded %d (hits %d); qloo live calls %s",
             len(storms), len(fresh) if not args.no_lock else 0, len(graded), hits, client.live_calls if client else 0)


if __name__ == "__main__":
    main()
