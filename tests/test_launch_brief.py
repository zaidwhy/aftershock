import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from aftershock import api, launch_brief, llm_kits  # noqa: E402


def _kit(prefix):
    return {d: [{"name": f"{prefix} {d} {i}", "entity_id": f"{d}{i}"} for i in range(5)]
            for d in ("artist", "tv_show", "movie", "brand")}


def _confirmed(n):
    domains = ["artist", "tv_show", "movie", "brand"]
    return [{"domain": domains[i % 4], "name": f"Pick{i}", "both": i == 0} for i in range(n)]


def detail(rows):
    return {"id": "show", "title": "Show", "origin_countries": [{"code": "JP", "name": "Japan"}],
            "spillover": {"horizon_weeks": 4, "forecasts": [
                {"code": "KR", "name": "South Korea", "probability": 0.21},
                {"code": "TW", "name": "Taiwan", "probability": 0.05},
                {"code": "FR", "name": "France", "probability": 0.01}]},
            "launch_kit": rows}


def specific_row():
    return {"code": "KR", "kit": _kit("K"), "hotspots": {"places": ["Seoul", "Busan", "Daegu", "Gwangju"]},
            "specificity": 0.8, "generic": False,
            "plan": {"confirmed": _confirmed(5), "dropped": {"not_placed": 4, "not_in_qloo": 2}, "model": "gem"}}


def keys(made):
    return [s["key"] for s in made["steps"]]


def test_title_specific_kit_with_confirmed_picks_leads_with_ai():
    made = launch_brief.brief(detail([specific_row()]), "kr")
    assert keys(made) == ["forecast", "qloo_kit", "ai_proposals", "qloo_check", "cities", "events", "brief"]
    by = {s["key"]: s for s in made["steps"]}
    assert "21% chance" in by["forecast"]["found"] and "rank 1 of 3" in by["forecast"]["found"]
    assert "title-specific" in by["qloo_kit"]["found"] and "decision" not in by["qloo_kit"]
    assert "proposed 11 names" in by["ai_proposals"]["found"]
    assert by["qloo_check"]["found"].startswith("5 confirmed by Qloo") and "4 known to Qloo" in by["qloo_check"]["found"]
    assert "puts them ahead" in by["qloo_check"]["decision"]
    b = made["brief"]
    assert b["partner_basis"] == "ai_confirmed" and b["cities"] == ["Seoul", "Busan", "Daegu"]
    artists = next(g for g in b["partners"] if g["domain"] == "artist")["picks"]
    assert artists[0] == {"name": "Pick0", "source": "ai_confirmed", "also_in_qloo_kit": True}
    assert b["summary_source"] == "template" and "Seoul" in b["summary"]
    assert not any("distinctive" in a for a in b["avoid"])


def test_countrywide_kit_leans_on_confirmed_ai_picks_and_warns():
    row = specific_row() | {"generic": True, "specificity": 0.25}
    made = launch_brief.brief(detail([row]), "KR")
    by = {s["key"]: s for s in made["steps"]}
    assert by["qloo_kit"]["decision"].startswith("A countrywide kit")
    assert by["qloo_check"]["decision"] == ("The kit mostly matches the country's general taste, so the brief leans on "
                                            "the AI picks Qloo confirmed.")
    assert made["brief"]["kit_scope"] == "countrywide" and made["brief"]["partner_basis"] == "ai_confirmed"
    assert any("Do not say this audience is distinctive" in a for a in made["brief"]["avoid"])


def test_few_confirmed_picks_fall_back_to_qloo_kit():
    row = specific_row()
    row["plan"]["confirmed"] = _confirmed(2)
    made = launch_brief.brief(detail([row]), "KR")
    assert made["steps"][3]["decision"] == "Qloo confirmed fewer than 3 AI picks, so the brief uses Qloo's own kit."
    picks = [p for g in made["brief"]["partners"] for p in g["picks"]]
    assert made["brief"]["partner_basis"] == "qloo_kit" and {p["source"] for p in picks} == {"qloo_kit"}
    assert picks[0]["name"] == "K artist 0"


def test_row_without_a_plan_uses_qloo_kit_and_no_cities_is_stated():
    row = specific_row() | {"hotspots": {"places": []}}
    del row["plan"]
    made = launch_brief.brief(detail([row]), "KR")
    by = {s["key"]: s for s in made["steps"]}
    assert "No AI picks were made" in by["ai_proposals"]["found"]
    assert by["qloo_check"]["decision"].startswith("There is no AI plan")
    assert made["brief"]["cities"] == [] and "does not suggest cities" in by["cities"]["decision"]
    assert made["brief"]["partner_basis"] == "qloo_kit"
    assert "Start in" not in made["brief"]["summary"]


def test_unknown_country_has_no_brief():
    d = detail([specific_row()])
    assert launch_brief.brief(d, "TW") is None  # forecast but no kit row
    assert launch_brief.brief(d, "ZZ") is None


def test_api_brief_and_404s(monkeypatch, tmp_path):
    (tmp_path / "storms.json").write_text(json.dumps(
        {"week": "2026-10-25", "storms": [{"summary": {"id": "show"}, "detail": detail([specific_row()])}]}),
        encoding="utf-8")
    monkeypatch.setattr(api, "PRIVATE", tmp_path)
    c = TestClient(api.app)
    ok = c.get("/api/brief", params={"storm": "show", "country": "KR"}).json()
    assert ok["brief"]["headline"].startswith("Show has a 21% chance") and len(ok["steps"]) == 7
    assert c.get("/api/storms/show").json()["launch_kit"][0]["brief"] == ok
    nope = c.get("/api/brief", params={"storm": "nope", "country": "KR"})
    assert nope.status_code == 404 and nope.json()["detail"].startswith("No breakout called nope")
    nokit = c.get("/api/brief", params={"storm": "show", "country": "TW"})
    assert nokit.status_code == 404 and nokit.json()["detail"].startswith("No launch kit for TW on Show")


GOOD = "Show has a 21% chance of charting in South Korea within 4 weeks. Start in Seoul and approach Pick0."


def test_summary_validator_rejects_invented_name_and_number():
    b = launch_brief.brief(detail([specific_row()]), "KR")["brief"]
    assert launch_brief.validate_summary(GOOD, b)
    assert not launch_brief.validate_summary(GOOD + " Taylor Swift fans will love it.", b)
    assert not launch_brief.validate_summary(GOOD.replace("21%", "35%"), b)
    assert not launch_brief.validate_summary("", b)


def test_summaries_use_model_text_only_when_checked(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    d1, d2 = detail([specific_row()]), copy.deepcopy(detail([specific_row()]))
    calls = []

    def fake(prompt):
        calls.append(prompt)
        return {"summaries": [{"id": 0, "summary": GOOD}, {"id": 1, "summary": "Show will beat Oppenheimer in Seoul."}]}

    monkeypatch.setattr(llm_kits, "ask", fake)
    assert launch_brief.add_summaries([{"detail": d1}, {"detail": d2}]) == 1
    assert len(calls) == 1
    first = launch_brief.brief(d1, "KR")["brief"]
    assert first["summary_source"] == "ai, checked" and first["summary"] == GOOD
    assert launch_brief.brief(d2, "KR")["brief"]["summary_source"] == "template"


def test_no_key_means_template_and_no_call(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(llm_kits, "ask", lambda p: (_ for _ in ()).throw(AssertionError("Gemini was called")))
    d = detail([specific_row()])
    assert launch_brief.add_summaries([{"detail": d}]) == 0
    assert launch_brief.brief(d, "KR")["brief"]["summary_source"] == "template"


def test_calls_are_capped(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    n = launch_brief.BRIEFS_PER_CALL * (launch_brief.MAX_CALLS + 2)
    storms = [{"detail": detail([specific_row()])} for _ in range(n)]
    calls = []
    monkeypatch.setattr(llm_kits, "ask", lambda p: calls.append(p) or {"summaries": []})
    launch_brief.add_summaries(storms)
    assert len(calls) == launch_brief.MAX_CALLS


def test_event_ideas_step_section_caveat_and_validator():
    row = specific_row() | {"events": [{"artist": "Pick0", "cities": ["Seoul", "Busan"]},
                                       {"artist": "Pick4", "cities": ["Seoul"]}], "events_checked": 3}
    made = launch_brief.brief(detail([row]), "KR")
    by = {s["key"]: s for s in made["steps"]}
    assert by["events"]["title"] == "Match artists to cities"
    assert by["events"]["found"] == "Qloo's audience maps for 3 artists overlap this title's audience in 2 cities."
    assert "decision" not in by["events"]
    b = made["brief"]
    assert b["event_ideas"][0]["text"] == "Pick0 in Seoul and Busan: both audiences concentrate there."
    assert "Event ideas are where audiences overlap, not ticket-demand forecasts." in b["avoid"]
    assert launch_brief.validate_summary("Start in Busan with Pick0, who is strong in Seoul.", b)
    assert not launch_brief.validate_summary("Start in Osaka with Pick0.", b)


def test_no_overlap_states_the_decision_and_adds_no_caveat():
    row = specific_row() | {"events": [], "events_checked": 3}
    made = launch_brief.brief(detail([row]), "KR")
    by = {s["key"]: s for s in made["steps"]}
    assert by["events"]["decision"] == ("No artist's audience overlaps the title's cities, so the brief lists no "
                                        "event idea.")
    assert made["brief"]["event_ideas"] == []
    assert not any("Event ideas" in a for a in made["brief"]["avoid"])
