import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aftershock.launch_kit import DOMAINS, PER_DOMAIN, launch_kit  # noqa: E402
from aftershock.qloo import QlooError  # noqa: E402


class FakeInsights:
    def __init__(self, by_type):
        self.by_type = by_type
        self.calls = []

    def get(self, path, params):
        self.calls.append(params)
        result = self.by_type[params["filter.type"]]
        if isinstance(result, Exception):
            raise result
        return {"results": {"entities": result}}


def entities(prefix, n):
    return [{"name": f"{prefix} {i}", "entity_id": f"id-{prefix}-{i}"} for i in range(n)]


def test_empty_domains_dropped_and_failures_skipped():
    client = FakeInsights({"urn:entity:artist": entities("Artist", 3), "urn:entity:tv_show": [],
                           "urn:entity:movie": QlooError("boom"), "urn:entity:brand": entities("Brand", 1)})
    kit = launch_kit(client, "title-id", "Japan")
    assert list(kit) == ["artist", "brand"]
    assert kit["brand"] == [{"name": "Brand 0", "entity_id": "id-Brand-0"}]


def test_at_most_five_per_domain_and_query_shape():
    client = FakeInsights({t: entities(d, 9) for d, t in DOMAINS.items()})
    kit = launch_kit(client, "title-id", "Japan")
    assert set(kit) == set(DOMAINS)
    assert all(len(v) == PER_DOMAIN == 5 for v in kit.values())
    assert all(c["signal.interests.entities"] == "title-id" and c["signal.location.query"] == "Japan" for c in client.calls)


def test_missing_title_returns_empty_without_calls():
    client = FakeInsights({})
    assert launch_kit(client, None, "Japan") == {}
    assert client.calls == []


def test_repair_name_fixes_mac_roman_mojibake_and_leaves_clean_names():
    from aftershock.launch_kit import repair_name
    assert repair_name("Chav\u221a\u2265n La Escuela De Dise\u221a\u00b1o") == "Chav\u00f3n La Escuela De Dise\u00f1o"
    for clean in ("Chav\u00f3n", "S\u01a1n T\u00f9ng M-TP", "GoPro", "\u81fa\u5317\u5e02"):
        assert repair_name(clean) == clean


def test_specificity_identical_is_zero_and_generic_disjoint_is_one_empty_skipped():
    from aftershock.launch_kit import GENERIC_AT_OR_BELOW, specificity
    same = {"artist": ["A", "B"], "brand": ["X"]}
    assert specificity(same, same) == 0 and specificity(same, same) <= GENERIC_AT_OR_BELOW
    assert specificity({"artist": ["A", "B"]}, {"artist": ["C", "D"]}) == 1
    # tv_show has no control list and movie has no kit names: both skipped, only artist counts (1 - 1/3)
    mixed = specificity({"artist": ["A", "B"], "tv_show": ["T"], "movie": []},
                        {"artist": ["B", "C"], "movie": ["M"]})
    assert abs(mixed - (1 - 1 / 3)) < 1e-9
    assert specificity({"artist": []}, {"artist": ["A"]}) is None


def test_name_key_strips_accents_case_and_punctuation():
    from aftershock.launch_kit import name_key
    assert name_key("Señor  D.J.") == "senor d j"
