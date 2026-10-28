"""How much warning the spillover forecast gives, on the held-out breakouts of the registered backtest.

Same data, split, model and horizon as scripts/backtest_spillover.py (imported, not copied). For each
held-out breakout the forecast week is its breakout week and the model is fit on earlier breakouts only.
Case-study rule, fixed before any result was looked at: the three held-out breakouts with the highest
top-1 forecast probability (ties: earlier breakout week, then title).
"""
import json
import logging
import statistics
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from aftershock.netflix import (  # noqa: E402
    HistoryBaseline, breakout_events, first_entries, load_rows, title_categories,
)
from backtest_spillover import HORIZON, RAW, TEST_WEEKS  # noqa: E402

OUT = ROOT / "data" / "results" / "lead_time.json"
TOP_K = 3
CASES = 3


def top_picks(scorer, event, countries, k=TOP_K):
    candidates = [c for c in countries if c not in event["origin_countries"]]
    probabilities = scorer(event, candidates)
    ranked = sorted(candidates, key=lambda c: (-probabilities[c], c))[:k]
    return [(c, probabilities[c]) for c in ranked]


def charted_week(event, country, horizon):
    """Weeks after the breakout week the title first charted in `country`, or None within the horizon."""
    gap = event["later"].get(country)
    return gap if gap is not None and gap <= horizon else None


def measure(model_scorer, baseline_scorer, events, countries, horizon=HORIZON, k=TOP_K):
    def arm(scorer):
        hits, picks, charted, leads = 0, 0, 0, []
        for event in events:
            got = [charted_week(event, c, horizon) for c, _ in top_picks(scorer, event, countries, k)]
            picks += len(got)
            charted += sum(g is not None for g in got)
            hits += any(g is not None for g in got)
            leads += [g for g in got if g is not None]
        return {"breakouts": len(events), "hit_breakouts": hits, "hit_rate": hits / len(events),
                "picks": picks, "picks_charted": charted, "per_pick_precision": charted / picks,
                "lead_weeks": {"median": statistics.median(leads) if leads else None,
                               "mean": statistics.fmean(leads) if leads else None,
                               "distribution": {str(w): leads.count(w) for w in range(1, horizon + 1)}}}
    return {"model": arm(model_scorer), "baseline": arm(baseline_scorer)}


def case_studies(model_scorer, events, countries, horizon=HORIZON, k=TOP_K, n=CASES):
    ranked = sorted(events, key=lambda e: (-top_picks(model_scorer, e, countries, 1)[0][1],
                                           e["origin_week"], e["title"]))[:n]
    out = []
    for event in ranked:
        picks = top_picks(model_scorer, event, countries, k)
        out.append({
            "title": list(event["title"]), "category": event["category"],
            "breakout_week": str(event["origin_week"]), "origin_countries": event["origin_countries"],
            "top3": [{"country": c, "probability": round(p, 4), "charted_after_weeks": charted_week(event, c, horizon)}
                     for c, p in picks],
            "all_countries_charted_within_horizon": sorted(c for c in event["later"] if event["later"][c] <= horizon),
        })
    return out


def run(rows):
    countries = sorted({r["country_iso2"] for r in rows})
    last_week = date.fromisoformat(max(r["week"] for r in rows))
    events = breakout_events(first_entries(rows), title_categories(rows), max_origin=3)
    observed_by = last_week - timedelta(weeks=HORIZON)
    cutoff = last_week - timedelta(weeks=TEST_WEEKS + HORIZON)
    train = [e for e in events if e["origin_week"] < cutoff]
    test = [e for e in events if cutoff <= e["origin_week"] <= observed_by]
    model = HistoryBaseline(horizon=HORIZON).fit(train, countries)
    rate = model.base_rate

    def baseline(event, cs):  # the backtest's "global country base rate"
        return {c: rate[c] for c in cs}

    result = measure(model.predict, baseline, test, countries)
    return {
        "note": "Backtest on history-only forecasts (no Qloo data). Forecast week = breakout week; model fit on earlier breakouts only.",
        "horizon_weeks": HORIZON, "top_k": TOP_K, "cutoff": str(cutoff), "last_week": str(last_week),
        "train_events": len(train), "test_events": len(test),
        "baseline_picks": "the 3 countries with the highest overall chart-join rate, skipping the title's origin countries",
        "baseline_most_common_picks": Counter(c for e in test for c, _ in top_picks(baseline, e, countries)).most_common(5),
        "breakouts_that_spread_at_all": sum(any(g <= HORIZON for g in e["later"].values()) for e in test),
        **result,
        "case_study_rule": "the 3 held-out breakouts with the highest top-1 forecast probability (ties: earlier week, then title)",
        "case_studies": case_studies(model.predict, test, countries),
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = run(load_rows(RAW))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
