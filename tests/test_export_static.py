import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from aftershock import api  # noqa: E402
import export_static  # noqa: E402

client = TestClient(api.app)
pytestmark = pytest.mark.skipif(not (api.PRIVATE / "storms.json").exists(), reason="forecast files not generated")


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    path = tmp_path_factory.mktemp("static")
    export_static.export(path)
    return path


def _file(out, name):
    return json.loads((out / name).read_text(encoding="utf-8"))


def test_storm_list_matches_api(out):
    assert _file(out, "storms.json") == client.get("/api/storms").json()


def test_one_storm_matches_api(out):
    first = client.get("/api/storms").json()["storms"][0]["id"]
    assert _file(out, f"storms/{first}.json") == client.get(f"/api/storms/{first}").json()


def test_scorecard_matches_api(out):
    assert _file(out, "scorecard.json") == client.get("/api/scorecard").json()


def test_ripples_and_replays_match_api(out):
    assert _file(out, "ripples.json") == client.get("/api/ripples").json()
    assert _file(out, "replays.json") == client.get("/api/replays").json()
