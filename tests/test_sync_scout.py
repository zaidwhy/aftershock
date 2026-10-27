import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aftershock.ripple import AGE_BANDS  # noqa: E402
from aftershock.sync_scout import why, TOP_N, scout  # noqa: E402


def demographics(values):
    return {"results": {"demographics": [{"query": {"age": dict(zip(AGE_BANDS, values))}}]}}


YOUNG = [0.7, 0.4, 0.1, -0.6, -0.3, -0.5]
OLD = [-0.6, -0.4, 0.0, 0.3, 0.5, 0.6]
MID = [0.0, 0.1, 0.2, 0.2, 0.1, 0.0]


class FakeClient:
    """Show 'S' is young; artists a1..: a1 young, a2 old, a3 has no profile, a4 middling."""

    def __init__(self, show_known=True, show_profile=True, extra=0):
        self.show_known, self.show_profile = show_known, show_profile
        self.profiles = {"a1": YOUNG, "a2": OLD, "a3": None, "a4": MID}
        for i in range(extra):
            self.profiles[f"x{i}"] = MID
        self.calls = 0

    def search(self, query, types=None, take=5):
        self.calls += 1
        if self.show_known and query == "Show":
            return [{"name": "Show", "entity_id": "S"}]
        return []

    def insights(self, **params):
        self.calls += 1
        if params["filter__type"] == "urn:entity:artist":
            return {"results": {"entities": [{"entity_id": k, "name": f"Name {k}", "query": {"affinity": 0.987}}
                                             for k in self.profiles]}}
        entity = params["signal__interests__entities"]
        if entity == "S":
            return demographics(YOUNG) if self.show_profile else {"results": {"demographics": []}}
        values = self.profiles[entity]
        return demographics(values) if values else {"results": {"demographics": []}}


def test_ranks_by_gap_and_keeps_taste_rank():
    out = scout(FakeClient(), "Show")
    assert out["resolved"] is True
    assert [a["entity_id"] for a in out["artists"]] == ["a2", "a4", "a1"]
    assert [a["taste_rank"] for a in out["artists"]] == [2, 4, 1]
    gaps = [a["gap"] for a in out["artists"]]
    assert gaps == sorted(gaps, reverse=True) and gaps[0] > 0.7 and gaps[-1] < 0.3


def test_artists_without_profile_are_dropped():
    out = scout(FakeClient(), "Show")
    assert "a3" not in {a["entity_id"] for a in out["artists"]}
    assert out["candidates"] == 4 and out["profiled"] == 3


def test_unresolved_show_returns_reason():
    out = scout(FakeClient(show_known=False), "Show")
    assert out["resolved"] is False and out["artists"] == [] and out["reason"]


def test_show_without_profile_returns_reason():
    out = scout(FakeClient(show_profile=False), "Show")
    assert out["resolved"] is False and "audience profile" in out["reason"]


def test_output_has_no_raw_affinity_or_demographics():
    out = scout(FakeClient(), "Show")
    row = out["artists"][0]
    assert set(row) == {"name", "entity_id", "gap", "taste_rank", "leans", "why"}
    text = str(out)
    assert "0.987" not in text and "affinity" not in text and "age_profile" not in text
    assert row["why"].startswith("Audience leans 55 and older") and "24 and younger" in row["why"]


def test_why_names_every_band_a_two_sided_audience_leans_on():
    show = {"24_and_younger": 0.75, "25_to_29": -0.3, "30_to_34": -0.6, "35_to_44": -0.4,
            "45_to_54": 0.0, "55_and_older": 0.8}
    artist = {"24_and_younger": 0.9, "25_to_29": 0.7, "30_to_34": 0.1, "35_to_44": -0.6,
              "45_to_54": -0.2, "55_and_older": -0.3}
    text = why(show, artist)
    assert "the show's leans 55 and older and 24 and younger" in text
    assert "Overlap only at 24 and younger" in text


def test_returns_at_most_top_n():
    out = scout(FakeClient(extra=30), "Show")
    assert len(out["artists"]) == TOP_N
