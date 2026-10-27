import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from aftershock.qloo import best_title_match, release_year  # noqa: E402
import run_forecasts  # noqa: E402


def hit(name, entity_id, year=None, popularity=None, release_date=None):
    props = {}
    if year is not None:
        props["release_year"] = year
    if release_date:
        props["release_date"] = release_date
    out = {"name": name, "entity_id": entity_id, "properties": props}
    if popularity is not None:
        out["popularity"] = popularity
    return out


def test_film_prefers_release_nearest_the_chart_year():
    hits = [hit("Relatives", "old", 1984, 0.9), hit("Relatives", "new", 2026, 0.1)]
    assert best_title_match(hits, "Relatives", 2026, film=True)["entity_id"] == "new"
    assert best_title_match(list(reversed(hits)), "Relatives", 2026, film=True)["entity_id"] == "new"


def test_film_within_two_years_beats_a_closer_year_less_popular_rule_ties_on_popularity():
    hits = [hit("Heat", "a", 2024, 0.2), hit("Heat", "b", 2024, 0.8), hit("Heat", "c", 1995, 0.99)]
    assert best_title_match(hits, "Heat", 2026, film=True)["entity_id"] == "b"


def test_tv_accepts_any_earlier_season_year_and_rejects_later_ones_then_popularity():
    hits = [hit("Show", "future", 2030, 0.99), hit("Show", "small", 2010, 0.2), hit("Show", "big", 2016, 0.7)]
    assert best_title_match(hits, "Show", 2026, film=False)["entity_id"] == "big"


def test_missing_year_ranks_last_and_non_exact_names_are_ignored():
    hits = [hit("Show Extra", "x", 2026), hit("Show", "noyear"), hit("Show", "dated", 2001)]
    assert best_title_match(hits, "Show", 2026, film=False)["entity_id"] == "dated"
    assert best_title_match([hit("Other", "z", 2026)], "Show", 2026, film=False) is None


def test_release_year_falls_back_to_release_date():
    assert release_year(hit("A", "a", release_date="2026-02-01")) == 2026
    assert release_year(hit("A", "a")) is None


def test_resolve_title_uses_the_chart_year_and_asks_for_more_hits():
    class C:
        taken = None

        def search(self, query, types=None, take=5):
            C.taken = take
            return [hit("Relatives", "old", 1984), hit("Relatives", "new", 2026)]
    event = {"title": ("Relatives", "N/A"), "category": "Films (English)", "origin_week": date(2026, 10, 19)}
    assert run_forecasts.resolve_title(C(), event) == "new"
    assert C.taken > 5


def test_film_with_no_hit_in_window_falls_back_to_popularity():
    hits = [{"name": "Housefull", "entity_id": "OBSCURE", "popularity": 0.0, "properties": {"release_year": 2013}},
            {"name": "Housefull", "entity_id": "KNOWN", "popularity": 0.9, "properties": {"release_year": 2010}}]
    assert best_title_match(hits, "Housefull", 2026, film=True)["entity_id"] == "KNOWN"
