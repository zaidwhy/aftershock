import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import json  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from aftershock import api, artist_view, launch_brief  # noqa: E402
import export_static  # noqa: E402


def _row(code, confirmed, events=(), kit_artists=(), brands=()):
    conf = [{"domain": "artist", "name": n, "both": n in kit_artists} for n in confirmed]
    conf += [{"domain": "brand", "name": b, "both": False} for b in brands]
    return {"code": code, "kit": {"artist": [{"name": n, "entity_id": n} for n in kit_artists], "brand": [], "movie": [], "tv_show": [{"name": "Filler", "entity_id": "f"}]},
            "hotspots": {"places": ["Seoul", "Busan", "Daegu"]},
            "plan": {"confirmed": conf, "dropped": {}}, "events": [{"artist": a, "cities": c} for a, c in events]}


def _item(sid, title, rows, season=None):
    fcs = [{"code": "KR", "name": "South Korea", "probability": 0.21}, {"code": "TW", "name": "Taiwan", "probability": 0.05}]
    d = {"id": sid, "title": title, "season": season, "origin_countries": [{"code": "JP", "name": "Japan"}],
         "spillover": {"horizon_weeks": 4, "forecasts": fcs}, "launch_kit": rows}
    return {"summary": {"id": sid, "title": title}, "detail": d}


ITEMS = [
    _item("a", "Alpha", [_row("KR", ["Veronica Maggio", "Zed"], events=[("Veronica Maggio", ["Seoul", "Busan"])],
                              kit_artists=["Zed"]),
                         _row("TW", ["Veronica Maggio"])]),
    _item("b", "Beta", [_row("TW", ["Zed"]), _row("KR", ["Veronica Maggio"], events=[("Event Only", ["Daegu"])])]),
]


def test_index_dedupes_sorts_and_marks_evidence():
    idx = artist_view.build(ITEMS)
    names = [a["name"] for a in idx["artists"]]
    assert names == ["Veronica Maggio", "Zed", "Event Only"]  # 3 breakouts, 2, 1
    vm = idx["artists"][0]
    assert vm["slug"] == "veronica-maggio" and len(vm["breakouts"]) == 3
    assert [b["chance"] for b in vm["breakouts"]] == [0.21, 0.21, 0.05]
    top = vm["breakouts"][0]
    assert top["cities"] == ["Seoul", "Busan"] and top["qloo_confirmed"] and not top["in_qloo_kit"]
    assert vm["countries"] == ["South Korea", "Taiwan"]
    zed_kr = next(b for b in idx["artists"][1]["breakouts"] if b["code"] == "KR")
    assert zed_kr["in_qloo_kit"] is True and zed_kr["cities"] == []
    eo = idx["artists"][2]["breakouts"][0]
    assert eo["cities"] == ["Daegu"] and eo["qloo_confirmed"] is False


def test_slugs_are_url_safe_and_unique():
    items = [_item("c", "C", [_row("KR", ["Beyoncé", "Beyonce", "宇多田ヒカル", "Sigur Rós!"])])]
    slugs = [a["slug"] for a in artist_view.build(items)["artists"]]
    assert len(slugs) == len(set(slugs)) == 3
    assert all(s and s.replace("-", "").isalnum() and s.isascii() for s in slugs)


def test_listing_and_detail_and_404(monkeypatch):
    monkeypatch.setattr(api, "_load", lambda path: {"week": "2026-10-18", "storms": ITEMS})
    client = TestClient(api.app)
    lst = client.get("/api/artists").json()
    assert lst["artists"][0] == {"name": "Veronica Maggio", "slug": "veronica-maggio", "breakouts": 3,
                                 "countries": ["South Korea", "Taiwan"], "countrywide_only": False}
    one = client.get("/api/artists/veronica-maggio").json()
    assert one["week"] == "2026-10-18" and len(one["breakouts"]) == 3
    miss = client.get("/api/artists/nobody")
    assert miss.status_code == 404 and miss.json()["detail"] == "No artist called nobody appears in this week's forecasts."


def test_export_writes_artist_files(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "artists", lambda: artist_view.listing(artist_view.build(ITEMS), "w"))
    monkeypatch.setattr(api, "artist", lambda slug: artist_view.detail(artist_view.build(ITEMS), "w", slug))
    monkeypatch.setattr(api, "storms", lambda: {"storms": [], "week": "w"})
    for name in ("scorecard", "replays"):
        monkeypatch.setattr(api, name, lambda: {})
    monkeypatch.setattr(export_static, "_ledger_body", lambda listing: {})
    monkeypatch.setattr(api, "ARCHIVE", tmp_path / "none")
    export_static.export(tmp_path / "out")
    out = tmp_path / "out"
    assert len(json.loads((out / "artists.json").read_text(encoding="utf-8"))["artists"]) == 3
    assert json.loads((out / "artists" / "zed.json").read_text(encoding="utf-8"))["name"] == "Zed"


def _detail(rows):
    return ITEMS[0]["detail"] | {"launch_kit": rows}


def test_moves_only_from_facts():
    full = _row("KR", ["Veronica Maggio", "Nike", "Pick2"], events=[("Veronica Maggio", ["Seoul", "Busan"])], brands=["Nike"])
    moves = {m["buyer"]: m["text"] for m in launch_brief.brief(_detail([full]), "KR")["brief"]["moves"]}
    assert set(moves) == {"Label", "Artist", "Brand marketer", "Distributor"}
    assert moves["Label"] == ("Push Veronica Maggio's catalogue to listeners in Seoul and Busan this week; "
                              "Qloo links them to Alpha's viewers in South Korea.")
    assert "Nike" in moves["Brand marketer"] and "21% chance" in moves["Distributor"]
    no_event = _row("KR", ["A1", "A2", "A3"])
    got = {m["buyer"] for m in launch_brief.brief(_detail([no_event]), "KR")["brief"]["moves"]}
    assert got == {"Label", "Distributor"}  # artist move needs an event idea, brand needs a confirmed brand
    bare = _row("KR", [])
    bare["hotspots"] = {"places": []}
    bare["kit"]["artist"] = [{"name": "Kit Artist", "entity_id": "k"}]
    got = {m["buyer"] for m in launch_brief.brief(_detail([bare]), "KR")["brief"]["moves"]}
    assert got == {"Distributor"}  # no cities: no local moves
