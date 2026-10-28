import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_forecasts  # noqa: E402
from aftershock import api  # noqa: E402


def storm(sid, title, rows):
    return {"summary": {"id": sid, "title": title},
            "detail": {"spillover": {"forecasts": [{"code": "BR", "name": "Brazil"}, {"code": "DE", "name": "Germany"}]},
                       "launch_kit": rows}}


def row(code, spec, generic, kit=None):
    return {"code": code, "specificity": spec, "generic": generic, "kit": kit if kit is not None else {"artist": [{"name": "A"}]}}


def test_kit_check_counts_means_and_examples():
    out = run_forecasts.kit_check([
        storm("a", "A", [row("BR", 0.9, False), row("DE", 0.2, True)]),
        storm("b", "B", [row("BR", 0.7, False), row("DE", 0.3, True), row("DE", None, False), row("BR", 0.5, False, kit={})])])
    assert (out["kits"], out["specific"], out["generic"]) == (4, 2, 2)
    assert out["mean_specificity"] == 0.525
    assert out["example_specific"]["id"] == "a" and out["example_specific"]["country"] == "Brazil"
    assert out["example_generic"]["id"] == "a" and out["example_generic"]["code"] == "DE"


def test_kit_check_without_kits_is_none():
    assert run_forecasts.kit_check([storm("a", "A", [])]) is None


def test_scorecard_adds_the_experiment_only_when_its_file_exists(tmp_path, monkeypatch):
    private = tmp_path / "private"
    private.mkdir()
    (private / "scorecard.json").write_text(json.dumps({"data_week": "2026-10-18"}), encoding="utf-8")
    monkeypatch.setattr(api, "PRIVATE", private)
    monkeypatch.setattr(api, "ROOT", tmp_path)
    assert "kit_experiment" not in api.scorecard()
    (tmp_path / "data" / "results").mkdir(parents=True)
    (tmp_path / "data" / "results" / "kit_experiment.json").write_text(json.dumps({
        "title_specificity": {"verdict": "no difference shown", "qloo": 0.61, "llm": 0.58},
        "llm_grounding": {"share_resolving_in_qloo": 0.4}, "scored_pairs": 80, "model": "m",
        "title_specificity_grounded_llm_only": {"pairs": 51, "qloo": 0.57, "llm_grounded": 0.83}}), encoding="utf-8")
    out = api.scorecard()["kit_experiment"]
    assert out["verdict"] == "no difference shown" and out["grounding_share"] == 0.4 and out["scored_pairs"] == 80
    assert (out["grounded_pairs"], out["grounded_qloo"], out["grounded_llm"]) == (51, 0.57, 0.83)
