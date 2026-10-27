# AFTERSHOCK API contract

All endpoints are GET and return JSON. The Qloo key never leaves the server. Every number in the examples below is synthetic (invented to show the shape), not a result and not Qloo output.

## GET /health
`{"status": "ok", "qloo_key": true, "cache_entries": 1234}`

## GET /api/storms
Current breakouts: titles that entered the Netflix Top 10 in 1 to 3 countries in the latest published week.
```json
{"week": "2026-10-25", "storms": [
  {"id": "example-show-s1", "title": "Example Show", "season": "Season 1",
   "category": "TV (Non-English)", "origin_countries": [{"code": "JP", "name": "Japan"}],
   "origin_week": "2026-10-25", "qloo_entity": "uuid-or-null",
   "top_forecast": {"code": "KR", "name": "South Korea", "probability": 0.21,
                    "why": "South Korea joined 23 of 100 past breakouts that started in Japan"}}
]}
```

## GET /api/storms/{id}
SPILLOVER forecast for one breakout. Probabilities come from Netflix history only: how often the country followed past breakouts from the same origin countries, smoothed toward the same-category rate, then toward the country's base rate. Every candidate country is listed and locked in the ledger.
```json
{"id": "example-show-s1", "title": "Example Show", "season": "Season 1", "category": "TV (Non-English)",
 "origin_week": "2026-10-25",
 "origin_countries": [{"code": "JP", "name": "Japan"}],
 "qloo_entity": "uuid-or-null",
 "top_forecast": {"code": "KR", "name": "South Korea", "probability": 0.21, "why": "..."},
 "spillover": {
   "horizon_weeks": 4,
   "forecasts": [{"code": "KR", "name": "South Korea", "probability": 0.21,
                  "why": "South Korea joined 23 of 100 past breakouts that started in Japan"}],
   "locked_at": "2026-10-30T10:00:00Z", "ledger_id": "sha-prefix"},
 "partners": [{"code": "KR", "artists": ["Example Artist A", "Example Artist B"]}],
 "launch_kit": [{"code": "KR", "kit": {
   "artist": [{"name": "Example Artist A", "entity_id": "uuid"}],
   "tv_show": [{"name": "Example Show A", "entity_id": "uuid"}],
   "movie": [{"name": "Example Film A", "entity_id": "uuid"}],
   "brand": [{"name": "Example Brand A", "entity_id": "uuid"}]}}]
}
```
`partners` is the one place Qloo appears here: artists the title's audience over-indexes on in each forecast country. It does not change the probabilities (Qloo gave no AUC lift in the backtest).

`launch_kit` covers the same top three forecast countries. Per country, `kit` maps a domain (`artist`, `tv_show`, `movie`, `brand`) to up to five entities the title's audience there over-indexes on, in Qloo's order; a domain that returned nothing is omitted, and a country with no results is omitted. No affinity values are exposed. The MCP tool `launch_kit(storm_id, country)` returns one country's kit from the same data.

## GET /api/ripple?show=Example%20Show&songs=Song%20One%20by%20Artist%20One;Song%20Two|Artist%20Two
Live scoring for any show and up to 8 songs, separated by `;`. Each song is `song|artist` (split on the first `|`) or `song by artist` (split on the last ` by `, case-insensitive, so `Stand by Me by Example Singer` is song `Stand by Me`, artist `Example Singer`); anything else is a 422 naming both formats. Optional an optional `as_of=YYYY-MM-DD` (between 2015-08-01 and today). `as_of` changes only the Wikipedia context window; Qloo audiences are today's. Limits: 10 scorings per hour per visitor (first address in `X-Forwarded-For`, else the socket peer) and 300 per day per server process; either returns HTTP 429 with the limit named.
```json
{"resolved": true, "show": "Example Show", "as_of": "2026-10-27",
 "show_age": {"24_and_younger": 0.5, "25_to_29": 0.3, "30_to_34": 0.1, "35_to_44": -0.4, "45_to_54": -0.3, "55_and_older": -0.4},
 "songs": [{"song": "Song One", "artist": "Artist One", "resolved": true,
            "score": 0.68, "age_gap": 0.68, "fit": 0.4,
            "artist_age": {"24_and_younger": 0.0, "25_to_29": 0.1, "30_to_34": 0.2, "35_to_44": 0.2, "45_to_54": 0.3, "55_and_older": 0.1},
            "prior_daily_views": 350.0, "wiki_article": "Song_One", "obscurity": -5.9}]}
```
`score` equals `age_gap`, in [0,1]: how far the artist's audience sits from the show's audience by age band (the artist's over-index weighted by the age bands the show over-indexes on). `fit` (Qloo taste fit), `prior_daily_views` and `obscurity` are context only and are not scored. A song whose artist has no Qloo audience profile has `score: null`; an unmatched artist has `resolved: false`. When the show has no Qloo audience profile the response is `{"resolved": false, "show": "...", "songs": []}`.

## GET /api/scorecard
```json
{"spillover": {"locked": 3000, "graded": 0, "hits": 0, "pending": 3000, "auc": null},
 "ripple": {"locked": 0, "graded_releases": 0, "pending_releases": 0, "mean_spearman": null},
 "backtest": {
   "spillover": {"history_auc": 0.81, "test_breakouts": 800, "subset_breakouts": 200,
                 "history_auc_same_subset": 0.82, "qloo_auc": 0.82},
   "ripple": {"n_artists": 190, "n_shows": 24, "n_shows_2024_plus": 9,
              "gap_2024_plus": 0.25, "gap_2024_plus_p": 0.03, "fit_2024_plus": 0.0, "obscurity_2024_plus": 0.30,
              "placebo": {"all": {"n_shows": 24, "real: obscurity": 0.25, "real: gap": 0.10,
                                  "placebo: obscurity (its own pre-window)": 0.20, "placebo: gap": -0.10,
                                  "p: gap real minus gap placebo": 0.05},
                          "2024_plus": {"n_shows": 9, "...": 0}}}},
 "ledger_url": "https://github.com/zaidwhy/aftershock/blob/main/ledger/forecasts.jsonl",
 "ledger_intact": true, "data_week": "2026-10-25"}
```
`locked` for spillover counts ledger rows (one per candidate country per title); grading happens once a title's 4-week horizon has passed in Netflix's weekly data. The placebo block holds mean within-show Spearman against the real spike and against a spike measured entirely before release.

## GET /api/replays
Famous ripples with real Wikipedia monthly views, for the intro animation.
```json
{"replays": [{"show": "Stranger Things 4", "release": "2022-05-27", "song": "Running Up That Hill", "artist": "Kate Bush",
              "monthly_views": [["2022-01", 12000], ["2022-06", 909000]]}]}
```

## GET /api/ripples
New releases with known song placements. A release's songs are locked in the ledger only if the lock happens before its outcome window opens (release + 7 days) and at least 4 songs are scorable; otherwise `lockable` is false, `not_locked_reason` says why, and the release is an early read only.
```json
{"ripples": [{"id": "show-2026-10-23", "show": "Show", "show_type": "tv_show", "platform": "Netflix", "release_date": "2026-10-23",
              "songs": 14, "top_song": {"song": "...", "artist": "...", "score": 0.72}, "locked_at": "2026-10-27T01:00:00Z",
              "lockable": true, "not_locked_reason": null}]}
```

## GET /api/ripples/{id}
```json
{"id": "...", "show": "...", "show_type": "tv_show", "platform": "Netflix", "release_date": "2026-10-23",
 "qloo_show": "Show", "show_age": {"24_and_younger": 0.4, "...": 0},
 "lockable": true, "not_locked_reason": null, "locked_at": "...", "ledger_id": "...",
 "songs": [{"song": "...", "artist": "...", "resolved": true, "score": 0.61, "age_gap": 0.61, "fit": 0.3,
            "prior_daily_views": 66.3, "wiki_article": "Space_Song", "obscurity": -4.2,
            "artist_age": {"24_and_younger": -0.2, "...": 0},
            "early_status": "pending", "early_ratio": 1.8, "early_after_mean": 120.4}]}
```
`score` is the Qloo age gap. `early_ratio` is the mean daily Wikipedia views on days +7 to +35 after release over days -60 to -8, still accumulating while `early_status` is `pending`. Many new 2026 titles have no Qloo audience profile yet, so some releases have few or no scorable songs.

## GET /api/scout?show=Example%20Show
Sync Scout: artists from Qloo's taste neighbourhood for a show or film, ranked by the Qloo age gap (how far the artist's audience sits from the show's by age band, 0 to 1). It ranks artists, not scenes; the gap tracked real song spikes but not a placebo in the backtest, so it is modest, in-sample evidence and not a hit predictor. One scout makes at most 60 Qloo calls and takes about 15 seconds uncached. It shares the per-visitor and daily limit of `/api/ripple`. `show` is 1 to 120 characters. Raw affinity and demographic values are never returned.
```json
{"resolved": true, "show": "Example Show", "show_entity": "uuid", "candidates": 50, "profiled": 44, "truncated": false,
 "artists": [{"name": "Example Artist", "entity_id": "uuid", "gap": 0.71, "taste_rank": 9,
              "why": "Audience over-indexes on ages 45 to 54; the show's on ages 24 and younger."}]}
```
`artists` holds up to 12 rows sorted by `gap` descending; `taste_rank` is the artist's position (1 to 50) in Qloo's taste order for the show. Artists with no Qloo audience profile are dropped, and `truncated` is true if the Qloo call budget ran out partway. An unknown show or one without an audience profile returns `{"resolved": false, "show": "...", "reason": "...", "artists": []}`. The MCP tool `sync_scout(show)` returns the same shape, limited to 6 calls per hour per server process.
