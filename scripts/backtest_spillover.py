"""Backtest the history-only spillover baseline against two dumb baselines."""
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aftershock.netflix import (  # noqa: E402
    HistoryBaseline, breakout_events, first_entries, joined, load_rows, roc_auc, title_categories,
)

HORIZON = 4
TEST_WEEKS = 26
TOP_K = 5
RAW = ROOT / "data" / "raw" / "all-weeks-countries.tsv"
OUT = ROOT / "data" / "results" / "spillover_backtest.json"


def evaluate(name, scorer, test_events, countries):
    scores, labels, top_hits = [], [], []
    for event in test_events:
        candidates = [c for c in countries if c not in event["origin_countries"]]
        probabilities = scorer(event, candidates)
        scores += [probabilities[c] for c in candidates]
        labels += [1 if joined(event, c, HORIZON) else 0 for c in candidates]
        # Ties break alphabetically so the uniform baseline is deterministic.
        ranked = sorted(candidates, key=lambda c: (-probabilities[c], c))[:TOP_K]
        top_hits.append(sum(joined(event, c, HORIZON) for c in ranked) / TOP_K)
    brier = sum((s - y) ** 2 for s, y in zip(scores, labels)) / len(labels)
    return {
        "model": name,
        "auc": roc_auc(scores, labels),
        "brier": brier,
        "top5_precision": sum(top_hits) / len(top_hits),
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rows = load_rows(RAW)
    countries = sorted({r["country_iso2"] for r in rows})
    last_week = date.fromisoformat(max(r["week"] for r in rows))
    events = breakout_events(first_entries(rows), title_categories(rows), max_origin=3)

    observed_by = last_week - timedelta(weeks=HORIZON)
    cutoff = last_week - timedelta(weeks=TEST_WEEKS + HORIZON)
    train = [e for e in events if e["origin_week"] < cutoff]
    test = [e for e in events if cutoff <= e["origin_week"] <= observed_by]
    pending = sorted((e for e in events if e["origin_week"] > observed_by),
                     key=lambda e: e["origin_week"], reverse=True)[:10]

    model = HistoryBaseline(horizon=HORIZON).fit(train, countries)
    rate = model.base_rate
    table = [
        evaluate("history baseline", model.predict, test, countries),
        evaluate("global country base rate", lambda e, cs: {c: rate[c] for c in cs}, test, countries),
        evaluate("uniform", lambda e, cs: {c: 0.5 for c in cs}, test, countries),
    ]
    trials = sum(len(countries) - len(e["origin_countries"]) for e in test)
    positives = sum(joined(e, c, HORIZON) for e in test for c in countries
                    if c not in e["origin_countries"])

    print(f"last week {last_week}, cutoff {cutoff}, horizon {HORIZON} weeks, countries {len(countries)}")
    print(f"train events {len(train)}, test events {len(test)}, test positives {positives} of {trials} pairs")
    print(f"{'model':28s} {'AUC':>7s} {'Brier':>8s} {'top-5':>7s}")
    for row in table:
        print(f"{row['model']:28s} {row['auc']:7.4f} {row['brier']:8.4f} {row['top5_precision']:7.4f}")
    print("\nMost recent breakouts, horizon not yet observed:")
    for e in pending:
        print(f"  {e['origin_week']}  {e['title'][0]} / {e['title'][1]}  [{e['category']}]  "
              f"origin {','.join(e['origin_countries'])}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "horizon_weeks": HORIZON, "cutoff": str(cutoff), "last_week": str(last_week),
        "train_events": len(train), "test_events": len(test),
        "test_positives": positives, "test_pairs": trials, "metrics": table,
        "pending_events": [{"title": list(e["title"]), "origin_countries": e["origin_countries"],
                            "origin_week": str(e["origin_week"])} for e in pending],
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
