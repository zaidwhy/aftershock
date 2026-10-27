"""Write the read-only API responses as static files under public/data/, so the site needs no
serverless function (and no cold start) to read them.

Run after scripts/run_forecasts.py: .venv/Scripts/python scripts/export_static.py
Song releases (ripples) are deliberately not exported.
The bodies come from the API's own handler functions, so they are identical to the API's.
public/data/ holds Qloo-derived data and is gitignored; it ships in a deploy, not in the repo.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datetime import date, timedelta  # noqa: E402

from aftershock import api, ledger  # noqa: E402
from aftershock.netflix import first_entries, load_rows  # noqa: E402

OUT = ROOT / "public" / "data"
RAW = ROOT / "data" / "raw" / "all-weeks-countries.tsv"
HORIZON = 4
LEDGER_ROWS = 50
LEDGER_URL = "https://github.com/zaidwhy/aftershock/blob/main/ledger/forecasts.jsonl"


def _write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, separators=(",", ":")), encoding="utf-8")


def ledger_page(records, intact, first=None, last_week=None, names=None, horizon=HORIZON):
    """Small summary of the ledger for the #/ledger page: counts, first and last lock time, chain check and the
    most recent forecasts. `first` is {(show, season): {country: week}} from the Netflix history (grades the rows);
    without it every row is pending. Newest lock first; within one lock batch the likeliest forecast first.
    A row is a hit as soon as the country joined inside the horizon, a miss once the horizon has closed without."""
    names = names or {}

    def status(r):
        if r.get("kind") != "spillover" or first is None or last_week is None:
            return "pending"
        origin = date.fromisoformat(r["origin_week"])
        joined = first.get(tuple(r["title"]), {}).get(r["target"])
        if joined and origin < joined <= origin + timedelta(weeks=horizon):
            return "hit"
        return "miss" if origin + timedelta(weeks=horizon) <= last_week else "pending"

    def title(r):
        show, season = r["title"]
        return show if season == "N/A" else season

    recent = sorted(records, key=lambda r: (r["locked_at"], r.get("probability") or r.get("score") or 0), reverse=True)
    rows = [{"locked_at": r["locked_at"], "title": title(r), "country": names.get(r["target"], r["target"]),
             "probability": r.get("probability"), "status": status(r)} for r in recent[:LEDGER_ROWS]]
    return {"total": len(records), "titles": len({tuple(r["title"]) for r in records}),
            "first_locked": min((r["locked_at"] for r in records), default=None),
            "last_locked": max((r["locked_at"] for r in records), default=None),
            "intact": intact, "raw_url": LEDGER_URL, "rows": rows}


def _ledger_body(listing):
    first = last_week = None
    names = {f["code"]: f["name"] for s in listing["storms"] for f in [s["top_forecast"]] if f}
    if RAW.exists():
        rows = load_rows(RAW)
        first, last_week = first_entries(rows), date.fromisoformat(max(r["week"] for r in rows))
        names |= {r["country_iso2"]: r["country_name"] for r in rows}
    return ledger_page(ledger.read(), ledger.verify() is None, first, last_week, names)


def export(out=OUT):
    """Return the list of files written."""
    out = Path(out)
    listing = api.storms()
    _write(out / "storms.json", listing)
    for s in listing["storms"]:
        _write(out / "storms" / f"{s['id']}.json", api.storm(s["id"]))
    _write(out / "scorecard.json", api.scorecard())
    _write(out / "replays.json", api.replays())
    _write(out / "ledger.json", _ledger_body(listing))
    run = api.PRIVATE / "agent_run.json"
    if run.exists():
        _write(out / "agent_run.json", json.loads(run.read_text(encoding="utf-8")))
    return sorted(p for p in out.rglob("*.json"))


if __name__ == "__main__":
    files = export()
    print(f"wrote {len(files)} files under {OUT}")
