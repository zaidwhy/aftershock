"""Append-only public forecast ledger.

Each line is one forecast, written before its outcome exists. Lines carry a hash chained to the
previous line, so an edited or reordered past forecast is detectable. Only our own derived numbers
go here (probabilities, scores), never raw Qloo responses.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "ledger" / "forecasts.jsonl"


def _lines(path=LEDGER):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append(forecasts, path=LEDGER, now=None):
    """forecasts: list of dicts with kind, subject, target, probability or score, resolves_after."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _lines(path)
    previous = existing[-1]["hash"] if existing else "genesis"
    locked_at = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    written = []
    with path.open("a", encoding="utf-8") as out:
        for item in forecasts:
            record = {"locked_at": locked_at, **item, "prev": previous}
            record["hash"] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()[:16]
            out.write(json.dumps(record, sort_keys=True) + "\n")
            previous = record["hash"]
            written.append(record)
    return written


def verify(path=LEDGER):
    """Return the index of the first broken line, or None when the chain is intact."""
    previous = "genesis"
    for index, record in enumerate(_lines(path)):
        claimed = record.get("hash")
        body = {k: v for k, v in record.items() if k != "hash"}
        if body.get("prev") != previous:
            return index
        if hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16] != claimed:
            return index
        previous = claimed
    return None


def read(path=LEDGER):
    return _lines(path)
