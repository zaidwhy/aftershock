# CLAUDE.md - aftershock

Hackathon prototype for the Qloo Agentic Hackathon (October 2026): forecasts which country a Netflix title charts in next and checks an AI's launch partners against Qloo audience data. Status: maintained only; weekly runs and grading are paused until Netflix permits reading its files.
Doc of record: `HANDOFF.md` - read it before changing anything (newest entry first).

## Run

| What | Command |
|---|---|
| Activate env | `.venv\Scripts\activate` (Python 3.12) |
| Install | `python -m pip install -r requirements-dev.txt` |
| Run | `python -m uvicorn aftershock.api:app --port 8000` (URL: `http://127.0.0.1:8000`); needs `python scripts/run_forecasts.py` and `python scripts/export_static.py` first |
| Tests | `python -m pytest -q` - expected: `436 passed` |
| Lint / typecheck | n/a (none configured) |
| Build | `python scripts/export_static.py` writes `public/data/` |

## Deploy

- Provider: Vercel (personal account), scope `syzayds-projects`; Zaid runs `vercel deploy --prod --yes --scope syzayds-projects`.
- Config: `vercel.json`, `.vercelignore`, `requirements.txt`; secrets to set (names only): `QLOO_API_KEY`, `GEMINI_API_KEY`; optional `QLOO_BASE_URL`.
- Live URL: https://aftershock-qloo.vercel.app (verified 2026-11-13 with `curl -sI -L`: 200, real page)
- Rollback: promote a previous Vercel deployment. Full notes in `docs/DEPLOYMENT.md`.

## Layout

```
aftershock/   api.py (FastAPI), netflix.py (spillover), launch_kit/hotspots/grounded_plan, ripple.py, ledger.py, mcp_server.py
api/index.py  Vercel entry; vercel.json rewrites /api/* to it
scripts/      weekly run, backtests, experiments, static export
public/       front end (vanilla JS); public/data/ is generated and gitignored
data/results/ committed measurement files; data/private/ is Qloo-derived and gitignored
docs/         README detail: MODELS, RESULTS, RUN, DEPLOYMENT, API, pre-registrations
ledger/forecasts.jsonl   append-only hash chain
```

## Definition of done (for any change here)

- Tests green with the count above (run, not assumed); new logic tested; bug fixes have a reproducing test.
- `aftershock.ledger.verify()` returns `None` after any change near the ledger.
- Docs updated if commands, config or behavior changed (README, docs/, this file).
- Committed with a descriptive message; `git fetch origin` then push; `git status -sb` clean.
- No U+2014, no attribution, no secrets, no invented numbers.

## Gotchas

- `public/data/` and `data/private/` hold Qloo-derived data: never commit them.
- Netflix automated downloads stopped on 2026-10-29; do not re-enable `.github/workflows/forecast.yml` without Zaid.
- Vercel `maxDuration` is 60 s; a cold live Qloo call took 14 to 32 s.

## Do not

- Rewrite or reorder `ledger/forecasts.jsonl`; revert with a new commit, never a rewrite.
- Claim customers, pilots or lift; the forecast uses no Qloo data because Qloo added no lift in the test.
- Use Tunefind data; it was removed after its terms were read.
