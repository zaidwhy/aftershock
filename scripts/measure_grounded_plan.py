"""EXPLORATORY measurement of the grounded plan (aftershock/grounded_plan.py). Not pre-registered: it was
designed after seeing the registered experiment's result (docs/EXPERIMENT_KITS.md, kit_experiment.json), on the
same 81 title-country pairs and the same cached Gemini answers, so it can describe the idea but not confirm it.

For each pair the LLM's title-specific picks are checked against Qloo; we report how many are confirmed, not
placed or not in Qloo, how title-specific the confirmed-only plan is against the LLM's country-only kit (the
registered metric), and how many confirmed names Qloo's own top-5 kit did not contain.
Writes data/results/grounded_plan.json: aggregate numbers only, no entity names or affinities (Qloo terms).

Run: .venv/Scripts/python scripts/measure_grounded_plan.py   (reads cached Gemini answers; no new Gemini calls)
"""
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import experiment_kits as ek  # noqa: E402
from aftershock.grounded_plan import ground  # noqa: E402
from aftershock.launch_kit import DOMAINS, country_picks  # noqa: E402
from aftershock.llm_baseline import calls as llm_calls  # noqa: E402
from aftershock.qloo import Qloo  # noqa: E402

OUT = ROOT / "data" / "results" / "grounded_plan.json"
QLOO_BUDGET = 600


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    storms = json.loads(ek.STORMS.read_text(encoding="utf-8"))["storms"]
    entity_of = {s["summary"]["id"]: s["detail"].get("qloo_entity") for s in storms}
    kit_of = {(s["summary"]["id"], r["code"]): r["kit"] for s in storms for r in s["detail"].get("launch_kit") or []}
    pairs = ek.load_pairs()
    client = Qloo(call_budget=QLOO_BUDGET)
    llm = ek.llm_title_kits(pairs)
    lc = ek.llm_country_kits({p["country"] for p in pairs})
    if llm_calls["live"]:
        raise SystemExit(f"{llm_calls['live']} live Gemini call(s) were needed; the cache should have had them all")
    qc = {c: {d: country_picks(client, c, t) for d, t in DOMAINS.items()} for c in sorted({p["country"] for p in pairs})}

    totals = {"confirmed": 0, "not_placed": 0, "not_in_qloo": 0}
    checked_pairs, new_names, both_names = [], 0, 0
    for p in pairs:
        if p["id"] not in llm or p["country"] not in lc:
            continue
        plan = ground(client, entity_of[p["storm"]], p["country"], llm[p["id"]], kit_of[(p["storm"], p["code"])])
        if not plan:
            continue
        by_domain = {d: [c["name"] for c in plan["confirmed"] if c["domain"] == d] for d in DOMAINS}
        totals["confirmed"] += len(plan["confirmed"])
        totals["not_placed"] += plan["dropped"]["not_placed"]
        totals["not_in_qloo"] += plan["dropped"]["not_in_qloo"]
        both_names += sum(c["both"] for c in plan["confirmed"])
        new_names += sum(not c["both"] for c in plan["confirmed"])
        checked_pairs.append({"plan": ek.specificity(by_domain, lc[p["country"]]),
                              "llm": ek.specificity(llm[p["id"]], lc[p["country"]]),
                              "qloo": ek.specificity(p["Q"], qc[p["country"]]), "n": len(plan["confirmed"])})
    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None  # noqa: E731
    both = [c for c in checked_pairs if c["plan"] is not None and c["llm"] is not None and c["qloo"] is not None]
    picks = sum(totals.values())
    result = {
        "status": "exploratory, not pre-registered; designed after the registered result, same 81 pairs and cached Gemini answers",
        "model": ek.MODEL,
        "pairs": len(pairs), "pairs_checked": len(checked_pairs), "picks_checked": picks,
        "verdict_shares": {k: round(v / picks, 3) for k, v in totals.items()} if picks else None,
        "verdict_counts": totals,
        "title_specificity_same_pairs": {"pairs": len(both), "qloo_kit": mean([c["qloo"] for c in both]),
                                         "llm_all_picks": mean([c["llm"] for c in both]),
                                         "grounded_plan_confirmed_only": mean([c["plan"] for c in both]),
                                         "note": "against the LLM country-only kit, as in the registered metric; "
                                                 "Qloo's kit is scored against Qloo's country-only kit"},
        "confirmed_picks": {"total": totals["confirmed"], "also_in_qloo_top5_kit": both_names,
                            "not_in_qloo_top5_kit": new_names,
                            "mean_new_per_pair": mean([0] if not checked_pairs else [new_names / len(checked_pairs)])},
        "calls": {"qloo_live": client.live_calls, "qloo_budget": QLOO_BUDGET, "llm_live": llm_calls["live"],
                  "llm_cached": llm_calls["cached"]},
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
