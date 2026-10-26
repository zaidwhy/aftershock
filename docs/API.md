# AFTERSHOCK API contract

All endpoints are GET and return JSON. The Qloo key never leaves the server.

## GET /health
`{"status": "ok", "qloo_key": true, "cache_entries": 1234}`

## GET /api/storms
Current breakouts: titles that entered the Netflix Top 10 in 1 to 3 countries in the latest published week.
```json
{"week": "2026-10-25", "storms": [
  {"id": "hakone-ekiden-our-story-s1", "title": "Hakone Ekiden: Our Story", "season": "Season 1",
   "category": "TV (Non-English)", "origin_countries": [{"code": "JP", "name": "Japan"}],
   "origin_week": "2026-10-25", "qloo_entity": "uuid-or-null", "top_forecast": {"code": "KR", "name": "South Korea", "probability": 0.21},
   "has_ripple": false}
]}
```

## GET /api/storms/{id}
```json
{"id": "...", "title": "...", "season": "...", "category": "...", "origin_week": "...",
 "origin_countries": [{"code": "JP", "name": "Japan"}],
 "spillover": {
   "horizon_weeks": 4,
   "forecasts": [{"code": "KR", "name": "South Korea", "probability": 0.21,
                  "history_probability": 0.17, "qloo_relative": 0.04,
                  "why": "South Korea joined 23 of 61 past breakouts that started in Japan; Qloo affinity here is 0.04 above this title's average country"}],
   "locked_at": "2026-10-30T10:00:00Z", "ledger_id": "sha-prefix"},
 "ripple": null,
 "partners": [{"code": "KR", "artists": ["..."], "brands": ["..."]}]
}
```
`ripple`, when the title has known song placements:
```json
{"show_age": {"24_and_younger": 0.71, "25_to_29": 0.45, "30_to_34": 0.16, "35_to_44": -0.62, "45_to_54": -0.32, "55_and_older": -0.49},
 "songs": [{"song": "Running Up That Hill", "artist": "Kate Bush", "score": 0.83, "fit": 0.93, "age_gap": 0.68,
            "artist_age": {"24_and_younger": 0.03, "...": 0}, "wiki_article": "Running_Up_That_Hill", "status": "pending|graded",
            "observed_ratio": null}]}
```

## GET /api/ripple?show=Stranger%20Things&songs=Running%20Up%20That%20Hill|Kate%20Bush;Master%20of%20Puppets|Metallica
Live scoring for any show and up to 8 songs, same `ripple` shape plus `resolved` flags. Rate limited per visitor (10 per hour).

## GET /api/scorecard
```json
{"spillover": {"locked": 120, "graded": 80, "hits_top5": 9, "auc": 0.81, "baseline_auc": 0.80, "weeks": ["2026-11-01"]},
 "ripple": {"locked": 40, "graded": 12, "spearman": 0.41, "baseline_spearman": 0.12},
 "backtest": {"spillover": {"history_auc": 0.817, "qloo_auc": null}, "ripple": {"n": 0, "spearman": null}},
 "ledger_url": "https://github.com/zaidwhy/aftershock/blob/main/ledger/forecasts.jsonl"}
```

## GET /api/replays
Famous ripples with real Wikipedia monthly views, for the intro animation.
```json
{"replays": [{"show": "Stranger Things 4", "release": "2022-05-27", "song": "Running Up That Hill", "artist": "Kate Bush",
              "monthly_views": [["2022-01", 12000], ["2022-06", 909000]]}]}
```
