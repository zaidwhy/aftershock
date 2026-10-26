"""Weekly forecast job: refresh Netflix data, forecast this week's breakouts, lock them in the
ledger, grade earlier forecasts, and write the files the API serves.

Run: .venv/Scripts/python scripts/run_forecasts.py [--no-refresh] [--no-qloo] [--no-lock]
"""
import argparse
import csv
import json
import logging
import math
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aftershock import ledger, wiki  # noqa: E402
from aftershock.netflix import (  # noqa: E402
    HistoryBaseline, breakout_events, first_entries, load_rows, roc_auc, title_categories,
)
from aftershock.qloo import Qloo, QlooError, norm  # noqa: E402
from aftershock.ripple import score_placements  # noqa: E402

RAW = ROOT / "data" / "raw" / "all-weeks-countries.tsv"
NETFLIX_URL = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"
PRIVATE = ROOT / "data" / "private"
RESULTS = ROOT / "data" / "results"
LIVE_PLACEMENTS = ROOT / "data" / "placements_live.csv"
HORIZON = 4
SHOW_TOP = 15
MIN_RIPPLE_SONGS = 4
MAX_STORMS = 40
MAX_RIPPLE_SONGS = 25
log = logging.getLogger("run_forecasts")


def refresh_netflix():
    RAW.parent.mkdir(parents=True, exist_ok=True)
    resp = httpx.get(NETFLIX_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    if not resp.text.startswith("country_name"):
        raise RuntimeError("Netflix TSV did not have the expected header; not overwriting")
    RAW.write_text(resp.text, encoding="utf-8")
    log.info("refreshed Netflix data: %d bytes", len(resp.text))


def season_label(title):
    """Netflix's season_title repeats the show name ("Show: Season 2"); keep only the season part."""
    show, season = title
    if season == "N/A":
        return None
    return season[len(show):].lstrip(": ").strip() or season if season.startswith(show) else season


def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", f"{title[0]} {'' if title[1] == 'N/A' else title[1]}".lower()).strip("-")[:80]


def why_text(model, event, target, names):
    parts = []
    for origin in event["origin_countries"]:
        trials, joins = model._pair_trials[origin, target], model._pair_joins[origin, target]
        if trials:
            parts.append(f"{names[target]} joined {joins} of {trials} past breakouts that started in {names[origin]}")
    return "; ".join(parts) or f"no past breakouts from these origins; uses {names[target]}'s general rate"


def resolve_title(client, event):
    entity_type = "urn:entity:movie" if event["category"].startswith("Films") else "urn:entity:tv_show"
    for hit in client.search(event["title"][0], types=entity_type):
        if norm(hit.get("name", "")) == norm(event["title"][0]):
            return hit["entity_id"]
    return None


def partners(client, entity_id, country_name):
    """Artists this title's audience in one country over-indexes on."""
    try:
        body = client.get("/v2/insights", {"filter.type": "urn:entity:artist", "signal.interests.entities": entity_id,
                                           "signal.location.query": country_name, "take": 3})
        return [e["name"] for e in body.get("results", {}).get("entities", [])]
    except QlooError as err:
        log.warning("partners failed: %s", err)
        return []


def live_placements():
    """{storm-style id: {show, show_type, platform, release_date, songs: [(song, artist)]}}."""
    if not LIVE_PLACEMENTS.exists():
        return {}
    titles = {}
    with LIVE_PLACEMENTS.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = slug((row["show"], row["release_date"]))
            entry = titles.setdefault(key, {"id": key, "show": row["show"], "show_type": row.get("show_type", ""),
                                            "platform": row.get("platform", ""), "release_date": row["release_date"],
                                            "songs": []})
            if (row["song"], row["artist"]) not in entry["songs"]:
                entry["songs"].append((row["song"], row["artist"]))
    return titles


def ripple_watch(client, titles, today):
    """Score each new release's soundtrack as of its release date, plus the early Wikipedia read."""
    watched = []
    for entry in titles.values():
        types = {"movie": "urn:entity:movie", "tv_show": "urn:entity:tv_show"}.get(entry["show_type"])
        try:
            ripple = score_placements(client, entry["show"], entry["songs"][:MAX_RIPPLE_SONGS], show_type=types,
                                      as_of=date.fromisoformat(entry["release_date"]), max_songs=MAX_RIPPLE_SONGS)
        except QlooError as err:
            log.warning("ripple failed for %s: %s", entry["show"], err)
            continue
        if not ripple.get("resolved"):
            log.info("not in Qloo: %s", entry["show"])
            continue
        for song in ripple["songs"]:
            if song.get("wiki_article"):
                early = wiki.spike(song["wiki_article"], entry["release_date"], today)
                song.update(early_status=early.status, early_ratio=round(early.ratio, 2) if early.ratio else None,
                            early_after_mean=round(early.after_mean, 1) if early.after_mean is not None else None)
        watched.append({**{k: entry[k] for k in ("id", "show", "show_type", "platform", "release_date")},
                        "qloo_show": ripple["show"], "show_age": ripple["show_age"], "songs": ripple["songs"]})
    return watched


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def grade_ripples(today):
    """Within-release Spearman of locked ripple scores against the Wikipedia spike, for releases
    whose 35-day window has closed."""
    by_release = {}
    for record in ledger.read():
        if record.get("kind") == "ripple" and record.get("wiki_article"):
            by_release.setdefault((tuple(record["title"]), record["origin_week"]), []).append(record)
    rhos, pending = [], 0
    for (_, release), records in by_release.items():
        spikes = [(r["score"], wiki.spike(r["wiki_article"], release, today)) for r in records]
        if any(spike.status != "ok" for _, spike in spikes):
            pending += 1
            continue
        usable = [(score, math.log(spike.ratio)) for score, spike in spikes if spike.ratio]
        if len(usable) >= MIN_RIPPLE_SONGS:
            rhos.append(spearman([u[0] for u in usable], [u[1] for u in usable]))
    return {"graded_releases": len(rhos), "pending_releases": pending,
            "mean_spearman": round(sum(rhos) / len(rhos), 3) if rhos else None}


def spearman(xs, ys):
    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        for rank, i in enumerate(order):
            out[i] = float(rank)
        return out
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    var = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return cov / var if var else 0.0


def grade(rows, last_week):
    """Grade locked spillover forecasts. Closed: the 4-week horizon has passed. So far: the
    horizon is still open, and a country counts as a hit only if it has already joined; misses
    there can still turn into hits, so the partial AUC is labelled as such everywhere."""
    first = first_entries(rows)
    graded, so_far, pending = [], [], 0
    for record in ledger.read():
        if record.get("kind") != "spillover":
            continue
        origin = date.fromisoformat(record["origin_week"])
        joined_week = first.get(tuple(record["title"]), {}).get(record["target"])
        joined = joined_week and origin < date.fromisoformat(joined_week) <= origin + timedelta(weeks=HORIZON)
        row = {"probability": record["probability"], "hit": bool(joined)}
        if origin + timedelta(weeks=HORIZON) <= last_week:
            graded.append(row)
        else:
            pending += 1
            if last_week > origin:
                so_far.append(row)
    return graded, so_far, pending


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-refresh", action="store_true")
    parser.add_argument("--no-qloo", action="store_true")
    parser.add_argument("--no-lock", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if not args.no_refresh:
        try:
            refresh_netflix()
        except (httpx.HTTPError, RuntimeError) as err:
            log.warning("Netflix refresh failed, using the cached file: %s", err)
    rows = load_rows(RAW)
    countries = sorted({r["country_iso2"] for r in rows})
    names = {r["country_iso2"]: r["country_name"] for r in rows}
    last_week = date.fromisoformat(max(r["week"] for r in rows))
    events = breakout_events(first_entries(rows), title_categories(rows), max_origin=3)
    observed = [e for e in events if e["origin_week"] <= last_week - timedelta(weeks=HORIZON)]
    storms_now = [e for e in events if e["origin_week"] == last_week][:MAX_STORMS]
    model = HistoryBaseline(horizon=HORIZON).fit(observed, countries)
    log.info("last week %s: %d breakouts this week, model fit on %d events", last_week, len(storms_now), len(observed))

    client = None if args.no_qloo else Qloo(call_budget=4000)
    titles = live_placements()
    storms, to_lock = [], []
    entity_of = {e["title"]: resolve_title(client, e) for e in storms_now} if client else {}
    for event in storms_now:
        candidates = [c for c in countries if c not in event["origin_countries"]]
        probabilities = model.predict(event, candidates)
        entity_id = entity_of.get(event["title"])
        ranked = sorted(candidates, key=lambda c: -probabilities[c])[:SHOW_TOP]
        # History only: Qloo's in-country affinity added no AUC in scripts/test_spillover_qloo.py
        # (it had a value for 1.8% of title-country pairs), so Qloo's job here is the partners list.
        forecasts = [{"code": c, "name": names[c], "probability": round(probabilities[c], 4),
                      "why": why_text(model, event, c, names)} for c in ranked]
        partner_rows = [{"code": c, "artists": partners(client, entity_id, names[c])} for c in ranked[:3]] if entity_id else []
        storm_id = slug(event["title"])
        summary = {"id": storm_id, "title": event["title"][0], "season": season_label(event["title"]),
                   "category": event["category"], "origin_week": str(event["origin_week"]),
                   "origin_countries": [{"code": c, "name": names[c]} for c in event["origin_countries"]],
                   "qloo_entity": entity_id,
                   "top_forecast": forecasts[0] if forecasts else None}
        storms.append({"netflix_title": list(event["title"]), "summary": summary, "detail": {**summary, "spillover": {"horizon_weeks": HORIZON, "forecasts": forecasts},
                                                      "partners": partner_rows}})
        # Every candidate country is locked, not just the top rows, so AUC and calibration can be graded.
        to_lock += [{"kind": "spillover", "title": list(event["title"]), "origin_week": str(event["origin_week"]),
                     "target": c, "probability": round(probabilities[c], 4)} for c in sorted(candidates)]

    watched = ripple_watch(client, titles, date.today()) if client else []
    for item in watched:
        scored = [song for song in item["songs"] if song.get("score") is not None]
        # A ripple forecast counts only if locked before the outcome window opens (release + 7 days)
        # and ranks at least MIN_RIPPLE_SONGS songs; anything else is shown as an early read only.
        opens = date.fromisoformat(item["release_date"]) + timedelta(days=wiki.AFTER_FROM)
        item["lockable"] = date.today() < opens and len(scored) >= MIN_RIPPLE_SONGS
        if not item["lockable"]:
            item["not_locked_reason"] = ("released before tracking began; its outcome window was already open"
                                         if date.today() >= opens else f"fewer than {MIN_RIPPLE_SONGS} scorable songs")
            continue
        to_lock += [{"kind": "ripple", "title": [item["show"], item["release_date"]], "origin_week": item["release_date"],
                     "target": f"{song['song']} | {song['artist']}", "score": song["score"],
                     "wiki_article": song.get("wiki_article")}
                    for song in item["songs"] if song.get("score") is not None]
    already = {(tuple(r["title"]), r["origin_week"]) for r in ledger.read()}
    fresh = [f for f in to_lock if (tuple(f["title"]), f["origin_week"]) not in already]
    if fresh and not args.no_lock:
        written = ledger.append(fresh)
        lock_ids = {(tuple(w["title"]), w["origin_week"]): (w["locked_at"], w["hash"]) for w in written}
    else:
        lock_ids = {}
    for record in ledger.read():
        lock_ids.setdefault((tuple(record["title"]), record["origin_week"]), (record["locked_at"], record["hash"]))
    for storm in storms:
        key = (tuple(storm["netflix_title"]), storm["summary"]["origin_week"])
        if key in lock_ids:
            storm["detail"]["spillover"]["locked_at"], storm["detail"]["spillover"]["ledger_id"] = lock_ids[key]

    graded, so_far, pending = grade(rows, last_week)
    hits = sum(g["hit"] for g in graded)
    so_far_hits = sum(g["hit"] for g in so_far)
    ripple_graded = grade_ripples(date.today())
    backtest = _read_json(RESULTS / "spillover_backtest.json")
    qloo_test = _read_json(RESULTS / "spillover_qloo_test.json")
    ripple_test = _read_json(RESULTS / "ripple_test_artist.json")
    controls = _read_json(RESULTS / "ripple_controls.json")
    metric = lambda table, name: next((m["auc"] for m in table.get("metrics", []) if m["model"] == name), None)  # noqa: E731
    records = ledger.read()
    recent = ripple_test.get("2024_plus", {})
    scorecard = {
        "spillover": {"locked": sum(1 for r in records if r["kind"] == "spillover"), "graded": len(graded),
                      "hits": hits, "pending": pending,
                      "auc": roc_auc([g["probability"] for g in graded], [int(g["hit"]) for g in graded])
                      if graded and 0 < hits < len(graded) else None,
                      "so_far": {"forecasts": len(so_far), "hits": so_far_hits,
                                 "auc": roc_auc([g["probability"] for g in so_far], [int(g["hit"]) for g in so_far])
                                 if so_far and 0 < so_far_hits < len(so_far) else None}},
        "ripple": {"locked": sum(1 for r in records if r["kind"] == "ripple"), **ripple_graded},
        "backtest": {
            "spillover": {"history_auc": metric(backtest, "history baseline"),
                          "test_breakouts": backtest.get("test_events"),
                          "subset_breakouts": qloo_test.get("test_events"),
                          "history_auc_same_subset": metric(qloo_test, "history baseline"),
                          "qloo_auc": metric(qloo_test, "history + Qloo")},
            "ripple": {"n_artists": ripple_test.get("n"), "n_shows": ripple_test.get("n_shows"),
                       "n_shows_2024_plus": ripple_test.get("n_shows_2024_plus"),
                       "gap_2024_plus": recent.get("gap", {}).get("mean_spearman"),
                       "gap_2024_plus_p": recent.get("gap", {}).get("p_value"),
                       "fit_2024_plus": recent.get("fit", {}).get("mean_spearman"),
                       "obscurity_2024_plus": recent.get("obscurity", {}).get("mean_spearman"),
                       "placebo": controls},
        },
        "ledger_url": "https://github.com/zaidwhy/aftershock/blob/main/ledger/forecasts.jsonl",
        "ledger_intact": ledger.verify() is None,
        "data_week": str(last_week),
    }
    PRIVATE.mkdir(parents=True, exist_ok=True)
    for item in watched:
        key = (tuple([item["show"], item["release_date"]]), item["release_date"])
        if key in lock_ids:
            item["locked_at"], item["ledger_id"] = lock_ids[key]
    (PRIVATE / "storms.json").write_text(json.dumps({"week": str(last_week), "storms": storms, "ripples": watched},
                                                    indent=1), encoding="utf-8")
    (PRIVATE / "scorecard.json").write_text(json.dumps(scorecard, indent=1), encoding="utf-8")
    log.info("wrote %d storms; locked %d new forecasts; graded %d (hits %d); qloo live calls %s",
             len(storms), len(fresh) if not args.no_lock else 0, len(graded), hits, client.live_calls if client else 0)


if __name__ == "__main__":
    main()
