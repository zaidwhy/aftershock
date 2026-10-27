import sys
from argparse import Namespace
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_forecasts  # noqa: E402


def storm(kits):
    return {"detail": {"launch_kit": kits}}


KITS = [{"kit": {"artist": [1]}, "generic": False, "hotspots": {"places": ["A"]}},
        {"kit": {"artist": [1]}, "generic": True, "hotspots": {}}, {"kit": {}, "generic": False}]


def build(no_lock, resolved=2, missing=("X",)):
    return run_forecasts.agent_run_log(
        datetime(2026, 10, 27, tzinfo=timezone.utc), Namespace(no_lock=no_lock), "from the cached file", date(2026, 10, 18),
        94, 1000, 3, resolved, list(missing), 300, 40, [storm(KITS)], 8721, 0, 0, 5, 1, 9)


def test_log_counts_and_plain_sentences():
    log = build(no_lock=False)
    by = {s["key"]: s for s in log["steps"]}
    assert by["netflix"]["text"] == "Read Netflix's Top 10 for the week of 18 Oct in 94 countries"
    assert by["breakouts"]["text"] == "Found 3 titles that broke out in 1 to 3 countries"
    assert by["qloo_titles"]["not_found"] == ["X"] and by["qloo_titles"]["count"] == 2
    assert (by["lock"]["count"], by["lock"]["already_locked"]) == (40, 260)
    assert (by["kits"]["count"], by["kits"]["title_specific"], by["kits"]["countrywide"]) == (2, 1, 1)
    assert by["hotspots"]["count"] == 1 and by["index"]["count"] == 8721
    assert "none is graded" in by["graded"]["text"]
    assert log["summary"] == {"breakouts": 3, "forecasts_locked": 300, "launch_kits": 2}


def test_dry_run_locks_nothing_and_says_so():
    log = build(no_lock=True)
    assert log["dry_run"] is True and log["summary"]["forecasts_locked"] == 260
    assert "Dry run" in next(s for s in log["steps"] if s["key"] == "lock")["text"]


def test_offline_run_skips_qloo_step():
    step = next(s for s in build(no_lock=True, resolved=None, missing=())["steps"] if s["key"] == "qloo_titles")
    assert step["count"] is None and "Skipped" in step["text"]
