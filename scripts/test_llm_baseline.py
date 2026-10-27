"""LLM-only baseline for RIPPLE's age gap: does an LLM guessing age profiles from artist and show
names alone match the Qloo age gap? Same artists, shows, outcome (artist page spike) and statistics
as test_ripple.py --outcome artist and test_ripple_controls.py; Qloo is recomputed in the same run.
"""
import csv
import json
import logging
import math
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from aftershock import llm_baseline as llm  # noqa: E402
from aftershock.qloo import Qloo, QlooError  # noqa: E402
from aftershock.ripple import age_gap  # noqa: E402
from test_ripple import MIN_SONGS, TRUTH, evaluate, show_features, spearman  # noqa: E402
from test_ripple_controls import mean, permutation_p as controls_p, placebo_baseline  # noqa: E402

OUT = ROOT / "data" / "results" / "ripple_llm_baseline.json"
QLOO_LIVE_LIMIT = 300
log = logging.getLogger("llm_baseline")


def build_by_show(client):
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
    by_show = {}
    for (show, show_type, release), group in groups.items():
        if len(group) < MIN_SONGS:
            continue
        try:
            features = show_features(client, show, show_type, group, "artist_ratio", "artist_baseline_mean")
        except QlooError as err:
            log.warning("skipping %s: %s", show, err)
            continue
        if features and len(features) >= MIN_SONGS:
            by_show[(show, release)] = features
        if client.live_calls > QLOO_LIVE_LIMIT:
            raise SystemExit(f"stopping: {client.live_calls} live Qloo calls")
    return by_show


def table(by_show, key, label):
    """Real and placebo mean Spearman, permutation p and real-minus-placebo p for one gap key."""
    out = {}
    for name, subset in (("all", by_show), ("2024_plus", {k: v for k, v in by_show.items() if k[1] >= "2024-01-01"})):
        per_show = [(k[1], fs) for k, fs in subset.items()]
        for _, fs in per_show:
            for f in fs:
                f["gap"] = f[key]  # the controls' permutation test shuffles the field called "gap"
        real = evaluate(subset, key)
        out[name] = {
            "n_shows": len(subset), "n_artists": sum(len(v) for v in subset.values()),
            "real_spearman": real["mean_spearman"], "real_p_one_sided": real["p_value"],
            "placebo_spearman": mean([spearman([f[key] for f in fs], [f["placebo_log_ratio"] for f in fs]) for _, fs in per_show]),
            "p_real_minus_placebo": controls_p(per_show, lambda g, fs: spearman(g, [f["log_ratio"] for f in fs])
                                               - spearman(g, [f["placebo_log_ratio"] for f in fs])),
        }
    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    client = Qloo(call_budget=QLOO_LIVE_LIMIT)
    by_show = build_by_show(client)
    log.info("shows=%d artists=%d live qloo calls=%d", len(by_show), sum(len(v) for v in by_show.values()), client.live_calls)
    for (show, release), fs in by_show.items():
        for f in fs:
            pre = placebo_baseline(f["article"], date.fromisoformat(release))
            f["placebo_log_ratio"] = math.log((f["baseline_mean"] + 1) / (pre + 1))
            f["qloo_gap"] = f["gap"]

    model, info = llm.pick_model()
    log.info("model %s", model)
    artist_names = sorted({f["artist"] for fs in by_show.values() for f in fs})
    show_labels = {(s, r): f"{s} ({r[:4]})" for (s, r) in by_show}
    artist_over = llm.to_overindex(llm.age_shares(model, artist_names, "musical artist"))
    show_over = llm.to_overindex(llm.age_shares(model, sorted(show_labels.values()), "TV show or film (with release year)"))
    dropped = 0
    llm_by_show = {}
    for key, fs in by_show.items():
        if show_labels[key] not in show_over:
            continue
        kept = []
        for f in fs:
            if f["artist"] in artist_over:
                kept.append(dict(f, llm_gap=age_gap(show_over[show_labels[key]], artist_over[f["artist"]])))
            else:
                dropped += 1
        if len(kept) >= MIN_SONGS:
            llm_by_show[key] = kept
    # Qloo is recomputed on exactly the shows and artists the LLM also covers, and on the full set.
    qloo_full = table(by_show, "qloo_gap", "qloo")
    qloo_matched = table(llm_by_show, "qloo_gap", "qloo")
    llm_tab = table(llm_by_show, "llm_gap", "llm")

    qs = [f["qloo_gap"] for fs in llm_by_show.values() for f in fs]
    ls = [f["llm_gap"] for fs in llm_by_show.values() for f in fs]
    within = [spearman([f["qloo_gap"] for f in fs], [f["llm_gap"] for f in fs]) for fs in llm_by_show.values()]
    report = {
        "outcome": "artist (log artist-page spike), same rows, MIN_SONGS and seeds as test_ripple.py / test_ripple_controls.py",
        "model": model, "model_display_name": info.get("displayName"), "model_version": info.get("version"),
        "model_knowledge_cutoff_reported_by_api": info.get("knowledgeCutoff"),
        "llm_calls_live": llm.calls["live"], "llm_calls_cached": llm.calls["cached"],
        "live_qloo_calls": client.live_calls,
        "n_shows": len(llm_by_show), "n_artists": sum(len(v) for v in llm_by_show.values()),
        "n_artists_dropped_no_llm_profile": dropped,
        "prompt_text": llm.PROMPT, "batch_size": llm.BATCH,
        "prompt_inputs": "artist name only (artists), or show title plus release year (shows); never song, placement, or spike data",
        "conversion": ("LLM shares (renormalised to sum 1) minus the mean share per band across ALL entities of the same "
                       "kind (all artists pooled; all shows pooled), then passed to the existing age_gap. Pooled rather "
                       "than per-batch so that artists in different batches share one centre. age_gap is affine in "
                       "familiarity within a show, so the scale of the over-index does not change the ranking."),
        "qloo_full_set": qloo_full, "qloo_matched_to_llm_set": qloo_matched, "llm": llm_tab,
        "qloo_vs_llm_gap_agreement": {
            "spearman_pooled_across_artists": round(spearman(qs, ls), 3),
            "mean_within_show_spearman": round(sum(within) / len(within), 3),
        },
        "caveat": ("An LLM may know which songs and artists went viral after their placement (training-data "
                   "leakage), which would favour the LLM; Qloo's current data also postdates these releases. "
                   "The cutoff field above is whatever the models endpoint reports (null if it reports none)."),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
