# AFTERSHOCK

[![tests](https://github.com/zaidwhy/aftershock/actions/workflows/tests.yml/badge.svg)](https://github.com/zaidwhy/aftershock/actions/workflows/tests.yml) [live site](https://aftershock-qloo.vercel.app) · [public ledger](https://aftershock-qloo.vercel.app/#/ledger) · [pre-registered experiments](docs/EXPERIMENT_KITS.md)

**A Qloo taste agent for breakout shows: where a show lands next, and what travels with it.**

Every week AFTERSHOCK reads Netflix's public per-country Top 10 and finds titles that just broke out in one to three countries. Netflix history says where each is likely to chart next. Qloo's taste graph says what to do there: in each forecast country, the artists, shows, films and brands that title's audience over-indexes on (the launch kit) and the cities where that audience concentrates (Hotspots). Sync Scout uses Qloo to find on-taste artists whose audience sits outside a show's own age groups, for a music supervisor. Every forecast goes into a hash-chained ledger graded against later public data: Netflix's weekly charts and Wikipedia's daily pageviews.

The inspiration: in 2022 Stranger Things 4 put Kate Bush's 1985 "Running Up That Hill" in front of a new, younger audience, and its English Wikipedia page went from about 10,000 views a month to 909,926 in June 2022 (`data/public/replays.json`). We wanted to know whether that kind of jump can be seen coming, and we report what we found, including where it cannot.

Built for the [Qloo Agentic Hackathon](https://qloo.devpost.com/), October 2026. MIT licensed.

## 1. The problem

Distributors, dubbing studios, music publishers and catalog owners react to breakouts after the fact. Netflix sees its own viewing data; they do not. AFTERSHOCK gives them a forecast with its evidence attached, local partners from Qloo, and a public record of how good those forecasts have been.

## 2. The models and the Qloo calls

**SPILLOVER (countries).** For a title that broke out in countries A, the probability that country B charts it within four weeks is how often B followed past breakouts that started in A, smoothed toward B's rate for the same category, which is smoothed toward B's overall rate (`aftershock/netflix.py`). Qloo's job here is the partners list: `GET /v2/insights?filter.type=urn:entity:artist&signal.interests.entities=<title>&signal.location.query=<country>`, the artists the title's audience over-indexes on in each forecast country.

**Launch kit (what to do there).** For each storm's top three forecast countries, the same call is repeated for `urn:entity:tv_show`, `urn:entity:movie` and `urn:entity:brand` (four calls per country, about 330 added calls per weekly run), giving up to five names per domain in Qloo's order (`aftershock/launch_kit.py`). We probed seven domains and kept the four that were title-specific and local; podcasts (identical across titles), books and places (from other countries) were dropped, see `data/results/launch_kit_probe.json`. Like partners, the kit does not change the probabilities.

**Is the kit about the title? (country-only control).** For each kit country the same four calls are made once more without the title signal, giving what the whole country over-indexes on. A kit's specificity is the mean over domains of 1 minus the Jaccard overlap with that control; at 0.4 or below (overlap 0.6 or more, the threshold registered in `docs/EXPERIMENT_KITS.md`) the kit is labelled "mostly countrywide taste", otherwise "title-specific", and names that are also in the control are greyed out on the page. In the week of 18 Oct, 48 of 81 kits were title-specific (mean specificity 0.62); thin titles such as stand-up specials fall back to the country's general taste.

**Hotspots (which cities).** For the same three countries, one `GET /v2/insights?filter.type=urn:heatmap&signal.interests.entities=<title>&filter.location.query=<country>` call returns about 1,800 geohash cells with an affinity rank; the top 120 are kept as `[lat, lon, weight]`. The three strongest cells that are at least 60 km apart are named by reverse geocoding with OpenStreetMap Nominatim (one request per second, cached under `.cache/nominatim/`, at most eight tries per country), so a promo or touring team sees where in the country to start (`aftershock/hotspots.py`). If either call fails the storm keeps whatever was gathered. Place names are © OpenStreetMap contributors.

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

Every number here comes from a script in this repo and a file in `data/results/`.

**SPILLOVER** (`scripts/backtest_spillover.py` -> `spillover_backtest.json`; 8,696 training and 829 test breakouts, March to October 2026, 4-week horizon):

| Model | ROC AUC | Top-5 precision |
|---|---|---|
| Netflix history | 0.817 | 0.041 |
| Each country's general rate | 0.558 | 0.015 |
| Uniform | 0.500 | 0.012 |

Does Qloo help? `scripts/test_spillover_qloo.py` added each title's location-conditioned Qloo affinity as features on a 200-breakout subset (1,432 Qloo calls): AUC 0.8188 history-only vs 0.8182 with Qloo, so no lift. Qloo returned an in-country value for only about 1.8% of title-country pairs. The country forecast is therefore history-only.

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

What this says: no Qloo signal predicts which soundtrack songs spike on this data. The age gap points the right way (real above placebo) but is not significant (real minus placebo p 0.14 on all shows, 0.15 on the 4 recent ones), and taste fit predicts nothing. Obscurity does beat its placebo here, so part of its effect may be real attention from the show, not only regression to the mean.

How we got here, for the record: an earlier version of this test used placement lists collected from Tunefind and showed a significant age-gap effect on releases from 2024 on. We then found that Tunefind's terms do not permit automated collection, discarded that data and everything computed from it, and rebuilt the ground truth from MusicBrainz (CC0). The effect did not replicate. The song score is therefore shown as an explorer, not a predictor, and nothing in the product claims otherwise.

## 4. The ledger

`ledger/forecasts.jsonl` holds one line per forecast, each chained to the previous line's hash (`aftershock.ledger.verify()` checks the chain). For each breakout, every candidate country's probability is locked, not only the top rows, so AUC and calibration can be graded once its 4-week horizon passes. A RIPPLE forecast is locked only before the release's outcome window opens (release + 7 days) and only if at least 4 songs are scorable; releases found later are shown as an early read with the reason they were not locked. The chain proves the file was not edited line by line; the public timestamp comes from the git history on GitHub. Before its first push the ledger was rebuilt twice, after a scoring bug fix and after the locking rules above were tightened.

**Early read, defined before the data.** Each week, for every locked breakout, its single top forecast country is checked against Netflix's newest data: how many have already charted, against the number calibrated forecasts would expect and against a naive "busiest country" baseline (`docs/EARLY_GRADE.md`, committed and pushed before the week of 25 Oct was published). The full four-week grade lands on 15 Nov 2026.

## 5. Run it

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt      # macOS/Linux: .venv/bin/python
cp .env.example .env    # then put your Qloo hackathon key after QLOO_API_KEY=
.venv/Scripts/python scripts/probe.py                 # 25 calls: checks the API returns what the models need
.venv/Scripts/python scripts/backtest_spillover.py    # no key needed
.venv/Scripts/python scripts/run_forecasts.py         # refresh Netflix data, forecast, lock, grade
.venv/Scripts/python -m uvicorn aftershock.api:app --port 8000   # site and API on http://127.0.0.1:8000
.venv/Scripts/python -m pytest -q
```

From an agent: `aftershock/mcp_server.py` is an MCP server (stdio) with seven tools, `list_storms`, `spillover_forecast`, `launch_kit`, `ripple_score`, `sync_scout`, `netflix_history` and `ask` (the same plain-question router as the site). Add it to Claude Desktop or Claude Code with the command `.venv/Scripts/python -m aftershock.mcp_server`, run from the repo folder. The Qloo key stays in that process's environment.

Automation: `.github/workflows/forecast.yml` runs the forecast job every Tuesday after Netflix publishes and commits the ledger (it needs the `QLOO_API_KEY` repo secret). Read-only pages are served as static JSON: run `scripts/export_static.py` before `vercel deploy --prod`.

API contract: `docs/API.md`.

### Data and terms

Netflix Top 10 is Netflix's public weekly TSV; pageviews come from the Wikimedia API; soundtrack songs from MusicBrainz (CC0); place names from OpenStreetMap Nominatim. Raw Qloo responses are cached on the runner or locally and are never committed or served. Qloo is used under the hackathon key. AFTERSHOCK is not affiliated with Netflix or Qloo. Git history before 27 Oct 2026 still contains placement CSVs that were collected from Tunefind; they were removed from the current tree once their terms were read, and nothing in the product uses them.

## 6. Limits: what the results do not establish

- The country probability uses no Qloo data (Qloo added no lift in our test); Qloo's role there is the launch kit, which we have not validated against outcomes.
- No Qloo signal we tested predicts which soundtrack songs spike (section 3). Sync Scout and the song score are discovery tools, not forecasts.
- Many 2026 titles and new artists have no Qloo audience profile yet.
- Wikipedia pageviews measure attention to an article, not streams or sales, and only notable songs and artists have one.
- Placements are songs on official soundtrack albums (MusicBrainz), which can include songs a show barely used.
- Qloo describes the taste of groups, never of a person. No personal data is sent to Qloo, and Qloo responses are cached privately (`.cache/`, and the deployment's bundled data), never committed.
