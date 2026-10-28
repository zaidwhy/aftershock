import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from aftershock import api, grounded_plan  # noqa: E402
from aftershock.qloo import Qloo as RealQloo  # noqa: E402
from aftershock.qloo import QlooError  # noqa: E402
from test_grounded_plan import FakeQloo  # noqa: E402

KNOWN = {"Alpha": "a", "Beta": "b"}
PLACED = {"a": 0.9}


def test_check_name_three_verdicts_and_qloo_spelling():
    fake = FakeQloo(KNOWN, PLACED)
    fake.canonical = {"a": "ALPHA!"}
    assert grounded_plan.check_name(fake, "title", "Japan", "artist", "Alpha") == {"verdict": "confirmed", "name": "ALPHA!"}
    assert grounded_plan.check_name(fake, "title", "Japan", "artist", "Beta") == {"verdict": "not_placed", "name": "Beta"}
    assert grounded_plan.check_name(fake, "title", "Japan", "artist", "Zed  Zed") == {"verdict": "not_in_qloo", "name": "Zed Zed"}


def test_check_name_asks_for_the_domain_type_and_country():
    fake = FakeQloo(KNOWN, PLACED)
    grounded_plan.check_name(fake, "title", "Japan", "brand", "Alpha")
    p = fake.insight_params[0]
    assert p["filter.type"] == "urn:entity:brand" and p["signal.location.query"] == "Japan"
    assert p["signal.interests.entities"] == "title" and p["filter.results.entities"] == "a"


def test_check_name_raises_qloo_errors():
    with pytest.raises(QlooError):
        grounded_plan.check_name(FakeQloo(KNOWN, PLACED, search_error={"Alpha"}), "t", "Japan", "artist", "Alpha")
    with pytest.raises(QlooError):
        grounded_plan.check_name(FakeQloo(KNOWN, PLACED, insights_error=True), "t", "Japan", "artist", "Alpha")


@pytest.fixture
def served(monkeypatch, tmp_path):
    row = {"code": "JP", "kit": {"artist": [{"name": "Alpha", "entity_id": "a"}]}}
    detail = {"id": "show", "title": "Show", "category": "TV (English)", "qloo_entity": "title", "origin_countries": [],
              "spillover": {"horizon_weeks": 4, "forecasts": [{"code": "JP", "name": "Japan", "probability": 0.2}]},
              "launch_kit": [row]}
    (tmp_path / "storms.json").write_text(json.dumps(
        {"week": "2026-10-25", "storms": [{"summary": {"id": "show"}, "detail": detail}]}), encoding="utf-8")
    monkeypatch.setattr(api, "PRIVATE", tmp_path)
    monkeypatch.setattr(api, "Qloo", lambda **k: FakeQloo(KNOWN, PLACED))
    api._ripple_hits.clear()
    api._daily.update(day=None, count=0)
    return TestClient(api.app)


def get(c, **over):
    params = {"storm": "show", "country": "jp", "domain": "artist", "name": "Alpha"} | over
    return c.get("/api/check", params=params)


def test_endpoint_returns_each_verdict(served):
    assert get(served).json() == {"verdict": "confirmed", "name": "Alpha"}
    assert get(served, name="Beta").json() == {"verdict": "not_placed", "name": "Beta"}
    assert get(served, name="Nobody").json() == {"verdict": "not_in_qloo", "name": "Nobody"}


def test_endpoint_bounds(served):
    assert get(served, name="").status_code == 422
    assert get(served, name="   ").status_code == 422
    assert get(served, name="x" * 81).status_code == 422
    assert get(served, name="x" * 80).status_code == 200
    assert get(served, domain="podcast").status_code == 422
    assert get(served, storm="nope").status_code == 404
    assert get(served, country="KR").status_code == 404


def test_endpoint_uses_the_shared_live_limit(served):
    codes = [get(served).status_code for _ in range(api.RIPPLE_PER_HOUR + 1)]
    assert codes[:-1] == [200] * api.RIPPLE_PER_HOUR and codes[-1] == 429


def test_failures_become_sentences(served, monkeypatch):
    for status, expect in ((401, "switched off"), (429, "rate-limiting"), (None, "did not answer")):
        monkeypatch.setattr(api, "Qloo", lambda **k: FakeQloo(KNOWN, PLACED, insights_error=True))
        monkeypatch.setattr(grounded_plan, "_placed_with_audience",
                            lambda *a, _s=status, **k: (_ for _ in ()).throw(QlooError("x", status=_s)))
        resp = get(served)
        assert resp.status_code in (502, 503) and expect in resp.json()["detail"]


def test_missing_key_is_a_sentence(served, monkeypatch):
    monkeypatch.setattr(api, "Qloo", RealQloo)
    monkeypatch.setenv("QLOO_API_KEY", "")
    resp = get(served)
    assert resp.status_code == 503 and "switched off" in resp.json()["detail"]
