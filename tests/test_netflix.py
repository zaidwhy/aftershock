import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aftershock.netflix import (  # noqa: E402
    HistoryBaseline, breakout_events, first_entries, load_rows, roc_auc, title_categories,
)

HEADER = ("country_name\tcountry_iso2\tweek\tcategory\tweekly_rank\t"
          "show_title\tseason_title\tcumulative_weeks_in_top_10")


def write_tsv(tmp_path, entries):
    lines = [HEADER] + [
        f"{iso}\t{iso}\t{week}\t{cat}\t1\t{title}\t{season}\t1"
        for iso, week, cat, title, season in entries
    ]
    path = tmp_path / "fixture.tsv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def fixture_rows(tmp_path):
    entries = []
    # Spreads AA -> BB -> CC, with AA charting again the second week.
    for iso, week in [("AA", "2024-01-07"), ("BB", "2024-01-14"), ("CC", "2024-01-21"), ("AA", "2024-01-14")]:
        entries.append((iso, week, "TV", "Spreader", "Season 1"))
    # Film starting in BB, joined by AA a week later.
    entries += [("BB", "2024-02-04", "Films", "Movie", "N/A"), ("AA", "2024-02-11", "Films", "Movie", "N/A")]
    # DD charts 20 weeks after origin: a re-entry that must be ignored.
    entries += [("AA", "2024-03-03", "TV", "Evergreen", "Season 1"), ("DD", "2024-07-21", "TV", "Evergreen", "Season 1")]
    # Four origin countries: excluded at max_origin=3.
    for iso in ["AA", "BB", "CC", "DD"]:
        entries.append((iso, "2024-04-07", "Films", "Global Hit", "N/A"))
    return load_rows(write_tsv(tmp_path, entries))


def build_events(tmp_path, max_origin=3):
    rows = fixture_rows(tmp_path)
    return breakout_events(first_entries(rows), title_categories(rows), max_origin=max_origin)


def test_first_entries(tmp_path):
    first = first_entries(fixture_rows(tmp_path))
    assert first[("Spreader", "Season 1")] == {
        "AA": date(2024, 1, 7), "BB": date(2024, 1, 14), "CC": date(2024, 1, 21)}
    assert first[("Movie", "N/A")]["AA"] == date(2024, 2, 11)


def test_breakout_events(tmp_path):
    events = {e["title"]: e for e in build_events(tmp_path)}
    assert ("Global Hit", "N/A") not in events
    spreader = events[("Spreader", "Season 1")]
    assert spreader["origin_countries"] == ["AA"]
    assert spreader["later"] == {"BB": 1, "CC": 2}
    assert events[("Movie", "N/A")]["category"] == "Films"
    assert events[("Evergreen", "Season 1")]["later"] == {}
    assert ("Global Hit", "N/A") in {e["title"] for e in build_events(tmp_path, max_origin=4)}


def test_baseline_probabilities_and_pair_strength(tmp_path):
    events = build_events(tmp_path)
    model = HistoryBaseline(horizon=4).fit(events, ["AA", "BB", "CC", "DD"])
    probe = {"title": ("New", "N/A"), "category": "TV", "origin_week": date(2025, 1, 5),
             "origin_countries": ["AA"], "later": {}}
    probabilities = model.predict(probe, ["BB", "CC", "DD"])
    assert all(0.0 <= p <= 1.0 for p in probabilities.values())
    assert probabilities["BB"] > probabilities["DD"]
    assert model.predict(probe, ["BB"], extra={"BB": {"x": 1.0}}) == model.predict(probe, ["BB"])


def test_blend_learns_informative_feature(tmp_path):
    events = build_events(tmp_path)
    model = HistoryBaseline(horizon=4).fit(events, ["AA", "BB", "CC", "DD"])
    extras = [{c: {"affinity": 1.0 if c in e["later"] else 0.0} for c in model.countries} for e in events]
    model.fit_blend(events, extras)
    assert model.blend["weights"]["affinity"] > 0


def test_roc_auc_hand_checked():
    assert roc_auc([0.9, 0.8, 0.3, 0.1], [1, 1, 0, 0]) == 1.0
    assert roc_auc([0.9, 0.3, 0.8, 0.1], [1, 0, 0, 1]) == 0.5
    assert roc_auc([0.5, 0.5], [1, 0]) == 0.5
    assert roc_auc([0.1, 0.2], [1, 1]) is None
