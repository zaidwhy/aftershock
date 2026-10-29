# AFTERSHOCK

[![tests](https://github.com/zaidwhy/aftershock/actions/workflows/tests.yml/badge.svg)](https://github.com/zaidwhy/aftershock/actions/workflows/tests.yml) [live site](https://aftershock-qloo.vercel.app) · [public ledger](https://aftershock-qloo.vercel.app/#/ledger) · [pre-registered experiments](docs/EXPERIMENT_KITS.md)

**Shows travel. See where next.** When a Netflix show gets popular in one country, it often spreads to the next. AFTERSHOCK predicts which country is next, plans the launch there with Qloo's audience data, and throws out every AI suggestion Qloo cannot support.

An LLM alone, asked what a title's audience in a country loves, answers fluently and specifically. Of the 1,615 names an LLM proposed on 81 title-country pairs, 66% are names Qloo knows and 29% are ones Qloo links to that audience in that country; the other 71% are not backed: 34% are names Qloo has no data on (a gap in Qloo's coverage, not proof the name is wrong) and 37% are names Qloo knows but does not place with that audience (section 3). On title-specificity (section 3, 0 to 1) Qloo alone scores 0.62, the LLM alone 0.81 and the LLM checked by Qloo 0.86 (exploratory, not pre-registered). So in AFTERSHOCK the LLM proposes and Qloo decides: every name is checked for that title's audience in that country, and only confirmed names reach the plan.

Each week it ran, the agent read Netflix's public per-country Top 10 (the weekly runs are paused until Netflix permits them; see Data and terms), finds titles that just broke out in one to three countries, and forecasts where each charts next from Netflix history. For the top countries it asks Qloo what that title's audience over-indexes on (the launch kit, checked against the country's general taste), asks Gemini for more ideas and checks each one against Qloo, finds the cities where the audience concentrates (Hotspots), and writes a **Launch Brief** per country: where, which cities, which partners, and what the evidence does not support. **Plan a launch** on the site replays those steps one by one (they are precomputed by the weekly run, not run live), lists the AI names Qloo rejected struck through with the reason, and ends in the brief; **Follow one title** recolours the world map by one title's chances. Every forecast is locked in a hash-chained ledger before its outcome exists and graded against Netflix's later charts.

Built for the [Qloo Agentic Hackathon](https://qloo.devpost.com/), October 2026. MIT licensed. The live site shows the last weekly run; its Agent page says when that was.

**Live name check.** The plan page has a box under the check step: type an artist, brand, TV show or film and Qloo confirms or rejects it for that title's audience in that country, now (`GET /api/check`, `aftershock.grounded_plan.check_name`: `resolve` by exact name, then the same filtered `/v2/insights` call the weekly plan uses; verdict `confirmed`, `not_placed` or `not_in_qloo`, same per-visitor live limit as Song check, API contract in `docs/API.md`). Names Qloo has no data on are shown unstruck as "No Qloo data yet"; only names Qloo knows but does not place with the audience are struck through. Names equal to the title or its franchise ("Nightwatch" for "Nightwatch: Demons Are Forever") are dropped from AI proposals and from stored plans at read time.

**Words used below.** The site uses plain words; this README keeps the working terms. A *breakout* (the site says *a show popular in one country*, or a *trending show*) is a title that has just entered Netflix's Top 10 in one to three countries. *SPILLOVER* is the forecast of which other countries chart it within four weeks. A *launch kit* (on the site, *Qloo's picks*) is what that title's audience over-indexes on in one forecast country, from Qloo; *Hotspots* (on the site, *where fans live*) are the cities where that audience concentrates. The *Launch Brief* is the site's *launch plan*; the *ledger* is its *prediction history*; the *scorecard* is *prediction results*. *Song check* (code name RIPPLE) compares a show's audience with each artist's by age; *Sync Scout* runs the same comparison over artists Qloo says the show's fans like. *Over-index* is Qloo's term for "likes this more than the average person". *Spearman* is a rank correlation from -1 to 1; *Jaccard overlap* is the share of names two lists have in common.

## 1. The problem

Labels, music publishers, promoters and brands, then local distributors and dubbing studios, react to breakouts after the fact. Netflix sees its own viewing data; they do not. AFTERSHOCK gives them a forecast with its evidence attached, local partners from Qloo, and a public record of how good those forecasts have been.

## 2. The models and the Qloo calls

**For artists (`aftershock/artist_view.py`, `#/artists`, `#/artist/<slug>`, `/api/artists`, MCP `artist_opportunities`).** Artists are a beneficiary here, not only a name on a brand's list. For this week's storms the view indexes every artist that is a Qloo-confirmed AI pick or appears in an event idea, and for each (title, country) shows the chance the title charts there within four weeks, the cities where both audiences concentrate (when an event idea exists), whether Qloo's own kit also named the artist and whether Qloo confirmed the AI's suggestion. It re-indexes data the weekly run already holds: no new Qloo or model call. It is audience overlap, not a forecast of streams or ticket sales. Partner order in a brief (`launch_brief._partners`): when the kit is title-specific (not countrywide, specificity at least 0.6) Qloo's own kit leads, headed by a data line built from its first three shows, films or artists, and the AI names Qloo confirmed follow as "Also confirmed by Qloo from the AI's suggestions" (duplicates skipped); a countrywide kit keeps the AI-confirmed names first. Platform brands (Spotify, Netflix, YouTube and similar) are dropped from brand partners and moves, and the home example follows the same order. Every Launch Brief also ends its facts with a "This week's moves" section (`launch_brief._moves`): one deterministic move per buyer, dropped when its facts are missing.

**Why the agent follows a fixed plan instead of letting the LLM choose its own steps.** A brief someone acts on has to say why each name is in it. An LLM that picks its own tools can skip the Qloo check, call it on the wrong audience, or explain a step it never ran, and nobody can tell afterwards. So the order is fixed (forecast, Qloo kit, AI proposals, Qloo check, cities, artist-city match, brief), the LLM does what it is good at inside that order (proposing names, drafting the summary), and every decision is a rule printed next to the step it changed, such as "Qloo confirmed fewer than 3 AI picks, so the brief uses Qloo's own kit". The same steps run the same way for every title, which is what lets us measure them.

**Which plan the site opens on.** The home button and `#/plan` open the featured plan, computed in `aftershock/api.py` (`featured_plan`) and carried in the storms list: among title-specific kit rows with at least 3 Qloo-confirmed AI picks and at least 1 event idea, prefer titles released within 5 years of the data week, then the most confirmed picks, then the country's chance (without such a row, the first title-specific row with 3 confirmed picks among the likeliest storms, else the top storm's first kit row).

**SPILLOVER (countries).** For a title that broke out in countries A, the probability that country B charts it within four weeks is how often B followed past breakouts that started in A, smoothed toward B's rate for the same category, which is smoothed toward B's overall rate (`aftershock/netflix.py`). Qloo's job here is the partners list: `GET /v2/insights?filter.type=urn:entity:artist&signal.interests.entities=<title>&signal.location.query=<country>`, the artists the title's audience over-indexes on in each forecast country.

**Launch kit (what to do there).** For each storm's top three forecast countries, the same call is repeated for `urn:entity:tv_show`, `urn:entity:movie` and `urn:entity:brand` (four calls per country, about 330 added calls per weekly run), giving up to five names per domain in Qloo's order (`aftershock/launch_kit.py`). We probed seven domains and kept the four that were title-specific and local; podcasts (identical across titles), books and places (from other countries) were dropped, see `data/results/launch_kit_probe.json`. Like partners, the kit does not change the probabilities.

**Is the kit about the title? (country-only control).** For each kit country the same four calls are made once more without the title signal, giving what the whole country over-indexes on. A kit's specificity is the mean over domains of 1 minus the Jaccard overlap with that control; at 0.4 or below (overlap 0.6 or more, the threshold registered in `docs/EXPERIMENT_KITS.md`) the kit is labelled "mostly countrywide taste", otherwise "title-specific", and names that are also in the control are greyed out on the page. In the week of 18 Oct, 48 of 81 kits were title-specific (mean specificity 0.61); thin titles such as stand-up specials fall back to the country's general taste.

**Hotspots (which cities).** For the same three countries, one `GET /v2/insights?filter.type=urn:heatmap&signal.interests.entities=<title>&filter.location.query=<country>` call returns about 1,800 geohash cells with an affinity rank; the top 120 are kept as `[lat, lon, weight]`. The three strongest cells that are at least 60 km apart are named by reverse geocoding with OpenStreetMap Nominatim (one request per second, cached under `.cache/nominatim/`, at most eight tries per country; the cell each name came from is kept), so a promo or touring team sees where in the country to start (`aftershock/hotspots.py`). If either call fails the storm keeps whatever was gathered. At read time each name is replaced by the most popular Qloo destination within 35 km of its cell, so a suburb reads as its metro city (Lidingö becomes Stockholm); a cell with no destination that close keeps the OpenStreetMap name, and names that become equal merge (`aftershock/metro_names.py`; the destinations come from `scripts/build_metro_names.py`, one `urn:entity:destination` call per country, into the gitignored `data/private/metro_names.json`). Place names are © OpenStreetMap contributors.

**Live events (which artist, in which city).** A promoter whose show is breaking out in a country wants an artist and a city, and an LLM cannot say where in a country an artist's audience lives. For each launch-kit row we take up to three of the launch brief's artist partners, fetch each artist's heatmap in that country (one cached call each, about 250 extra calls a week) and call a title hotspot an event city for the artist when one of the artist's 5 strongest cells (`ARTIST_TOP_CELLS`) lies within `OVERLAP_KM = 30` km of the title cell that hotspot's name came from (haversine; `aftershock/live_events.py`). The brief lists these as quick-turn activation ideas next to a caveat: they show where two audiences overlap, not ticket demand, and we have not tested whether they predict sales. The thresholds were tightened after a first run at 30 cells and 60 km named every one of the title's cities for 114 of 176 ideas, which says nothing; at 5 cells and 30 km the average idea names 1.3 cities.

**This week's map and the Netflix lookup.** The home page shades every country by the expected number of this week's breakouts that reach its Top 10 within four weeks (the sum of the storms' probabilities for it; a lower bound, since each storm keeps its top 15 countries), and opens on the week's clearest worked example, chosen by rule: the highest top-country probability whose kit is title-specific and has named hotspots. "Look up any title" searches an index of the 8,721 titles that charted since 2024 (`data/private/titles.json`, built each run): when and where each first charted, and, for titles still spreading, a history-only forecast for the countries they have not reached.

**Sync Scout (songs to place).** A discovery tool for a music supervisor: one call gets the 50 artists the show's audience over-indexes on (`urn:entity:artist` with the show as the signal), one `urn:demographics` call per artist gets their audience, and the list is ranked by age gap, so the top picks are on-taste artists whose audience sits outside the show's generation (`aftershock/sync_scout.py`, at most 60 calls per scout). It ranks artists, not scenes, and the age gap it ranks by did not predict song spikes in our test (section 3), so it is a way to find candidates, not a forecast.

**RIPPLE (songs).** Score = the Qloo age gap in [0, 1]: the artist's age-band over-index, weighted by the bands the show's audience over-indexes on, mapped so that 1 means the artist's audience sits entirely outside the show's (`aftershock/ripple.py`). Calls:

| Step | Qloo call | Note |
|---|---|---|
| Resolve a show, film or artist | `GET /search` with `types`, then a name check | `/search` always returns its nearest match, even for names it does not know. We accept only an exact normalized match, and prefer the full name over a subtitled spin-off ("Love Is Blind" never becomes "Love Is Blind: UK") |
| The show's audience | `GET /v2/insights?filter.type=urn:demographics&signal.interests.entities=<show>` | six age bands |
| Each artist's audience | same, with the artist as the signal | an artist with no profile is unknown, not average |
| Taste fit, shown as context | `GET /v2/insights?filter.type=urn:entity:artist&signal.interests.entities=<show>&filter.results.entities=<artists>` | tested and did not predict (section 3) |

Wikipedia supplies context and the outcome: mean daily views of the song's article (or the artist's) on days -60..-8 before release, and the spike, which is mean daily views on days +7..+35 over days -60..-8.

## 3. What we measured, including what did not work

Every backtest and test number here comes from a script in this repo and a file in `data/results/`. Counts that describe the current week (kits, titles indexed) come from the weekly run's output, which holds Qloo-derived data and is not committed; the site and its Agent page show them.

**SPILLOVER** (`scripts/backtest_spillover.py` -> `spillover_backtest.json`; 8,696 training and 829 test breakouts, March to October 2026, 4-week horizon):

| Model | ROC AUC | Top-5 precision |
|---|---|---|
| Netflix history | 0.817 | 0.041 |
| Each country's general rate | 0.558 | 0.015 |
| Uniform | 0.500 | 0.012 |

ROC AUC 0.817 means the model ranks a country that went on to chart above one that did not 82% of the time.

**How much warning the spillover forecast gives** (`scripts/measure_lead_time.py` -> `lead_time.json`; a backtest on history-only forecasts, same 829 held-out breakouts, split, model and 4-week horizon as above; the forecast week is the breakout week and the model is fit on earlier breakouts only). Top-3 hit rate is the share of breakouts where at least one of the three forecast countries charted the title within 4 weeks; the baseline is the three countries with the highest overall join rate (the "general rate" row above: Maldives, Singapore, Malaysia for nearly every title).

| | Model's top 3 | Baseline top 3 |
|---|---|---|
| Breakouts with at least one hit | 81 of 829 (9.8%) | 34 of 829 (4.1%) |
| Per-pick precision | 131 of 2,487 (5.3%) | 49 of 2,487 (2.0%) |
| Lead time, median / mean (weeks) | 1 / 1.20 | 1 / 1.39 |
| Picks that charted after 1 / 2 / 3 / 4 weeks | 117 / 6 / 4 / 4 | 39 / 5 / 1 / 4 |

Only 113 of the 829 breakouts charted in any other country within 4 weeks, so the ceiling is low: counting all 829 breakouts the model's top 3 caught a charting country for 81 (9.8%) against 34 (4.1%) for the baseline, 2.4 times; of the 113 that spread, 81 of 113 against 34. Lead time counts only picks that charted (a miss has no lead time) and is measured from the breakout week, so most of the warning is one week. Three case studies were chosen by a rule fixed in the script before the results were read (the three held-out breakouts with the highest top-1 probability); they are on the Scorecard and in `lead_time.json`, and two of the three are misses.

Does Qloo help? `scripts/test_spillover_qloo.py` added each title's location-conditioned Qloo affinity as features on a 200-breakout subset (1,432 Qloo calls): AUC 0.8188 history-only vs 0.8182 with Qloo, so no lift. Qloo returned an in-country value for only 2.8% of title-country pairs (975 of 35,344, `qloo_value_coverage` in the same file); top-5 precision was identical (0.052) with and without Qloo, and 147 of the 200 test breakouts resolved in Qloo. The country forecast is therefore history-only.

**RIPPLE.** Ground truth: 490 songs from the official song soundtracks of 34 titles in MusicBrainz (`scripts/build_placements_musicbrainz.py` -> `data/placements.csv`; release and source per title in `data/placements_sources.csv`), with Wikipedia spikes in `data/ripple_truth.csv`. A placement here means "on the title's official song soundtrack", which is broader than "used in a scene". Main test (`scripts/test_ripple.py --outcome artist` -> `ripple_test_artist.json`): one row per artist per show, artists without a Qloo audience profile excluded, 229 artists in 24 shows with at least 4 scored artists. Mean within-show Spearman with the log spike, one-sided permutation p-value:

| Predictor | All 24 shows | 4 shows released 2024 or later |
|---|---|---|
| Qloo age gap | 0.02 (p 0.40) | 0.18 (p 0.22) |
| Qloo taste fit | 0.04 (p 0.29) | -0.27 (p 0.87) |
| obscurity (few Wikipedia views before release) | 0.22 (p 0.003) | 0.48 (p 0.03) |

Placebo control (`scripts/test_ripple_controls.py` -> `ripple_controls.json`): the same ratio measured entirely before release (days -60..-8 over days -120..-68), when the show cannot have caused anything. A predictor that also "predicts" the placebo is picking up regression to the mean, because the spike is a ratio over the same pre-release baseline that obscurity measures.

| | Real spike, all / 2024+ | Placebo spike, all / 2024+ |
|---|---|---|
| obscurity | 0.22 / 0.48 | 0.11 / 0.01 |
| Qloo age gap | 0.02 / 0.18 | -0.13 / -0.20 |

What this says: no Qloo signal predicts which soundtrack songs spike on this data. The age gap points the right way (real above placebo) but is not significant (real minus placebo p 0.14 on all shows, 0.15 on the 4 recent ones), and taste fit predicts nothing. Holding obscurity fixed, the age gap's partial correlation on the 4 recent shows is 0.42 (permutation p 0.07): suggestive, from 4 shows, not significant. Obscurity sits further above its placebo here than in the earlier data (0.22 against 0.11 on all shows), so part of its effect may be real attention from the show; we did not test that difference for significance.

**Qloo against an LLM** (`scripts/experiment_kits.py` -> `kit_experiment.json`, pre-registered in `docs/EXPERIMENT_KITS.md` on 27 Oct before any LLM answer existed). Same 81 title-country pairs, four arms (Qloo and Gemini `gemini-3.5-flash`, each with and without the title), scored by name overlap with no LLM judge.

| | Qloo | LLM |
|---|---|---|
| Title-specificity, all 81 pairs (primary) | 0.617 | 0.812 |
| Title-specificity, the 51 pairs where the LLM's picks resolve in Qloo | 0.575 | 0.831 |
| Cross-title distinctness, 62 title pairs (secondary) | 0.852 | 0.804 |

By the registered rule the LLM is more title-specific (paired difference -0.195, one-sided permutation p below 0.001 in the LLM's favour). This is the result we said we would report whichever way it landed, and it went against Qloo. Two things qualify it without reversing it: only 66% of the LLM's 1,620 picks resolve to a Qloo entity of the right type (the same 66% as the 1,067 of 1,615 names Qloo knows in the grounded check below; the rest may be real names Qloo lacks, or not audience taste at all, such as the title's own cast), and the LLM still leads when only resolving picks count. Qloo's lists differ more between titles in the same country, a secondary metric with no registered test. What we changed: nothing in the product claims a kit beats an LLM; each kit is compared with Qloo's country-only answer and the 33 of 81 that mostly match it are labelled countrywide on the storm page.

**The LLM proposes, Qloo grounds** (`scripts/measure_grounded_plan.py` -> `grounded_plan.json`; **exploratory, not pre-registered**: designed after the result above, on the same 81 pairs and the same cached Gemini answers, so it describes the idea and does not confirm it). The storm page's "AI plan, checked by Qloo" block (`aftershock/grounded_plan.py`) resolves each LLM-proposed name to a Qloo entity by exact name, then asks Qloo, in one filtered insights call per domain, which of them it places with this title's audience in this country. 1,615 proposed names (5 of the 1,620 were duplicates or unusable):

| Verdict | Share of the LLM's picks |
|---|---|
| Confirmed: Qloo places it with this audience | 28.6% (462) |
| Not placed: Qloo knows it, does not place it with this audience here | 37.5% (605) |
| Not in Qloo: no exact-name entity | 33.9% (548) |

| Mean title-specificity, 79 pairs where all three can be scored | |
|---|---|
| Qloo's own kit | 0.607 |
| The LLM's picks, all of them | 0.812 |
| The LLM's picks, confirmed only | 0.862 |

Of the 462 confirmed names, 47 were also in Qloo's own top-5 kit and 415 were not: about 5 per pair that the LLM adds and Qloo vouches for. Caveats: confirmed names carry Qloo's spelling while the control is the LLM's country-only list, and a smaller set can overlap less by chance, so 0.862 against 0.812 is not a clean comparison; "confirmed" means Qloo places the entity with this audience, not that the pick is good (no outcome data tests either); Qloo's kit here is scored against Qloo's country-only kit, so its 0.607 is on 79 pairs rather than the registered 81 (0.617). The measurement used 296 live Qloo calls and no new Gemini calls.

How we got here, for the record: an earlier version of this test used placement lists collected from Tunefind and showed a significant age-gap effect on releases from 2024 on. We then found that Tunefind's terms do not permit automated collection, discarded that data and everything computed from it, and rebuilt the ground truth from MusicBrainz (CC0). The effect did not replicate. The song score is therefore shown as an explorer, not a predictor, and nothing in the product claims otherwise.

## 4. The ledger

`ledger/forecasts.jsonl` holds one line per forecast, each chained to the previous line's hash (`aftershock.ledger.verify()` checks the chain). For each breakout, every candidate country's probability is locked, not only the top rows, so AUC and calibration can be graded once its 4-week horizon passes. A RIPPLE forecast is locked only before the release's outcome window opens (release + 7 days) and only if at least 4 songs are scorable; releases found later are shown as an early read with the reason they were not locked. The chain proves the file was not edited line by line; the public timestamp comes from the git history on GitHub. Before its first push the ledger was rebuilt twice, after a scoring bug fix and after the locking rules above were tightened.

**Early read, defined before the data.** Each week, for every locked breakout, its single top forecast country is checked against Netflix's newest data: how many have already charted, against the number calibrated forecasts would expect and against a naive "busiest country" baseline (`docs/EARLY_GRADE.md`, committed and pushed to this public repo before the week of 25 Oct was published; "registered" here means that public commit, not an external registry). The full four-week grade lands on 15 Nov 2026.

## 5. Run it

You need Python 3.12 and, for anything that calls Qloo, a Qloo API key (hackathon keys come from Qloo's form linked on the hackathon page). Nothing Qloo-derived is committed, so a fresh clone has no forecasts or site data until the weekly job has run once.

```bash
python -m venv .venv
# Windows: .venv\Scripts\python   macOS/Linux: .venv/bin/python   (written as "python" below)
python -m pip install -r requirements-dev.txt
python -m pytest -q                        # no key, no network: fixtures and fakes; tests needing local data skip
cp .env.example .env                       # Windows PowerShell: Copy-Item .env.example .env; then set QLOO_API_KEY
python scripts/run_forecasts.py            # downloads Netflix's TSV, forecasts, locks new forecasts, builds kits, hotspots and the title index
python scripts/export_static.py            # writes the read-only site data to public/data/
python -m uvicorn aftershock.api:app --port 8000   # site and API on http://127.0.0.1:8000
```

A first `run_forecasts.py` takes 15 to 30 minutes: about 700 Qloo calls (paced at 4 per second) and up to about 150 OpenStreetMap lookups (1 per second); later runs reuse the disk cache in `.cache/`. `scripts/backtest_spillover.py` needs no key but reads the Netflix file that `run_forecasts.py` downloads to `data/raw/`. The research scripts (`test_ripple*.py`, `test_spillover_qloo.py`, `experiment_kits.py`) also need the key, and `experiment_kits.py` a `GEMINI_API_KEY`.

From an agent: `aftershock/mcp_server.py` is an MCP server (stdio) with ten tools, `list_storms`, `spillover_forecast`, `launch_kit`, `launch_brief`, `artist_opportunities`, `ripple_score`, `sync_scout`, `release_plan`, `netflix_history` and `ask` (the same plain-question router as the site). It reads the weekly run's output, so run `run_forecasts.py` first. In Claude Desktop's config:

```json
{ "mcpServers": { "aftershock": { "command": "<repo>/.venv/bin/python", "args": ["-m", "aftershock.mcp_server"], "cwd": "<repo>" } } }
```

The Qloo key stays in that process's environment. `tests/test_mcp_stdio.py` checks the server with a real MCP client.

Automation: `.github/workflows/tests.yml` runs the tests on every push; `.github/workflows/forecast.yml` ran the forecast job every Tuesday and committed the ledger (it needs the `QLOO_API_KEY` repo secret); it is disabled until Netflix permits reading its files. The site is a static front end plus one Python function on Vercel: run `scripts/export_static.py`, then `vercel deploy --prod` from a linked project.

Accessibility, checked on the live site on 28 Oct 2026: axe-core 4.9.1 reports 0 violations of any severity on all eight pages in light and dark mode, including the home page with an Ask answer and a map country open; every control is reachable by keyboard in reading order with a visible focus ring; answers appear in polite live regions so screen readers announce them; the map has keyboard buttons and a text list of its top countries; `prefers-reduced-motion` stops the animations.

API contract: `docs/API.md`.

### Data and terms

Netflix publishes its weekly Top 10 lists on its Top 10 site, with download links for the files. We read the per-country file each week and credit Netflix; on 29 Oct 2026 we stopped every automated download until we have Netflix's permission. We have not asked Netflix for permission, and nothing here means Netflix approves of, endorses or is connected with AFTERSHOCK. Netflix's Terms of Use (section 1.8) restrict reproducing information from the Netflix service, automated access and data extraction, and use in connection with machine learning; whether they cover the public Top 10 files is not something we can settle, so this is a hackathon prototype, and any use beyond it would need Netflix's permission first. Beyond Netflix: pageviews come from the Wikimedia API; soundtrack songs from MusicBrainz (CC0); place names from OpenStreetMap Nominatim. Raw Qloo responses are cached on the runner or locally and are never committed or served. Qloo is used under the hackathon key. Git history before 27 Oct 2026 still contains placement CSVs that were collected from Tunefind; they were removed from the current tree once their terms were read, and nothing in the product uses them.

## 6. Limits: what the results do not establish

- Titles that launch worldwide on day one are not breakouts, so AFTERSHOCK would not have flagged Stranger Things 4 or Wednesday.
- The warning is about a week: it suits quick-turn activations, playlist pushes and local ads, not tours, which are booked months ahead.
- The country forecast is Netflix history only; kits and activation ideas are not yet validated against outcomes; grading of the locked forecasts is paused until Netflix permits reading its newer files.
- The country probability uses no Qloo data (Qloo added no lift in our test); Qloo's role there is the launch kit, which we have not validated against outcomes.
- No Qloo signal we tested predicts which soundtrack songs spike (section 3). Sync Scout and the song score are discovery tools, not forecasts.
- Many 2026 titles and new artists have no Qloo audience profile yet.
- Wikipedia pageviews measure attention to an article, not streams or sales, and only notable songs and artists have one.
- Placements are songs on official soundtrack albums (MusicBrainz), which can include songs a show barely used.
- Qloo describes the taste of groups, never of a person. No personal data is sent to Qloo, and Qloo responses are cached privately (`.cache/`, and the deployment's bundled data), never committed.
