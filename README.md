# AFTERSHOCK

**When a show breaks out, where does it go next, and which of its songs reach a new audience?**

AFTERSHOCK reads Netflix's public per-country Top 10 every week and finds titles that just broke out in one to three countries. For each one it forecasts the countries it charts in next and names, from Qloo, the local artists its audience already loves there. For songs placed in a show, it scores how far each artist's audience sits from the show's audience by age, which is the one Qloo signal that survived our controls for predicting which placed songs spike. Every forecast goes into a hash-chained ledger that is graded against later public data: Netflix's weekly charts and Wikipedia's daily pageviews.

The inspiration: in 2022 Stranger Things 4 put Kate Bush's 1985 "Running Up That Hill" in front of a new, younger audience, and its English Wikipedia page went from about 10,000 views a month to 909,926 in June 2022 (`data/public/replays.json`). We wanted to know whether that kind of jump can be seen coming, and we report what we found, including where it cannot.

Built for the [Qloo Agentic Hackathon](https://qloo.devpost.com/), October 2026. MIT licensed.

## 1. The problem

Distributors, dubbing studios, music publishers and catalog owners react to breakouts after the fact. Netflix sees its own viewing data; they do not. AFTERSHOCK gives them a forecast with its evidence attached, local partners from Qloo, and a public record of how good those forecasts have been.

## 2. The models and the Qloo calls

**SPILLOVER (countries).** For a title that broke out in countries A, the probability that country B charts it within four weeks is how often B followed past breakouts that started in A, smoothed toward B's rate for the same category, which is smoothed toward B's overall rate (`aftershock/netflix.py`). Qloo's job here is the partners list: `GET /v2/insights?filter.type=urn:entity:artist&signal.interests.entities=<title>&signal.location.query=<country>`, the artists the title's audience over-indexes on in each forecast country.

**Launch kit (what to do there).** For each storm's top three forecast countries, the same call is repeated for `urn:entity:tv_show`, `urn:entity:movie` and `urn:entity:brand` (four calls per country, about 330 added calls per weekly run), giving up to five names per domain in Qloo's order (`aftershock/launch_kit.py`). We probed seven domains and kept the four that were title-specific and local; podcasts (identical across titles), books and places (from other countries) were dropped, see `data/results/launch_kit_probe.json`. Like partners, the kit does not change the probabilities.

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

**RIPPLE.** Ground truth: 516 placements from 44 titles collected with source URLs (`data/placements.csv`, reproducible with `scripts/scrape_placements.py`), with Wikipedia spikes in `data/ripple_truth.csv`. Main test (`scripts/test_ripple.py --outcome artist` -> `ripple_test_artist.json`): one row per artist per show, artists without a Qloo audience profile excluded, 195 artists in 24 shows with at least 4 scored artists. Mean within-show Spearman with the log spike, one-sided permutation p-value:

| Predictor | All 24 shows | 9 shows released 2024 or later |
|---|---|---|
| Qloo age gap (shipped) | 0.08 (p 0.16) | 0.28 (p 0.02) |
| Qloo taste fit | 0.00 (p 0.48) | -0.01 (p 0.50) |
| obscurity (few Wikipedia views before release) | 0.27 (p 0.001) | 0.29 (p 0.01) |

Obscurity looks strongest, so we tested whether it is real (`scripts/test_ripple_controls.py` -> `ripple_controls.json`). The spike is a ratio over the pre-release baseline, and obscurity is that same baseline, so a noisy, low baseline can produce a high ratio by itself. The placebo is the same ratio measured entirely before release (days -60..-8 over days -120..-68), when the show cannot have caused anything:

| | Real spike, all / 2024+ | Placebo spike, all / 2024+ |
|---|---|---|
| obscurity | 0.27 / 0.29 | 0.19 / 0.28 |
| Qloo age gap | 0.08 / 0.28 | -0.13 / -0.11 |

Obscurity "predicts" the placebo almost as well as the real thing, so it is mostly regression to the mean; it is shown as context, never scored. The age gap does not predict the placebo, and its real-minus-placebo difference is significant (permutation p 0.04 on all shows, 0.03 on 2024+). Holding obscurity fixed, the gap's partial correlation is 0.06 overall (p 0.28) and 0.20 on 2024+ (p 0.12): directional, not proven. Older releases are weaker for a known reason: Qloo's data is a current snapshot, so a song that already spiked has since gained the younger audience it reached, which shrinks its measured gap.

Choosing the 2024+ subset and the artist-page outcome came after looking at the data, and all of this is in-sample on 24 shows. Read it as evidence for one mechanism, not as a validated model. The ledger is the out-of-sample test.

Worked example (`scripts/example_wednesday.py` -> `example_wednesday.json`): Wednesday Season 1, the five placed songs with a Wikipedia article, scored as of release day 2022-11-23. By age gap: Space Song 0.61, Non, je ne regrette rien 0.57, Physical 0.54, Don't Worry, Be Happy 0.48, In Dreams 0.42. Measured spikes: 4.2x, 2.1x, 1.1x, 0.8x, 1.3x. The top two by gap were the two biggest spikes. That is one show, an illustration rather than evidence.

## 4. The ledger

`ledger/forecasts.jsonl` holds one line per forecast, each chained to the previous line's hash (`aftershock.ledger.verify()` checks the chain). For each breakout, every candidate country's probability is locked, not only the top rows, so AUC and calibration can be graded once its 4-week horizon passes. A RIPPLE forecast is locked only before the release's outcome window opens (release + 7 days) and only if at least 4 songs are scorable; releases found later are shown as an early read with the reason they were not locked. The chain proves the file was not edited line by line; the public timestamp comes from the git history on GitHub. Before its first push the ledger was rebuilt twice, after a scoring bug fix and after the locking rules above were tightened.

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

From an agent: `aftershock/mcp_server.py` is an MCP server (stdio) with three tools, `list_storms`, `spillover_forecast` and `ripple_score`. Add it to Claude Desktop or Claude Code with the command `.venv/Scripts/python -m aftershock.mcp_server`, run from the repo folder. The Qloo key stays in that process's environment.

Weekly automation: `.github/workflows/forecast.yml` runs the forecast job every Tuesday after Netflix publishes and commits the ledger (it needs the `QLOO_API_KEY` repo secret).

API contract: `docs/API.md`.

## 6. Limits: what the results do not establish

- The country forecast uses no Qloo data; Qloo adds the partners, which we have not validated.
- RIPPLE's evidence is in-sample, on 24 shows, with the strongest result in a subset chosen after looking. The gap's effect beyond obscurity is directional, not significant.
- The score does not see how a show uses a song. It would not have picked Running Up That Hill, which was already well known before Stranger Things 4; the spike came from the scene.
- Many 2026 titles and new artists have no Qloo audience profile yet, so live RIPPLE covers fewer songs than the placements list.
- Wikipedia pageviews measure attention to an article, not streams or sales, and only notable songs and artists have one.
- Placements come from Tunefind and Wikipedia; a listed placement that the show cut would add noise.
- Qloo describes the taste of groups, never of a person. No personal data is sent to Qloo, and Qloo responses are cached privately (`.cache/`, and the deployment's bundled data), never committed.
