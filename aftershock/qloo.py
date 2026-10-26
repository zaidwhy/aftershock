"""Qloo hackathon API client: GET-only, paced, disk-cached, bounded.

The key comes from QLOO_API_KEY (loaded from .env). Responses are cached under .cache/qloo/,
which is gitignored: Qloo's terms forbid publishing their data in a public repo.
"""
import hashlib
import json
import logging
import os
import re
import threading
import time
import unicodedata
from pathlib import Path

import httpx
from dotenv import load_dotenv

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Serverless filesystems are read-only outside /tmp.
CACHE_DIR = Path("/tmp/qloo-cache") if os.environ.get("VERCEL") else ROOT / ".cache" / "qloo"
MIN_INTERVAL_S = 0.25  # 4 req/s; the documented tier allows 5
TIMEOUT_S = 20.0


class QlooError(RuntimeError):
    pass


class Qloo:
    def __init__(self, api_key=None, base_url=None, call_budget=2000, offline=False):
        self.api_key = api_key or os.environ.get("QLOO_API_KEY", "")
        self.base_url = (base_url or os.environ.get("QLOO_BASE_URL") or "https://hackathon.api.qloo.com").rstrip("/")
        self.call_budget = call_budget
        self.offline = offline
        self.live_calls = 0
        self.month_remaining = None
        self._lock = threading.Lock()
        self._last = 0.0
        if not self.api_key and not offline:
            raise QlooError("QLOO_API_KEY is not set; copy .env.example to .env and fill it in")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get(self, path, params):
        key = hashlib.sha256(json.dumps([path, sorted(params.items())], default=str).encode()).hexdigest()[:32]
        cached = CACHE_DIR / f"{key}.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))
        if self.offline:
            raise QlooError(f"offline and not cached: {path} {params}")
        if self.live_calls >= self.call_budget:
            raise QlooError(f"call budget of {self.call_budget} reached")
        with self._lock:
            wait = MIN_INTERVAL_S - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.live_calls += 1
        resp = httpx.get(self.base_url + path, params=params, headers={"X-Api-Key": self.api_key}, timeout=TIMEOUT_S)
        # The header name has varied across the event (Discord reports two spellings).
        for name, value in resp.headers.items():
            if "remaining" in name.lower() and "month" in name.lower():
                self.month_remaining = value
        if resp.status_code != 200:
            raise QlooError(f"{resp.status_code} on {path}: {resp.text[:300]}")
        body = resp.json()
        cached.write_text(json.dumps(body), encoding="utf-8")
        return body

    def search(self, query, types=None, take=5):
        params = {"query": query, "take": take}
        if types:
            params["types"] = types
        return self.get("/search", params).get("results", [])

    def insights(self, **params):
        return self.get("/v2/insights", {k.replace("__", "."): v for k, v in params.items()})


def norm(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\(.*?\)|:.*$", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def resolve(client, name, types):
    """Return the first search hit whose name matches, or None. /search always returns its
    nearest match even for unknown names, so an unchecked first hit is not a resolution."""
    for hit in client.search(name, types=types):
        if norm(hit.get("name", "")) == norm(name):
            return hit
    return None
