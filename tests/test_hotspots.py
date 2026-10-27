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
        return {"results": {"entities": self.entities}}


def test_top_cells_caps_at_120_and_orders_by_affinity():
    entities = [cell(i * 0.01, 0.0, i / 1000, 1000 - i) for i in range(300)]
    cells = hs.top_cells({"results": {"entities": entities}})
    assert len(cells) == 120
    assert cells[0][0] == 2.99 and cells[0][2] == 1.0
    assert all(0 < c[2] <= 1 for c in cells)
    assert [c[2] for c in cells] == sorted((c[2] for c in cells), reverse=True)


def test_places_skip_cells_within_60km_and_cap_at_three():
    # A and B are ~11 km apart, C ~110 km from A, D ~220 km, E ~330 km.
    entities = [cell(10.0, 20.0, 0.9, 1), cell(10.1, 20.0, 0.8, 2), cell(11.0, 20.0, 0.7, 3),
                cell(12.0, 20.0, 0.6, 4), cell(13.0, 20.0, 0.5, 5)]
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
    entities = [cell(10.0, 20.0, 0.9, 1), cell(12.0, 20.0, 0.8, 2)]

    def boom(lat, lon):
        raise httpx.ConnectError("down")

    out = hs.hotspots(FakeClient(entities), "id1", "Testland", geocode=boom)
    assert out["places"] == [] and len(out["cells"]) == 2


def test_geocode_failure_after_first_name_keeps_it():
    entities = [cell(10.0, 20.0, 0.9, 1), cell(12.0, 20.0, 0.8, 2)]
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
