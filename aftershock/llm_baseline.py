"""LLM-only baseline for the age-gap predictor: a minimal Gemini REST client plus a prompt that asks
for the US audience's age-band shares of each entity (artist or show), cached on disk by request hash."""
import hashlib
import json
import os
import time
from pathlib import Path

import httpx

from aftershock import qloo  # noqa: F401  (importing it loads the project's environment file)
from aftershock.ripple import AGE_BANDS

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "llm"
BASE = "https://generativelanguage.googleapis.com/v1beta"
MIN_INTERVAL = 7.0
BATCH = 25

PROMPT = (
    "For each entity below, estimate the share of its US audience that falls in each of these six age "
    "bands: " + ", ".join(AGE_BANDS) + ". Use your general knowledge of who listens to or watches it. "
    "For each entity the six shares are non-negative numbers that sum to 1. "
    "Reply with JSON only: an object mapping each entity string exactly as given to an object with the "
    "six band names as keys and the shares as values.\n\nKind of entity: {kind}\nEntities:\n{names}"
)

_last_call = [0.0]
calls = {"live": 0, "cached": 0}


def _key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return key.strip().strip("\"'").lstrip("=")


def _check(resp):
    """raise_for_status would put the request URL (which carries the key) in the message."""
    if resp.status_code >= 400:
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")


def pick_model():
    """gemini-2.5-flash is listed but returns 404 "no longer available to new users" for this key, and the
    error names gemini-3.8-flash as the replacement, but 3.8 and 3.7 flash timed out under load in a probe while
    3.5 flash answered; so prefer 3.5 flash, then the newest plain flash model."""
    resp = httpx.get(f"{BASE}/models", params={"pageSize": 200}, headers={"x-goog-api-key": _key()}, timeout=30)
    _check(resp)
    models = [m for m in resp.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    ids = {m["name"].split("/", 1)[1]: m for m in models}
    if "gemini-3.5-flash" in ids:
        return "gemini-3.5-flash", ids["gemini-3.5-flash"]
    flash = sorted(i for i in ids if "flash" in i and "lite" not in i and "preview" not in i)
    if not flash:
        raise RuntimeError("no flash model available")
    return flash[-1], ids[flash[-1]]


def generate(model, prompt):
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
    digest = hashlib.sha256(json.dumps([model, body], sort_keys=True).encode()).hexdigest()
    path = CACHE / f"{digest}.json"
    if path.exists():
        calls["cached"] += 1
        return json.loads(path.read_text(encoding="utf-8"))
    wait = MIN_INTERVAL - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    resp = httpx.post(f"{BASE}/models/{model}:generateContent", headers={"x-goog-api-key": _key()}, json=body, timeout=180)
    _last_call[0] = time.time()
    calls["live"] += 1
    _check(resp)
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(text)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(parsed), encoding="utf-8")
    return parsed


def age_shares(model, names, kind):
    """{name: {band: share}} for every name, in batches of BATCH; shares are renormalised to sum to 1."""
    out = {}
    names = list(dict.fromkeys(names))
    for i in range(0, len(names), BATCH):
        chunk = names[i:i + BATCH]
        reply = generate(model, PROMPT.format(kind=kind, names="\n".join(chunk)))
        for name in chunk:
            row = reply.get(name)
            if not isinstance(row, dict):
                continue
            vals = {b: max(float(row.get(b, 0.0)), 0.0) for b in AGE_BANDS}
            total = sum(vals.values())
            if total > 0:
                out[name] = {b: v / total for b, v in vals.items()}
    return out


def to_overindex(shares):
    """Shares minus the mean share per band across all entities of the same kind (positive = over-represents)."""
    mean = {b: sum(s[b] for s in shares.values()) / len(shares) for b in AGE_BANDS}
    return {name: {b: s[b] - mean[b] for b in AGE_BANDS} for name, s in shares.items()}
