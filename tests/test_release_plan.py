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
            tag = params["filter.tags"].split(",")[0]
            where = params["filter.location"]
            return {"results": {"entities": [{"name": f"Hall {where}", "entity_id": f"hall-{where}",
                                              "location": {"lat": 1.0, "lon": 2.0},
                                              "properties": {"address": "1  Main St"},
                                              "tags": [{"id": "urn:tag:category:place:bar", "name": "Bar"},
                                                       {"id": tag, "name": tag.rsplit(":", 1)[-1].replace("_", " ").title()}]}]}}
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
    assert out["steps"][0]["ok"] is False and out["calls"] == 4  # each name is tried by kind, then across all types


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
    assert out["countries"][0]["summary"].startswith("India is the best match: Qloo match score 0.90, the highest of the 24 countries")
    assert "0.10 below India" in out["countries"][1]["summary"] and "concentrated around Town" in out["countries"][1]["summary"]
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
        assert venue["address"] == "1 Main St" and len(venue["tags"]) <= 3
        assert venue["tags"][0] == tag.split(",")[0].rsplit(":", 1)[-1].replace("_", " ").title() and "id" not in venue


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

    def fake(client, name, kind, like, **options):
        seen.update(name=name, kind=kind, like=like, **options)
        return {"resolved": True}
    monkeypatch.setattr(api.release_plan, "plan_release", fake)
    monkeypatch.setattr(api, "Qloo", lambda **k: None)
    api._ripple_hits.clear()
    resp = web.get("/api/release", params={"name": " An  Act ", "kind": "series", "like": "Squid Game, Alice in Borderland"})
    assert resp.status_code == 200 and seen == {
        "name": "An Act", "kind": "series", "like": ["Squid Game", "Alice in Borderland"], "region": "any", "home": None,
        "goal": "premiere"}
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


# ---- name resolution: akas, retry across types ----------------------------------------------------------

SQUID = {"name": "Squid Game", "entity_id": "id-squid", "types": ["urn:entity:tv_show"],
         "properties": {"akas": [{"language": "es", "value": "El juego del calamar"},
                                 {"language": "ko", "value": "오징어 게임"}]}}


class Catalog(FakeClient):
    """A search that answers like Qloo: only entities whose type is in `types`, else the nearest unrelated hit."""

    def __init__(self, *entities):
        super().__init__(known=())
        self.entities = list(entities)

    def search(self, query, types=None, take=5):
        self.searches.append((query, types))
        wanted = set((types or "").split(","))
        fold = release_plan._fold
        hits = [e for e in self.entities if set(e["types"]) & wanted
                and fold(query) in {fold(e["name"]), *(fold(a["value"]) for a in e.get("properties", {}).get("akas", []))}]
        return hits or [{"name": "Game of Thrones: Nearest", "entity_id": "nearest", "types": ["urn:entity:tv_show"]},
                        {"name": "그 다른 노래", "entity_id": "other-korean", "types": ["urn:entity:artist"]}]


def test_a_korean_alternative_title_resolves_to_the_entity():
    out = run(Catalog(SQUID), "오징어 게임", "series")
    assert out["resolved"] and out["signal"]["used"] == "title"
    assert out["signal"]["entities"][0] == {"name": "Squid Game", "id": "id-squid", "type": "urn:entity:tv_show"}


def test_a_non_latin_name_never_matches_another_non_latin_hit_by_default():
    # norm() turns every non-Latin name into "", which would have made the unrelated Korean artist a match
    out = run(Catalog(), "오징어 게임", "music")
    assert out["resolved"] is False


def test_folding_keeps_accents_and_ignores_case_and_spacing():
    hit = {"name": "Amélie", "entity_id": "a", "types": ["urn:entity:movie"],
           "properties": {"akas": [{"language": "fr", "value": "Le Fabuleux Destin d'Amélie Poulain"}]}}
    assert run(Catalog(hit), "  LE fabuleux   destin d'amélie poulain ", "film")["signal"]["entities"][0]["id"] == "a"
    assert run(Catalog(hit), "amelie poulain", "film")["resolved"] is False


def test_a_name_missing_under_the_chosen_kind_is_retried_across_all_types_and_says_so():
    client = Catalog(SQUID)
    out = run(client, "Squid Game", "music")
    assert out["signal"]["used"] == "title" and out["signal"]["entities"][0]["type"] == "urn:entity:tv_show"
    assert [t for _, t in client.searches] == ["urn:entity:artist", release_plan.ALL_TYPES]
    assert "found as a TV show although you chose music" in out["steps"][0]["note"]
    assert out["steps"][0]["calls"] == 2


def test_each_comparable_is_retried_across_all_types_too():
    client = Catalog(SQUID)
    out = run(client, "Unreleased Act", "music", like=["Squid Game"])
    assert out["signal"]["used"] == "comparables" and out["signal"]["entities"][0]["id"] == "id-squid"
    assert "'Squid Game' was found as a TV show although you chose music" in out["steps"][0]["note"]
    assert [t for _, t in client.searches] == ["urn:entity:artist", release_plan.ALL_TYPES] * 2


def test_a_name_found_under_the_chosen_kind_is_not_retried():
    client = Catalog(SQUID)
    run(client, "Squid Game", "series")
    assert len(client.searches) == 1


# ---- region, home, goal, scores ---------------------------------------------------------------------------

def asked_codes(client):
    return sorted(p["filter.geocode.country_code"] for _, p in client.gets if p.get("filter.type") == "urn:entity:destination")


def test_region_any_keeps_exactly_the_original_24_and_a_region_uses_every_pool_country_in_it():
    base = FakeClient()
    out = run(base, "Act", "music")
    assert asked_codes(base) == sorted(release_plan.CANDIDATES) and len(release_plan.CANDIDATES) == 24
    assert out["countries_checked"] == 24 and out["region"] == "any"
    asia = FakeClient()
    out = run(asia, "Act", "music", region="asia")
    assert asked_codes(asia) == sorted(release_plan.REGIONS["asia"]) and out["countries_checked"] == 11
    assert {"TH", "MY", "VN", "TW", "PK"} <= set(asked_codes(asia)) and out["region"] == "asia"
    names = [code for region in release_plan.REGIONS.values() for code in region]
    assert len(names) == len(set(names)) and set(names) == set(release_plan.POOL)  # each pool country in one region


def test_home_is_left_out_of_the_ranking_the_calls_and_named_in_the_steps():
    client = FakeClient()
    out = run(client, "Act", "music", home="in")
    assert out["home"] == "IN" and "IN" not in asked_codes(client) and out["countries_checked"] == 23
    assert "IN" not in [c["code"] for c in out["countries"]] and "IN" not in [s["code"] for s in out["scores"]]
    assert out["countries"][0]["code"] == "AE" and "IN is left out as the home market" in out["steps"][1]["note"]


def test_scores_list_every_country_with_data_best_first_not_just_the_top_n():
    out = run(FakeClient(), "Act", "music", n_countries=2)
    assert [s["code"] for s in out["scores"]] == ["IN", "AE", "GB", "US", "CA"] and len(out["countries"]) == 2
    assert out["scores"][0] == {"code": "IN", "name": "India", "score": 0.9}
    assert [s["score"] for s in out["scores"]] == sorted((s["score"] for s in out["scores"]), reverse=True)


def venue_tags(client):
    return {p["filter.tags"] for _, p in client.gets if p.get("filter.type") == "urn:entity:place"}


def test_goal_picks_the_venues_and_defaults_by_kind():
    tour, premiere = "urn:tag:category:place:comedy_club", "urn:tag:category:place:movie_theater"
    for kind, goal, tags, effective in (("comedy", None, {tour}, "tour"), ("film", None, {premiere}, "premiere"),
                                        ("series", None, {premiere}, "premiere"),
                                        ("comedy", "premiere", {premiere}, "premiere"),
                                        ("music", "premiere", {premiere}, "premiere")):
        client = FakeClient()
        out = run(client, "Act", kind, goal=goal)
        assert venue_tags(client) == tags and out["goal"] == effective
    music = FakeClient()
    run(music, "Act", "music")
    assert venue_tags(music) == {"urn:tag:category:place:concert_hall,urn:tag:category:place:live_music_venue"}


def test_a_film_with_goal_tour_is_treated_as_a_premiere_and_says_so():
    client = FakeClient()
    out = run(client, "Act", "film", goal="tour")
    assert out["goal"] == "premiere" and venue_tags(client) == {"urn:tag:category:place:movie_theater"}
    assert "treated as a premiere" in out["steps"][3]["note"]


def test_goal_digital_makes_no_venue_calls_and_says_so():
    client = FakeClient()
    out = run(client, "Act", "music", goal="digital")
    assert out["goal"] == "digital" and out["venues"] == [] and venue_tags(client) == set()
    venue_step = out["steps"][3]
    assert venue_step["calls"] == 0 and "digital" in venue_step["note"]
    assert out["calls"] == len(client.searches) + len(client.gets)
    assert not any("venue tag" in c for c in out["caveats"])


def test_refusals_keep_reason_and_try_and_echo_the_options():
    out = run(FakeClient(known=()), "Nobody", "film", region="europe", home="gb", goal="digital")
    assert out["resolved"] is False and out["reason"] and out["try"] and out["scores"] == []
    assert "add 2 or 3 similar film titles" in out["try"][0]
    assert (out["region"], out["home"], out["goal"]) == ("europe", "GB", "digital")
    with_like = run(FakeClient(known=()), "Nobody", "film", like=["Also Nobody"])
    assert "comparables" in with_like["try"][0] and with_like["try"][1:]


@pytest.mark.parametrize("kwargs,field", [({"region": "mars"}, "region"), ({"home": "India"}, "home"),
                                          ({"home": "1N"}, "home"), ({"goal": "party"}, "goal")])
def test_bad_options_name_the_field(kwargs, field):
    with pytest.raises(ReleaseInputError) as err:
        run(FakeClient(), "Act", "music", **kwargs)
    assert str(err.value).startswith(field)


@pytest.mark.parametrize("params,field", [({"region": "mars"}, "region"), ({"goal": "party"}, "goal"),
                                          ({"home": "India"}, "home"), ({"home": "I"}, "home")])
def test_api_rejects_bad_region_home_and_goal_with_422_naming_the_field(params, field):
    resp = web.get("/api/release", params={"name": "Act", "kind": "music", **params})
    assert resp.status_code == 422 and field in str(resp.json()["detail"])


# ---- venue quality: non-venues, opera houses, duplicates, city names ------------------------------------------

def place(name, entity_id, *tags, lat=1.0, lon=2.0):
    return {"name": name, "entity_id": entity_id, "location": {"lat": lat, "lon": lon},
            "tags": [{"id": f"urn:tag:category:place:{t.lower().replace(' ', '_')}", "name": t} for t in tags]}


class Places(FakeClient):
    """Every venue call returns `rows`, in order, whatever the city."""
    rows = ()

    def get(self, path, params):
        if params.get("filter.type") == "urn:entity:place":
            self.gets.append((path, dict(params)))
            return {"results": {"entities": list(self.rows)}}
        return super().get(path, params)


def venue_names(out):
    return [[v["name"] for v in city["venues"]] for city in out["venues"]]


def test_non_venues_are_dropped_and_counted_in_the_step_note():
    class Comedy(Places):
        rows = [place("Comedy Store", "a", "Comedy club", "Performing arts theater"),
                place("The Integral Space", "b", "Comedy club", "Mental health service", "Homeopath"),
                place("rynO interiO", "c", "Comedy club", "Interior designer"),
                place("Grand Hotel", "d", "Comedy club", "Hotel"),
                place("Bistro", "e", "Restaurant", "Bar")]  # no performing-arts tag at all
    out = run(Comedy(), "Act", "comedy")
    assert all(names == ["Comedy Store"] for names in venue_names(out)[:1])
    note = out["steps"][3]["note"]
    assert f"Dropped {4 * out['steps'][3]['calls']} non-venues" in note


def test_a_non_venue_count_is_exact_for_one_city():
    class One(Places):
        rows = [place("Club", "a", "Comedy club"), place("Clinic", "b", "Comedy club", "Homeopath"),
                place("Grand Hotel", "c", "Comedy club", "Hotel")]
    out = run(One(), "Act", "comedy", n_countries=1)
    assert venue_names(out) == [["Club"]]
    assert f"Dropped {2 * out['steps'][3]['calls']} non-venues" in out["steps"][3]["note"]  # 2 in each city's call


def test_music_tours_drop_opera_houses_but_other_goals_keep_them():
    rows = [place("Concert Arena", "a", "Concert hall"), place("Teatro Colon", "b", "Opera house", "Concert hall")]

    class Music(Places):
        pass
    Music.rows = rows
    assert venue_names(run(Music(), "Act", "music", n_countries=1)) == [["Concert Arena"]]
    Comedy = type("Comedy", (Places,), {"rows": [place("Opera Theatre", "b", "Opera house", "Performing arts theater")]})
    assert venue_names(run(Comedy(), "Act", "comedy", n_countries=1)) == [["Opera Theatre"]]


def test_a_venue_needs_a_performing_arts_style_tag_for_the_goal():
    cinema = [place("Odeon", "a", "Movie theater", "Candy store", "Popcorn store"),
              place("Playhouse", "b", "Performing arts theater")]  # a stage is not a cinema
    club = [place("Comedy Store", "c", "Comedy club"), place("Odeon", "d", "Movie theater")]
    assert venue_names(run(type("Film", (Places,), {"rows": cinema})(), "Act", "film", n_countries=1)) == [["Odeon"]]
    assert venue_names(run(type("Tour", (Places,), {"rows": club})(), "Act", "comedy", n_countries=1)) == [["Comedy Store"]]


def test_a_venue_listed_under_two_cities_is_kept_under_the_first_and_counted():
    class Shared(Places):
        rows = [place("Dad's Garage", "garage", "Comedy club"), place("Second Venue", "second", "Comedy club")]
    out = run(Shared(), "Act", "comedy")
    names = venue_names(out)
    assert names[0] == ["Dad's Garage", "Second Venue"]
    assert out["venues"][0]["city"] == place_name("IN", 0) and len(out["venues"]) == 1  # later cities had only repeats
    assert "duplicate" in out["steps"][3]["note"]


def test_bangkok_and_bangkok_metropolis_are_one_city_unrelated_neighbours_are_not():
    cells = [[13.75, 100.5, 1.0]]
    picked = release_plan._pick_cities([cand("Bangkok", 13.75, 100.5, popularity=0.99),
                                        cand("Bangkok Metropolis", 13.75, 100.5 + 0.35, popularity=0.8),  # ~38 km
                                        cand("Nonthaburi", 13.75, 100.5 + 0.3, popularity=0.7)], cells)
    assert [c["name"] for c in picked] == ["Bangkok", "Nonthaburi"]
    assert release_plan._same_city(cand("Playa del Carmen", 20.6, -87.1), cand("Playa Norte", 20.6, -86.8))
    assert not release_plan._same_city(cand("Santa Clara", 37.3, -121.9), cand("Santa Rosa", 38.44, -122.7))  # same first word, 140 km


def test_a_school_or_gym_tag_does_not_drop_a_place_with_a_strong_performance_tag_but_a_restaurant_needs_one():
    class Mixed(Places):
        rows = [place("Playhouse", "a", "Comedy club", "Performing arts theater", "Drama school"),
                place("Brasserie", "b", "Live music venue", "Restaurant"),
                place("Bar Stage", "c", "Live music venue", "Gym")]
    music = run(type("M", (Mixed,), {})(), "Act", "music", n_countries=1)
    assert venue_names(music) == [["Playhouse"]]  # live-music-only places with a restaurant or gym tag are not venues
    assert venue_names(run(Mixed(), "Act", "comedy", n_countries=1)) == [["Playhouse"]]


def test_a_place_whose_name_says_it_is_an_interior_design_firm_is_dropped():
    class Named(Places):
        rows = [place("rynO interiO", "a", "Comedy club"), place("Laugh Factory", "b", "Comedy club")]
    assert venue_names(run(Named(), "Act", "comedy", n_countries=1)) == [["Laugh Factory"]]
