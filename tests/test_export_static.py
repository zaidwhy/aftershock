import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from aftershock import api  # noqa: E402
import export_static  # noqa: E402

client = TestClient(api.app)


@pytest.fixture(autouse=True)
def no_metro_file():
    """Overrides conftest's isolation: these tests compare the export with the API on the real local files, metro names
    included, and the module-scoped `out` below is built once outside any per-test patch."""
pytestmark = pytest.mark.skipif(not (api.PRIVATE / "storms.json").exists(), reason="forecast files not generated")


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    path = tmp_path_factory.mktemp("static")
    export_static.export(path)
    return path


def _file(out, name):
    return json.loads((out / name).read_text(encoding="utf-8"))


def test_storm_list_matches_api(out):
    assert _file(out, "storms.json") == client.get("/api/storms").json()


def test_one_storm_matches_api(out):
    first = client.get("/api/storms").json()["storms"][0]["id"]
    assert _file(out, f"storms/{first}.json") == client.get(f"/api/storms/{first}").json()


def test_scorecard_matches_api(out):
    assert _file(out, "scorecard.json") == client.get("/api/scorecard").json()


def test_replays_match_api_and_ripples_not_exported(out):
    assert not (out / "ripples.json").exists() and not (out / "ripples").exists()
    assert _file(out, "replays.json") == client.get("/api/replays").json()


def test_ledger_page_counts_rows_status_and_chain(tmp_path):
    from datetime import date, datetime, timezone
    from aftershock import ledger
    path = tmp_path / "forecasts.jsonl"
    old = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    new = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    ledger.append([{"kind": "spillover", "title": ["Old Show", "N/A"], "origin_week": "2026-08-30", "target": "FR", "probability": 0.4},
                   {"kind": "spillover", "title": ["Old Show", "N/A"], "origin_week": "2026-08-30", "target": "DE", "probability": 0.2}], path, now=old)
    ledger.append([{"kind": "spillover", "title": ["New Show", "New Show: Season 2"], "origin_week": "2026-10-18", "target": "FR", "probability": 0.1},
                   {"kind": "spillover", "title": ["New Show", "New Show: Season 2"], "origin_week": "2026-10-18", "target": "DE", "probability": 0.7}], path, now=new)
    first = {("Old Show", "N/A"): {"FR": date(2026, 9, 6)}}
    page = export_static.ledger_page(ledger.read(path), ledger.verify(path) is None, first, date(2026, 10, 25), {"FR": "France", "DE": "Germany"})
    assert page["total"] == 4 and page["titles"] == 2 and page["intact"] is True
    assert page["first_locked"] == "2026-09-01T12:00:00Z" and page["last_locked"] == "2026-10-26T12:00:00Z"
    assert [(r["title"], r["country"], r["status"]) for r in page["rows"]] == [
        ("New Show: Season 2", "Germany", "pending"), ("New Show: Season 2", "France", "pending"),
        ("Old Show", "France", "hit"), ("Old Show", "Germany", "miss")]
    path.write_text(path.read_text(encoding="utf-8").replace("0.4", "0.9"), encoding="utf-8")
    assert ledger.verify(path) == 0


def test_export_includes_archived_storms(tmp_path, monkeypatch):
    from aftershock import storm_archive
    current = client.get("/api/storms").json()["storms"][0]["id"]
    arch = tmp_path / "arch"
    storm_archive.write_week(arch, "2026-01-04", [
        {"summary": {"id": "gone-show"}, "detail": {"title": "Gone Show"}},
        {"summary": {"id": current}, "detail": {"title": "STALE CLASH"}}])
    monkeypatch.setattr(api, "ARCHIVE", arch)
    dest = tmp_path / "static"
    export_static.export(dest)
    assert _file(dest, "storms/gone-show.json") == {"title": "Gone Show", "archived_week": "2026-01-04"}
    assert _file(dest, f"storms/{current}.json")["title"] != "STALE CLASH"
    assert "archived_week" not in _file(dest, f"storms/{current}.json")
