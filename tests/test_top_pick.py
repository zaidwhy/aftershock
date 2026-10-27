import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_forecasts as rf  # noqa: E402


def rec(title, origin, target, p):
    return {"kind": "spillover", "title": [title, "TV"], "origin_week": origin, "target": target, "probability": p}


def setup(monkeypatch, records, first):
    monkeypatch.setattr(rf.ledger, "read", lambda: records)
    monkeypatch.setattr(rf, "first_entries", lambda rows: first)


def test_hit_only_when_joined_after_origin_within_horizon(monkeypatch):
    records = [rec("A", "2026-10-18", "BD", 0.4), rec("A", "2026-10-18", "FR", 0.1),
               rec("B", "2026-10-18", "BD", 0.3), rec("C", "2026-10-18", "BD", 0.2)]
    first = {("A", "TV"): {"BD": date(2026, 10, 25)},
             ("B", "TV"): {"BD": date(2026, 10, 18)},      # same week as origin: not after
             ("C", "TV"): {"BD": date(2026, 12, 6)}}       # beyond 4 weeks
    setup(monkeypatch, records, first)
    out = rf.top_pick_grade([], date(2026, 10, 25))
    assert out["breakouts"] == 3 and out["top_pick_hits"] == 1 and out["expected_hits"] == 0.9


def test_origin_week_not_before_latest_is_excluded(monkeypatch):
    setup(monkeypatch, [rec("A", "2026-10-18", "BD", 0.4)], {})
    out = rf.top_pick_grade([], date(2026, 10, 18))
    assert out["breakouts"] == 0 and out["baseline_country"] is None and out["expected_hits"] == 0


def test_ties_take_first_in_ledger_order(monkeypatch):
    records = [rec("A", "2026-10-18", "BD", 0.3), rec("A", "2026-10-18", "FR", 0.3)]
    setup(monkeypatch, records, {("A", "TV"): {"FR": date(2026, 10, 25)}})
    assert rf.top_pick_grade([], date(2026, 10, 25))["top_pick_hits"] == 0


def test_baseline_picks_most_frequent_chart_country(monkeypatch):
    records = [rec("A", "2026-10-18", "BD", 0.5), rec("A", "2026-10-18", "FR", 0.1)]
    first = {("A", "TV"): {"FR": date(2026, 10, 25)},
             ("X", "TV"): {"FR": date(2026, 1, 4)}, ("Y", "TV"): {"FR": date(2026, 1, 4), "BD": date(2026, 1, 4)}}
    setup(monkeypatch, records, first)
    out = rf.top_pick_grade([], date(2026, 10, 25))
    assert out["baseline_country"] == "FR" and out["baseline_hits"] == 1 and out["top_pick_hits"] == 0
