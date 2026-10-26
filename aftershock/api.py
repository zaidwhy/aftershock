"""HTTP API for AFTERSHOCK. Serves precomputed storms, the scorecard, replays and live RIPPLE scoring.

Live Qloo calls happen only in /api/ripple, capped per visitor; everything else is read from files
the forecast job writes. The Qloo key stays in the server environment.
"""
import json
import logging
import os
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles

from aftershock.qloo import CACHE_DIR, Qloo, QlooError
from aftershock.ripple import MAX_SONGS, score_placements

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / "data" / "private"
PUBLIC_DATA = ROOT / "data" / "public"
RIPPLE_PER_HOUR = 10
MAX_FIELD = 120

app = FastAPI(title="AFTERSHOCK", docs_url=None, redoc_url=None)
_ripple_hits = defaultdict(deque)


def _load(path):
    if not path.exists():
        raise HTTPException(503, f"{path.name} has not been generated yet")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "qloo_key": bool(os.environ.get("QLOO_API_KEY")),
            "cache_entries": len(list(CACHE_DIR.glob("*.json"))) if CACHE_DIR.exists() else 0}


@app.get("/api/storms")
def storms():
    data = _load(PRIVATE / "storms.json")
    return {"week": data["week"], "storms": [s["summary"] for s in data["storms"]]}


@app.get("/api/storms/{storm_id}")
def storm(storm_id: str):
    for item in _load(PRIVATE / "storms.json")["storms"]:
        if item["summary"]["id"] == storm_id:
            return item["detail"]
    raise HTTPException(404, f"no storm with id {storm_id!r}")


@app.get("/api/scorecard")
def scorecard():
    return _load(PRIVATE / "scorecard.json")


@app.get("/api/replays")
def replays():
    return _load(PUBLIC_DATA / "replays.json")


def _parse_songs(songs):
    placements = []
    for chunk in filter(None, (c.strip() for c in songs.split(";"))):
        if "|" not in chunk:
            raise HTTPException(422, f"each song must be 'song|artist'; got {chunk[:MAX_FIELD]!r}")
        song, artist = (part.strip() for part in chunk.split("|", 1))
        if not song or not artist or len(song) > MAX_FIELD or len(artist) > MAX_FIELD:
            raise HTTPException(422, f"song and artist must each be 1 to {MAX_FIELD} characters")
        placements.append((song, artist))
    if not placements or len(placements) > MAX_SONGS:
        raise HTTPException(422, f"send 1 to {MAX_SONGS} songs; got {len(placements)}")
    return placements


@app.get("/api/ripple")
def ripple(request: Request, show: str = Query(..., min_length=1, max_length=MAX_FIELD),
           songs: str = Query(..., min_length=3, max_length=MAX_SONGS * (2 * MAX_FIELD + 2))):
    placements = _parse_songs(songs)
    visitor = request.client.host if request.client else "unknown"
    hits = _ripple_hits[visitor]
    now = time.time()
    while hits and now - hits[0] > 3600:
        hits.popleft()
    if len(hits) >= RIPPLE_PER_HOUR:
        raise HTTPException(429, f"limit is {RIPPLE_PER_HOUR} live scorings per hour per visitor")
    hits.append(now)
    try:
        return score_placements(Qloo(call_budget=40), show, placements)
    except QlooError as err:
        log.warning("ripple scoring failed: %s", err)
        raise HTTPException(502, "Qloo did not answer this request; try again in a minute") from err


# Local runs serve the frontend too; on Vercel, public/ is served by the platform.
if (ROOT / "public").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "public", html=True), name="site")
