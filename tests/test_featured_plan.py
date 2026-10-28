import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from aftershock import api  # noqa: E402


def row(code, n_confirmed, events=1, generic=False):
    return {"code": code, "generic": generic, "kit": {"artist": [{"name": "A"}]},
            "plan": {"confirmed": [{"domain": "artist", "name": f"N{i}", "both": False} for i in range(n_confirmed)]},
            "events": [{"artist": "A", "cities": ["X"]}] * events}


def storm(sid, year, rows, top=0.3, title=None, season=None, category="Films"):
    forecasts = [{"code": r["code"], "name": f"Country {r['code']}", "probability": 0.1 + i / 100} for i, r in enumerate(rows)]
    return {"summary": {"id": sid, "title": title or sid, "season": season, "category": category, "origin_countries": [], "meta": {"year": year},
                        "top_forecast": {"code": rows[0]["code"], "probability": top}},
            "detail": {"launch_kit": rows, "spillover": {"forecasts": forecasts}}}


def test_prefers_recent_over_more_confirmed():
    old = storm("old", 1998, [row("IN", 12)], top=0.9)
    new = storm("new", 2024, [row("SE", 4)], top=0.2)
    assert api.featured_plan([old, new], "2026-10-18") == {"id": "new", "code": "SE", "title": "new", "country": "Country SE"}


def test_then_most_confirmed_then_chance():
    a = storm("a", 2025, [row("AA", 5)], top=0.5)
    b = storm("b", 2025, [row("BB", 8)], top=0.1)
    assert api.featured_plan([a, b], "2026-10-18")["id"] == "b"
    c = storm("c", 2025, [row("CC", 8)])
    c["detail"]["spillover"]["forecasts"][0]["probability"] = 0.9
    assert api.featured_plan([b, c], "2026-10-18")["id"] == "c"


def test_needs_three_confirmed_an_event_idea_and_a_specific_kit():
    few = storm("few", 2025, [row("AA", 2)])
    no_event = storm("noevent", 2025, [row("BB", 9, events=0)])
    generic = storm("generic", 2025, [row("CC", 9, generic=True)])
    ok = storm("ok", 1990, [row("DD", 3)])
    assert api.featured_plan([few, no_event, generic, ok], "2026-10-18")["id"] == "ok"


def test_falls_back_to_the_older_rule():
    top = storm("top", 2025, [row("AA", 1)], top=0.8)
    grounded = storm("grounded", 2025, [row("BB", 6, events=0)], top=0.4)
    assert api.featured_plan([top, grounded], "2026-10-18")["id"] == "grounded"  # first specific row with 3+ confirmed
    assert api.featured_plan([top], "2026-10-18")["id"] == "top"  # no grounded row: the top storm's first kit row
    assert api.featured_plan([], "2026-10-18") is None


def test_storms_endpoint_carries_featured_plan_and_unique_labels(monkeypatch, tmp_path):
    items = [storm("money-trap", 2019, [row("TR", 4)], title="Money Trap"),
             storm("money-trap-s1", 2026, [row("DE", 4)], title="Money Trap", season="The Karun Treasure", category="TV"),
             storm("twin-a", 2020, [row("FR", 4)], title="Twin"), storm("twin-b", 2021, [row("ES", 4)], title="Twin")]
    (tmp_path / "storms.json").write_text(json.dumps({"week": "2026-10-18", "storms": items}), encoding="utf-8")
    monkeypatch.setattr(api, "PRIVATE", tmp_path)
    body = TestClient(api.app).get("/api/storms").json()
    assert body["featured_plan"]["code"] in {"TR", "DE", "FR", "ES"}
    labels = [s["label"] for s in body["storms"]]
    assert len(set(labels)) == len(labels)
    assert "Money Trap The Karun Treasure" in labels and "Twin (films, 2020)" in labels
