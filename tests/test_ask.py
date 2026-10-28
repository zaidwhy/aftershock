"""The ask router: every intent, run on fixture data. No live Qloo, no network."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from aftershock import ask, titles  # noqa: E402

FORECASTS = [("BD", "Bangladesh", 0.38), ("NP", "Nepal", 0.2), ("LK", "Sri Lanka", 0.1), ("BR", "Brazil", 0.05)]


def storm(title, origin=("IN", "India"), kit=True):
    forecasts = [{"code": c, "name": n, "probability": p, "why": f"{n} joined 3 of 10"} for c, n, p in FORECASTS]
    rows = [{"code": c, "kit": {"artist": [{"name": "Mika Singh"}, {"name": "Pop Star"}], "tv_show": [{"name": "Show A"}],
                                "movie": [], "brand": [{"name": "Brand A"}]},
             "control": {"artist": ["Pop Star"]}, "hotspots": {"places": ["Dhaka", "Sylhet"], "cells": []},
             "specificity": 0.97, "generic": False} for c in ("BD", "NP", "LK")] if kit else []
    summ = {"id": title.lower().replace(" ", "-"), "title": title, "season": None, "origin_week": "2026-10-18",
            "origin_countries": [{"code": origin[0], "name": origin[1]}], "meta": {"year": 2025, "genres": ["Comedy"]},
            "top_forecast": forecasts[0]}
    return {"netflix_title": [title, "N/A"], "summary": summ, "detail": {**summ, "spillover": {"horizon_weeks": 4, "forecasts": forecasts, "locked_at": "t"},
                                        "launch_kit": rows}}


@pytest.fixture
def ctx(tmp_path):
    data = {"week": "2026-10-18", "since": "2024-01-01", "horizon_weeks": 4, "base": "2020-01-01", "titles": [
        {"s": "Squid Game", "k": "t", "n": "Season 3", "c": [[2000, "KR"], [2010, "US,BR"]]},
        {"s": "Stranger Things", "k": "t", "n": "Season 5", "c": [[2300, "US,GB"]]},
        {"s": "Fresh Show", "k": "t", "c": [[2370, "KR"]],
         "f": {"origin": ["KR"], "next": [{"code": "JP", "name": "Japan", "probability": 0.31, "why": None}]}}]}
    path = tmp_path / "titles.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    storms = [storm("Fukrey Returns"), storm("The Face Thailand", ("TH", "Thailand"), kit=False)]
    wm = {"origins": ["IN", "TH"], "countries": [{"code": "BR", "name": "Brazil", "chance": 0.2,
                                                    "top": [{"id": "fukrey-returns", "title": "Fukrey Returns", "p": 0.05}]}]}
    return {"storms": storms, "week": "2026-10-18", "titles": titles.load(path), "week_map": lambda: wm, "live": None}


class FakeLive:
    def __init__(self):
        self.calls = []

    def take(self):
        self.calls.append("take")

    def ripple(self, show, songs):
        self.calls.append(("ripple", show, songs))
        return {"resolved": True, "show": show, "show_leans": ["25_to_29"], "songs": []}

    def scout(self, show):
        self.calls.append(("scout", show))
        return {"resolved": True, "show": show, "artists": [], "candidates": 0}


def test_launch_kit_for_a_storm_and_country(ctx):
    r = ask.answer("What should Fukrey Returns pair with in Bangladesh?", ctx)
    a = r["answer"]
    assert r["intent"] == "launch_kit" and a["kind"] == "kit"
    assert (a["country"], a["probability"], a["rank"]) == ("Bangladesh", 0.38, 1)
    assert a["picks"]["artist"] == ["Mika Singh"] and a["common"]["artist"] == ["Pop Star"]  # control names are not title-specific
    assert a["places"] == ["Dhaka", "Sylhet"] and a["generic"] is False
    notes = [s["note"] for s in r["steps"]]
    assert "Looked up this week's forecast: Bangladesh 38%." in notes
    assert "Read the Qloo launch kit (title-specific 97%)." in notes
    assert any(n.startswith("Added Qloo hotspots") for n in notes)
    assert [s["n"] for s in r["steps"]] == [1, 2, 3, 4]
    assert r["links"] == [{"label": "Full forecast for Fukrey Returns", "href": "#/storm/fukrey-returns"}]


def test_launch_kit_country_outside_top_three_offers_the_forecast(ctx):
    a = ask.answer("which brands should Fukrey Returns partner with in Brazil", ctx)["answer"]
    assert a["kind"] == "storm" and "no launch kit for Brazil" in a["note"]
    assert "Bangladesh, Nepal, Sri Lanka" in a["note"] and a["focus"]["rank"] == 4


def test_launch_kit_for_a_storm_without_kit_rows(ctx):
    a = ask.answer("launch The Face Thailand in Bangladesh", ctx)["answer"]
    assert a["kind"] == "storm" and "no launch kit" in a["note"]


def test_launch_kit_for_a_title_that_is_not_a_storm(ctx):
    r = ask.answer("What should Squid Game pair with in Brazil?", ctx)
    assert r["intent"] == "launch_kit" and r["answer"]["kind"] == "title"
    assert "not one of this week's breakouts" in r["answer"]["note"]
    assert "already charted in Brazil" in r["answer"]["focus"]


def test_where_next_for_a_storm(ctx):
    r = ask.answer("Where will Fukrey Returns go next?", ctx)
    a = r["answer"]
    assert r["intent"] == "forecast" and a["kind"] == "storm"
    assert [f["name"] for f in a["forecast"]][:2] == ["Bangladesh", "Nepal"]
    assert a["kit_countries"] == ["Bangladesh", "Nepal", "Sri Lanka"]


def test_where_next_for_an_older_title_uses_the_static_index(ctx):
    r = ask.answer("Where will Squid Game go next?", ctx)
    assert r["intent"] == "title_lookup" and r["answer"]["kind"] == "title"
    assert r["answer"]["history"]["title"] == "Squid Game: Season 3"
    assert any("past the forecast window" in s["note"] for s in r["steps"])


def test_where_next_for_a_recent_title_gives_its_forecast(ctx):
    r = ask.answer("where did Fresh Show chart", ctx)
    assert r["answer"]["history"]["forecast"]["next"][0]["name"] == "Japan"
    assert any("most likely next is Japan (31%)" in s["note"] for s in r["steps"])


def test_title_match_tolerates_a_typo_but_not_a_stranger(ctx):
    assert ask.answer("Fukrey Return in India", ctx)["answer"]["title"] == "Fukrey Returns"
    assert ask.answer("Where will Stranger Thing go next", ctx)["answer"]["kind"] == "title"
    assert ask.answer("where will Zebra Planet go next", ctx)["answer"]["kind"] == "help"


def test_country_alone(ctx):
    r = ask.answer("What is heading to Brazil?", ctx)
    a = r["answer"]
    assert r["intent"] == "country" and a["name"] == "Brazil" and a["chance"] == 0.2
    assert a["top"][0]["title"] == "Fukrey Returns"
    assert ask.answer("brazil", ctx)["intent"] == "country"


def test_country_with_no_forecast_says_so(ctx):
    a = ask.answer("what is heading to Nepal", ctx)["answer"]
    assert a["kind"] == "country" and a["chance"] is None


def test_unparseable_question_fails_gracefully(ctx):
    r = ask.answer("who will win the world cup", ctx)
    assert r["intent"] == "none" and r["answer"]["kind"] == "help"
    assert "Where will Squid Game go next?" in r["answer"]["message"]
    assert r["links"] == [] and r["steps"][0]["ok"] is False
    assert ask.answer("   ", ctx)["answer"]["kind"] == "help"


def test_songs_for_a_show_uses_scout_and_a_live_slot(ctx):
    live = FakeLive()
    r = ask.answer("Find songs for Stranger Things", {**ctx, "live": live})
    assert r["intent"] == "artists_for_show" and r["answer"]["kind"] == "scout"
    assert live.calls == ["take", ("scout", "Stranger Things")]
    assert ask.answer("music for Wednesday in Brazil", {**ctx, "live": live})["answer"]["show"] == "Wednesday"


def test_song_check_parses_one_and_several_songs(ctx):
    live = FakeLive()
    r = ask.answer("Running Up That Hill by Kate Bush for Stranger Things", {**ctx, "live": live})
    assert r["intent"] == "song_check" and r["answer"]["kind"] == "ripple"
    assert live.calls[1] == ("ripple", "Stranger Things", [("Running Up That Hill", "Kate Bush")])
    live.calls.clear()
    ask.answer("Psycho Killer by Talking Heads and Master of Puppets by Metallica, Hey Jude by Simon and Garfunkel in Wednesday",
               {**ctx, "live": live})
    assert live.calls[1][2] == [("Psycho Killer", "Talking Heads"), ("Master of Puppets", "Metallica"),
                                ("Hey Jude", "Simon and Garfunkel")]


def test_song_check_limits(ctx):
    many = ", ".join(f"S{i} by A{i}" for i in range(9))
    r = ask.answer(f"{many} for Wednesday", {**ctx, "live": FakeLive()})
    assert r["answer"]["kind"] == "help" and "1 to 8 songs" in r["answer"]["message"]


def test_live_routes_report_a_refused_slot_in_the_steps(ctx):
    class Busy(FakeLive):
        def take(self):
            raise ask.LiveError("limit is 10 live scorings per hour per visitor")

    r = ask.answer("songs for Wednesday", {**ctx, "live": Busy()})
    assert r["answer"]["kind"] == "unavailable" and "limit is 10" in r["answer"]["message"]
    assert r["steps"][-1]["ok"] is False
    assert ask.answer("songs for Wednesday", ctx)["answer"]["kind"] == "unavailable"  # no live tools at all


def test_response_shape_and_question_length_cap(ctx):
    r = ask.answer("Where will Fukrey Returns go next? " + "x" * 500, ctx)
    assert set(r) == {"intent", "steps", "answer", "links"}
    assert all(set(s) >= {"tool", "input", "ok", "note"} for s in r["steps"])


def test_endpoint_wires_the_router(monkeypatch, ctx):
    from fastapi.testclient import TestClient

    from aftershock import api
    monkeypatch.setattr(api, "ask_context", lambda live=None: {**ctx, "live": live})
    c = TestClient(api.app)
    body = c.get("/api/ask", params={"q": "What should Fukrey Returns pair with in Bangladesh?"}).json()
    assert body["intent"] == "launch_kit"
    assert c.get("/api/ask", params={"q": "x" * 201}).status_code == 422
    assert c.get("/api/ask", params={"q": ""}).status_code == 422


def test_non_latin_question_gets_a_script_hint_not_a_guess(ctx):
    out = ask.answer("\u091c\u092c \u0935\u0940 \u092e\u0947\u091f", ctx)
    assert out["intent"] == "none" and "Latin alphabet" in out["steps"][0]["note"]


def test_unknown_place_is_named_in_the_steps_not_ignored(ctx):
    r = ask.answer("What should Fukrey Returns pair with in Narnia?", ctx)
    assert any("I don't know a country called Narnia" in s["note"] for s in r["steps"])
    assert r["answer"]["kind"] in ("storm", "title")


def test_where_next_for_a_title_netflix_never_charted_says_so_and_suggests_breakouts(ctx):
    r = ask.answer("where will visionquest go next?", ctx)
    assert r["intent"] == "forecast"
    assert r["answer"]["message"].startswith("visionquest has not been in Netflix's Top 10 in any country since 2024")
    assert "this week's include Fukrey Returns" in r["answer"]["message"]
    assert r["links"][0] == {"label": "Fukrey Returns", "href": "#/storm/fukrey-returns"}
    assert [s["ok"] for s in r["steps"]] == [True, False]


def test_help_example_uses_the_featured_plan(ctx):
    ctx["featured"] = {"title": "Nightwatch: Demons Are Forever", "country": "Sweden"}
    msg = ask.answer("zzz yyy xxx www vvv uuu ttt sss", ctx)["answer"]["message"]
    assert "What should Nightwatch: Demons Are Forever pair with in Sweden?" in msg and "Fukrey Returns pair" not in msg


PHRASINGS = ["visionquest in india", "forecast for visionquest", "will visionquest chart in brazil?", "how will visionquest do",
             "visionquest", "next countries for visionquest", "which countries will visionquest reach", "what about visionquest?",
             "plan a launch for visionquest in nepal", "launch visionquest in brazil", "is visionquest a breakout",
             "visionquest nepal", "where will visionquest go next", "What should visionquest pair with in Brazil?",
             "spread of visionquest to brazil", "tell me about visionquest", "how far will visionquest travel",
             "which brands fit visionquest fans in nepal", "where will nightwach go next", "is fukrey retuns a breakout",
             "forecast for fukrey retuns in nepal", "Where Will Visionquest Chart Next", "Visionquest in NP", "visionquest?!"]


@pytest.mark.parametrize("question", PHRASINGS)
def test_no_phrasing_about_a_title_dead_ends(ctx, question):
    r = ask.answer(question, ctx)
    msg = r["answer"].get("message", "")
    assert "could not tell what you are asking" not in msg and r["intent"] != "none"


def test_unknown_title_answer_names_the_title_without_intent_words_or_country(ctx):
    r = ask.answer("plan a launch for Vision Quest in Nepal", ctx)
    assert r["answer"]["message"].startswith("Vision Quest has not been in Netflix's Top 10 in any country since 2024, so there")
    assert 'ask "What is heading to Nepal?"' in r["answer"]["message"]
    assert r["answer"]["did_you_mean"] is None
    assert "Fukrey Returns" in r["answer"]["message"]


def test_did_you_mean_links_a_storm_and_names_an_index_title(ctx):
    r = ask.answer("where will fkry rtrns go next", ctx)
    assert r["answer"]["did_you_mean"] == {"title": "Fukrey Returns", "href": "#/storm/fukrey-returns"}
    assert "Did you mean Fukrey Returns?" in r["answer"]["message"]
    assert r["links"][0] == {"label": "Storm page for Fukrey Returns", "href": "#/storm/fukrey-returns"}


def test_whats_heading_to_a_country_routes_to_the_country_answer(ctx):
    for q in ("what's heading to Brazil", "whats heading to Brazil", "What’s coming to Brazil?"):
        a = ask.answer(q, ctx)["answer"]
        assert a["kind"] == "country" and a["name"] == "Brazil"


def test_questions_that_are_not_about_a_title_still_get_help(ctx):
    for q in ("who will win the world cup", "zzz yyy xxx www vvv uuu ttt sss", "   "):
        assert ask.answer(q, ctx)["answer"]["kind"] == "help"
        assert "could not tell" in ask.answer(q, ctx)["answer"]["message"] or q.strip() == ""
