import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from aftershock import api  # noqa: E402

client = TestClient(api.app)


def test_health_reports_without_secrets():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "qloo_key", "cache_entries"}


def test_ripple_rejects_malformed_song_lines():
    resp = client.get("/api/ripple", params={"show": "Wednesday", "songs": "Goo Goo Muck without artist"})
    assert resp.status_code == 422
    assert "song|artist" in resp.json()["detail"]


def test_ripple_rejects_too_many_songs():
    songs = ";".join(f"Song {i}|Artist {i}" for i in range(9))
    resp = client.get("/api/ripple", params={"show": "Wednesday", "songs": songs})
    assert resp.status_code == 422
    assert "1 to 8" in resp.json()["detail"]


def test_ripple_rate_limit_per_visitor(monkeypatch):
    monkeypatch.setattr(api, "score_placements", lambda *a, **k: {"resolved": True, "songs": []})
    monkeypatch.setattr(api, "Qloo", lambda **k: None)
    api._ripple_hits.clear()
    codes = [client.get("/api/ripple", params={"show": "X", "songs": "A|B"}).status_code
             for _ in range(api.RIPPLE_PER_HOUR + 1)]
    assert codes[:-1] == [200] * api.RIPPLE_PER_HOUR
    assert codes[-1] == 429


def _stub_scoring(monkeypatch):
    monkeypatch.setattr(api, "score_placements", lambda *a, **k: {"resolved": True, "songs": []})
    monkeypatch.setattr(api, "Qloo", lambda **k: None)
    api._ripple_hits.clear()
    api._daily.update(day=None, count=0)


def test_ripple_limit_keys_on_first_forwarded_address(monkeypatch):
    _stub_scoring(monkeypatch)
    params = {"show": "X", "songs": "A|B"}
    for _ in range(api.RIPPLE_PER_HOUR):
        assert client.get("/api/ripple", params=params, headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"}).status_code == 200
    assert client.get("/api/ripple", params=params, headers={"X-Forwarded-For": "203.0.113.7"}).status_code == 429
    assert client.get("/api/ripple", params=params, headers={"X-Forwarded-For": "203.0.113.8"}).status_code == 200


def test_ripple_daily_cap_across_visitors(monkeypatch):
    _stub_scoring(monkeypatch)
    monkeypatch.setattr(api, "RIPPLE_PER_DAY", 3)
    params = {"show": "X", "songs": "A|B"}
    codes = [client.get("/api/ripple", params=params, headers={"X-Forwarded-For": f"198.51.100.{i}"}).status_code
             for i in range(4)]
    assert codes == [200, 200, 200, 429]
    resp = client.get("/api/ripple", params=params, headers={"X-Forwarded-For": "198.51.100.99"})
    assert resp.status_code == 429
    assert "daily limit of 3" in resp.json()["detail"]


def test_unknown_storm_is_404_with_reason(tmp_path, monkeypatch):
    (tmp_path / "storms.json").write_text('{"week": "2026-10-18", "storms": [], "ripples": []}', encoding="utf-8")
    monkeypatch.setattr(api, "PRIVATE", tmp_path)
    resp = client.get("/api/storms/nope")
    assert resp.status_code == 404
    assert "nope" in resp.json()["detail"]


def test_ripple_rejects_as_of_before_pageview_history():
    resp = client.get("/api/ripple", params={"show": "X", "songs": "A|B", "as_of": "2010-01-01"})
    assert resp.status_code == 422
    assert "as_of" in resp.json()["detail"]
