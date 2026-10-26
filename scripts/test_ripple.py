"""Decision test for RIPPLE: within each show, does score = fit x age_gap rank the placed songs
by their measured Wikipedia spike better than simple baselines?

Input: data/ripple_truth.csv (built by build_ripple_truth.py). Qloo rescales affinity within a
response, so everything is compared within a show, then averaged across shows.
Leakage note: Qloo's current data postdates these releases, so results are optimistic; famous
2022 cases are the most contaminated, which is why results are also reported for 2024+ releases.
"""
import csv
import json
import logging
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aftershock.qloo import Qloo, QlooError, resolve  # noqa: E402
import argparse  # noqa: E402
from aftershock.ripple import age_gap, age_profile, resolve_show  # noqa: E402

TRUTH = ROOT / "data" / "ripple_truth.csv"
OUT_DIR = ROOT / "data" / "results"
MIN_SONGS = 4
log = logging.getLogger("test_ripple")


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def spearman(xs, ys):
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    var = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return cov / var if var else 0.0


def show_features(client, show, show_type, rows, ratio_col="ratio", base_col="baseline_mean"):
    types = "urn:entity:movie" if show_type == "movie" else "urn:entity:tv_show"
    hit = resolve_show(client, show, types) or resolve_show(client, show, "urn:entity:tv_show,urn:entity:movie")
    if not hit:
        return None
    show_age = age_profile(client, hit["entity_id"])
    artist_ids = {}
    for row in rows:
        if row["artist"] not in artist_ids:
            found = resolve(client, row["artist"], "urn:entity:artist")
            artist_ids[row["artist"]] = found["entity_id"] if found else None
    known = sorted({a for a in artist_ids.values() if a})
    if len(known) < 2:
        return None
    body = client.insights(filter__type="urn:entity:artist", signal__interests__entities=hit["entity_id"],
                           filter__results__entities=",".join(known), take=len(known))
    # Some entities come back without an affinity value; they are treated as unscored.
    fit = {e["entity_id"]: float(e["query"]["affinity"]) for e in body.get("results", {}).get("entities", [])
           if e.get("query", {}).get("affinity") is not None}
    features = []
    for row in rows:
        artist_id = artist_ids.get(row["artist"])
        if not artist_id or artist_id not in fit:
            continue
        gap = age_gap(show_age, age_profile(client, artist_id))
        features.append({"song": row["song"], "artist": row["artist"], "fit": fit[artist_id], "gap": gap,
                         "score": fit[artist_id] * gap, "log_ratio": math.log(float(row[ratio_col])),
                         "obscurity": -math.log(float(row[base_col]) + 1)})
    return features


def permutation_p(by_show, key, observed, trials=2000, seed=5):
    """One-sided p: share of within-show shuffles of the outcome whose mean Spearman >= observed."""
    rng = random.Random(seed)
    shows = list(by_show.values())
    hits = 0
    for _ in range(trials):
        total = 0.0
        for fs in shows:
            outcome = [f["log_ratio"] for f in fs]
            rng.shuffle(outcome)
            total += spearman([f[key] for f in fs], outcome)
        hits += total / len(shows) >= observed
    return (hits + 1) / (trials + 1)


def evaluate(by_show, key):
    per_show = [spearman([f[key] for f in fs], [f["log_ratio"] for f in fs]) for fs in by_show.values()]
    top1 = [max(fs, key=lambda f: f[key])["log_ratio"] == max(f["log_ratio"] for f in fs) for fs in by_show.values()]
    mean = sum(per_show) / len(per_show) if per_show else None
    return {"mean_spearman": round(mean, 3) if per_show else None,
            "top1_hit_rate": round(sum(top1) / len(top1), 3) if top1 else None,
            "p_value": round(permutation_p(by_show, key, mean), 4) if per_show and key != "random" else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outcome", choices=["song", "artist"], default="song")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    ratio_col, base_col, status_col = (("ratio", "baseline_mean", "status") if args.outcome == "song"
                                       else ("artist_ratio", "artist_baseline_mean", "artist_status"))
    rows = [r for r in csv.DictReader(TRUTH.open(encoding="utf-8"))
            if r.get(status_col) == "ok" and r.get(ratio_col) and r.get(base_col)]
    if args.outcome == "artist":
        # The outcome is the artist's page, so one artist placed twice in a show is one data point.
        seen = set()
        rows = [r for r in rows if (r["show"], r["artist"]) not in seen and not seen.add((r["show"], r["artist"]))]
    groups = defaultdict(list)
    for row in rows:
        groups[(row["show"], row.get("show_type", ""), row["release_date"])].append(row)
    client = Qloo(call_budget=1500)
    by_show = {}
    for (show, show_type, release), group in groups.items():
        if len(group) < MIN_SONGS:
            continue
        try:
            features = show_features(client, show, show_type, group, ratio_col, base_col)
        except QlooError as err:
            log.warning("skipping %s: %s", show, err)
            continue
        if features and len(features) >= MIN_SONGS:
            by_show[(show, release)] = features
    rng = random.Random(11)
    for fs in by_show.values():
        obscurity_rank, gap_rank = ranks([f["obscurity"] for f in fs]), ranks([f["gap"] for f in fs])
        for f, o, g in zip(fs, obscurity_rank, gap_rank):
            f["random"] = rng.random()
            # Does Qloo's age gap add to the non-Qloo obscurity baseline? Equal-weight rank sum.
            f["obscurity_plus_gap"] = o + g
    recent = {k: v for k, v in by_show.items() if k[1] >= "2024-01-01"}
    report = {"outcome": args.outcome, "n_shows": len(by_show), "n": sum(len(v) for v in by_show.values()),
              "n_shows_2024_plus": len(recent), "live_calls": client.live_calls}
    for label, subset in (("all", by_show), ("2024_plus", recent)):
        if subset:
            report[label] = {key: evaluate(subset, key) for key in ("score", "fit", "gap", "obscurity", "obscurity_plus_gap", "random")}
    report["spearman"] = report.get("all", {}).get("score", {}).get("mean_spearman")
    report["baseline_spearman"] = report.get("all", {}).get("obscurity", {}).get("mean_spearman")
    out = OUT_DIR / ("ripple_test.json" if args.outcome == "song" else "ripple_test_artist.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    for (show, release), fs in sorted(by_show.items(), key=lambda kv: kv[0][1])[:40]:
        best = max(fs, key=lambda f: f["score"])
        spike = max(fs, key=lambda f: f["log_ratio"])
        print(f"{release} {show[:30]:30s} n={len(fs):2d} top-scored: {best['song'][:28]:28s} biggest spike: {spike['song'][:28]}")


if __name__ == "__main__":
    main()
