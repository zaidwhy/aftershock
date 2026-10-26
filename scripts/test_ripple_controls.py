"""Controls for RIPPLE's backtest: is "obscurity" just regression to the mean, and does the
Qloo age gap predict spikes once obscurity is held fixed?

1. Placebo: the same ratio measured entirely before release (days -60..-8 over -120..-68).
   A predictor that also "predicts" the placebo is picking up noise in the baseline, not the show.
2. Partial correlation: within each show, Spearman of the age gap with the real log spike
   controlling for obscurity (the shared baseline window).
Uses the cached Qloo features from test_ripple.py and Wikimedia pageviews (no key needed).
"""
import json
import logging
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from aftershock import wiki  # noqa: E402
from aftershock.qloo import Qloo  # noqa: E402
from test_ripple import MIN_SONGS, TRUTH, show_features, spearman  # noqa: E402

OUT = ROOT / "data" / "results" / "ripple_controls.json"
log = logging.getLogger("ripple_controls")


def placebo_baseline(article, release):
    start, end = release - timedelta(days=120), release - timedelta(days=68)
    series = wiki.daily_views(article, start, end)
    return sum(series.values()) / len(series)


def partial(x, y, z):
    rxy, rxz, ryz = spearman(x, y), spearman(x, z), spearman(y, z)
    denom = math.sqrt(max(1e-12, (1 - rxz ** 2) * (1 - ryz ** 2)))
    return (rxy - rxz * ryz) / denom


def permutation_p(per_show, stat, trials=2000, seed=3):
    """One-sided p for mean over shows of stat(gaps, fs), shuffling the gap within each show."""
    import random
    rng = random.Random(seed)
    observed = sum(stat([f["gap"] for f in fs], fs) for _, fs in per_show) / len(per_show)
    hits = 0
    for _ in range(trials):
        total = 0.0
        for _, fs in per_show:
            gaps = [f["gap"] for f in fs]
            rng.shuffle(gaps)
            total += stat(gaps, fs)
        hits += total / len(per_show) >= observed
    return round((hits + 1) / (trials + 1), 4)


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    import csv
    rows = [r for r in csv.DictReader(TRUTH.open(encoding="utf-8"))
            if r.get("artist_status") == "ok" and r.get("artist_ratio") and r.get("artist_baseline_mean")]
    seen, deduped = set(), []
    for r in rows:
        if (r["show"], r["artist"]) not in seen:
            seen.add((r["show"], r["artist"]))
            deduped.append(r)
    groups = defaultdict(list)
    for row in deduped:
        groups[(row["show"], row.get("show_type", ""), row["release_date"])].append(row)
    client = Qloo(call_budget=200)
    report = {"outcome": "artist", "shows": []}
    per_show = []
    for (show, show_type, release), group in groups.items():
        if len(group) < MIN_SONGS:
            continue
        features = show_features(client, show, show_type, group, "artist_ratio", "artist_baseline_mean")
        if not features or len(features) < MIN_SONGS:
            continue
        rel = date.fromisoformat(release)
        for f in features:
            pre = placebo_baseline(f["article"], rel)
            f["placebo_log_ratio"] = math.log((f["baseline_mean"] + 1) / (pre + 1))
            f["placebo_obscurity"] = -math.log(pre + 1)
        per_show.append((release, features))
    results = {}
    for label, subset in (("all", per_show), ("2024_plus", [s for s in per_show if s[0] >= "2024-01-01"])):
        results[label] = {
            "n_shows": len(subset),
            "real: obscurity": mean([spearman([f["obscurity"] for f in fs], [f["log_ratio"] for f in fs]) for _, fs in subset]),
            "real: gap": mean([spearman([f["gap"] for f in fs], [f["log_ratio"] for f in fs]) for _, fs in subset]),
            "placebo: obscurity (its own pre-window)": mean([spearman([f["placebo_obscurity"] for f in fs], [f["placebo_log_ratio"] for f in fs]) for _, fs in subset]),
            "placebo: gap": mean([spearman([f["gap"] for f in fs], [f["placebo_log_ratio"] for f in fs]) for _, fs in subset]),
            "real: gap controlling for obscurity (partial)": mean([partial([f["gap"] for f in fs], [f["log_ratio"] for f in fs], [f["obscurity"] for f in fs]) for _, fs in subset]),
            "p: gap partial (shuffle gap within show)": permutation_p(subset, lambda g, fs: partial(g, [f["log_ratio"] for f in fs], [f["obscurity"] for f in fs])),
            "p: gap real minus gap placebo": permutation_p(subset, lambda g, fs: spearman(g, [f["log_ratio"] for f in fs]) - spearman(g, [f["placebo_log_ratio"] for f in fs])),
            "real: obscurity controlling for gap (partial)": mean([partial([f["obscurity"] for f in fs], [f["log_ratio"] for f in fs], [f["gap"] for f in fs]) for _, fs in subset]),
        }
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
