import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aftershock import artist_view, grounded_plan, launch_brief  # noqa: E402
from test_grounded_plan import FakeQloo  # noqa: E402
from test_launch_brief import detail, specific_row  # noqa: E402


def test_is_own_title_matches_title_and_franchise_only():
    t = "Nightwatch: Demons Are Forever"
    assert grounded_plan.is_own_title("Nightwatch", t)
    assert grounded_plan.is_own_title("nightwatch  demons are forever", t)
    assert not grounded_plan.is_own_title("Night Watch Records", t)
    assert not grounded_plan.is_own_title("Alpha", t)


def test_ground_drops_the_title_before_checking_or_counting():
    fake = FakeQloo({"Alpha": "a", "Nightwatch": "n"}, {"a": 0.9, "n": 0.8})
    plan = grounded_plan.ground(fake, "t", "Sweden", {"tv_show": ["Nightwatch", "Alpha"]}, None, "Nightwatch: Demons Are Forever")
    assert [c["name"] for c in plan["confirmed"]] == ["Alpha"]
    assert plan["dropped"] == {"not_placed": 0, "not_in_qloo": 0}


def test_clean_plan_recounts_stored_rows_without_new_calls():
    plan = {"confirmed": [{"domain": "tv_show", "name": "Nightwatch", "both": False}, {"domain": "artist", "name": "A", "both": False}],
            "dropped": {"not_placed": 2, "not_in_qloo": 1},
            "rejected": [{"domain": "tv_show", "name": "Nightwatch", "verdict": "not_placed"},
                         {"domain": "artist", "name": "B", "verdict": "not_placed"},
                         {"domain": "artist", "name": "C", "verdict": "not_in_qloo"}]}
    out = grounded_plan.clean_plan(plan, "Nightwatch: Demons Are Forever")
    assert [c["name"] for c in out["confirmed"]] == ["A"]
    assert out["dropped"] == {"not_placed": 1, "not_in_qloo": 1}
    assert grounded_plan.clean_plan(out, "Nightwatch: Demons Are Forever") == out  # idempotent
    assert len(plan["confirmed"]) == 2  # the input is untouched


def test_brief_counts_come_from_the_filtered_plan():
    row = specific_row()
    row["plan"]["confirmed"].append({"domain": "tv_show", "name": "Show", "both": False})  # detail()'s title
    row["plan"]["rejected"] = ([{"domain": "tv_show", "name": "Show", "verdict": "not_placed"}]
                               + [{"domain": "artist", "name": f"X{i}", "verdict": "not_placed"} for i in range(3)]
                               + [{"domain": "artist", "name": f"U{i}", "verdict": "not_in_qloo"} for i in range(2)])
    made = launch_brief.brief(detail([row]), "KR")
    by = {s["key"]: s for s in made["steps"]}
    assert "suggested 10 names" in by["ai_proposals"]["found"]
    assert by["qloo_check"]["found"].startswith("5 supported by Qloo for this audience, 3 known to Qloo but not linked")
    assert "2 with no Qloo data yet" in by["qloo_check"]["found"]
    assert all(r["name"] != "Show" for r in by["qloo_check"]["rejected"])
    assert all(c["name"] != "Show" for g in made["brief"]["partners"] for c in g["picks"])


def test_partner_groups_split_approach_from_watches():
    made = launch_brief.brief(detail([specific_row()]), "KR")
    groups = {g["domain"]: g["group"] for g in made["brief"]["partners"]}
    assert groups == {"artist": "partner", "tv_show": "watches", "movie": "watches", "brand": "partner"}
    summary = made["brief"]["summary"]
    assert "Pick1" not in summary  # the first TV show pick is not an approach target


def test_distributor_move_has_no_dub_wording():
    made = launch_brief.brief(detail([specific_row()]), "KR")
    move = next(m for m in made["brief"]["moves"] if m["buyer"] == "Distributor")
    assert move["text"].startswith("Prepare South Korea promotion now:") and "dub" not in move["text"]


def test_artist_view_marks_countrywide_appearances_and_sorts_them_last():
    def item(sid, generic, chance):
        row = {"code": "KR", "generic": generic, "kit": {"artist": []},
               "plan": {"confirmed": [{"domain": "artist", "name": "Solo", "both": False}]}}
        return {"summary": {"id": sid}, "detail": {"id": sid, "title": sid, "origin_countries": [],
                "spillover": {"horizon_weeks": 4, "forecasts": [{"code": "KR", "name": "South Korea", "probability": chance}]},
                "launch_kit": [row]}}
    idx = artist_view.build([item("a", True, 0.5), item("b", False, 0.1)])
    solo = idx["artists"][0]
    assert [b["countrywide"] for b in solo["breakouts"]] == [False, True]
    assert solo["countrywide_only"] is False
    only = artist_view.build([item("a", True, 0.5)])["artists"][0]
    assert only["countrywide_only"] is True
    assert artist_view.listing({"artists": [only]}, "w")["artists"][0]["countrywide_only"] is True
