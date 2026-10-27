# AFTERSHOCK handoff

Deadline: Devpost, 30 Oct 2026 11:45pm EDT = 31 Oct 09:15 IST. Judges: 2-5 Nov (Discord says keys live to 16 Nov); top 3 present on air 5 Nov.

## Live (27 Oct)

- Repo: https://github.com/zaidwhy/aftershock (public, MIT), `main` pushed; Actions secret `QLOO_API_KEY` set.
- Site: https://aftershock-beige.vercel.app (personal Vercel, project syzayds-projects/aftershock; `aftershock.vercel.app` was taken). `/health` shows `"qloo_key": true`; `/requirements.txt` and `/data/private/*` return 404.
- Git auto-deploy is disconnected on purpose: a git-built deploy would ship without the gitignored `data/private/`. Deploy only with `vercel deploy --prod` from this folder.
- `api/index.py` restores the original path from `__path` (set by the rewrites in vercel.json), because Vercel hands the function `/api/index`.

## Still to do (Zaid)

4. Before judging (after Netflix's 3 Nov update), refresh the live site's data: `.venv/Scripts/python scripts/run_forecasts.py` then `vercel deploy --prod`. The site reads `data/private/storms.json`, which is generated locally and bundled into the deployment, never committed.
5. Review the Devpost draft in `docs/DEVPOST.md` and submit it yourself. Also record the demo video (the kit and Devpost expect one): landing seismograph, a storm page, a Songs to watch page, Try it with Stranger Things + Running Up That Hill | Kate Bush, the scorecard.

## State (overnight, 27 Oct)

See the end of this file for the latest results; everything below is committed locally on `main`.

## Decisions taken overnight (and why)

- SPILLOVER: Qloo in-country affinity added no AUC (0.8188 history vs 0.8182 with Qloo on 200 breakouts; Qloo had a value for 1.8% of pairs). The country forecast is history-only; Qloo supplies the partners list.
- RIPPLE went through three models, each tested before shipping:
  1. taste fit x age gap: did not beat a no-Qloo baseline;
  2. obscurity + age gap: looked best, until an independent review pointed out that obscurity is the spike's own denominator;
  3. a placebo control (spike measured entirely before release) showed obscurity is mostly regression to the mean, while the Qloo age gap tracks the real spike and not the placebo (real minus placebo p 0.03 on 2024+, 0.04 overall). Shipped: score = Qloo age gap. Fit and obscurity are context only.
- Ledger rebuilt twice before any publication (scoring bug fix, then stricter locking rules: every country locked; RIPPLE locks only before release + 7 days with 4+ scorable songs). None of the 12 live releases qualified: all were found after their windows opened, and new 2026 titles mostly lack Qloo audience profiles.
- Stayed with AFTERSHOCK rather than switching to READ THE ROOM: the build exists and the measured honesty is the differentiator.
- No paid LLM. Agentic parts: the weekly job (detect, resolve, forecast, lock, grade) as a GitHub Action, and the MCP server.

## Results (all in data/results/)

- spillover_backtest.json: history AUC 0.817 on 829 test breakouts.
- spillover_qloo_test.json: 0.8188 vs 0.8182 (no Qloo lift).
- ripple_test_artist.json, ripple_controls.json: see README section 3.
- example_wednesday.json: the README's worked example.
- Ledger: 3,240 spillover forecasts (35 breakouts x every candidate country), 0 ripple; chain verifies.

## Known gaps

- Demo video not recorded.
- Early SPILLOVER grades appear once Netflix publishes the week ending 25 Oct; rerun `scripts/run_forecasts.py` then (no new locks are created for already-locked titles).
- The weekly Action commits the ledger but does not refresh the deployed site; redeploy by hand before judging.
- Partners are unvalidated, and odd for some small territories.
- Quota: about 47,900 calls left this month after the backtests; teammates' keys are spares.
