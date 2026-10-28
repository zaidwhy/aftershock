"""Precompute the five worked "Plan a release" examples into public/data/release/, so the page shows a plan with no
live call and no wait.

Run: .venv/Scripts/python scripts/build_release_showcases.py
Each example is a live plan (up to 40 Qloo calls, cached on disk afterwards). public/data/ holds Qloo-derived data and
is gitignored; it ships in a deploy, not in the repo. Standalone on purpose: export_static.py only adds files and
never clears public/data/, so these survive it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aftershock.qloo import Qloo  # noqa: E402
from aftershock import release_plan  # noqa: E402
from aftershock.release_plan import MAX_CALLS, plan_release  # noqa: E402

OUT = ROOT / "public" / "data" / "release"
EXAMPLE = "Worked example, not a real upcoming release."
EXAMPLE_ACT = "Worked example for a real act, not an announced tour or release."
SHOWCASES = [
    {"slug": "zakir-khan", "name": "Zakir Khan", "kind": "comedy", "like": [], "headline": "A comedian's tour",
     "note": EXAMPLE_ACT},
    {"slug": "kevin-hart", "name": "Kevin Hart", "kind": "comedy", "like": [], "headline": "A comedian's tour",
     "note": EXAMPLE_ACT},
    {"slug": "korean-survival-thriller", "name": "An upcoming Korean survival thriller", "kind": "series",
     "like": ["Squid Game", "Alice in Borderland"], "headline": "An unreleased series, planned from comparables",
     "note": EXAMPLE},
    {"slug": "spanish-heist-film", "name": "A new Spanish heist thriller", "kind": "film",
     "like": ["Money Heist", "Elite"], "headline": "An unreleased film, planned from comparables",
     "note": EXAMPLE},
    {"slug": "dua-lipa", "name": "Dua Lipa", "kind": "music", "like": [], "headline": "A global pop tour",
     "note": EXAMPLE_ACT},
]


def _write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def main():
    release_plan.GEOCODE_BUDGET_S = 300  # a build has time for the Nominatim fallback; a live request does not
    client = Qloo(call_budget=len(SHOWCASES) * MAX_CALLS)
    index = []
    for spec in SHOWCASES:
        plan = plan_release(client, spec["name"], spec["kind"], spec["like"], region=spec.get("region", "any"),
                            home=spec.get("home"), goal=spec.get("goal"))
        plan |= {"example": True, "example_note": spec["note"], "headline": spec["headline"], "like": spec["like"]}
        _write(OUT / f"{spec['slug']}.json", plan)
        top = [{"name": c["name"], "places": (c.get("hotspots") or {}).get("places", []), "score": c["score"]}
               for c in plan.get("countries", [])[:3]]
        index.append({"slug": spec["slug"], "name": spec["name"], "kind": spec["kind"], "headline": spec["headline"],
                      "example_note": spec["note"], "resolved": plan["resolved"],
                      "signal_used": (plan.get("signal") or {}).get("used"), "region": plan["region"], "home": plan["home"],
                      "goal": plan["goal"], "top_countries": top})
        print(f"{spec['slug']}: resolved={plan['resolved']} signal={(plan.get('signal') or {}).get('used')} "
              f"calls={plan['calls']} top={[(t['name'], t['places'], t['score']) for t in top]}")
    _write(OUT / "index.json", {"examples": index})
    print(f"wrote {len(SHOWCASES) + 1} files under {OUT}; live Qloo calls this run: {client.live_calls}")


if __name__ == "__main__":
    main()
