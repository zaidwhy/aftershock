import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_lead_time as lt  # noqa: E402

COUNTRIES = ["AA", "BB", "CC", "DD", "EE"]


def event(title, later, origin=("AA",)):
    return {"title": (title, "N/A"), "category": "TV", "origin_week": date(2026, 5, 3),
            "origin_countries": list(origin), "later": later}


def scorer(order):
    """Probability falls along `order`; other countries get 0.01."""
    return lambda e, cs: {c: (0.9 - 0.1 * order.index(c) if c in order else 0.01) for c in cs}


def test_hit_at_week_two_gives_lead_two_and_misses_are_not_counted():
    # Top 3 by the model: BB, CC, DD. BB charts at week 2, CC never, DD after the horizon (week 6).
    events = [event("T1", {"BB": 2, "DD": 6})]
    out = lt.measure(scorer(["BB", "CC", "DD"]), scorer(["EE", "DD", "CC"]), events, COUNTRIES, horizon=4)
    m = out["model"]
    assert (m["hit_breakouts"], m["picks"], m["picks_charted"]) == (1, 3, 1)
    assert m["lead_weeks"]["median"] == 2 and m["lead_weeks"]["distribution"] == {"1": 0, "2": 1, "3": 0, "4": 0}
    assert abs(m["per_pick_precision"] - 1 / 3) < 1e-9


def test_breakout_with_no_charting_pick_is_a_miss_with_no_lead():
    out = lt.measure(scorer(["BB", "CC", "DD"]), scorer(["EE"]), [event("T2", {"EE": 1})], COUNTRIES, horizon=4)
    assert out["model"]["hit_rate"] == 0 and out["model"]["lead_weeks"]["median"] is None
    assert out["baseline"]["hit_rate"] == 1 and out["baseline"]["lead_weeks"]["median"] == 1


def test_baseline_skips_origin_countries_and_distribution_aggregates():
    events = [event("T3", {"BB": 1, "CC": 3}, origin=("AA",)), event("T4", {"BB": 1}, origin=("BB",))]
    # Baseline order AA, BB, CC, DD: T3 picks BB, CC, DD (AA is the origin); T4 picks AA, CC, DD.
    out = lt.measure(scorer(["BB"]), scorer(["AA", "BB", "CC", "DD"]), events, COUNTRIES, horizon=4)
    b = out["baseline"]
    assert (b["hit_breakouts"], b["picks_charted"]) == (1, 2)
    assert b["lead_weeks"]["distribution"] == {"1": 1, "2": 0, "3": 1, "4": 0} and b["lead_weeks"]["mean"] == 2


def test_case_studies_follow_the_fixed_rule_and_include_misses():
    events = [event("Low", {"BB": 1}), event("High", {}), event("Mid", {"BB": 1})]

    def by_title(e, cs):
        top = {"Low": 0.2, "High": 0.8, "Mid": 0.5}[e["title"][0]]
        return {c: (top if c == "BB" else 0.01) for c in cs}

    cases = lt.case_studies(by_title, events, COUNTRIES, horizon=4, n=2)
    assert [c["title"][0] for c in cases] == ["High", "Mid"]
    assert cases[0]["top3"][0]["country"] == "BB" and cases[0]["top3"][0]["charted_after_weeks"] is None
    assert cases[1]["top3"][0]["charted_after_weeks"] == 1
