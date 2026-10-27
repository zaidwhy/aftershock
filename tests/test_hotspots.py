import httpx

from aftershock import hotspots as hs
from aftershock.qloo import QlooError


def cell(lat, lon, affinity, rank):
    return {"location": {"latitude": lat, "longitude": lon, "geohash": "x"},
            "query": {"affinity": affinity, "affinity_rank": rank, "popularity": 0.1}}


class FakeClient:
    def __init__(self, entities=None, error=None):
        self.entities, self.error, self.calls = entities or [], error, []

    def get(self, path, params):
        self.calls.append((path, params))
        if self.error:
            raise self.error
        return {"results": {"heatmap": self.entities}}


def test_top_cells_caps_at_120_and_orders_by_affinity():
    entities = [cell(i * 0.01, 0.0, i / 1000, i / 1000) for i in range(300)]
    cells = hs.top_cells({"results": {"heatmap": entities}})
    assert len(cells) == 120
    assert cells[0][0] == 2.99 and cells[0][2] == 1.0
    assert all(0 < c[2] <= 1 for c in cells)
    assert [c[2] for c in cells] == sorted((c[2] for c in cells), reverse=True)


def test_places_skip_cells_within_60km_and_cap_at_three():
    # A and B are ~11 km apart, C ~110 km from A, D ~220 km, E ~330 km.
    entities = [cell(10.0, 20.0, 0.9, 0.9), cell(10.1, 20.0, 0.8, 0.8), cell(11.0, 20.0, 0.7, 0.7),
                cell(12.0, 20.0, 0.6, 0.6), cell(13.0, 20.0, 0.5, 0.5)]
    asked = []

    def geocode(lat, lon):
        asked.append((lat, lon))
        return f"place@{lat}"

    out = hs.hotspots(FakeClient(entities), "id1", "Testland", geocode=geocode)
    assert out["places"] == ["place@10.0", "place@11.0", "place@12.0"]
    assert (10.1, 20.0) not in asked
    assert len(out["cells"]) == 5
    assert out["cells"][0] == [10.0, 20.0, 1.0]


def test_request_uses_heatmap_filter():
    client = FakeClient([cell(1.0, 1.0, 0.5, 1)])
    hs.hotspots(client, "id1", "Testland", geocode=lambda lat, lon: "A")
    path, params = client.calls[0]
    assert path == "/v2/insights"
    assert params["filter.type"] == "urn:heatmap" and params["filter.location.query"] == "Testland"
    assert params["signal.interests.entities"] == "id1"


def test_geocode_failure_keeps_cells():
    entities = [cell(10.0, 20.0, 0.9, 0.9), cell(12.0, 20.0, 0.8, 0.8)]

    def boom(lat, lon):
        raise httpx.ConnectError("down")

    out = hs.hotspots(FakeClient(entities), "id1", "Testland", geocode=boom)
    assert out["places"] == [] and len(out["cells"]) == 2


def test_geocode_failure_after_first_name_keeps_it():
    entities = [cell(10.0, 20.0, 0.9, 0.9), cell(12.0, 20.0, 0.8, 0.8)]
    seen = []

    def flaky(lat, lon):
        seen.append(lat)
        if len(seen) > 1:
            raise httpx.ConnectError("down")
        return "First"

    assert hs.hotspots(FakeClient(entities), "id1", "Testland", geocode=flaky)["places"] == ["First"]


def test_qloo_failure_and_missing_entity_return_empty():
    empty = {"cells": [], "places": []}
    assert hs.hotspots(FakeClient(error=QlooError("budget")), "id1", "T", geocode=lambda a, b: "x") == empty
    assert hs.hotspots(FakeClient(), None, "T") == empty


def test_place_prefers_city_town_municipality_village_before_county_and_state():
    assert hs.place_from_address({"state": "S", "county": "C", "village": "V", "city": "Pune"}) == "Pune"
    assert hs.place_from_address({"county": "C", "village": "V", "town": "T"}) == "T"
    assert hs.place_from_address({"county": "C", "village": "V", "municipality": "M", "town": "T"}) == "T"
    assert hs.place_from_address({"county": "C", "village": "V", "municipality": "M"}) == "M"
    assert hs.place_from_address({"state_district": "SD", "county": "C", "village": "V"}) == "V"
    assert hs.place_from_address({"state_district": "SD", "county": "C"}) == "C"
    assert hs.place_from_address({"state": "S"}) == "S"
    assert hs.place_from_address({"country": "X"}) is None


def test_administrative_suffixes_are_stripped_on_word_boundaries():
    clean = hs.clean_place_name
    assert clean("Pune Municipal Corporation") == "Pune"
    assert clean("Ekurhuleni Metropolitan Municipality") == "Ekurhuleni"
    assert clean("Savar Upazila") == "Savar"
    assert clean("Kathmandu District") == "Kathmandu"
    assert clean("Chittagong City Corporation") == "Chittagong"
    assert clean("Dhaka ward") == "Dhaka"
    assert clean("Municipality of Gdynia") == "Gdynia"
    assert clean("Mexico City") == "Mexico City"
    assert clean("Kingston upon Hull") == "Kingston upon Hull"
    assert clean("Edwardsville") == "Edwardsville"
    assert clean("Ward") == "Ward"


def test_nominatim_name_applies_new_parsing_to_a_cached_response(tmp_path):
    import hashlib
    import json
    key = hashlib.sha256("18.520,73.856,en".encode()).hexdigest()[:24]
    (tmp_path / f"{key}.json").write_text(json.dumps(
        {"address": {"county": "Pune District", "city": "Pune Municipal Corporation"}}), encoding="utf-8")
    assert hs.nominatim_name(18.52, 73.856, cache_dir=tmp_path) == "Pune"
