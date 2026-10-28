import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aftershock import live_events as le  # noqa: E402
from aftershock.hotspots import distance_km, hotspots  # noqa: E402
from aftershock.qloo import QlooError  # noqa: E402

DELHI, JAIPUR, AGRA = (28.61, 77.21), (26.91, 75.79), (27.18, 78.01)


def heat(*points):
    return {"results": {"heatmap": [
        {"location": {"latitude": la, "longitude": lo}, "query": {"affinity": 1 - i / 100, "affinity_rank": 1 - i / 100}}
        for i, (la, lo) in enumerate(points)]}}


class FakeClient:
    """Heatmaps by entity id; searches resolve to 'id-<name>'; `fail` ids raise."""
    def __init__(self, maps, fail=()):
        self.maps, self.fail, self.calls = maps, set(fail), []

    def get(self, path, params):
        if path == "/search":
            return {"results": [{"name": params["query"], "entity_id": f"id-{params['query']}"}]}
        entity = params["signal.interests.entities"]
        self.calls.append(entity)
        if entity in self.fail:
            raise QlooError("boom")
        return self.maps[entity]

    def search(self, query, types=None, take=5):
        return self.get("/search", {"query": query})["results"]


def row():
    return {"code": "IN", "kit": {"artist": [{"name": f"A{i}", "entity_id": f"A{i}"} for i in range(5)]},
            "hotspots": {"places": ["Delhi", "Agra", "Jaipur"], "place_cells": [list(DELHI), list(AGRA), list(JAIPUR)],
                         "cells": []}}


def test_overlap_within_and_outside_60_km():
    near = (DELHI[0] + 0.3, DELHI[1])  # about 33 km
    far = (DELHI[0] + 0.7, DELHI[1])  # about 78 km
    assert distance_km(DELHI, near) < 60 < distance_km(DELHI, far)
    assert le.overlap_cities(["Delhi"], [DELHI], [[near[0], near[1], 1.0]]) == ["Delhi"]
    assert le.overlap_cities(["Delhi"], [DELHI], [[far[0], far[1], 1.0]]) == []


def test_only_the_artists_top_cells_count():
    cells = [[0.0, 0.0, 1.0]] * 30 + [[DELHI[0], DELHI[1], 0.1]]
    assert le.overlap_cities(["Delhi"], [DELHI], cells) == []


def test_artist_without_overlap_is_dropped_but_counted_and_cities_keep_show_order():
    client = FakeClient({"A0": heat(JAIPUR, DELHI), "A1": heat((35.0, 135.0)), "A2": heat(AGRA)})
    out = le.events_for_row(client, row(), "India")
    assert out == {"events": [{"artist": "A0", "cities": ["Delhi", "Jaipur"]}, {"artist": "A2", "cities": ["Agra"]}],
                   "events_checked": 3}


def test_at_most_three_artists_are_checked():
    client = FakeClient({f"A{i}": heat(DELHI) for i in range(5)})
    assert le.events_for_row(client, row(), "India")["events_checked"] == 3
    assert client.calls == ["A0", "A1", "A2"]


def test_errors_degrade_to_fewer_artists():
    client = FakeClient({"A0": heat(DELHI), "A2": heat(DELHI)}, fail={"A1"})
    out = le.events_for_row(client, row(), "India")
    assert [e["artist"] for e in out["events"]] == ["A0", "A2"] and out["events_checked"] == 2

    class Down(FakeClient):
        def get(self, path, params):
            raise httpx.ConnectError("down")
    assert le.events_for_row(Down({}), row(), "India") == {"events": [], "events_checked": 0}


def test_row_without_place_cells_is_skipped():
    r = row()
    del r["hotspots"]["place_cells"]
    assert le.events_for_row(FakeClient({}), r, "India") == {"events": [], "events_checked": 0}


def test_ai_confirmed_artists_are_checked_first_and_resolved_by_name():
    r = row()
    r["plan"] = {"confirmed": [{"domain": "artist", "name": f"Ai{i}", "both": False} for i in range(3)],
                 "dropped": {}}
    client = FakeClient({f"id-Ai{i}": heat(JAIPUR) for i in range(3)})
    out = le.events_for_row(client, r, "India")
    assert [e["artist"] for e in out["events"]] == ["Ai0", "Ai1", "Ai2"]
    assert all(e["cities"] == ["Jaipur"] for e in out["events"])


def test_add_events_sets_fields_on_rows_and_counts():
    detail = {"spillover": {"forecasts": [{"code": "IN", "name": "India"}]}, "launch_kit": [row()]}
    client = FakeClient({"A0": heat(DELHI), "A1": heat((0, 0)), "A2": heat((0, 0))})
    assert le.add_events(client, [{"detail": detail}]) == 1
    assert detail["launch_kit"][0]["events"] == [{"artist": "A0", "cities": ["Delhi"]}]
    assert detail["launch_kit"][0]["events_checked"] == 3


def test_hotspots_keeps_the_cell_each_place_was_named_from():
    client = FakeClient({"T": heat(DELHI, (28.62, 77.2), JAIPUR)})
    out = hotspots(client, "T", "India", geocode=lambda la, lo: "Delhi" if la > 28 else "Jaipur")
    assert out["places"] == ["Delhi", "Jaipur"]
    assert out["place_cells"] == [list(DELHI), list(JAIPUR)]
