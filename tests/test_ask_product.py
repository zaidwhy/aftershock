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
    ("how accurate is the forecast", "feature_help", "ROC AUC 0.82 on 829 held-out breakouts", "#/scorecard"),
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
    assert "Nepal has a 20% chance" in msg and "number 2 of 4" in msg and "Nepal joined 3 of 10." in msg


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
    assert "Bangladesh has a 38% chance" in msg and "After that: Nepal (20%), Sri Lanka (10%)." in msg


def test_why_for_an_index_title_without_a_written_reason_says_so(ctx):
    msg = ask.answer("why is Fresh Show heading to Japan", ctx)["answer"]["message"]
    assert "Japan has a 31% chance" in msg and "No written reason is stored" in msg


def test_where_should_i_release_x_links_plan_a_release_with_the_name(ctx):
    for q, name in (("Where should I release Midnight Drive?", "Midnight%20Drive"),
                    ("I'm launching Midnight Drive", "Midnight%20Drive"),
                    ("plan a release for The Long Walk", "The%20Long%20Walk"),
                    ("where will my album Blue Hour work", "Blue%20Hour")):
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
    assert r["intent"] == "release_plan" and r["links"][0]["href"] == "#/release?name=Blue%20Hour%20by%20Nova"


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
