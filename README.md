# AFTERSHOCK

**When a show breaks out, where does it go next, and which songs does it drag into the spotlight?**

AFTERSHOCK watches Netflix's public Top 10 for titles that just broke out in one to three countries. It forecasts the countries each title charts in next, and scores the songs placed in a show for how likely they are to spike. Every forecast is locked in a hash-chained public ledger before its outcome exists, then graded against Netflix's next weekly chart and Wikipedia's daily pageviews.

The thesis: a placed song spikes when a show puts it in front of people who do not know it yet. In 2022 Stranger Things 4 put Kate Bush's 1985 "Running Up That Hill" in front of viewers aged 24 and under; its English Wikipedia page went from about 10,000 views a month to 909,926 in June 2022. Qloo measures who each audience is by age band, so it can say how far a song's audience sits from a show's; Wikipedia says how known the song already was.

Built for the [Qloo Agentic Hackathon](https://qloo.devpost.com/), October 2026. MIT licensed.

## 1. The problem

Distributors, dubbing studios, music publishers and catalog owners all react to breakouts after the fact. A show trends in Japan and the decision about where to push it next is made on gut feel; a 40-year-old song gets placed in a hit and the label notices when the charts already moved. Netflix sees its own data; nobody else does. AFTERSHOCK gives them a forecast with its evidence attached, and a public record of how good those forecasts have been.

## 2. The Qloo workflow, and why

| Step | Qloo call | Why |
|---|---|---|
| Resolve a show, film or artist | `GET /search` with `types`, then an exact-name check | `/search` always returns its nearest match, even for names it does not know, so an unchecked first hit is not a resolution |
| Who the show's audience is | `GET /v2/insights?filter.type=urn:demographics&signal.interests.entities=<show>` | age-band over-index of the audience |
| Who each artist's audience is | same, with the artist as the signal | the age gap between the two audiences |
| Would the show's audience like the artist (tested, context only) | `GET /v2/insights?filter.type=urn:entity:artist&signal.interests.entities=<show>&filter.results.entities=<artists>` | cross-domain affinity; compared within one show because Qloo rescales affinity per response. It did not predict spikes (section 3), so it is shown, not scored |
| Who to work with in each forecast country | `GET /v2/insights?filter.type=urn:entity:artist&signal.interests.entities=<title>&signal.location.query=<country>` | local artists the title's audience over-indexes on |

RIPPLE score = the average of two within-show percentiles: the Qloo age gap between the artist's audience and the show's, and obscurity (the song's mean daily Wikipedia views in the 60 days before release, or its artist's when the song has no article). See `aftershock/ripple.py`.

SPILLOVER probability comes from Netflix history: for a title that broke out in countries A, how often each other country followed past breakouts that started in A, smoothed toward that country's general rate (`aftershock/netflix.py`).

## 3. What we measured, including what did not work

All numbers below come from scripts in this repo; rerun them to reproduce.

**SPILLOVER** (`scripts/backtest_spillover.py`, 8,696 training and 829 test breakouts, March to October 2026, 4-week horizon):

| Model | ROC AUC | Top-5 precision |
|---|---|---|
| Netflix history | 0.817 | 0.041 |
| Each country's general rate | 0.558 | 0.015 |
| Uniform | 0.500 | 0.012 |

We then tested whether Qloo's location-conditioned affinity for the title improves it (`scripts/test_spillover_qloo.py`, 200 test breakouts, 1,432 Qloo calls): AUC 0.8188 without Qloo, 0.8182 with it. Qloo returned an in-country value for only 1.8% of title-country pairs, so it carries almost no signal here. **The country forecast is therefore history-only**, and Qloo is used where it does add something: naming local partners.

**RIPPLE** (`scripts/test_ripple.py`). Ground truth: 516 real placements from 44 titles, each with a source URL (`data/placements.csv`, reproducible with `scripts/scrape_placements.py`). Outcome: the spike of the artist's Wikipedia page (mean daily views on days +7..+35 after release over days -60..-8), one row per artist per show; artists Qloo has no demographic profile for are excluded rather than treated as average. That leaves 195 artists in 24 shows with at least 4 scored artists. Mean within-show Spearman between each predictor and the log spike, with a one-sided permutation p-value (2,000 within-show shuffles):

| Predictor | All 24 shows | 9 shows released 2024 or later | Top pick was the biggest spike (2024+) |
|---|---|---|---|
| obscurity (Wikipedia views before release, no Qloo) | 0.27 (p 0.001) | 0.29 (p 0.01) | 33% |
| Qloo age gap | 0.08 (p 0.16) | 0.28 (p 0.02) | 33% |
| obscurity + Qloo age gap (shipped) | 0.20 (p 0.008) | 0.31 (p 0.007) | 56% |
| Qloo taste fit | 0.00 (p 0.48) | -0.01 (p 0.50) | 0% |

On song pages (96 songs, 15 shows) the shipped score reaches 0.29 on 2024+ releases against 0.16 for obscurity alone (p 0.07); small samples, read as direction, not proof.

What this says: how unknown a song was is the strongest single signal overall. On recent releases Qloo's age gap is as strong as obscurity on its own, and the two together are best; on older releases the gap fades. That split is what contamination predicts: Qloo's data is a current snapshot, so a song that already spiked has since gained a younger audience and now shows a smaller age gap than it had before release (within Stranger Things 4, Kate Bush now has the highest taste fit of any placed song, 0.925, and a below-average gap). Taste fit, the obvious Qloo feature, predicted nothing. The only clean test is a forecast made before release, which is what the ledger is for.

## 4. Request to result, one example

Input: Wednesday (released 2022-11-23) and five songs Tunefind lists as placed in it, scored as of the release date.
1. `/search?query=Wednesday&types=urn:entity:tv_show,urn:entity:movie` returns the show; the name matches exactly.
2. Demographics for the show and for each artist give six age-band over-indexes each; the age gap weights the artist's over-index by the bands the show over-indexes on.
3. Wikipedia: mean daily views of each song's article from 60 to 8 days before release.
4. Scores, highest first: Space Song (Beach House) 1.00, Physical (Dua Lipa) 0.60, Non, je ne regrette rien (Edith Piaf) 0.60, Dream Weaver (Gary Wright) 0.50, Dancing in the Dark (Bruce Springsteen) 0.10.
5. Measured song-page spikes (`data/ripple_truth.csv`): Space Song 4.2x, Non, je ne regrette rien 2.1x, Dream Weaver 1.4x, Physical 1.1x, Dancing in the Dark 1.1x.

## 5. Run it

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt      # macOS/Linux: .venv/bin/python
cp .env.example .env    # then put your Qloo hackathon key after QLOO_API_KEY=
.venv/Scripts/python scripts/probe.py                 # 25 calls: checks the API returns what both models need
.venv/Scripts/python scripts/backtest_spillover.py    # no key needed
.venv/Scripts/python scripts/run_forecasts.py         # refresh Netflix data, forecast, lock, grade
.venv/Scripts/python -m uvicorn aftershock.api:app --port 8000   # site and API on http://127.0.0.1:8000
.venv/Scripts/python -m pytest -q
```

Use it from an agent: `aftershock/mcp_server.py` is an MCP server (stdio) with three tools, `list_storms`, `spillover_forecast` and `ripple_score`. Add it to Claude Desktop or Claude Code with the command `.venv/Scripts/python -m aftershock.mcp_server` run from the repo folder. The Qloo key stays in that process's environment.

API contract: `docs/API.md`. Public ledger: `ledger/forecasts.jsonl` (each line chained to the previous line's hash; `aftershock.ledger.verify()` checks it).

## 6. Limits: what the results do not establish

- The score does not see how a show uses a song. It would not have picked Running Up That Hill: as of Stranger Things 4's release it ties for last of the six songs we tried, because the song already had about 350 Wikipedia views a day; the spike came from the scene, not from obscurity or age. Scene prominence is the next feature.
- Qloo describes the taste of groups, never of a person. No personal data is sent to Qloo.
- A probability is not a promise: a 20% forecast that misses was not wrong.
- Backtests use today's Qloo data on past events, so they can be optimistic (fit) or pessimistic (age gap). The live ledger is the real test.
- Wikipedia pageviews measure attention to a song's article, not streams or sales, and only notable songs have an article.
- Song placements come from Tunefind and Wikipedia pages; a placement the source lists but the show cut would add noise.
- Qloo response data is never committed to this repo: responses are cached privately under `.cache/` and in the deployment only.
