# Deployment

AFTERSHOCK is a static front end plus one Python function on Vercel. Live at
https://aftershock-qloo.vercel.app (checked 2026-11-13 with `curl -sI -L`: HTTP 200, page title
"AFTERSHOCK - Shows travel. See where next."; `/health` returns `{"status":"ok",...}`).

| Item | Value |
|---|---|
| Provider | Vercel (personal account, scope `syzayds-projects` per `HANDOFF.md`) |
| Config | `vercel.json`, `.vercelignore`, `requirements.txt` |
| Entry point | `api/index.py`, which wraps `aftershock.api:app` (FastAPI) |
| Function limits | `maxDuration` 60 s; bundles `aftershock/**`, `data/private/**`, `data/public/**` |
| Static site | `public/` (vanilla JS, vendored globe.gl); `public/data/` is generated, gitignored |
| Runtime pins | `fastapi==0.162.0`, `httpx==0.28.1`, `python-dotenv==1.1.1` |

## Secrets

Names only; values live in the Vercel project environment and a local `.env` (gitignored,
shape in `.env.example`).

| Name | Needed by | If missing |
|---|---|---|
| `QLOO_API_KEY` | live Qloo calls: `/api/ripple`, `/api/scout`, `/api/check`, `/api/release`, weekly run | precomputed pages render; live features show a sentence (kill-switch test in the suite) |
| `QLOO_BASE_URL` | optional override, default `https://hackathon.api.qloo.com` | default used |
| `GEMINI_API_KEY` | research script `scripts/experiment_kits.py` and AI proposals and brief summaries in the weekly run | the AI plan step is skipped and launch briefs keep the template summary (`grounded_plan.py`, `launch_brief.py`) |

The weekly GitHub Action also reads the repository secret `QLOO_API_KEY`.

## First deploy

1. `python -m venv .venv` and `python -m pip install -r requirements-dev.txt`; `python -m pytest -q` (436 tests, no key needed).
2. Set `QLOO_API_KEY` in `.env`, then `python scripts/run_forecasts.py` (15 to 30 minutes on a cold cache).
3. `python scripts/build_metro_names.py` (city names), `python scripts/build_release_showcases.py` (Plan a release examples, cached), then `python scripts/export_static.py` to write `public/data/`.
4. From a linked project: `vercel deploy --prod --yes --scope <scope>`. The first deploy of a Vercel project is production.
5. Set the two secrets above in the Vercel project, redeploy, and check `/health` and the home page.

`data/private/` and `public/data/` hold Qloo-derived data. They are gitignored and ship only
inside the deployment bundle; never commit them.

## Rollback

Vercel keeps previous deployments: promote an earlier one from the dashboard
(`vercel rollback` also works from a linked project). The ledger is append-only in git; a bad
weekly commit is reverted with a normal `git revert`, never a rewrite, because the hash chain
(`aftershock.ledger.verify()`) must stay intact.

## Automation

- `.github/workflows/tests.yml`: pytest on every push and pull request, Python 3.12, no keys.
- `.github/workflows/forecast.yml` (`weekly-forecast`): Tuesdays 22:00 UTC, runs the forecast and commits `ledger/forecasts.jsonl`. State on 2026-11-13: `disabled_manually` (`gh workflow list --all`), paused since 2026-10-29 until Netflix permits reading its files.

## Free-tier caveats

- Cold starts: a live Qloo call on a cold function took 14 to 32 s (`HANDOFF.md`, 28 Oct); `maxDuration` is 60 s.
- Live endpoints share a limiter: 10 live scorings per visitor per hour and 300 per server process per day (`aftershock/api.py`); the daily counter resets when the process does.
- Qloo calls use the hackathon key, which Qloo's Discord said stays live to 16 Nov 2026 (`HANDOFF.md`). After that the live features degrade to a sentence.
- The Vercel function bundle includes `data/private/**`, so its size grows with the weekly run's output.
