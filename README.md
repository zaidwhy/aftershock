# AFTERSHOCK

[![tests](https://github.com/zaidwhy/aftershock/actions/workflows/tests.yml/badge.svg)](https://github.com/zaidwhy/aftershock/actions/workflows/tests.yml)

An AI's launch plan sounds specific and cannot be audited. AFTERSHOCK forecasts which country a
Netflix title charts in next, from Netflix history alone, then makes the AI's launch partners
earn their place: every suggested name is checked against Qloo's audience data for that title in
that country, and the names Qloo cannot support are struck out with the reason. Every forecast is
locked in a hash-chained ledger before its outcome exists.

It is for labels, music publishers, promoters, brands, local distributors and dubbing studios
who react to a breakout after the fact because Netflix sees its viewing data and they do not.
Built for the [Qloo Agentic Hackathon](https://qloo.devpost.com/), October 2026.

- Live site (no login): https://aftershock-qloo.vercel.app, checked 2026-11-13 with `curl -sI -L`
  (HTTP 200, the AFTERSHOCK page). It shows the last weekly run, week of 2026-10-18.
- [2-minute demo video](https://youtu.be/99EfYU-mKl0)

```bash
python -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt   # Windows: .venv\Scripts\python
python -m pytest -q                              # no key, no network
cp .env.example .env                             # then set QLOO_API_KEY for anything that calls Qloo
python scripts/run_forecasts.py && python scripts/export_static.py
python -m uvicorn aftershock.api:app --port 8000
```

A fresh clone has no forecasts: nothing Qloo-derived is committed. More in
[`docs/RUN.md`](docs/RUN.md), including the MCP server with ten tools.

## What it does, in a fixed order

The agent follows a fixed plan instead of letting the LLM choose steps. An LLM that picks its
own tools can skip the Qloo check or explain a step it never ran, and nobody can tell afterwards.
The LLM proposes names and drafts the summary inside the order; every decision is a rule printed
next to the step it changed.

| Step | What happens | Source |
|---|---|---|
| 1. Forecast | probability that country B charts the title within 4 weeks, from how often B followed past breakouts that started in A | Netflix weekly Top 10 history |
| 2. Qloo kit | what the title's audience over-indexes on in each top-3 forecast country, checked against the country's general taste | Qloo `/v2/insights` |
| 3. AI proposals | an LLM suggests more partners | Gemini |
| 4. Qloo check | each name kept only if Qloo places it with that audience there; the rest are struck through | Qloo `/v2/insights` |
| 5. Cities | where the audience concentrates, named by metro | Qloo heatmap, OpenStreetMap |
| 6. Brief | where, which cities, which partners, what the evidence does not support | rules plus LLM summary |

Also on the site: a live name check, Plan a release, a song check (RIPPLE), Sync Scout and a
public scorecard. Models and every Qloo call: [`docs/MODELS.md`](docs/MODELS.md).

## Measured

Backtests use Netflix data through the week of 2026-10-18; each number comes from a script in
`scripts/` and a file in `data/results/`. Full tables and caveats: [`docs/RESULTS.md`](docs/RESULTS.md).

| Question | Result |
|---|---|
| Does the country forecast rank well? (829 held-out breakouts, 4-week horizon) | ROC AUC 0.817 against 0.558 for each country's general rate |
| Does it name the next country? | its top 3 hit for 81 of 829 breakouts (9.8%) against 34 (4.1%) for the busiest-country baseline; only 113 of 829 charted elsewhere at all |
| How much warning? | median 1 week |
| Does Qloo improve the country forecast? | no: AUC 0.8188 history-only vs 0.8182 with Qloo (200-breakout subset) |
| Is Qloo's kit more title-specific than an LLM's? (pre-registered, 81 title-country pairs) | no: 0.617 for Qloo, 0.812 for the LLM; reported as it landed |
| How much of an LLM's partner list does Qloo back? (1,615 names, exploratory) | 28.6% confirmed, 37.5% known but not placed, 33.9% not in Qloo |
| Does any Qloo signal predict soundtrack-song spikes? (490 songs, 24 shows) | no: age gap 0.02 (p 0.40) |

The ledger holds 3,240 spillover forecasts (`ledger/forecasts.jsonl`); `aftershock.ledger.verify()`
returned `None` (chain intact) on 2026-11-13. None is graded yet: the live `/api/scorecard`
shows `graded: 0`. The public timestamp comes from the git history on GitHub.

## Architecture

A FastAPI app (`aftershock/api.py`, entry `api/index.py` on Vercel) serves a vanilla-JS front end
with a three.js globe from `public/`. A weekly script (`scripts/run_forecasts.py`) reads Netflix's
per-country Top 10, forecasts, calls Qloo and Gemini, and writes data that `export_static.py`
turns into read-only files the site loads; live endpoints call Qloo on demand behind a shared
limiter. `aftershock/mcp_server.py` exposes the same data to an agent.

| Part | Where |
|---|---|
| Spillover model | `aftershock/netflix.py` |
| Launch kit, cities, events | `launch_kit.py`, `hotspots.py`, `metro_names.py`, `live_events.py` |
| AI plan and checks | `grounded_plan.py`, `llm_kits.py`, `launch_brief.py` |
| Song check, Sync Scout | `ripple.py`, `sync_scout.py` |
| Ledger | `ledger.py`, `ledger/forecasts.jsonl` |
| API contract | [`docs/API.md`](docs/API.md) |

Deployment, secrets and rollback: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Tests

`python -m pytest -q`: 436 passed (run 2026-11-13, Windows 11, Python 3.12). Fixtures and fakes
only, no keys; tests that need local data skip. CI runs the same command on every push.

## Status

Hackathon prototype, last commit 2026-10-30. The weekly run and the grading of locked
forecasts are paused: the `weekly-forecast` workflow is `disabled_manually` (checked 2026-11-13)
until Netflix permits reading its files. The live Qloo features depend on the hackathon key.
Deployed state of the latest commit was not verified.

## Data and terms

Netflix publishes its weekly Top 10 lists on its Top 10 site, with download links for the files. We read the per-country file each week and credit Netflix; on 29 Oct 2026 we stopped every automated download until we have Netflix's permission. We have not asked Netflix for permission, and nothing here means Netflix approves of, endorses or is connected with AFTERSHOCK. Netflix's Terms of Use (section 1.8) restrict reproducing information from the Netflix service, automated access and data extraction, and use in connection with machine learning; whether they cover the public Top 10 files is not something we can settle, so this is a hackathon prototype, and any use beyond it would need Netflix's permission first. Beyond Netflix: pageviews come from the Wikimedia API; soundtrack songs from MusicBrainz (CC0); place names from OpenStreetMap Nominatim (© OpenStreetMap contributors). Raw Qloo responses are cached on the runner or locally and are never committed or served. Qloo is used under the hackathon key. Git history before 27 Oct 2026 still contains placement CSVs that were collected from Tunefind; they were removed from the current tree once their terms were read, and nothing in the product uses them.

## Limits

- Titles that launch worldwide on day one are not breakouts, so AFTERSHOCK would not have flagged Stranger Things 4 or Wednesday.
- The warning is about a week: it suits quick-turn activations, playlist pushes and local ads, not tours, which are booked months ahead.
- The country forecast is Netflix history only; kits and activation ideas are not yet validated against outcomes.
- No Qloo signal tested predicts which soundtrack songs spike. Sync Scout and the song score are discovery tools, not forecasts.
- Many 2026 titles and new artists have no Qloo audience profile yet.
- Wikipedia pageviews measure attention to an article, not streams or sales, and only notable songs and artists have one.
- Placements are songs on official soundtrack albums (MusicBrainz), which can include songs a show barely used.
- Qloo describes the taste of groups, never of a person. No personal data is sent to Qloo.

Other documents: [`docs/EXPERIMENT_KITS.md`](docs/EXPERIMENT_KITS.md) and
[`docs/EARLY_GRADE.md`](docs/EARLY_GRADE.md) (pre-registrations), [`docs/DEVPOST.md`](docs/DEVPOST.md).

MIT licensed, see [`LICENSE`](LICENSE).
