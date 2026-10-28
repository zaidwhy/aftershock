# AFTERSHOCK API contract

All endpoints are GET and return JSON. The Qloo key never leaves the server. Every number in the examples below is synthetic (invented to show the shape), not a result and not Qloo output.

## GET /health
`{"status": "ok", "qloo_key": true, "cache_entries": 1234}`

## GET /api/storms
Current breakouts: titles that entered the Netflix Top 10 in 1 to 3 countries in the latest published week.
```json
{"week": "2026-10-25",
 "featured_plan": {"id": "example-show-s1", "code": "KR", "title": "Example Show", "country": "South Korea"},
 "storms": [
  {"id": "example-show-s1", "title": "Example Show", "season": "Season 1", "label": "Example Show Season 1",
   "category": "TV (Non-English)", "origin_countries": [{"code": "JP", "name": "Japan"}],
   "origin_week": "2026-10-25", "qloo_entity": "uuid-or-null",
   "top_forecast": {"code": "KR", "name": "South Korea", "probability": 0.21,
                    "why": "South Korea joined 23 of 100 past breakouts that started in Japan"}}
]}
```

`featured_plan` is the plan the site opens on (`null` when no storm has a launch kit): among title-specific kit rows with at least 3 Qloo-confirmed AI picks and at least 1 event idea, titles released within 5 years of the data week come first, then the most confirmed picks, then the country's chance; with no such row, the older rule (first title-specific row with 3 confirmed picks among the 8 likeliest storms, else the top storm's first kit row). `label` tells storms apart when titles repeat (the season, plus category and year if that still collides).

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
   "brand": [{"name": "Example Brand A", "entity_id": "uuid"}]},
   "hotspots": {"cells": [[37.5665, 126.978, 1.0], [35.1796, 129.0756, 0.992]],
                "places": ["Example City A", "Example City B", "Example City C"]},
   "control": {"artist": ["Example Artist X", "Example Artist A"], "tv_show": ["Example Show X"]},
   "specificity": 0.62, "generic": false}]
}
```
Each `launch_kit` row may also carry `plan`, added only when the weekly run had a `GEMINI_API_KEY` (the GitHub Action has none, so rows from that run have no `plan`): `{"confirmed": [{"domain": "artist", "name": "Example Artist C", "both": true}], "dropped": {"not_placed": 6, "not_in_qloo": 5}, "rejected": [{"domain": "artist", "name": "Example Artist D", "verdict": "not_placed"}, {"domain": "brand", "name": "Example Brand E", "verdict": "not_in_qloo"}], "model": "gemini-3.5-flash"}`. An LLM proposed up to 5 names per domain for this title and country; Qloo's strict exact-name search resolved each to an entity and one filtered `/v2/insights` call per domain kept those Qloo places with this audience. `confirmed` is those names, grouped by domain in kit order and ordered by Qloo's affinity within a domain (the values are not exposed); `both` is true when Qloo's own kit for the row also named it. `dropped.not_placed` counts names Qloo knows but does not place with this audience there; `dropped.not_in_qloo` counts names with no exact match. `rejected` lists those same names one by one, `{domain, name, verdict}` with verdict `not_placed` or `not_in_qloo`: the name is what the LLM proposed (not Qloo response data), the verdict is ours; the site strikes them through with the reason (up to 8, then "and N more"), and the `qloo_check` step of the brief carries the same list. Confirmed names use the spelling Qloo's insights answer gives. A name whose search or check failed is in neither count, so the three can sum to less than the names proposed. See `aftershock/grounded_plan.py`.

Each `launch_kit` row also carries `events` and `events_checked`, added by the weekly run (`aftershock/live_events.py`): `"events": [{"artist": "Example Artist A", "cities": ["Example City A", "Example City B"]}]`, `"events_checked": 3`. For up to three artists (the ones the launch brief names as partners, Qloo-confirmed AI picks first, otherwise Qloo's own kit) Qloo's heatmap for the artist in the same country is compared with the title's hotspots: a place in `hotspots.places` is an event city for the artist when one of the artist's 5 strongest cells lies within 30 km of the title cell that place was named from (`hotspots.place_cells`, `[lat, lon]` per place, same order). `cities` are in the title's hotspot order, strongest first; artists with no overlapping city are left out of `events` but counted in `events_checked`. Rows from older weeks have neither field. This is where two audiences overlap, not a ticket-demand forecast.

`partners` is the one place Qloo appears here: artists the title's audience over-indexes on in each forecast country. It does not change the probabilities (Qloo gave no AUC lift in the backtest).

`launch_kit` covers the same top three forecast countries. Per country, `kit` maps a domain (`artist`, `tv_show`, `movie`, `brand`) to up to five entities the title's audience there over-indexes on, in Qloo's order; a domain that returned nothing is omitted, and a country with no results is omitted. No affinity values are exposed. `hotspots` (same row) is where inside the country the title's audience concentrates: `cells` are up to 120 `[latitude, longitude, weight]` points (weight 1 is the strongest, from Qloo's `urn:heatmap` affinity rank) and `places` are up to three names from OpenStreetMap Nominatim reverse geocoding (place names © OpenStreetMap contributors); either list can be empty. `control` is Qloo's country-only list for the same domains (the same `/v2/insights` call without the title signal): what the whole country over-indexes on anyway. `specificity` is the mean over domains where both lists are non-empty of 1 minus the Jaccard overlap between the kit's names and the control's (names lower-cased, accents and punctuation stripped), in [0,1], or null when no domain can be compared. `generic` is true when `specificity` is 0.4 or less (overlap of 0.6 or more), the threshold registered in `docs/EXPERIMENT_KITS.md`. `GET /api/storms` also carries `has_kit` and `kit_specific` per storm (`kit_specific` is false when every kit row is generic). The MCP tool `launch_kit(storm_id, country)` returns one country's kit, `specificity`, `generic` and its hotspot place names (not the cells, not the control lists) from the same data.

## GET /api/brief?storm=example-show-s1&country=KR
The launch brief for one breakout in one of its launch-kit countries: what an agent would do, step by step, and the finished brief. Reads files only (no Qloo or model call). The same brief is already on each `launch_kit` row of `GET /api/storms/{id}` as `brief`, so the site needs no extra request. An unknown storm is 404 "No breakout called ... in any week we have forecast."; a country with no kit is 404 "No launch kit for ...".
```json
{"steps": [{"key": "forecast", "title": "Forecast where it goes next", "found": "one sentence with numbers"},
           {"key": "qloo_check", "title": "Check each AI name against Qloo", "found": "...", "decision": "a rule the agent applied"}],
 "brief": {"title": "Example Show", "country": "South Korea", "code": "KR", "headline": "...", "chance": 0.21,
           "rank": 1, "of_countries": 10, "kit_scope": "title-specific", "partner_basis": "ai_confirmed",
           "cities": ["Example City A"],
           "partners": [{"domain": "artist", "label": "Artists",
                         "picks": [{"name": "Example Artist C", "source": "ai_confirmed", "also_in_qloo_kit": true}]}],
           "avoid": ["..."], "evidence": ["..."], "summary": "two sentences", "summary_source": "ai, checked"}}
```
Steps, in order: `forecast`, `qloo_kit`, `ai_proposals`, `qloo_check`, `cities`, `events`, `brief`. The brief carries `event_ideas` (shown on the site as "Quick-turn activation ideas": things doable within about a week, not tours): `[{"artist": "Example Artist A", "cities": ["Example City A", "Example City B"], "text": "Example Artist A in Example City A and Example City B: both audiences concentrate there."}]` (empty when no artist's audience overlaps the title's cities; the `events` step then says so, and when there is at least one, "what not to claim" gains "Activation ideas are where audiences overlap, not ticket-demand forecasts."). Decisions are fixed rules in `aftershock/launch_brief.py`: Qloo-confirmed AI picks lead the partners only when at least 3 were confirmed, otherwise Qloo's own kit is used; a countrywide kit adds a "do not say this audience is distinctive" line. `summary_source` is `ai, checked` when Gemini wrote the summary in the weekly run and every name and number in it appears in the brief's facts, else `template`. The MCP tool `launch_brief(storm_id, country_code)` returns the same body.

## GET /api/ripple?show=Example%20Show&songs=Song%20One%20by%20Artist%20One;Song%20Two|Artist%20Two
Live scoring for any show and up to 8 songs, separated by `;`. Each song is `song|artist` (split on the first `|`) or `song by artist` (split on the last ` by `, case-insensitive, so `Stand by Me by Example Singer` is song `Stand by Me`, artist `Example Singer`); anything else is a 422 naming both formats. Optional an optional `as_of=YYYY-MM-DD` (between 2015-08-01 and today). `as_of` changes only the Wikipedia context window; Qloo audiences are today's. Limits: 10 scorings per hour per visitor (first address in `X-Forwarded-For`, else the socket peer) and 300 per day per server process; either returns HTTP 429 with the limit named.
```json
{"resolved": true, "show": "Example Show", "as_of": "2026-10-27",
 "show_leans": ["24_and_younger", "25_to_29", "30_to_34"],
 "songs": [{"song": "Song One", "artist": "Artist One", "resolved": true,
            "score": 0.68, "age_gap": 0.68,
            "leans": ["45_to_54", "35_to_44", "55_and_older"],
            "prior_daily_views": 350.0, "wiki_article": "Song_One", "obscurity": -5.9}]}
```
`score` equals `age_gap`, in [0,1]: how far the artist's audience sits from the show's audience by age band (the artist's over-index weighted by the age bands the show over-indexes on). `show_leans` and `leans` name the age bands each audience over-indexes on, strongest first; raw Qloo values (taste fit, per-band over-index numbers) are never returned. `prior_daily_views` and `obscurity` are context only and are not scored. A song whose artist has no Qloo audience profile has `score: null`; an unmatched artist has `resolved: false`. When the show has no Qloo audience profile the response is `{"resolved": false, "show": "...", "songs": []}`.

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
`locked` for spillover counts ledger rows (one per candidate country per title); grading happens once a title's 4-week horizon has passed in Netflix's weekly data. The placebo block holds mean within-show Spearman against the real spike and against a spike measured entirely before release. When `data/results/grounded_plan.json` exists the response also carries `grounded_plan`: `{"status": "exploratory, ...", "pairs": 81, "picks_checked": 1600, "unbacked_share": 0.71, "specificity_plan": 0.86, "specificity_llm": 0.81, "specificity_pairs": 79}` (synthetic values; `unbacked_share` is the share of the LLM's names Qloo did not confirm), which the Scorecard leads its Qloo-versus-LLM section with.

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
 "qloo_show": "Show", "show_leans": ["24_and_younger"],
 "lockable": true, "not_locked_reason": null, "locked_at": "...", "ledger_id": "...",
 "songs": [{"song": "...", "artist": "...", "resolved": true, "score": 0.61, "age_gap": 0.61,
            "prior_daily_views": 66.3, "wiki_article": "Space_Song", "obscurity": -4.2,
            "leans": ["45_to_54"],
            "early_status": "pending", "early_ratio": 1.8, "early_after_mean": 120.4}]}
```
`score` is the Qloo age gap. `early_ratio` is the mean daily Wikipedia views on days +7 to +35 after release over days -60 to -8, still accumulating while `early_status` is `pending`. Many new 2026 titles have no Qloo audience profile yet, so some releases have few or no scorable songs.

## GET /api/scout?show=Example%20Show
Sync Scout: artists from Qloo's taste neighbourhood for a show or film, ranked by the Qloo age gap (how far the artist's audience sits from the show's by age band, 0 to 1). It ranks artists, not scenes; the gap tracked real song spikes but not a placebo in the backtest, so it is modest, in-sample evidence and not a hit predictor. One scout makes at most 60 Qloo calls and takes about 15 seconds uncached. It shares the per-visitor and daily limit of `/api/ripple`. `show` is 1 to 120 characters. Raw affinity and demographic values are never returned.
```json
{"resolved": true, "show": "Example Show", "show_entity": "uuid", "candidates": 50, "profiled": 44, "truncated": false,
 "artists": [{"name": "Example Artist", "entity_id": "uuid", "gap": 0.71, "taste_rank": 9,
              "why": "...", "leans": ["45_to_54", "55_and_older"]}],
 "show_leans": ["24_and_younger", "25_to_29"]}
```
`artists` holds up to 12 rows sorted by `gap` descending; `taste_rank` is the artist's position (1 to 50) in Qloo's taste order for the show. Artists with no Qloo audience profile are dropped, and `truncated` is true if the Qloo call budget ran out partway. An unknown show or one without an audience profile returns `{"resolved": false, "show": "...", "reason": "...", "artists": []}`. The MCP tool `sync_scout(show)` returns the same shape, limited to 6 calls per hour per server process.

When the show is not found, the response also carries `suggestion`: the nearest name Qloo's search returns (for example `"Stranger Things"` for `"Stranger Thingz"`). It is only a suggestion; nothing is scored against it.

## GET /api/check?storm=example-show-s1&country=KR&domain=artist&name=Example%20Artist
Live. Checks one typed name for a title's audience in one of its launch-kit countries, exactly as the weekly plan checks each AI-proposed name: `aftershock.qloo.resolve` finds the entity of that type by exact name, then one filtered `/v2/insights` call (`filter.results.entities` = that entity, `signal.interests.entities` = the title, `signal.location.query` = the country) says whether Qloo places it with this audience (`aftershock.grounded_plan.check_name`).
```json
{"verdict": "confirmed", "name": "Example Artist"}
```
`verdict` is `confirmed` (Qloo places it with this audience there), `not_placed` (Qloo knows it but does not place it with this audience there) or `not_in_qloo` (no entity of that type with exactly that name); `name` is the name as Qloo spells it (the typed name for `not_in_qloo`). `domain` is one of `artist`, `brand`, `tv_show`, `movie`; `name` is 1 to 80 characters; `storm` and `country` must name a storm with a launch-kit row for that country (404 otherwise). Out-of-range input is 422. It uses the same per-visitor and daily live limit as `/api/ripple` and `/api/scout` (429), and Qloo failures come back as the same visitor-facing sentences (503 when the key is refused or Qloo is rate-limiting, 502 otherwise).

## GET /api/release?name=Example%20Act&kind=music&like=Comparable%20One,Comparable%20Two&region=asia&home=IN&goal=tour
Live. Plans a release from Qloo alone (`aftershock/release_plan.py`): which countries have the audience and where inside them, which venues there fit, and what that audience also likes locally. `kind` is `film`, `series`, `music` or `comedy`. `name` is 1 to 120 characters. `like` is optional, up to 5 comparables separated by comma, semicolon or `|`, each 1 to 120 characters. Optional inputs, each rejected with a 422 naming the field: `region` is `any` (default: the original 24 countries), `asia`, `europe`, `americas`, `middle-east-africa` or `oceania` (every pool country in it: 11, 11, 8, 8 and 2 countries; the pool also has Thailand, Malaysia, Vietnam, Taiwan, Pakistan, Poland, Norway, Denmark, Ireland, Colombia, Chile, Peru, Egypt, Kenya, Morocco and New Zealand; Bangladesh was tried and Qloo returns no destinations for it). `home` is a 2-letter ISO country code left out of the ranking and the calls (the home market). `goal` is `tour` (live venues: concert halls and live-music venues for music, comedy clubs for comedy), `premiere` (cinemas) or `digital` (no venue calls at all). With no `goal`, music and comedy mean tour and film and series mean premiere; a film or series with `goal=tour` is treated as a premiere, and the venue step says so.

The signal is the title if Qloo knows it by exactly that name (a comedian is a Qloo `person`, "Name, Comedian"; their specials are `tv_show`s). A name is matched exactly, or by Qloo's "Name, Occupation" form, or case- and space-folded (not ASCII-stripped) against the hit's name and its `properties.akas`, so a title in another script such as 오징어 게임 finds Squid Game. If nothing matches under the chosen kind's types, the same name is searched once more across film, TV show, artist and person, and the entity's real type is used; the resolve step then says so ("found as a TV show although you chose music"). Otherwise the first 3 comparables Qloo knows stand in, each searched the same way, which is how an unreleased title is planned. With neither, nothing is guessed. Which call produces what:
- **Countries** (`qloo_destinations`): `/v2/insights` with `filter.type=urn:entity:destination`, `filter.geocode.country_code` and `take=15`, once for each of 24 candidate countries. A country's `score` is its best destination affinity among destinations with Qloo popularity of at least 0.4, and the top 8 countries are returned. Destination affinity is travel-flavoured (its top row is often a village or resort), so it ranks countries and supplies city candidates; it is not shown as the audience's cities. The popularity floor removes villages (measured on 1,860 candidates: Larrabetzu 0.003, Dalyan 0.02, Lichfield 0.13, Morzine 0.38) and keeps mid-size cities (Jaipur 0.48, Nagoya 0.46); it cannot remove famous resorts (Whistler 0.90, Agra 0.77), which the density step handles.
- **Where the audience lives** (`qloo_heatmap`): for the top 3 countries, one `urn:heatmap` call (`signal.interests.entities`, `filter.location.query` = the country), as the launch kits do (`aftershock/hotspots.py`). The country's destination candidates are scored by audience density, the sum of heatmap cell weights within 40 km; candidates with no cells nearby, or under a tenth of the best density, are dropped, candidates within 15 km of each other, or within 40 km with related names (one name starts with the other or they share a first word, such as Bangkok and Bangkok Metropolis), are merged into the most popular, ties go to the higher destination affinity, and the top 3 are kept. Only a country where no candidate has cells nearby falls back to naming its strongest cells by OpenStreetMap Nominatim reverse geocoding (not a Qloo call; within a 10 second budget, after which the cells are kept without names). The result per country is `hotspots: {cells: [[lat, lon, weight]], places: [name], place_cells: [[lat, lon]]}`, the launch kits' shape, plus `cities: [{name, lat, lon, affinity, density}]` when the destination method found them (`affinity` is the destination affinity, `density` the summed cell weight). Countries 4 to 8 have only the score.
- **Venues** (`qloo_places`): `/v2/insights` with `filter.type=urn:entity:place`, `filter.tags` (comedy: `urn:tag:category:place:comedy_club`; music: `concert_hall` or `live_music_venue`; film and series: `movie_theater`) and a point-and-radius location (20 km) around the strongest city of each top country; a city with no venue is replaced by the next one down, up to 6 calls. Unfiltered place results are noise, and Qloo's venue tags are loose, so each place is checked against its own tags before it is listed: it is dropped when any tag marks another business (a clinic, homeopath, hotel, banquet or wedding venue, interior design, and, unless it also has a strong performing-arts tag, a school, gym, pharmacy and similar), when it is a restaurant or bar without a strong performing-arts tag, when it has no performing-arts tag for the goal (comedy club, concert hall, performing arts theater, auditorium and so on; a movie theater for a premiere, not a museum), and, for music, when it is an opera house. A venue Qloo lists near two cities is kept under the first. The step note says how many non-venues and duplicates were dropped.
- **Local taste** (`qloo_insights`): the signal's audience in the top 2 countries (`signal.location.query`) for TV shows, films and artists, with the signal itself removed.
```json
{"resolved": true, "name": "Example Act", "kind": "music", "region": "asia", "home": "IN", "goal": "tour",
 "signal": {"used": "title", "entities": [{"name": "Example Act", "id": "uuid", "type": "urn:entity:artist"}]},
 "countries_checked": 10,
 "scores": [{"code": "XA", "name": "Country A", "score": 0.778}, {"code": "XD", "name": "Country D", "score": 0.61}],
 "countries": [{"code": "XA", "name": "Country A", "score": 0.778,
                "summary": "Country A leads: Qloo's destination affinity 0.78, the highest of the 24 countries checked. Qloo's audience map peaks around City A, City B and City C.",
                "hotspots": {"cells": [[0.0, 0.0, 1.0]], "places": ["City A"], "place_cells": [[0.0, 0.0]]},
                "cities": [{"name": "City A", "lat": 0.0, "lon": 0.0, "affinity": 0.778, "density": 12.4}]},
               {"code": "XD", "name": "Country D", "score": 0.61, "summary": "Country D: Qloo's destination affinity 0.61, 0.17 below Country A."}],
 "venues": [{"city": "City A", "country": "Country A",
             "venues": [{"name": "Example Hall", "address": "...", "lat": 0.0, "lon": 0.0, "tags": ["Concert hall"]}]}],
 "local_taste": [{"code": "XA", "country": "Country A", "tv_show": ["Name"], "movie": ["Name"], "artist": ["Name"]}],
 "steps": [{"tool": "qloo_search", "endpoint": "/search", "params": {"query": "Example Act", "types": "urn:entity:artist", "take": 5},
            "ok": true, "note": "Qloo knows 'Example Act'; its audience is the signal.", "calls": 1},
           {"tool": "qloo_destinations", "endpoint": "/v2/insights",
            "params": {"filter.type": "urn:entity:destination", "signal.interests.entities": "uuid", "take": 3},
            "varies": {"filter.geocode.country_code": ["XA", "XB"]}, "ok": true, "note": "...", "calls": 24}],
 "calls": 36, "caveats": ["..."]}
```
`scores` has one row for every country checked that Qloo had destinations for (not only the top 8 in `countries`), best first, for drawing a world map; `region`, `home` and `goal` echo the inputs (`goal` as applied, `home` upper-cased). `score` is Qloo's relative destination affinity, not a probability and not a forecast of ticket or stream numbers; it is a country's single best destination. `steps` lists every Qloo call in order (resolve, countries, cities, venues, taste), each saying which call produced what: `params` are the parameters all calls in the step share, `varies` the ones that differ per call, `calls` how many. The key is never included. A plan makes at most 52 Qloo calls (typically 37 to 39 for the default region: 1 to 2 searches, 24 destination, 3 heatmap, 3 or 4 venue, 6 taste; fewer for a smaller region, for a `home`, and none of the venue calls for `goal=digital`) and takes about 10 to 20 seconds uncached (a region=asia run took 9.8 seconds); Qloo and Nominatim answers are cached on disk, under /tmp on Vercel. Venues are listed in Qloo's place ranking within the tag, not by this audience, and the tags are loose (a few bars or banquet halls appear); film and series venues are cinemas, not screening events. When neither the name nor a comparable is in Qloo the response is `{"resolved": false, "name": "...", "kind": "...", "region": "...", "home": null, "goal": "...", "reason": "...", "try": ["..."], "scores": [], "steps": [...], "calls": n}`; with no comparables the first `try` item says to add 2 or 3 similar titles or acts. Bad input is 422 naming the field and its limit; the same per-visitor and daily live limit as `/api/ripple` applies (429), and Qloo failures are the same 503 and 502 sentences as `/api/check`. The MCP tool `release_plan(name, kind, like, region, home, goal)` returns the same shape, limited to 6 calls per hour per server process.

## GET /api/title?name=Example%20Show

Netflix Top 10 history for any title that charted since 2024 (no Qloo calls, no rate limit). Matching ignores case, accents and "Season N"; a name must match closely (ratio 0.85 or a whole-word match) or the response is 404 `{"detail": "No close match in Netflix's Top 10 since 2024"}`. `name` is 1 to 80 characters.

```json
{"title": "Example Show: Season 2", "show": "Example Show", "season": "Season 2", "kind": "tv",
 "first_week": "2026-09-06", "countries": [["XA", "2026-09-06"], ["XB", "2026-09-13"]],
 "still_spreading": true, "storm_id": "example-show-season-2",
 "forecast": {"origin": ["XA"], "horizon_weeks": 4,
              "next": [{"code": "XC", "name": "Country C", "probability": 0.21, "why": "Country C joined 12 of 57 past breakouts that started in Country A"}]},
 "others": [{"title": "Example Show: Season 1", "kind": "tv", "first_week": "2025-03-02"}]}
```
`forecast` is present only for titles that first charted within the last four weeks in one to three countries; a title still spreading from more countries than that carries `forecast_note` ("already charting widely") instead. `storm_id` is present only when the title is one of this week's breakouts.

## GET /api/ask?q=What%20is%20heading%20to%20Country%20C

The plain-question router behind "Ask the agent" and the MCP tool `ask`. Fixed rules, no language model: it picks one intent and calls the site's own tools. `q` is 1 to 200 characters.

| intent | example question | tool used |
|---|---|---|
| `song_check` | "Song One by Artist One for Example Show" | the ripple scoring (live, counts against the limit below) |
| `artists_for_show` | "Find songs for Example Show" | Sync Scout (live) |
| `launch_kit` | "What should Example Show pair with in Country C?" | this week's storm, its kit and hotspots |
| `forecast` | "Where will Example Show go next?" | title lookup plus the storm forecast |
| `country` | "What is heading to Country C?" | this week's map entry |
| `none` | anything else | a list of what it can answer |

```json
{"intent": "country",
 "steps": [{"n": 1, "tool": "understand", "input": null, "ok": true, "note": "What is heading to Country C this week."},
           {"n": 2, "tool": "week_map", "input": "XC", "ok": true, "note": "Read this week's map."}],
 "answer": {"kind": "country", "name": "Country C", "code": "XC", "week": "2026-10-18", "chance": 0.2,
            "top": [{"title": "Example Show", "probability": 0.07, "id": "example-show"}]},
 "links": [{"label": "Full forecast for Example Show", "href": "#/storm/example-show"}]}
```
`steps` is what the agent did, in order; a failed step has `ok: false` and says why (an unknown country, a title that is not a breakout this week, a non-Latin title).

## Static files the site reads

Read-only pages load these files instead of the API, so they never wait for a cold start. They are written by `scripts/export_static.py` from the weekly run and match the API bodies exactly (`tests/test_export_static.py`).

| file | same as | notes |
|---|---|---|
| `/data/storms.json` | `GET /api/storms` | includes `map` (per country: chance at least one breakout arrives, top titles) and `hero` (the worked example) |
| `/data/storms/<id>.json` | `GET /api/storms/{id}` | |
| `/data/scorecard.json` | `GET /api/scorecard` | includes `kit_check`, `top_pick` and the experiment result once it exists |
| `/data/replays.json` | `GET /api/replays` | |
| `/data/agent_run.json` | (static only) | the last weekly run: `started`, `finished`, `netflix_week`, `dry_run`, `summary`, `steps[{key, count, text, detail}]` |
| `/data/ledger.json` | (static only) | `total`, `titles`, `first_locked`, `last_locked`, `intact` (hash chain verified), `raw_url`, 50 most recent `rows` |

## Limits and errors

- Live endpoints (`/api/ripple`, `/api/scout`, `/api/check`, `/api/release`, and `/api/ask` when it routes to them) share one limit: 10 per hour per visitor (first `X-Forwarded-For` address) and 300 per day per server process across all visitors; over the limit is 429 with a plain message.
- Text fields are length-limited (show, artist and release name 120 characters, title lookup 80, questions 200); a missing or too-long field is 422 naming the field.
- An unknown storm or title is 404 with a sentence in `detail`.
- Qloo failing is 502 "Qloo did not answer this request; try again in a minute".
