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

from aftershock import api  # noqa: E402

OUT = ROOT / "public" / "data"


def _write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, separators=(",", ":")), encoding="utf-8")


def export(out=OUT):
    """Return the list of files written."""
    out = Path(out)
    listing = api.storms()
    _write(out / "storms.json", listing)
    for s in listing["storms"]:
        _write(out / "storms" / f"{s['id']}.json", api.storm(s["id"]))
    _write(out / "scorecard.json", api.scorecard())
    _write(out / "replays.json", api.replays())
    return sorted(p for p in out.rglob("*.json"))


if __name__ == "__main__":
    files = export()
    print(f"wrote {len(files)} files under {OUT}")
