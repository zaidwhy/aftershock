# AFTERSHOCK

**When a show breaks out, where does it go next, and which songs does it drag into the spotlight?**

AFTERSHOCK watches Netflix's public Top 10 for titles that just broke out in one to three countries. It forecasts the countries each title charts in next, and scores the songs placed in a show for how likely they are to spike. Every forecast is locked in a hash-chained public ledger before its outcome exists, then graded against Netflix's next weekly chart and Wikipedia's daily pageviews.

The thesis: a placed song spikes when a show puts it in front of an audience that would like it but does not know it yet. In 2022 Stranger Things 4 put Kate Bush's 1985 "Running Up That Hill" in front of viewers aged 24 and under; its English Wikipedia page went from about 10,000 views a month to 909,926 in June 2022. Qloo can measure both halves of that sentence: how much a show's audience likes an artist (cross-domain affinity), and which age bands each audience over-indexes on (demographics).

Built for the [Qloo Agentic Hackathon](https://qloo.devpost.com/), October 2026. MIT licensed.

## 1. The problem

Distributors, dubbing studios, music publishers and catalog owners all react to breakouts after the fact. A show trends in Japan and the decision about where to push it next is made on gut feel; a 40-year-old song gets placed in a hit and the label notices when the charts already moved. Netflix sees its own data; nobody else does. AFTERSHOCK gives them a forecast with its evidence attached, and a public record of how good those forecasts have been.

## 2. The Qloo workflow, and why

| Step | Qloo call | Why |
|---|---|---|
| Resolve a show, film or artist | `GET /search` with `types`, then an exact-name check | `/search` always returns its nearest match, even for names it does not know, so an unchecked first hit is not a resolution |
| Who the show's audience is | `GET /v2/insights?filter.type=urn:demographics&signal.interests.entities=<show>` | age-band over-index of the audience |
| Who each artist's audience is | same, with the artist as the signal | the age gap between the two audiences is the "does not know it yet" half |
| Would the show's audience like the artist | `GET /v2/insights?filter.type=urn:entity:artist&signal.interests.entities=<show>&filter.results.entities=<artists>` | cross-domain affinity, the "would like it" half; compared within one show because Qloo rescales affinity per response |
| Who to work with in each forecast country | `GET /v2/insights?filter.type=urn:entity:artist&signal.interests.entities=<title>&signal.location.query=<country>` | local artists the title's audience over-indexes on |

RIPPLE score = taste fit x age gap, both in [0, 1] (`aftershock/ripple.py`).

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

**RIPPLE** (`scripts/test_ripple.py`, 516 real placements from 44 titles collected with source URLs in `data/placements.csv`; 105 songs in 17 shows have a Wikipedia article and at least 4 scored songs). Spike = mean daily views in days +7..+35 after release over days -60..-8 before. Mean within-show Spearman between predictor and log spike, one-sided permutation p-value:

| Predictor | All 17 shows | 8 shows released 2024 or later |
|---|---|---|
| fit x age gap | 0.11 (p 0.18) | 0.28 (p 0.053) |
| Qloo fit alone | 0.17 (p 0.08) | 0.12 |
| how obscure the song was | 0.15 | 0.16 |
| random | -0.04 | -0.06 |

This is not proof. The samples are small, and backtests on past spikes are contaminated by the spikes themselves: Qloo's data is a current snapshot, so after Stranger Things made Kate Bush popular with young viewers, her measured age gap shrank and her measured fit grew. Within Stranger Things 4 she has the highest fit of every placed song (0.925) but a below-average gap. The leak pushes the two halves of the score in opposite directions, so only forecasts made before release can test the idea fairly. That is what the ledger is for.

## 4. Request to result, one example

Input: Stranger Things, five placed songs.
1. `/search?query=Stranger Things&types=urn:entity:tv_show` returns entity `07F1170E-...`; the name matches exactly.
2. Demographics for the show: 24 and under +0.71, 25-29 +0.45, 35-44 -0.62.
3. Demographics for Kate Bush: 24 and under +0.03, 45-54 +0.34.
4. Artist affinity with the show as the signal: Kate Bush 0.925, The Clash 0.846, Metallica 0.768.
5. Age gap = (1 - familiarity) / 2, where familiarity is the artist's over-index weighted by the show's positive bands; score = fit x gap.

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

- Qloo describes the taste of groups, never of a person. No personal data is sent to Qloo.
- A probability is not a promise: a 20% forecast that misses was not wrong.
- Backtests use today's Qloo data on past events, so they can be optimistic (fit) or pessimistic (age gap). The live ledger is the real test.
- Wikipedia pageviews measure attention to a song's article, not streams or sales, and only notable songs have an article.
- Song placements come from Tunefind and Wikipedia pages; a placement the source lists but the show cut would add noise.
- Qloo response data is never committed to this repo: responses are cached privately under `.cache/` and in the deployment only.
