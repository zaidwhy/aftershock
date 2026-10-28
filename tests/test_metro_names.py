import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest  # noqa: E402

import build_metro_names as build  # noqa: E402
from aftershock import grounded_plan, launch_brief, live_events, metro_names  # noqa: E402

STOCKHOLM, LIDINGO, UPPSALA = (59.3307, 18.0605), (59.3667, 18.1333), (59.8586, 17.6389)
GOTHENBURG, KIRUNA = (57.7066, 11.9692), (67.8555, 20.2224)
SE = [["Stockholm", *STOCKHOLM, 0.97], ["Gothenburg", *GOTHENBURG, 0.85], ["Uppsala", *UPPSALA, 0.55]]


@pytest.fixture
def metro_file(tmp_path, monkeypatch):
    path = tmp_path / "metro_names.json"
    path.write_text(json.dumps({"floor": 0.5, "countries": {"SE": SE}}), encoding="utf-8")
    monkeypatch.setattr(metro_names, "METRO_FILE", path)
    return path


def dests():
    return [tuple(r) for r in SE]


def test_cell_takes_the_most_popular_destination_within_the_radius():
    assert metro_names.metro_for(LIDINGO, dests()) == "Stockholm"
    # A cell about 32 km from both Stockholm and Uppsala: both are in range, the more popular one wins.
    midway = ((STOCKHOLM[0] + UPPSALA[0]) / 2, (STOCKHOLM[1] + UPPSALA[1]) / 2)
    assert metro_names.metro_for(midway, dests(), radius_km=40) == "Stockholm"


def test_a_tie_in_popularity_goes_to_the_nearer_destination():
    near, far = ("Near", 10.0, 10.0, 0.7), ("Far", 10.2, 10.0, 0.7)
    assert metro_names.metro_for([10.05, 10.0], [far, near]) == "Near"


def test_cell_beyond_the_radius_keeps_its_openstreetmap_name():
    assert metro_names.metro_for(KIRUNA, dests()) is None
    names, cells, renamed = metro_names.relabel(["Kiruna"], [list(KIRUNA)], dests())
    assert names == ["Kiruna"] and cells == [list(KIRUNA)] and renamed == {"Kiruna": "Kiruna"}


def test_the_radius_edge():
    d = metro_names.distance_km(STOCKHOLM, LIDINGO)
    assert metro_names.metro_for(LIDINGO, dests(), radius_km=d + 1) == "Stockholm"
    assert metro_names.metro_for(LIDINGO, dests(), radius_km=d - 1) is None


def test_names_that_repeat_after_relabelling_merge_keeping_the_first_cell():
    places = ["Lidingö", "Stockholm", "Kiruna"]
    cells = [list(LIDINGO), list(STOCKHOLM), list(KIRUNA)]
    names, kept, renamed = metro_names.relabel(places, cells, dests())
    assert names == ["Stockholm", "Kiruna"] and kept == [list(LIDINGO), list(KIRUNA)]
    assert renamed == {"Lidingö": "Stockholm", "Stockholm": "Stockholm", "Kiruna": "Kiruna"}


def test_a_row_without_a_cell_per_place_is_left_as_it_is():
    assert metro_names.relabel(["Lidingö", "Kiruna"], [list(LIDINGO)], dests())[0] == ["Lidingö", "Kiruna"]


def test_popularity_floor_in_the_build_keeps_only_well_known_destinations():
    def entity(name, popularity, code="SE", lat=59.0):
        return {"name": name, "popularity": popularity, "location": {"lat": lat, "lon": 18.0},
                "properties": {"geocode": {"country_code": code}}}
    body = {"results": {"entities": [entity("Stockholm", 0.97), entity("Visby", 0.34), entity("Edge", 0.5),
                                     entity("Europe/Stockholm", 0.99), entity("Oslo", 0.94, code="NO"),
                                     {"name": "NoPop", "location": {"lat": 1, "lon": 1},
                                      "properties": {"geocode": {"country_code": "SE"}}}]}}
    assert build.destinations(body, "SE", floor=0.5) == [["Stockholm", 59.0, 18.0, 0.97], ["Edge", 59.0, 18.0, 0.5]]


def test_the_build_pages_while_the_page_is_full_and_above_the_floor(monkeypatch):
    monkeypatch.setattr(build, "TAKE", 2)

    def page(*pops):
        return {"results": {"entities": [{"name": f"P{p}", "popularity": p, "location": {"lat": 1, "lon": 1},
                                          "properties": {"geocode": {"country_code": "US"}}} for p in pops]}}
    pages = {0: page(0.9, 0.8), 2: page(0.7, 0.4), 4: page(0.3, 0.2)}

    class Client:
        def __init__(self):
            self.calls = []

        def get(self, path, params):
            self.calls.append(params.get("offset", 0))
            return pages[params.get("offset", 0)]
    client = Client()
    rows, fetched, capped = build.fetch(client, "US", floor=0.5)
    assert [r[0] for r in rows] == ["P0.9", "P0.8", "P0.7"] and fetched == 2 and not capped
    assert client.calls == [0, 2]


def test_load_is_empty_without_a_file_or_with_a_damaged_one(tmp_path):
    assert metro_names.load(tmp_path / "missing.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert metro_names.load(bad) == {}


def _row():
    return {"code": "SE", "hotspots": {"places": ["Lidingö kommun", "Stockholm", "Gothenburg", "Kiruna"],
                                       "place_cells": [list(LIDINGO), list(STOCKHOLM), list(GOTHENBURG), list(KIRUNA)]},
            "events": [{"artist": "A", "cities": ["Lidingö kommun", "Gothenburg"]},
                       {"artist": "B", "cities": ["Stockholm", "Lidingö kommun"]}]}


def test_relabel_row_renames_places_cells_and_event_cities_and_is_idempotent(metro_file):
    row = _row()
    metro_names.relabel_row(row)
    assert row["hotspots"]["places"] == ["Stockholm", "Gothenburg", "Kiruna"]
    assert row["hotspots"]["place_cells"] == [list(LIDINGO), list(GOTHENBURG), list(KIRUNA)]
    assert [e["cities"] for e in row["events"]] == [["Stockholm", "Gothenburg"], ["Stockholm"]]
    once = json.dumps(row, sort_keys=True)
    metro_names.relabel_row(row)
    assert json.dumps(row, sort_keys=True) == once


def test_a_country_without_destinations_only_loses_admin_wording(metro_file):
    row = _row() | {"code": "NO"}
    metro_names.relabel_row(row)
    assert row["hotspots"]["places"] == ["Lidingö", "Stockholm", "Gothenburg", "Kiruna"]


def test_clean_rows_applies_the_relabel_to_a_storm_detail(metro_file):
    detail = {"title": "T", "launch_kit": [_row()]}
    grounded_plan.clean_rows(detail)
    assert detail["launch_kit"][0]["hotspots"]["places"][0] == "Stockholm"


def test_the_launch_brief_names_the_metro_city(metro_file):
    kit = {d: [{"name": f"{d}{i}", "entity_id": f"{d}{i}"} for i in range(5)] for d in ("artist", "tv_show", "movie", "brand")}
    detail = {"id": "show", "title": "Show", "origin_countries": [{"code": "JP", "name": "Japan"}],
              "spillover": {"horizon_weeks": 4, "forecasts": [{"code": "SE", "name": "Sweden", "probability": 0.2}]},
              "launch_kit": [_row() | {"kit": kit}]}
    made = launch_brief.brief(detail, "SE")["brief"]
    assert made["cities"] == ["Stockholm", "Gothenburg", "Kiruna"]
    assert all("Lidingö" not in e["text"] for e in made["event_ideas"])
    assert any("Stockholm" in e["text"] for e in made["event_ideas"])


def test_new_event_ideas_are_named_for_the_metro_city(metro_file, monkeypatch):
    row = {"code": "SE", "kit": {"artist": [{"name": "Veronica", "entity_id": "V"}]},
           "hotspots": {"places": ["Lidingö", "Göteborg"], "place_cells": [list(LIDINGO), list(GOTHENBURG)], "cells": []}}
    monkeypatch.setattr(live_events, "partner_artists", lambda r: [{"name": "Veronica"}])
    monkeypatch.setattr(live_events, "heat_cells", lambda client, entity_id, country: [
        [STOCKHOLM[0], STOCKHOLM[1], 1.0], [GOTHENBURG[0], GOTHENBURG[1], 0.9]])
    out = live_events.events_for_row(object(), row, "Sweden")
    assert out["events"] == [{"artist": "Veronica", "cities": ["Stockholm", "Gothenburg"]}]
