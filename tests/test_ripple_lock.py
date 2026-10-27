import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_forecasts as rf  # noqa: E402
from aftershock import ledger  # noqa: E402


def item(release="2026-10-22", n=5):
    return {"show": "Show (Season 1)", "release_date": release,
            "songs": [{"song": f"s{i}", "artist": f"a{i}", "score": 0.5, "wiki_article": None} for i in range(n)]}


def test_locks_through_release_plus_six_days_not_seven():
    assert rf.ripple_lock_status("2026-10-22", 5, date(2026, 10, 22))[0]
    assert rf.ripple_lock_status("2026-10-22", 5, date(2026, 10, 28))[0]
    lockable, reason = rf.ripple_lock_status("2026-10-22", 5, date(2026, 10, 29))
    assert not lockable and "outcome window was already open" in reason


def test_needs_four_scored_songs():
    assert rf.ripple_lock_status("2026-10-22", 4, date(2026, 10, 23))[0]
    lockable, reason = rf.ripple_lock_status("2026-10-22", 3, date(2026, 10, 23))
    assert not lockable and "fewer than 4" in reason


def test_locking_is_idempotent(tmp_path):
    path = tmp_path / "f.jsonl"
    batch = rf.ripple_forecasts(item())
    keys = lambda: {(tuple(r["title"]), r["origin_week"]) for r in ledger.read(path)}  # noqa: E731
    first = rf.fresh_forecasts(batch, keys())
    ledger.append(first, path)
    assert len(first) == 5
    assert rf.fresh_forecasts(batch, keys()) == []
    other = rf.ripple_forecasts(item(release="2026-10-23"))
    second = rf.fresh_forecasts(batch + other, keys())
    ledger.append(second, path)
    assert len(second) == 5 and len(ledger.read(path)) == 10
    assert ledger.verify(path) is None
