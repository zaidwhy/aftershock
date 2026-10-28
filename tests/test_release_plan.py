import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from aftershock import api, release_plan  # noqa: E402
from aftershock.qloo import QlooError  # noqa: E402
from aftershock.release_plan import MAX_CALLS, ReleaseInputError, plan_release  # noqa: E402

web = TestClient(api.app)

# Synthetic: no Qloo data. Top destination affinity per country decides the ranking.
AFFINITY = {"AE": 0.80, "GB": 0.71, "US": 0.65, "IN": 0.90, "CA": 0.40}
CODES = list(release_plan.CANDIDATES)


def destination(code, where=None):
    """Three real towns on the country's heatmap cells (`where` moves them elsewhere) and a village that Qloo's
    destination affinity loves but whose popularity is far below the floor."""
    if code not in AFFINITY:
        return {"results": {"entities": []}}
    ents = [{"name": f"Town {code}{i}", "entity_id": f"{code}{i}", "properties": {"geocode": {"country_code": code}},
             "location": {"lat": (where or cell(code, i))[0], "lon": (where or cell(code, i))[1]},
             "popularity": 0.9 - i * 0.01, "query": {"affinity": AFFINITY[code] - i * 0.05}} for i in range(3)]
    ents.append({"name": f"Village {code}", "entity_id": f"v{code}", "properties": {"geocode": {"country_code": code}},
                 "location": {"lat": 1.0, "lon": 2.0}, "popularity": 0.05, "query": {"affinity": 0.99}})
    return {"results": {"entities": ents}}


def cell(code, i):
    """Cell i of a country's heatmap: countries sit 10 degrees apart, cells 1.2 apart (over the 60 km naming gap)."""
    n = CODES.index(code)
    return round(n * 10 + i * 1.2, 1), 20.0 + n


def heatmap(country_name):
    code = next(c for c, n in release_plan.CANDIDATES.items() if n == country_name)
    return {"results": {"heatmap": [{"location": {"latitude": cell(code, i)[0], "longitude": cell(code, i)[1]},
                                     "query": {"affinity": 1.0 - i * 0.01, "affinity_rank": 100 - i}} for i in range(8)]}}


def fake_geocode(lat, lon):
    return f"place@{lat:.1f},{lon:.1f}"


def place_name(code, i):
    return f"Town {code}{i}"


def run(client, *args, **kwargs):
    return plan_release(client, *args, geocode=kwargs.pop("geocode", fake_geocode), **kwargs)


class FakeClient:
    where = None  # set to (lat, lon) to put every destination far from its heatmap

    def __init__(self, known=("Act",), comparables=(), taste_extra=()):
        self.known, self.comparables, self.taste_extra = set(known), set(comparables), list(taste_extra)
        self.searches, self.gets = [], []

    def search(self, query, types=None, take=5):
        self.searches.append((query, types))
        if query in self.known | self.comparables:
            return [{"name": query, "entity_id": f"id-{query}", "types": [(types or "").split(",")[0]]}]
        # /search always returns its nearest hit, which must not count as a match
        return [{"name": query + ": Something Else", "entity_id": "nearest", "types": ["urn:entity:tv_show"]}]

    def get(self, path, params):
        self.gets.append((path, dict(params)))
        kind = params.get("filter.type")
        if kind == "urn:entity:destination":
            assert params["take"] == release_plan.DESTINATION_TAKE
            return destination(params["filter.geocode.country_code"], self.where)
        if kind == "urn:heatmap":
            return heatmap(params["filter.location.query"])
        if kind == "urn:entity:place":
            return {"results": {"entities": [{"name": "Hall", "location": {"lat": 1.0, "lon": 2.0},
                                              "properties": {"address": "1  Main St"},
                                              "tags": [{"id": "urn:tag:category:place:bar", "name": "Bar"},
                                                       {"id": params["filter.tags"].split(",")[0], "name": "Venue"}]}]}}
        ents = [{"name": n, "entity_id": f"t-{n}"} for n in ["Act", "Other A", "Other B", *self.taste_extra]]
        return {"results": {"entities": ents}}


def test_title_known_uses_the_title_as_signal():
    client = FakeClient()
    out = run(client, "Act", "music", like=["Never Searched"])
    assert out["resolved"] and out["signal"]["used"] == "title"
    assert out["signal"]["entities"][0]["id"] == "id-Act"
    assert [q for q, _ in client.searches] == ["Act"]


def test_unknown_title_falls_back_to_comparables_comma_joined():
    client = FakeClient(known=(), comparables=("A", "B", "C", "D"))
    out = run(client, "Unreleased", "series", like=["A", "B", "Nope", "C", "D"])
    assert out["signal"]["used"] == "comparables"
    assert [e["name"] for e in out["signal"]["entities"]] == ["A", "B", "C"]
    insight = next(p for path, p in client.gets if p.get("filter.type") == "urn:entity:destination")
    assert insight["signal.interests.entities"] == "id-A,id-B,id-C"
    assert "does not know 'Unreleased'" in out["steps"][0]["note"]


def test_refuses_when_nothing_resolves_and_never_guesses():
    client = FakeClient(known=())
    out = run(client, "Nobody", "film", like=["Also Nobody"])
    assert out["resolved"] is False and "Nobody" in out["reason"] and out["try"]
    assert client.gets == []
    assert out["steps"][0]["ok"] is False and out["calls"] == 2


def test_nearest_hit_with_a_longer_name_is_not_a_match():
    out = plan_release(FakeClient(known=()), "Zakir", "comedy")
    assert out["resolved"] is False


def test_comma_qualified_person_name_matches():
    class Person(FakeClient):
        def search(self, query, types=None, take=5):
            return [{"name": f"{query}, Comedian", "entity_id": "p1", "types": ["urn:entity:person"]}]
    out = run(Person(), "Zakir Khan", "comedy")
    assert out["signal"]["entities"][0] == {"name": "Zakir Khan, Comedian", "id": "p1", "type": "urn:entity:person"}


def test_countries_ranked_by_top_destination_affinity_with_heatmap_places_for_the_top_three():
    out = run(FakeClient(), "Act", "comedy", n_countries=5)
    assert [c["code"] for c in out["countries"]] == ["IN", "AE", "GB", "US", "CA"]
    assert out["countries"][0]["score"] == 0.9 and out["countries_checked"] == len(release_plan.CANDIDATES)
    top, rest = out["countries"][:3], out["countries"][3:]
    assert out["countries"][0]["score"] == 0.9  # the village's 0.99 is below the popularity floor
    for c in top:
        hs = c["hotspots"]
        assert len(hs["cells"]) == 8 and hs["places"] == [place_name(c["code"], i) for i in range(3)]
        assert hs["place_cells"][0] == list(cell(c["code"], 0))
        assert [x["name"] for x in c["cities"]] == hs["places"] and c["cities"][0]["density"] > c["cities"][1]["density"]
    assert all("hotspots" not in c and "cities" not in c and "candidates" not in c for c in rest)
    assert out["countries"][0]["summary"].startswith("India leads: Qloo's destination affinity 0.90, the highest of the 24 countries")
    assert "0.10 below India" in out["countries"][1]["summary"] and "peaks around Town" in out["countries"][1]["summary"]
    assert all("probab" not in c["summary"] for c in out["countries"])


def test_one_destination_call_per_candidate_country_and_a_failed_one_is_skipped():
    class Flaky(FakeClient):
        def get(self, path, params):
            if params.get("filter.geocode.country_code") == "AE":
                raise QlooError("500 on /v2/insights", status=500)
            return super().get(path, params)
    client = Flaky()
    out = run(client, "Act", "comedy")
    asked = [p["filter.geocode.country_code"] for _, p in client.gets if p.get("filter.type") == "urn:entity:destination"]
    assert sorted(asked + ["AE"]) == sorted(release_plan.CANDIDATES)  # AE raised before the fake logged it
    assert "AE" not in [c["code"] for c in out["countries"]]
    assert out["steps"][1]["ok"] is False and "returned nothing" in out["steps"][1]["note"]


def test_a_refused_key_ends_the_plan():
    class Refused(FakeClient):
        def get(self, path, params):
            raise QlooError("401 on /v2/insights", status=401)
    with pytest.raises(QlooError):
        run(Refused(), "Act", "comedy")


def test_call_cap_is_enforced_and_counts_every_call():
    client = FakeClient(comparables=("A", "B", "C", "D", "E"), known=())
    out = run(client, "Unreleased", "film", like=["A", "B", "C"], n_countries=8)
    assert out["calls"] == len(client.searches) + len(client.gets) <= MAX_CALLS
    many = {code: release_plan.CANDIDATES[code] for code in AFFINITY} | {f"C{i}": f"Country {i}" for i in range(60)}
    capped = FakeClient()
    out = run(capped, "Act", "music", countries=many)
    assert out["calls"] == MAX_CALLS == len(capped.searches) + len(capped.gets)
    assert out["resolved"] and out["venues"] == [] and any("cap" in c for c in out["caveats"])


def test_venue_calls_carry_the_tag_filter_around_each_top_countrys_strongest_place():
    for kind, tag in (("comedy", "urn:tag:category:place:comedy_club"), ("film", "urn:tag:category:place:movie_theater"),
                      ("music", "urn:tag:category:place:concert_hall,urn:tag:category:place:live_music_venue")):
        client = FakeClient()
        out = run(client, "Act", kind)
        places = [p for _, p in client.gets if p.get("filter.type") == "urn:entity:place"]
        assert len(places) == 3 and all(p["filter.tags"] == tag for p in places)
        assert sorted(p["filter.location"] for p in places) == sorted(
            "POINT({1} {0})".format(*cell(code, 0)) for code in ("IN", "AE", "GB"))
        assert [v["city"] for v in out["venues"]] == [place_name(c, 0) for c in ("IN", "AE", "GB")]
        venue = out["venues"][0]["venues"][0]
        assert venue["address"] == "1 Main St" and venue["tags"][0] == "Venue" and len(venue["tags"]) <= 3


def test_local_taste_drops_signal_entities_for_top_two_countries():
    client = FakeClient(taste_extra=["Another"])
    out = run(client, "Act", "music")
    assert [t["code"] for t in out["local_taste"]] == ["IN", "AE"]
    for row in out["local_taste"]:
        for domain in ("tv_show", "movie", "artist"):
            assert "Act" not in row[domain] and row[domain][:2] == ["Other A", "Other B"]
    taste = [p for _, p in client.gets if "signal.location.query" in p]
    assert len(taste) == 6 and {p["signal.location.query"] for p in taste} == {"India", "United Arab Emirates"}


def test_steps_trail_says_which_call_produced_what_and_lists_every_call_without_a_key():
    client = FakeClient()
    out = run(client, "Act", "comedy")
    assert [s["tool"] for s in out["steps"]] == ["qloo_search", "qloo_destinations", "qloo_heatmap", "qloo_places",
                                                 "qloo_insights"]
    assert sum(s["calls"] for s in out["steps"]) == out["calls"] == len(client.searches) + len(client.gets)
    countries, cities = out["steps"][1], out["steps"][2]
    assert countries["calls"] == 24 and len(countries["varies"]["filter.geocode.country_code"]) == 24
    assert countries["params"]["filter.type"] == "urn:entity:destination" and "rank" in countries["note"]
    assert cities["calls"] == 3 and cities["params"]["filter.type"] == "urn:heatmap"
    assert cities["varies"]["filter.location.query"] == ["India", "United Arab Emirates", "United Kingdom"]
    assert "no Nominatim lookup was needed" in cities["note"] and "destinations" in cities["note"]
    assert "key" not in str(out["steps"]).lower().replace("keep", "")


@pytest.mark.parametrize("name,kind,like,field", [
    ("", "music", (), "name"), ("x" * 121, "music", (), "name"), ("Act", "podcast", (), "kind"),
    ("Act", "music", ["a"] * 6, "like"), ("Act", "music", ["y" * 121], "like")])
def test_validate_names_the_field_and_limit(name, kind, like, field):
    with pytest.raises(ReleaseInputError) as err:
        run(FakeClient(), name, kind, like)
    assert str(err.value).startswith(field) or f" {field} " in str(err.value)


@pytest.mark.parametrize("params,field", [
    ({"name": "", "kind": "music"}, "name"), ({"name": "x" * 121, "kind": "music"}, "name"),
    ({"name": "Act", "kind": "podcast"}, "kind"), ({"name": "Act"}, "kind"), ({"kind": "music"}, "name"),
    ({"name": "Act", "kind": "music", "like": "a,b,c,d,e,f"}, "like"),
    ({"name": "Act", "kind": "music", "like": "y" * 121}, "like"),
    ({"name": "   ", "kind": "music"}, "name")])
def test_api_bounds_return_422_naming_the_field(params, field):
    resp = web.get("/api/release", params=params)
    assert resp.status_code == 422
    assert field in str(resp.json()["detail"])


def test_api_runs_the_plan_with_split_comparables_under_the_live_limit(monkeypatch):
    seen = {}

    def fake(client, name, kind, like):
        seen.update(name=name, kind=kind, like=like)
        return {"resolved": True}
    monkeypatch.setattr(api.release_plan, "plan_release", fake)
    monkeypatch.setattr(api, "Qloo", lambda **k: None)
    api._ripple_hits.clear()
    resp = web.get("/api/release", params={"name": " An  Act ", "kind": "series", "like": "Squid Game, Alice in Borderland"})
    assert resp.status_code == 200 and seen == {"name": "An Act", "kind": "series", "like": ["Squid Game", "Alice in Borderland"]}
    codes = [web.get("/api/release", params={"name": "A", "kind": "film"}).status_code for _ in range(11)]
    assert codes[-1] == 429


def test_a_place_with_no_tagged_venues_is_replaced_by_the_next_one_down():
    india_top = "POINT({1} {0})".format(*cell("IN", 0))

    class Sparse(FakeClient):
        def get(self, path, params):
            if params.get("filter.type") == "urn:entity:place" and params["filter.location"] == india_top:
                self.gets.append((path, dict(params)))
                return {"results": {"entities": []}}  # the strongest place has no tagged venue
            return super().get(path, params)
    client = Sparse()
    out = run(client, "Act", "comedy")
    places = [p for _, p in client.gets if p.get("filter.type") == "urn:entity:place"]
    assert len(places) == 4
    assert [v["city"] for v in out["venues"]] == [place_name("AE", 0), place_name("GB", 0), place_name("IN", 1)]
    assert f"none near {place_name('IN', 0)}" in out["steps"][3]["note"] and out["steps"][3]["calls"] == 4


class Elsewhere(FakeClient):
    where = (-80.0, -170.0)  # no destination has heatmap cells within 40 km


def test_cities_come_from_destinations_without_any_geocoding():
    def forbidden(lat, lon):
        raise AssertionError("Nominatim must not be on the live path when destinations have cells nearby")
    out = run(FakeClient(), "Act", "comedy", geocode=forbidden)
    assert out["countries"][0]["hotspots"]["places"] == [place_name("IN", i) for i in range(3)]
    assert "no Nominatim lookup was needed" in out["steps"][2]["note"]


def test_geocoding_is_only_the_fallback_when_no_destination_has_cells_nearby():
    out = run(Elsewhere(), "Act", "comedy")
    for c in out["countries"][:3]:
        assert c["hotspots"]["places"] == [fake_geocode(*cell(c["code"], i)) for i in range(3)] and "cities" not in c
    assert "reverse geocoding" in out["steps"][2]["note"]


def test_a_failing_geocoder_keeps_the_cells_drops_the_names_and_does_not_fail_the_plan():
    def down(lat, lon):
        raise OSError("nominatim unreachable")
    out = run(Elsewhere(), "Act", "comedy", geocode=down)
    assert out["resolved"]
    for c in out["countries"][:3]:
        assert len(c["hotspots"]["cells"]) == 8 and c["hotspots"]["places"] == []
        assert "peaks around" not in c["summary"]
    # venues are anchored on each country's strongest cell instead
    assert len(out["venues"]) == 3 and out["venues"][0]["city"].startswith("the strongest cell")


def cand(name, lat, lon, affinity=0.5, popularity=0.9):
    return {"name": name, "lat": lat, "lon": lon, "affinity": affinity, "popularity": popularity}


CELLS = [[10.0, 10.0, 1.0], [10.0, 10.1, 0.9], [20.0, 20.0, 0.5], [30.0, 30.0, 0.04]]


def test_pick_cities_ranks_by_heatmap_density_then_affinity_and_drops_empty_ones():
    picked = release_plan._pick_cities([cand("Far", 50.0, 50.0, 0.99), cand("Weak", 20.0, 20.0, 0.9),
                                        cand("Dense", 10.0, 10.05, 0.1)], CELLS)
    assert [c["name"] for c in picked] == ["Dense", "Weak"]  # Far has no cells within 40 km
    assert picked[0]["density"] == 1.9 and picked[1]["density"] == 0.5
    tie = release_plan._pick_cities([cand("Low", 20.0, 20.0, 0.2), cand("High", 20.2, 20.0, 0.8)], CELLS)
    assert [c["name"] for c in tie] == ["High", "Low"]  # same cell, higher destination affinity first


def test_pick_cities_merges_near_duplicates_into_the_most_popular_and_drops_noise():
    picked = release_plan._pick_cities([cand("Old Name", 10.0, 10.0, popularity=0.7),
                                        cand("Big City", 10.05, 10.0, popularity=0.98),
                                        cand("Ward", 10.0, 10.02, popularity=0.74),
                                        cand("Noise", 30.0, 30.0)], CELLS)  # density 0.04 is under a tenth of 1.9
    assert [c["name"] for c in picked] == ["Big City"]


def test_popularity_floor_keeps_cities_and_drops_villages():
    body = {"results": {"entities": [
        {"name": n, "properties": {"geocode": {"country_code": "XX"}}, "location": {"lat": 1.0, "lon": 2.0},
         "popularity": pop, "query": {"affinity": 0.9}}
        for n, pop in (("Village", 0.003), ("Resort town", 0.378), ("Mid-size city", 0.42), ("Capital", 0.98))]}}
    assert [c["name"] for c in release_plan._candidates(body, "XX")] == ["Mid-size city", "Capital"]


def test_a_slow_geocoder_stops_naming_once_its_time_budget_is_spent():
    geo = release_plan._Geocode(fake_geocode, budget=-1)
    with pytest.raises(OSError):
        geo(1.0, 2.0)
    assert release_plan._Geocode(fake_geocode, budget=60)(1.0, 2.0) == "place@1.0,2.0"


def test_the_default_geocoder_caches_under_tmp_on_vercel(monkeypatch):
    seen = {}
    monkeypatch.setattr(release_plan.audience_map, "nominatim_name", lambda lat, lon, cache_dir=None: seen.update(d=cache_dir))
    monkeypatch.setenv("VERCEL", "1")
    release_plan._Geocode()(1.0, 2.0)
    assert Path(seen["d"]).as_posix() == "/tmp/nominatim-cache"
    monkeypatch.delenv("VERCEL")
    release_plan._Geocode()(1.0, 2.0)
    assert seen["d"] is None


def test_a_read_only_cache_costs_the_cache_not_the_answer(monkeypatch, tmp_path):
    from aftershock import hotspots, qloo
    blocker = tmp_path / "file"
    blocker.write_text("x")  # a directory path under a file cannot be created or written
    unwritable = blocker / "cache"

    class Resp:
        status_code, headers = 200, {}

        def json(self):
            return {"results": {}}
    monkeypatch.setattr(qloo, "CACHE_DIR", unwritable)
    monkeypatch.setattr(qloo.httpx, "get", lambda *a, **k: Resp())
    monkeypatch.setattr(qloo, "MIN_INTERVAL_S", 0)
    client = qloo.Qloo(api_key="k", call_budget=5)
    assert client.get("/v2/insights", {"a": 1}) == {"results": {}}

    class Nominatim(Resp):
        def json(self):
            return {"address": {"city": "Testville"}}

        def raise_for_status(self):
            pass
    monkeypatch.setattr(hotspots.httpx, "get", lambda *a, **k: Nominatim())
    monkeypatch.setattr(hotspots, "_last_request", [1e12])
    monkeypatch.setattr(hotspots.time, "sleep", lambda s: None)
    assert hotspots.nominatim_name(1.0, 2.0, cache_dir=unwritable) == "Testville"
