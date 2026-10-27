"""Per-week archive of breakout storms, so links to a past week's storm keep resolving after the week rolls over."""
import json
from pathlib import Path


def write_week(archive_dir, week, storms):
    """Write {week, storms: [{id, summary, detail}]} for one week; the same week is overwritten on a rerun."""
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    body = {"week": str(week), "storms": [{"id": s["summary"]["id"], "summary": s["summary"], "detail": s["detail"]}
                                          for s in storms]}
    (archive_dir / f"{week}.json").write_text(json.dumps(body, indent=1), encoding="utf-8")


def weeks(archive_dir):
    """Archived week files, most recent week first."""
    archive_dir = Path(archive_dir)
    return sorted(archive_dir.glob("*.json"), key=lambda p: p.stem, reverse=True) if archive_dir.exists() else []


def find(archive_dir, storm_id):
    """(week, detail) for the most recent archived week holding this id, else None."""
    for path in weeks(archive_dir):
        for item in json.loads(path.read_text(encoding="utf-8"))["storms"]:
            if item["id"] == storm_id:
                return path.stem, item["detail"]
    return None


def all_storms(archive_dir):
    """Every archived (week, id, detail), most recent week first."""
    out = []
    for path in weeks(archive_dir):
        out += [(path.stem, i["id"], i["detail"]) for i in json.loads(path.read_text(encoding="utf-8"))["storms"]]
    return out
