"""Build data/ripple_truth.csv: each placed song with its Wikipedia article and measured spike."""
import csv
import logging
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aftershock import wiki  # noqa: E402

log = logging.getLogger("build_ripple_truth")

PLACEMENTS = ROOT / "data" / "placements.csv"
TRUTH = ROOT / "data" / "ripple_truth.csv"
RESULT_COLUMNS = ["article", "baseline_mean", "after_mean", "ratio", "peak", "status"]
ARTIST_COLUMNS = ["artist_article", "artist_baseline_mean", "artist_after_mean", "artist_ratio", "artist_status"]
_artist_cache: dict[tuple[str, str], dict] = {}


def measure_artist(row: dict) -> dict:
    """Artist-level spike; computed once per (first artist, release date) and reused."""
    key = (wiki.first_artist(row["artist"]).casefold(), row["release_date"])
    if key not in _artist_cache:
        article = wiki.resolve_artist_article(row["artist"])
        if article is None:
            _artist_cache[key] = dict.fromkeys(ARTIST_COLUMNS, "") | {"artist_status": "no_article"}
        else:
            result = wiki.spike(article, row["release_date"])
            _artist_cache[key] = {
                "artist_article": article,
                "artist_baseline_mean": "" if result.baseline_mean is None else round(result.baseline_mean, 2),
                "artist_after_mean": "" if result.after_mean is None else round(result.after_mean, 2),
                "artist_ratio": "" if result.ratio is None else round(result.ratio, 3),
                "artist_status": result.status,
            }
    return _artist_cache[key]


def measure(row: dict) -> dict:
    article = wiki.resolve_article(row["song"], row["artist"])
    if article is None:
        return {"article": "", "baseline_mean": "", "after_mean": "", "ratio": "", "peak": "", "status": "no_article"}
    result = wiki.spike(article, row["release_date"])
    return {
        "article": article,
        "baseline_mean": "" if result.baseline_mean is None else round(result.baseline_mean, 2),
        "after_mean": "" if result.after_mean is None else round(result.after_mean, 2),
        "ratio": "" if result.ratio is None else round(result.ratio, 3),
        "peak": "" if result.peak is None else result.peak,
        "status": result.status,
    }


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    with PLACEMENTS.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        columns = list(reader.fieldnames)
        rows = list(reader)

    out = []
    for i, row in enumerate(rows, 1):
        out.append({**row, **measure(row), **measure_artist(row)})
        if i % 25 == 0:
            print(f"{i}/{len(rows)}", file=sys.stderr)

    with TRUTH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns + RESULT_COLUMNS + ARTIST_COLUMNS)
        writer.writeheader()
        writer.writerows(out)

    with_article = [r for r in out if r["article"]]
    scored = [r for r in with_article if r["ratio"] != ""]
    print(f"rows: {len(out)}")
    print(f"rows with an article: {len(with_article)}")
    if scored:
        print(f"median ratio (articles with a ratio): {statistics.median(float(r['ratio']) for r in scored):.3f}")
    print("top 15 by ratio:")
    for r in sorted(scored, key=lambda r: float(r["ratio"]), reverse=True)[:15]:
        print(f"  {float(r['ratio']):9.2f}  {r['song']} - {r['artist']}  [{r['show']}] ({r['status']})")

    artist_scored = [r for r in out if r["artist_ratio"] != ""]
    print(f"rows with artist_ratio: {len(artist_scored)}")
    if artist_scored:
        print(f"median artist ratio: {statistics.median(float(r['artist_ratio']) for r in artist_scored):.3f}")
    print("top 10 by artist_ratio:")
    for r in sorted(artist_scored, key=lambda r: float(r["artist_ratio"]), reverse=True)[:10]:
        print(f"  {float(r['artist_ratio']):9.2f}  {wiki.first_artist(r['artist'])}  [{r['show']}] ({r['song']})")


if __name__ == "__main__":
    main()
