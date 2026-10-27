"""Wikipedia ground truth for RIPPLE: song article lookup and pageview spikes around a release.

Both Wikimedia endpoints are public. Responses are cached under .cache/wiki/ (gitignored) and
network calls are paced to at most 10 requests per second.
"""
import hashlib
import json
import logging
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
# Serverless filesystems are read-only outside /tmp.
CACHE_DIR = Path("/tmp/wiki-cache") if os.environ.get("VERCEL") else ROOT / ".cache" / "wiki"
USER_AGENT = "aftershock-research/0.1 (https://github.com/zaidwhy)"
API_URL = "https://en.wikipedia.org/w/api.php"
VIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia/all-access/user/{article}/daily/{start}/{end}"
)
MIN_INTERVAL_S = 0.1
TIMEOUT_S = 20.0

BASELINE_FROM, BASELINE_TO = -60, -8
AFTER_FROM, AFTER_TO = 7, 35
INTRO_CHARS = 1200

_pace_lock = threading.Lock()
_last_call = 0.0


class WikiError(RuntimeError):
    pass


@dataclass(frozen=True)
class Spike:
    status: str  # "ok" or "pending"
    baseline_mean: float | None
    after_mean: float | None
    ratio: float | None
    peak: int | None


def _pace() -> None:
    global _last_call
    with _pace_lock:
        wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def _cached_get(url: str, params: dict | None = None) -> dict:
    """GET url and return {"status": int, "json": ...}, using the disk cache."""
    key_src = url + "?" + json.dumps(params or {}, sort_keys=True)
    path = CACHE_DIR / (hashlib.sha256(key_src.encode()).hexdigest() + ".json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    _pace()
    resp = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
    if resp.status_code not in (200, 404):
        raise WikiError(f"{resp.status_code} from {url}: {resp.text[:200]}")
    body = resp.json() if resp.status_code == 200 else None
    if isinstance(body, dict) and "error" in body:
        # MediaWiki reports overload ("cirrussearch-too-busy-error") as a 200; caching it would poison reruns
        raise WikiError(f"API error from {url}: {str(body['error'])[:200]}")
    record = {"status": resp.status_code, "json": body}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.casefold().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _name_variants(name: str) -> set[str]:
    """Normalized forms of a song or article title: with and without bracketed parts and ' - ' tails."""
    head = re.split(r"\s+-\s+", name)[0]
    stripped = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", head)
    variants = {_fold(name), _fold(head), _fold(stripped)}
    variants.discard("")
    return variants


NON_SONG_SUFFIX = re.compile(
    r"\b(film|movie|tv|television|series|album|ep|band|novel|book|character|surname|given name|company|"
    r"video game|musical|play|opera|disambiguation|soundtrack)\b",
    re.I,
)


def title_matches(title: str, song: str) -> bool:
    """True when a Wikipedia title names the song, allowing '(song)' / '(Kate Bush song)' suffixes."""
    suffix = re.search(r"\(([^)]*)\)\s*$", title)
    if suffix and NON_SONG_SUFFIX.search(suffix.group(1)) and not NON_SONG_SUFFIX.search(song):
        return False
    return bool(_name_variants(title) & _name_variants(song))


def _artist_tokens(artist: str) -> list[str]:
    parts = re.split(r",|&|\band\b|\bfeat\.?|\bfeaturing\b|\bwith\b|/", artist, flags=re.I)
    names = [_fold(p) for p in parts]
    names = [re.sub(r"^the ", "", n) for n in names if n]
    return [n for n in names if len(n) > 2]


def mentions_artist(text: str, artist: str) -> bool:
    folded = _fold(text)
    return any(re.search(rf"\b{re.escape(n)}\b", folded) for n in _artist_tokens(artist))


def resolve_article(song: str, artist: str) -> str | None:
    """English Wikipedia article title for the song, or None when there is no confident match."""
    head = re.split(r"\s+-\s+", song)[0]
    base = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", head).strip() or head
    first_artist = _artist_tokens(artist)
    query = f"{base} {first_artist[0] if first_artist else artist}"
    found = _cached_get(
        API_URL,
        {"action": "query", "list": "search", "srsearch": query, "srnamespace": 0,
         "srlimit": 8, "format": "json"},
    )["json"]
    titles = [hit["title"] for hit in found["query"]["search"] if title_matches(hit["title"], song)]
    if not titles:
        return None
    extracts = _cached_get(
        API_URL,
        {"action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1,
         "exchars": INTRO_CHARS, "exlimit": "max", "titles": "|".join(titles),
         "redirects": 1, "format": "json"},
    )["json"]
    intro = {p["title"]: p.get("extract", "") for p in extracts["query"]["pages"].values()}
    for title in titles:
        if mentions_artist(intro.get(title, ""), artist):
            return title
    return None


MUSIC_WORD = re.compile(
    r"\b(band|singer|musician|rapper|group|duo|trio|quartet|dj|producer|composer|songwriter|vocalist|"
    r"artist|guitarist|drummer|pianist|violinist|orchestra|choir|ensemble)\b",
    re.I,
)


def first_artist(artist: str) -> str:
    return artist.split(",")[0].strip()


def artist_title_matches(title: str, artist: str) -> bool:
    """True when a Wikipedia title is the artist's own page: exact name, music disambiguator only."""
    name = first_artist(artist)
    suffix = re.search(r"\s*\(([^)]*)\)\s*$", title)
    base = title[: suffix.start()] if suffix else title
    if suffix and not MUSIC_WORD.search(suffix.group(1)):
        return False
    if suffix and re.search(r"\b(song|single|album|film|ep|soundtrack)\b", suffix.group(1), re.I):
        return False
    wanted = _fold(name)
    got = _fold(base)
    return bool(wanted) and (got == wanted or re.sub(r"^the ", "", got) == re.sub(r"^the ", "", wanted))


def resolve_artist_article(artist: str) -> str | None:
    """English Wikipedia article for the artist (first of a comma list), or None."""
    name = first_artist(artist)
    if not name:
        return None
    found = _cached_get(
        API_URL,
        {"action": "query", "list": "search", "srsearch": name, "srnamespace": 0,
         "srlimit": 8, "format": "json"},
    )["json"]
    titles = [hit["title"] for hit in found["query"]["search"] if artist_title_matches(hit["title"], artist)]
    if not titles:
        return None
    extracts = _cached_get(
        API_URL,
        {"action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1,
         "exchars": INTRO_CHARS, "exlimit": "max", "titles": "|".join(titles),
         "redirects": 1, "format": "json"},
    )["json"]
    intro = {p["title"]: p.get("extract", "") for p in extracts["query"]["pages"].values()}
    for title in titles:
        text = intro.get(title, "")
        if "may refer to" not in text and MUSIC_WORD.search(text):
            return title
    return None


def daily_views(article: str, start: date, end: date) -> dict[date, int]:
    """Daily user pageviews for [start, end] inclusive. Days Wikimedia omits are returned as 0."""
    url = VIEWS_URL.format(
        article=quote(article.replace(" ", "_"), safe=""),
        start=start.strftime("%Y%m%d00"),
        end=end.strftime("%Y%m%d00"),
    )
    record = _cached_get(url)
    series = {start + timedelta(days=i): 0 for i in range((end - start).days + 1)}
    if record["status"] == 404:
        return series
    for item in record["json"]["items"]:
        day = datetime.strptime(item["timestamp"][:8], "%Y%m%d").date()
        series[day] = item["views"]
    return series


def _mean(series: dict[date, int], release: date, first: int, last: int, yesterday: date) -> float | None:
    days = [release + timedelta(days=d) for d in range(first, last + 1)]
    values = [series.get(d, 0) for d in days if d <= yesterday]
    return sum(values) / len(values) if values else None


def spike_from_series(series: dict[date, int], release: date, today: date) -> Spike:
    """Spike statistics from a daily series. Releases under 36 days old are 'pending' with partial values."""
    yesterday = today - timedelta(days=1)
    pending = (today - release).days <= AFTER_TO
    baseline = _mean(series, release, BASELINE_FROM, BASELINE_TO, yesterday)
    after = _mean(series, release, AFTER_FROM, AFTER_TO, yesterday)
    peak_days = [release + timedelta(days=d) for d in range(0, AFTER_TO + 1)]
    peaks = [series.get(d, 0) for d in peak_days if d <= yesterday]
    ratio = (after + 1) / (baseline + 1) if after is not None and baseline is not None else None
    return Spike("pending" if pending else "ok", baseline, after, ratio, max(peaks) if peaks else None)


def spike(article: str, release_date: date | str, today: date | None = None) -> Spike:
    release = date.fromisoformat(release_date) if isinstance(release_date, str) else release_date
    today = today or date.today()
    yesterday = today - timedelta(days=1)
    start = release + timedelta(days=BASELINE_FROM)
    end = min(release + timedelta(days=AFTER_TO), yesterday)
    if end < start:
        return Spike("pending", None, None, None, None)
    return spike_from_series(daily_views(article, start, end), release, today)
