"""Minimal cached MusicBrainz client (1 req/s, descriptive User-Agent, disk cache)."""
import hashlib
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "musicbrainz"
UA = "aftershock/0.1 (https://github.com/zaidwhy/aftershock; zaidsyed7021@gmail.com)"
BASE = "https://musicbrainz.org/ws/2/"
LIMIT = 1500
stats = {"live": 0, "cached": 0}
_last = [0.0]


def get(path: str, **params) -> dict:
    params["fmt"] = "json"
    key = hashlib.sha1((path + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if f.exists():
        stats["cached"] += 1
        return json.loads(f.read_text(encoding="utf-8"))
    if stats["live"] >= LIMIT:
        raise RuntimeError("MusicBrainz request cap reached")
    for attempt in range(4):
        wait = 1.1 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        stats["live"] += 1
        try:
            r = httpx.get(BASE + path, params=params, headers={"User-Agent": UA}, timeout=30)
        except httpx.TransportError:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code in (503, 429):
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        break
    else:
        raise RuntimeError(f"MusicBrainz unavailable for {path}")
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(r.json()), encoding="utf-8")
    return r.json()
