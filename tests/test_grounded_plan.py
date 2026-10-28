import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from aftershock import api, grounded_plan, llm_kits  # noqa: E402
from aftershock.qloo import QlooError  # noqa: E402

ARTIST = "urn:entity:artist"


class FakeQloo:
    """known: {name: entity_id} that /search finds exactly; placed: {entity_id: affinity} Qloo places with the audience.
    Like Qloo, a filtered insights call returns only the requested ids that are placed."""

    def __init__(self, known, placed, search_error=None, insights_error=None):
        self.known, self.placed = known, placed
        self.search_error, self.insights_error = search_error, insights_error
        self.insight_params = []

    def search(self, name, types=None, take=5):
        if self.search_error and name in self.search_error:
            raise QlooError("search down")
        if name in self.known:
            return [{"name": name, "entity_id": self.known[name]}]
        return [{"name": "Nearest Unrelated Thing", "entity_id": "nearest"}]  # /search always answers

    def get(self, path, params):
        self.insight_params.append(params)
        if self.insights_error:
            raise QlooError("insights down")
        wanted = params["filter.results.entities"].split(",")
        return {"results": {"entities": [{"entity_id": i, "name": i, "query": {"affinity": a}}
                                         for i, a in self.placed.items() if i in wanted]}}


KNOWN = {"Alpha": "a", "Beta": "b", "Delta": "d"}
PLACED = {"a": 0.9, "d": 0.95}


def test_verdicts_confirmed_not_placed_not_in_qloo():
    client = FakeQloo(KNOWN, PLACED)
    kit = {"artist": [{"name": "Alpha", "entity_id": "a"}, {"name": "Other"}]}
    plan = grounded_plan.ground(client, "title", "Japan", {"artist": ["Alpha", "Beta", "Gamma", "Delta"]}, kit)
    assert plan["confirmed"] == [{"domain": "artist", "name": "Delta", "both": False},
                                 {"domain": "artist", "name": "Alpha", "both": True}]  # affinity order, not proposal order
    assert plan["dropped"] == {"not_placed": 1, "not_in_qloo": 1}
    assert "affinity" not in str(plan)
    sent = client.insight_params[0]
    assert sent["filter.results.entities"] == "a,b,d" and sent["signal.location.query"] == "Japan"
    assert sent["signal.interests.entities"] == "title" and sent["take"] == 50


def test_inputs_are_capped_and_cleaned():
    names = [f"N{i}" for i in range(9)] + ["x" * 121, 7, "  ", "N0"]
    assert grounded_plan.clean_names(names) == [f"N{i}" for i in range(5)]
    assert grounded_plan.clean_names(["x" * 121, "ok"]) == ["ok"]
    assert grounded_plan.clean_names(None) == []


def test_failed_insights_call_degrades_to_no_rows():
    client = FakeQloo(KNOWN, PLACED, insights_error=True)
    assert grounded_plan.ground(client, "title", "Japan", {"artist": ["Alpha"]}) is None


def test_failed_search_skips_only_that_name():
    client = FakeQloo(KNOWN, PLACED, search_error={"Alpha"})
    plan = grounded_plan.ground(client, "title", "Japan", {"artist": ["Alpha", "Delta"]})
    assert [c["name"] for c in plan["confirmed"]] == ["Delta"]
    assert plan["dropped"] == {"not_placed": 0, "not_in_qloo": 0}


def test_no_title_entity_means_no_plan():
    assert grounded_plan.ground(FakeQloo(KNOWN, PLACED), None, "Japan", {"artist": ["Alpha"]}) is None


def storms():
    row = {"code": "JP", "kit": {"artist": [{"name": "Alpha", "entity_id": "a"}]}}
    return [{"detail": {"title": "Show", "category": "TV (English)", "qloo_entity": "title",
                        "spillover": {"forecasts": [{"code": "JP", "name": "Japan"}]}, "launch_kit": [row]}}], row


def test_no_gemini_key_leaves_kits_unchanged(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(llm_kits, "title_kits", lambda pairs: (_ for _ in ()).throw(AssertionError("Gemini was called")))
    rows, row = storms()
    before = dict(row)
    assert grounded_plan.add_plans(FakeQloo(KNOWN, PLACED), rows) == 0
    assert row == before and "plan" not in row


def test_plan_is_added_with_a_key_and_kit_untouched(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(llm_kits, "title_kits", lambda pairs: {p["id"]: {"artist": ["Alpha", "Delta", "Gamma"]} for p in pairs})
    rows, row = storms()
    kit = dict(row["kit"])
    assert grounded_plan.add_plans(FakeQloo(KNOWN, PLACED), rows) == 1
    assert row["kit"] == kit
    assert [c["name"] for c in row["plan"]["confirmed"]] == ["Delta", "Alpha"]
    assert row["plan"]["dropped"] == {"not_placed": 0, "not_in_qloo": 1} and row["plan"]["model"] == llm_kits.MODEL


def test_gemini_failure_leaves_kits_unchanged(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(llm_kits, "title_kits", lambda pairs: (_ for _ in ()).throw(RuntimeError("Gemini HTTP 500")))
    rows, row = storms()
    assert grounded_plan.add_plans(FakeQloo(KNOWN, PLACED), rows) == 0 and "plan" not in row


def test_storm_detail_endpoint_carries_the_plan(monkeypatch, tmp_path):
    rows, row = storms()
    row["plan"] = {"confirmed": [{"domain": "artist", "name": "Alpha", "both": True}],
                   "dropped": {"not_placed": 2, "not_in_qloo": 1}, "model": "m"}
    detail = {**rows[0]["detail"]}
    (tmp_path / "storms.json").write_text(json.dumps(
        {"week": "2026-10-25", "storms": [{"summary": {"id": "show"}, "detail": detail}]}), encoding="utf-8")
    monkeypatch.setattr(api, "PRIVATE", tmp_path)
    body = TestClient(api.app).get("/api/storms/show").json()
    assert body["launch_kit"][0]["plan"]["confirmed"][0]["name"] == "Alpha"
    assert body["launch_kit"][0]["plan"]["dropped"] == {"not_placed": 2, "not_in_qloo": 1}
