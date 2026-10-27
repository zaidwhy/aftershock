import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from aftershock import api, titles  # noqa: E402

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


def test_song_by_artist_splits_on_last_by():
    assert api._parse_songs("Stand by Me by Ben E. King") == [("Stand by Me", "Ben E. King")]
    assert api._parse_songs("Space Song BY Beach House") == [("Space Song", "Beach House")]


def test_pipe_format_still_works_and_wins_over_by():
    assert api._parse_songs("X | Y") == [("X", "Y")]
    assert api._parse_songs("Stand by Me | Ben E. King; Song by Artist") == [("Stand by Me", "Ben E. King"), ("Song", "Artist")]


def test_song_chunk_with_neither_format_names_both():
    resp = client.get("/api/ripple", params={"show": "Wednesday", "songs": "Just a title"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "song|artist" in detail and "song by artist" in detail


def test_scout_validates_show():
    assert client.get("/api/scout").status_code == 422
    assert client.get("/api/scout", params={"show": "x" * 121}).status_code == 422
    assert client.get("/api/scout", params={"show": "   "}).status_code == 422


def test_scout_shares_the_ripple_limiter(monkeypatch):
    _stub_scoring(monkeypatch)
    monkeypatch.setattr(api, "scout", lambda *a, **k: {"resolved": True, "artists": []})
    codes = [client.get("/api/scout", params={"show": "X"}).status_code for _ in range(api.RIPPLE_PER_HOUR + 1)]
    assert codes[:-1] == [200] * api.RIPPLE_PER_HOUR and codes[-1] == 429
    assert client.get("/api/ripple", params={"show": "X", "songs": "A|B"}).status_code == 429


def test_ripple_response_has_no_raw_qloo_values(monkeypatch):
    raw = {"resolved": True, "show": "X", "as_of": "2026-10-27",
           "show_age": {"24_and_younger": 0.5, "25_to_29": 0.3, "30_to_34": 0.1, "35_to_44": -0.4, "45_to_54": -0.3, "55_and_older": -0.4},
           "songs": [{"song": "S", "artist": "A", "resolved": True, "fit": 0.4, "score": 0.6, "age_gap": 0.6,
                      "artist_age": {"24_and_younger": -0.2, "25_to_29": 0.0, "30_to_34": 0.2, "35_to_44": 0.3, "45_to_54": 0.3, "55_and_older": 0.1}}]}
    monkeypatch.setattr(api, "score_placements", lambda *a, **k: raw)
    monkeypatch.setattr(api, "Qloo", lambda **k: None)
    api._ripple_hits.clear()
    api._daily.update(day=None, count=0)
    body = client.get("/api/ripple", params={"show": "X", "songs": "S|A"}).json()
    assert "show_age" not in body and "show_leans" in body
    song = body["songs"][0]
    assert not {"fit", "artist_age", "show_age"} & set(song)
    assert song["leans"][0] == "45_to_54" or song["leans"][0] == "35_to_44"
    assert song["score"] == 0.6


def _item(sid, prob, generic=False, places=("Lyon",)):
    row = {"code": "FR", "generic": generic, "specificity": 0.8,
           "kit": {"artist": [{"name": "A"}, {"name": "Common"}, {"name": "B"}, {"name": "C"}], "brand": [{"name": "X"}]},
           "control": {"artist": ["common"]}, "hotspots": {"places": list(places)}}
    return {"summary": {"id": sid, "title": sid.title(), "origin_countries": [{"code": "KR", "name": "South Korea"}],
                        "top_forecast": {"code": "FR", "name": "France", "probability": prob, "why": "w"}},
            "detail": {"launch_kit": [row]}}


def test_hero_picks_highest_qualifying_storm():
    hero = api._hero([_item("low", 0.1), _item("generic", 0.9, generic=True), _item("noplace", 0.8, places=()),
                      _item("best", 0.4)])
    assert hero["id"] == "best" and hero["probability"] == 0.4
    assert hero["artists"] == ["A", "B", "C"] and hero["places"] == ["Lyon"]


def test_hero_none_when_nothing_qualifies():
    assert api._hero([_item("g", 0.9, generic=True), _item("p", 0.5, places=())]) is None
    assert api._hero([]) is None


class _FakeQloo:
    """Search-only stand-in: the show and Ed Sheeran exist; "edshreen" is not a name but is nearest to him."""
    def search(self, query, types=None, take=5):
        if "tv_show" in (types or ""):
            return [{"name": "Stranger Things", "entity_id": "show"}]
        if "artist" in (types or ""):
            return [{"name": "Ed Sheeran", "entity_id": "ed"}] if "sheeran" not in query.lower() else \
                [{"name": "Ed Sheeran", "entity_id": "ed"}]
        return []

    def insights(self, **params):
        age = {"24_and_younger": 0.4, "25_to_29": 0.2, "30_to_34": 0.0, "35_to_44": -0.2, "45_to_54": -0.2, "55_and_older": -0.2}
        if params.get("filter__type") == "urn:demographics":
            return {"results": {"demographics": [{"query": {"age": age}}]}}
        return {"results": {"entities": []}}


def test_unresolved_artist_row_carries_a_suggestion(monkeypatch):
    from aftershock import ripple
    monkeypatch.setattr(ripple, "prior_attention", lambda *a, **k: (None, None))
    out = ripple.score_placements(_FakeQloo(), "Stranger Things", [("Shape of You", "edshreen"), ("Perfect", "Ed Sheeran")])
    by_artist = {s["artist"]: s for s in out["songs"]}
    assert by_artist["edshreen"]["resolved"] is False
    assert by_artist["edshreen"]["suggestion"] == "Ed Sheeran"
    assert by_artist["Ed Sheeran"]["resolved"] is True and by_artist["Ed Sheeran"]["matched_artist"] == "Ed Sheeran"
    assert "suggestion" not in by_artist["Ed Sheeran"]


def test_unresolved_show_carries_a_suggestion(monkeypatch):
    from aftershock import ripple
    class Near(_FakeQloo):
        def search(self, query, types=None, take=5):
            return [{"name": "Stranger Things", "entity_id": "show"}]
    out = ripple.score_placements(Near(), "Stranger Thingz", [("A", "B")])
    assert out["resolved"] is False and out["suggestion"] == "Stranger Things"


def test_api_passes_suggestion_through(monkeypatch):
    raw = {"resolved": True, "show": "X", "songs": [{"song": "S", "artist": "edshreen", "resolved": False, "suggestion": "Ed Sheeran"}]}
    monkeypatch.setattr(api, "score_placements", lambda *a, **k: raw)
    monkeypatch.setattr(api, "Qloo", lambda **k: None)
    api._ripple_hits.clear()
    api._daily.update(day=None, count=0)
    body = client.get("/api/ripple", params={"show": "X", "songs": "S|edshreen"}).json()
    assert body["songs"][0]["suggestion"] == "Ed Sheeran"


def test_suggest_respells_a_name_qloo_search_cannot_match():
    from aftershock.qloo import suggest

    class Picky:
        def search(self, query, types=None, take=5):
            return [{"name": "Ed Sheeran"}, {"name": "Ed Harcourt"}] if query == "ed shreen" else []

    assert suggest(Picky(), "edshreen", "urn:entity:artist") == "Ed Sheeran"
    assert suggest(Picky(), "zzzzqqq", "urn:entity:artist") is None


def test_scout_unresolved_show_carries_suggestion():
    from aftershock.sync_scout import scout

    class Near:
        def search(self, query, types=None, take=5):
            return [{"name": "Wednesday", "entity_id": "w"}] if query == "Wednsday" and False else \
                [{"name": "Stranger Things", "entity_id": "s"}] if query.startswith("Strangr") else []

    out = scout(Near(), "Strangr Things")
    assert out["resolved"] is False and out["suggestion"] == "Stranger Things"


# ---- /api/title and the map on /api/storms -------------------------------------------------------------
class _StubModel:
    _pair_trials = defaultdict(int, {("BR", "US"): 10})  # the real model's counters are defaultdicts
    _pair_joins = defaultdict(int, {("BR", "US"): 4})

    def predict(self, event, candidates):
        return {c: 0.5 / (1 + i) for i, c in enumerate(sorted(candidates))}


def _row(country, week, show, season="N/A", category="TV (Non-English)"):
    return {"country_iso2": country, "week": week, "show_title": show, "season_title": season, "category": category}


@pytest.fixture
def title_files(tmp_path, monkeypatch):
    rows = [_row("US", "2024-03-03", "Squid Game", "Squid Game: Season 1"), _row("GB", "2024-03-10", "Squid Game", "Squid Game: Season 1"),
            _row("US", "2025-06-01", "Squid Game", "Squid Game: Season 3"),
            _row("US", "2023-01-01", "Old Hit"),  # charted only before the cutoff: not indexed
            _row("BR", "2026-10-11", "Café Nocturne"), _row("BR", "2026-10-18", "Café Nocturne"),
            _row("FR", "2026-10-18", "Fukrey Returns", category="Films (Non-English)"),
            _row("US", "2026-10-18", "Fukrey Returns", category="Films (Non-English)")]
    index = titles.build_index(rows, _StubModel(), ["BR", "FR", "GB", "US"], {"BR": "Brazil", "FR": "France", "GB": "United Kingdom", "US": "United States"},
                               date(2026, 10, 18), {("Fukrey Returns", "N/A")}, 4)
    (tmp_path / "titles.json").write_text(json.dumps(index), encoding="utf-8")
    storms = {"week": "2026-10-18", "ripples": [], "storms": [{"netflix_title": ["Fukrey Returns", "N/A"], "summary": {"id": "fukrey-returns"}}]}
    (tmp_path / "storms.json").write_text(json.dumps(storms), encoding="utf-8")
    monkeypatch.setattr(api, "TITLES", tmp_path / "titles.json")
    monkeypatch.setattr(api, "PRIVATE", tmp_path)
    return index


def test_title_lookup_ignores_case_accents_and_season(title_files):
    found = client.get("/api/title", params={"name": "  squid GAME season 1 "}).json()
    assert found["title"] == "Squid Game: Season 1" and found["season"] == "Season 1"
    assert found["first_week"] == "2024-03-03" and found["countries"] == [["US", "2024-03-03"], ["GB", "2024-03-10"]]
    assert found["still_spreading"] is False and found["storm_id"] is None
    assert [o["title"] for o in found["others"]] == ["Squid Game: Season 3"]
    assert client.get("/api/title", params={"name": "cafe nocturne"}).json()["title"] == "Café Nocturne"


def test_title_lookup_prefers_newest_season_and_tolerates_typos(title_files):
    assert client.get("/api/title", params={"name": "Squid Game"}).json()["season"] == "Season 3"
    assert client.get("/api/title", params={"name": "Squid Gam"}).json()["show"] == "Squid Game"


def test_title_lookup_rejects_weak_fuzzy_matches(title_files, tmp_path):
    # "The Sopranos" vs "The Orphans" is ratio 0.78: shares "the" and letters, but is not the same title
    rows = [_row("US", "2026-10-11", "The Orphans")]
    index = titles.build_index(rows, _StubModel(), ["US"], {"US": "United States"}, date(2026, 10, 18), set(), 4)
    (tmp_path / "titles.json").write_text(json.dumps(index), encoding="utf-8")
    assert client.get("/api/title", params={"name": "The Sopranos"}).status_code == 404
    assert client.get("/api/title", params={"name": "Orphans"}).json()["show"] == "The Orphans"  # whole word


def test_title_lookup_storm_and_forecast(title_files):
    storm = client.get("/api/title", params={"name": "Fukrey Returns"}).json()
    assert storm["storm_id"] == "fukrey-returns" and storm["still_spreading"] is True and "forecast" not in storm
    spreading = client.get("/api/title", params={"name": "Cafe Nocturne"}).json()
    assert spreading["still_spreading"] is True and spreading["storm_id"] is None
    assert spreading["forecast"]["origin"] == ["BR"] and spreading["forecast"]["horizon_weeks"] == 4
    assert [f["code"] for f in spreading["forecast"]["next"]] == ["FR", "GB", "US"]
    assert spreading["forecast"]["next"][2]["why"] == "United States joined 4 of 10 past breakouts that started in Brazil"


def test_title_lookup_not_found_and_limits(title_files):
    missing = client.get("/api/title", params={"name": "Zzzz Nothing"})
    assert missing.status_code == 404 and "No close match in Netflix's Top 10 since 2024" in missing.json()["detail"]
    assert client.get("/api/title", params={"name": "Old Hit"}).status_code == 404
    assert client.get("/api/title", params={"name": "x" * 81}).status_code == 422
    assert client.get("/api/title", params={"name": ""}).status_code == 422


def test_title_lookup_uses_no_live_slot(title_files):
    api._ripple_hits.clear()
    client.get("/api/title", params={"name": "Squid Game"})
    assert not any(api._ripple_hits.values())


def test_week_map_chance_of_at_least_one_and_top_titles(tmp_path, monkeypatch):
    def storm(sid, title, origin, fcs):
        return {"netflix_title": [title, "N/A"], "summary": {"id": sid, "title": title, "origin_countries": [{"code": origin, "name": origin}],
                                                              "top_forecast": None},
                "detail": {"spillover": {"forecasts": [{"code": c, "name": c.title(), "probability": p} for c, p in fcs]}}}
    data = {"week": "2026-10-18", "ripples": [], "storms": [storm("a", "A", "KR", [("bd", 0.4), ("fr", 0.1)]),
                                                            storm("b", "B", "JP", [("bd", 0.3)])]}
    (tmp_path / "storms.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(api, "PRIVATE", tmp_path)
    body = api.storms()
    assert body["map"]["origins"] == ["JP", "KR"]
    first = body["map"]["countries"][0]
    assert first["code"] == "bd" and first["chance"] == round(1 - 0.6 * 0.7, 4)
    assert [t["id"] for t in first["top"]] == ["a", "b"] and first["top"][0]["p"] == 0.4


@pytest.mark.parametrize("status, code, says", [(401, 503, "refused the API key"), (403, 503, "refused the API key"),
                                                (429, 503, "rate-limiting"), (500, 502, "did not answer")])
def test_live_lookup_failures_say_what_happened(monkeypatch, status, code, says):
    from aftershock.qloo import QlooError

    def refuse(*a, **k):
        raise QlooError(f"{status} on /search", status=status)
    _stub_scoring(monkeypatch)
    monkeypatch.setattr(api, "score_placements", refuse)
    resp = client.get("/api/ripple", params={"show": "X", "songs": "A|B"})
    assert resp.status_code == code and says in resp.json()["detail"]


def _archive_with(tmp_path, monkeypatch, sid="gone-show", week="2026-01-04"):
    from aftershock import storm_archive
    detail = {"title": "Gone Show", "origin_week": week}
    storm_archive.write_week(tmp_path, week, [{"summary": {"id": sid}, "detail": detail}])
    monkeypatch.setattr(api, "ARCHIVE", tmp_path)


def test_storm_falls_back_to_archive(tmp_path, monkeypatch):
    _archive_with(tmp_path, monkeypatch)
    body = client.get("/api/storms/gone-show").json()
    assert body["title"] == "Gone Show" and body["archived_week"] == "2026-01-04"


def test_storm_archive_prefers_most_recent_week(tmp_path, monkeypatch):
    from aftershock import storm_archive
    _archive_with(tmp_path, monkeypatch)
    storm_archive.write_week(tmp_path, "2026-02-01", [{"summary": {"id": "gone-show"}, "detail": {"title": "Newer"}}])
    assert client.get("/api/storms/gone-show").json()["archived_week"] == "2026-02-01"


def test_unknown_storm_404_sentence(tmp_path, monkeypatch):
    _archive_with(tmp_path, monkeypatch)
    resp = client.get("/api/storms/not-real")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No breakout called not-real in any week we have forecast."
