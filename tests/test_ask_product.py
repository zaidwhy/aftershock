"""The ask router's product questions: what each feature does, why a title is missing or forecast where it is, where to
release something, who it is for, small talk and the never-a-dead-end fallback. Fixture data only, no network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402
from test_ask import ctx  # noqa: E402,F401  (the shared fixture)

from aftershock import ask  # noqa: E402

FEATURE_CASES = [
    ("what does plan a launch do", "feature_help", "7 visible steps", "#/plan"),
    ("What is Plan A Launch?", "feature_help", "downloadable Launch Brief", "#/plan"),
    ("what is the scorecard", "feature_help", "including the misses", "#/scorecard"),
    ("WHAT IS THE SCORCARD", "feature_help", "including the misses", "#/scorecard"),  # misspelled, shouted
    ("what is the ledger", "feature_help", "3,240 forecasts", "#/ledger"),
    ("wat is the ledgr", "feature_help", "graded from 15 Nov", "#/ledger"),
    ("what is sync scout", "feature_help", "different their listeners' ages are", "#/scout"),
    ("Sync Scout", "feature_help", "which artists its fans like", "#/scout"),
    ("what is song check", "feature_help", "reaches a new crowd", "#/try"),
    ("what's the song checker", "feature_help", "age groups are compared", "#/try"),
    ("what is for artists", "feature_help", "where their next fans are this week", "#/artists"),
    ("what is the globe", "feature_help", "this week's breakouts", "#/"),
    ("what does the map show", "feature_help", "forecast to go next", "#/"),
    ("what is plan a release", "feature_help", "audience affinity", "#/release"),
    ("explain the weekly job", "feature_help", "automatic weekly job", "#/agent"),
    ("how accurate is the forecast", "feature_help", "(ROC AUC 0.82)", "#/scorecard"),
    ("how do I use this", "tour", "tour button replays the guided tour", "#/"),
    ("give me a tour", "tour", "Plan a release does the same", "#/plan"),
    ("what can you do", "capabilities", "what each page of the site does", "#/release"),
    ("what is qloo's role", "qloo_role", "71% of the time", "#/plan"),
    ("how does it use Qloo?", "qloo_role", "the AI proposes and Qloo decides", "#/plan"),
]


@pytest.mark.parametrize("question,intent,text,href", FEATURE_CASES)
def test_feature_questions_get_a_short_paragraph_and_the_page_link(ctx, question, intent, text, href):
    r = ask.answer(question, ctx)
    assert r["intent"] == intent and r["answer"]["kind"] == "help"
    assert text in r["answer"]["message"]
    assert href in [link["href"] for link in r["links"]]
    assert [s["n"] for s in r["steps"]] == list(range(1, len(r["steps"]) + 1)) and r["steps"][0]["tool"] == "understand"


def test_qloo_answer_numbers_add_up(ctx):
    msg = ask.answer("what is qloo's role", ctx)["answer"]["message"]
    for fact in ("1,615 names", "29% were backed", "37% were known", "34% were not in Qloo", "Netflix history only"):
        assert fact in msg


def test_a_title_named_like_a_feature_word_stays_a_title(ctx):
    r = ask.answer("where will Squid Game go next", ctx)
    assert r["intent"] == "title_lookup"
    assert ask.answer("plan a launch for visionquest in nepal", ctx)["intent"] == "forecast"  # not the Plan a launch blurb


def test_why_a_title_is_not_here_when_it_charted_but_is_not_a_breakout(ctx):
    for q in ("why isn't Squid Game here", "Why can't I find Squid Game?"):
        r = ask.answer(q, ctx)
        msg = r["answer"]["message"]
        assert r["intent"] == "why_missing"
        assert "Squid Game: Season 3 is in Netflix's Top 10 history (first charted 2025-06-23, last added a country 2025-07-03" in msg
        assert "has to start in one country" in msg and "worldwide" in msg and "nothing to forecast" in msg


def test_why_missing_repairs_a_misspelling_and_says_so(ctx):
    r = ask.answer("why is Stranger Thing missing", ctx)
    assert "The closest title is Stranger Things: Season 5." in r["answer"]["message"]


def test_why_missing_for_a_title_netflix_never_charted_points_to_plan_a_release(ctx):
    for q in ("why isn't Zebra Planet here", "WHY CANT I FIND zebra planet"):
        r = ask.answer(q, ctx)
        assert "has not been in Netflix's Top 10 in any country since 2024" in r["answer"]["message"]
        assert "Plan a release" in r["answer"]["message"]
        assert r["links"][-1]["href"] == "#/release?name=" + ("Zebra%20Planet" if "Zebra" in q else "zebra%20planet")
        assert [x["ok"] for x in r["steps"]] == [True, False]


def test_why_missing_suggests_the_nearest_title(ctx):
    r = ask.answer("why isn't fkry rtrns here", ctx)
    assert "Did you mean Fukrey Returns?" in r["answer"]["message"] and r["intent"] == "why_missing"
    assert r["links"][0] == {"label": "Storm page for Fukrey Returns", "href": "#/storm/fukrey-returns"}
    assert "is here" in ask.answer("why isnt Fukrey Retuns listed", ctx)["answer"]["message"]  # a near-exact typo resolves


def test_why_missing_for_a_current_breakout_says_it_is_here(ctx):
    r = ask.answer("why is Fukrey Returns not showing", ctx)
    assert "Fukrey Returns is here" in r["answer"]["message"]
    assert r["links"] == [{"label": "Full forecast for Fukrey Returns", "href": "#/storm/fukrey-returns"}]


def test_why_is_a_title_breaking_in_a_country_uses_the_forecast_why(ctx):
    r = ask.answer("Why is Fukrey Returns breaking in Bangladesh?", ctx)
    msg = r["answer"]["message"]
    assert r["intent"] == "why_forecast"
    assert "started in India" in msg and "38% chance" in msg and "Why: Bangladesh joined 3 of 10." in msg
    assert r["links"] == [{"label": "Full forecast for Fukrey Returns", "href": "#/storm/fukrey-returns"}]


def test_why_will_a_title_go_to_a_country_names_its_rank(ctx):
    msg = ask.answer("why will fukrey returns go to nepal", ctx)["answer"]["message"]
    assert "Nepal is the second most likely next country (of 4): a 20% chance" in msg and "Nepal joined 3 of 10." in msg


def test_why_a_country_that_is_not_in_the_forecast_lists_the_ones_that_are(ctx):
    msg = ask.answer("Why is Fukrey Returns going to Japan", ctx)["answer"]["message"]
    assert "Japan is not in the forecast for Fukrey Returns" in msg
    assert "Bangladesh (38%), Nepal (20%), Sri Lanka (10%)" in msg


def test_why_a_country_alone_reads_the_week_map_and_the_forecast_why(ctx):
    for q in ("why Brazil", "WHY BRAZIL?"):
        r = ask.answer(q, ctx)
        assert "Brazil has a 20% chance of getting at least one new breakout this week" in r["answer"]["message"]
        assert "Fukrey Returns (5%): Brazil joined 3 of 10." in r["answer"]["message"]
        assert r["links"][0]["href"] == "#/storm/fukrey-returns"


def test_why_without_a_country_gives_the_top_forecast(ctx):
    msg = ask.answer("why Fukrey Returns", ctx)["answer"]["message"]
    assert "Bangladesh is the most likely next country (of 4): a 38% chance" in msg and "After that: Nepal (20%), Sri Lanka (10%)." in msg


def test_why_for_an_index_title_without_a_written_reason_says_so(ctx):
    msg = ask.answer("why is Fresh Show heading to Japan", ctx)["answer"]["message"]
    assert "Japan is the most likely next country (of 1): a 31% chance" in msg and "No written reason is stored" in msg


def test_where_should_i_release_x_links_plan_a_release_with_the_name(ctx):
    for q, name in (("Where should I release Midnight Drive?", "Midnight%20Drive"),
                    ("I'm launching Midnight Drive", "Midnight%20Drive"),
                    ("plan a release for The Long Walk", "The%20Long%20Walk"),
                    ("where will my album Blue Hour work", "Blue%20Hour&kind=music")):
        r = ask.answer(q, ctx)
        assert r["intent"] == "release_plan" and "Qloo ranks countries and cities by audience affinity" in r["answer"]["message"]
        assert r["links"][0]["href"] == f"#/release?name={name}", q


def test_a_release_question_without_a_title_links_the_bare_page(ctx):
    for q in ("where will my comedy special work", "Where should I release my comedy tour in Brazil?", "where should I tour"):
        r = ask.answer(q, ctx)
        assert r["intent"] == "release_plan" and r["links"] == [{"label": "Plan a release", "href": "#/release"}], q
        assert "Type your title on that page" in r["answer"]["message"]


def test_a_release_title_is_url_encoded(ctx):
    link = ask.answer("I'm launching Tom & Jerry: The Tour", ctx)["links"][0]["href"]
    assert link == "#/release?name=Tom%20%26%20Jerry%3A%20The%20Tour"


def test_a_song_by_an_artist_in_a_release_question_is_not_a_song_check(ctx):
    r = ask.answer("where should I release my album Blue Hour by Nova in Brazil", ctx)
    assert r["intent"] == "release_plan" and r["links"][0]["href"] == "#/release?name=Blue%20Hour%20by%20Nova&kind=music"


def test_who_is_this_for_names_the_buyers_and_admits_there_are_no_customers(ctx):
    for q in ("who is this for", "Who would pay for this?"):
        r = ask.answer(q, ctx)
        msg = r["answer"]["message"]
        assert r["intent"] == "audience" and "labels' catalogue teams" in msg and "promoters" in msg and "brand marketers" in msg
        assert "There are no customers and no prices yet." in msg


def test_who_made_this_links_the_team_page(ctx):
    for q in ("who made this", "Who built AFTERSHOCK?"):
        r = ask.answer(q, ctx)
        assert r["intent"] == "about" and r["links"] == [{"label": "About the team", "href": "#/about"}]


def test_small_talk_gets_a_friendly_line_and_three_examples(ctx):
    for q, line in (("hi", "Hi, I am the AFTERSHOCK assistant."), ("Thanks!", "You are welcome."), ("HELLO there", "Hi, I am")):
        r = ask.answer(q, ctx)
        assert r["intent"] == "small_talk" and r["answer"]["message"].startswith(line)
        assert r["answer"]["message"].count('"') == 6  # three quoted example questions


def test_unmatched_question_with_a_feature_word_gets_the_closest_feature(ctx):
    r = ask.answer("how do I download the brief", ctx)
    assert r["intent"] == "closest_feature" and "closest thing AFTERSHOCK does is Plan a launch" in r["answer"]["message"]
    assert r["links"] == [{"label": "Plan a launch", "href": "#/plan"}] and r["steps"][-1]["ok"] is True
    r = ask.answer("any good venues for stand up in london", ctx)
    assert r["links"][0]["href"] == "#/release" and "I could not" not in r["answer"]["message"]


def test_a_question_with_nothing_to_match_still_gets_examples_not_a_dead_end(ctx):
    for q in ("can I get a refund on my subscription", "Why is the sky blue"):
        r = ask.answer(q, ctx)
        assert r["intent"] == "none" and "I can answer questions like" in r["answer"]["message"]
        assert "I could not tell" not in r["answer"]["message"] and r["links"]
        assert r["answer"]["message"].count('"') == 6


def test_product_answers_keep_the_response_shape(ctx):
    for q in ("what is the ledger", "why Brazil", "hi", "who made this", "where should I tour", "why isn't Zebra Planet here"):
        r = ask.answer(q, ctx)
        assert set(r) == {"intent", "steps", "answer", "links"}
        assert all(set(link) == {"label", "href"} for link in r["links"])
        assert all(set(s) >= {"tool", "input", "ok", "note", "n"} for s in r["steps"])


# ---- round 2: the cold review's findings -------------------------------------------------------------------------

from test_ask import storm  # noqa: E402


@pytest.mark.parametrize("question,href", [
    ("where should Kevin Hart tour", "#/release?name=Kevin%20Hart&kind=music"),
    ("Where should Dua Lipa tour in 2027?", "#/release?name=Dua%20Lipa&kind=music"),
    ("plan a tour for Dua Lipa", "#/release?name=Dua%20Lipa&kind=music"),
    ("plan a tour for Kevin Hart the comedian", "#/release?name=Kevin%20Hart&kind=comedy"),
    ("where should comedian Kevin Hart tour", "#/release?name=Kevin%20Hart&kind=comedy"),
])
def test_a_touring_question_goes_to_plan_a_release_not_the_site_tour(ctx, question, href):
    r = ask.answer(question, ctx)
    assert r["intent"] == "release_plan" and r["links"][0]["href"] == href


def test_a_music_default_for_a_tour_is_admitted_as_a_guess(ctx):
    guess = ask.answer("where should Dua Lipa tour", ctx)["answer"]["message"]
    assert "That is a guess, so switch the type on that page" in guess
    assert "guess" not in ask.answer("where should comedian Kevin Hart tour", ctx)["answer"]["message"]


@pytest.mark.parametrize("question", ["give me a guided tour", "take the tour", "Replay the tour", "show me around", "how do I use this"])
def test_only_the_guided_tour_phrases_map_to_the_site_tour(ctx, question):
    r = ask.answer(question, ctx)
    assert r["intent"] == "tour" and "tour button replays the guided tour" in r["answer"]["message"]


def test_the_word_tour_alone_is_not_the_site_tour(ctx):
    assert ask.answer("tour", ctx)["intent"] != "tour"
    assert ask.answer("which countries should my band tour", ctx)["intent"] == "release_plan"


@pytest.mark.parametrize("question,name", [("Cedric the Entertainer", "Cedric the Entertainer"), ("Kevin Hart", "Kevin Hart"),
                                           ("who is Kevin Hart", "Kevin Hart"), ("Who's dua lipa?", "dua lipa")])
def test_a_bare_name_is_not_called_a_netflix_title(ctx, question, name):
    r = ask.answer(question, ctx)
    msg = r["answer"]["message"]
    assert r["intent"] == "unknown_name" and f"AFTERSHOCK tracks Netflix breakouts, and {name} is not one this week" in msg
    assert "has not been in Netflix's Top 10" not in msg and "switch the type on that page" in msg
    assert r["links"][-1]["href"] == f"#/release?name={ask.quote(name, safe='')}&kind=music"
    assert [s["ok"] for s in r["steps"]] == [True, False]


@pytest.mark.parametrize("question", ["privacy", "Is my data stored?", "what data do you use", "legal", "terms of use"])
def test_a_data_question_gets_the_privacy_answer(ctx, question):
    r = ask.answer(question, ctx)
    msg = r["answer"]["message"]
    assert r["intent"] == "data_privacy" and r["links"] == [{"label": "About and data sources", "href": "#/about"}]
    assert "no accounts" in msg and "no cookies for tracking" in msg and "used only in memory" in msg and "not stored" in msg
    for source in ("Netflix's public Top 10 lists", "Qloo audience data", "Wikimedia pageviews", "MusicBrainz", "OpenStreetMap"):
        assert source in msg


def test_the_ip_claim_matches_the_limiter():
    """The privacy answer says the address lives only in memory; the limiter must be a plain in-process dict of timestamps."""
    from collections import deque

    from aftershock import api

    class Req:
        headers = {"x-forwarded-for": "203.0.113.9"}
        client = None

    api._ripple_hits.clear()
    api._take_live_slot(Req())
    (hits,) = api._ripple_hits.values()
    assert isinstance(hits, deque) and all(isinstance(t, float) for t in hits)
    api._ripple_hits.clear()


@pytest.mark.parametrize("question", ["best pizza in new york", "what is the best pizza in new york", "how tall is the eiffel tower",
                                      "cheap flights to paris next week"])
def test_off_topic_questions_get_generic_help_not_a_title_answer(ctx, question):
    r = ask.answer(question, ctx)
    msg = r["answer"]["message"]
    assert r["intent"] == "none" and "I can answer questions like" in msg
    assert "has not been in Netflix's Top 10" not in msg


@pytest.mark.parametrize("question", ["what does Qloo think Fukrey Returns fans in Bangladesh like",
                                      "what does Qloo think Fukrey fans in Bangladesh like",
                                      "What do Fukrey Returns fans in Bangladesh listen to",
                                      "what do fukrey returns viewers from Bangladesh watch"])
def test_what_do_fans_in_a_country_like_returns_the_kit_rows(ctx, question):
    r = ask.answer(question, ctx)
    a = r["answer"]
    assert r["intent"] == "launch_kit" and a["kind"] == "kit" and (a["title"], a["country"]) == ("Fukrey Returns", "Bangladesh")
    assert a["picks"]["artist"] == ["Mika Singh"] and a["places"] == ["Dhaka", "Sylhet"]


def test_fans_in_a_country_outside_the_kit_says_so(ctx):
    a = ask.answer("what do Fukrey Returns fans in Brazil like", ctx)["answer"]
    assert a["kind"] == "storm" and "no launch kit for Brazil" in a["note"]


@pytest.fixture
def primate_ctx(ctx):
    return {**ctx, "storms": ctx["storms"] + [storm("Primate", ("JM", "Jamaica"))]}


@pytest.mark.parametrize("question", ["why is Primate breaking in Jamaica", "Why will Primate go to Jamaica?"])
def test_why_a_title_in_its_origin_country_says_it_broke_out_there(primate_ctx, question):
    r = ask.answer(question, primate_ctx)
    msg = r["answer"]["message"]
    assert r["intent"] == "why_forecast" and "Primate broke out in Jamaica" in msg
    assert "not in the forecast" not in msg and "Bangladesh (38%), Nepal (20%), Sri Lanka (10%)" in msg


@pytest.mark.parametrize("alias,code,name", [("Trinidad", "TT", "Trinidad and Tobago"), ("Korea", "KR", "South Korea"),
                                             ("UAE", "AE", "United Arab Emirates"), ("Emirates", "AE", "United Arab Emirates"),
                                             ("Holland", "NL", "Netherlands"), ("Czechia", "CZ", "Czechia"), ("Czech", "CZ", "Czechia")])
def test_country_aliases_resolve_even_when_no_forecast_names_the_country(alias, code, name):
    found = ask.find_country(ask._norm(f"what is heading to {alias}"), f"what is heading to {alias}", {"BR": "Brazil"})
    assert found[:2] == (code, name)


def test_aliases_resolve_to_the_forecasts_own_spelling(ctx):
    names = {"KR": "South Korea", "NL": "Netherlands"}
    assert ask.find_country("korea", "Korea", names)[:2] == ("KR", "South Korea")
    a = ask.answer("what is heading to Holland", ctx)["answer"]
    assert a["kind"] == "country" and a["code"] == "NL"


def test_fallback_examples_use_this_weeks_recent_breakout_not_a_catalog_title(ctx):
    old = storm("Old Catalog Show")
    old["summary"]["meta"]["year"] = 2009
    old["summary"]["top_forecast"] = {**old["summary"]["top_forecast"], "probability": 0.9}
    new = storm("Fresh Release")
    new["summary"]["top_forecast"] = {**new["summary"]["top_forecast"], "probability": 0.3}
    msg = ask.answer("zzz yyy xxx www vvv uuu ttt sss", {**ctx, "storms": [old, new]})["answer"]["message"]
    assert 'Where will Fresh Release go next?' in msg and "What should Fresh Release pair with in Bangladesh?" in msg
    assert "Old Catalog Show" not in msg and "Squid Game" not in msg


def test_fallback_examples_keep_a_static_fallback_only_when_there_are_no_storms(ctx):
    msg = ask.answer("zzz yyy xxx www vvv uuu ttt sss", {**ctx, "storms": []})["answer"]["message"]
    assert "Where will Squid Game go next?" in msg and "Nightwatch: Demons Are Forever pair with in Sweden" in msg


@pytest.mark.parametrize("question", ["does the forecast work", "Is it accurate?", "how well does it work"])
def test_accuracy_questions_get_the_baseline_comparison_not_a_title_lookup(ctx, question):
    # A judge asking whether it works must hear the result against the obvious guess, not "not in Netflix's Top 10".
    r = ask.answer(question, ctx)
    assert r["intent"] == "feature_help"
    assert "4.1%" in r["answer"]["message"] and "9.8%" in r["answer"]["message"]


def test_ledger_answer_says_locked_before_netflix_published(ctx):
    msg = ask.answer("what is the ledger", ctx)["answer"]["message"]
    assert "before Netflix published" in msg and "outcomes were known" not in msg
