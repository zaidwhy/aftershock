# AFTERSHOCK handoff

Deadline: Devpost, 30 Oct 2026 11:45pm EDT = 31 Oct 09:15 IST. Judges: 2-5 Nov (Discord says keys live to 16 Nov); top 3 present on air 5 Nov.

## Do first in the morning (Zaid)

1. Push the repo before Netflix publishes the next Top 10 (Tuesdays; the 27 Oct release is likely evening IST). The ledger's credibility is its public timestamp. The overnight session could not create the GitHub repo (the permission classifier blocks creating public or private repos without you):
   ```
   ! cd C:/Users/Asus/projects/aftershock && gh repo create zaidwhy/aftershock --public --source . --remote origin --push --description "Forecasts where a breakout show spreads next and which songs it pulls into the spotlight, using Qloo's taste graph."
   ```
   Then check the License shows in the repo's About box (MIT is in LICENSE).
2. Deploy to your personal Vercel (not the Nobero scope). Link first so the first deploy is a preview, set the key, then go to production:
   ```
   ! cd C:/Users/Asus/projects/aftershock && vercel link --yes --project aftershock && vercel env add QLOO_API_KEY production && vercel deploy --prod
   ```
   Then `curl -L https://aftershock.vercel.app/health` must show `"qloo_key": true`, and `/requirements.txt` must 404.
3. Add the repo secret so the weekly job runs: GitHub repo Settings > Secrets > Actions > `QLOO_API_KEY`. Then Actions > weekly-forecast > Run workflow once to check it (it commits the ledger).
4. Before judging (after Netflix's 3 Nov update), refresh the live site's data: `.venv/Scripts/python scripts/run_forecasts.py` then `vercel deploy --prod`. The site reads `data/private/storms.json`, which is generated locally and bundled into the deployment, never committed.
5. Review the Devpost draft in `docs/DEVPOST.md` and submit it yourself. Also record the demo video (the kit and Devpost expect one): landing seismograph, a storm page, a Songs to watch page, Try it with Stranger Things + Running Up That Hill | Kate Bush, the scorecard.

## State (overnight, 27 Oct)

See the end of this file for the latest results; everything below is committed locally on `main`.

## Decisions taken overnight (and why)

- SPILLOVER decision test: Qloo location affinity adds no AUC (0.8188 history vs 0.8182 with Qloo; Qloo had a value for 1.8% of title-country pairs). Per the pre-set rule, the country forecast is history-only and Qloo is used for local partners instead.
- RIPPLE: the first formula (taste fit x age gap) did not beat a no-Qloo obscurity baseline. On the larger artist-level test, fit predicted nothing while the age gap matched obscurity on 2024+ releases, so the shipped score is obscurity + Qloo age gap and fit is context only. Past data is contaminated (Qloo's snapshot postdates the spikes), so the forward ledger is the real test.
- Stayed with AFTERSHOCK rather than switching to READ THE ROOM: the product, data pipeline and ledger exist, the honesty of the measurement is itself the differentiator, and a rebuild in 3 days was the bigger risk.
- No paid LLM. The agentic parts: an autonomous weekly job (detect, resolve, forecast, lock, grade) and an MCP server so Claude and other agents can call the tools.

## Results log

- SPILLOVER backtest (history only): AUC 0.817 on 829 test breakouts (Mar-Oct 2026). Qloo in-country affinity: no lift (0.8188 vs 0.8182 on 200), coverage 1.8%.
- RIPPLE backtest (artist-page outcome, 195 artists, 24 shows): obscurity 0.27 (p .001); on 2024+ releases age gap 0.28 (p .02), obscurity + gap 0.31 (p .007), top pick 56% vs 33%; Qloo fit 0.00. Shipped score = obscurity + age gap.
- Ledger: 350 spillover forecasts (35 breakouts, week ending 2026-10-18) + 10 ripple forecasts (12 new releases, 63 placements; most songs lack Qloo demographics or a Wikipedia page). Ripple locks were made 4-18 days after those releases, from pre-release data only; say so if asked. Clean forward ripple tests are releases after the lock date.
- Rebuilt the ledger once overnight, before any publication, after fixing a bug that scored artists without Qloo demographics as average.
- Live site pieces verified locally (uvicorn on 127.0.0.1:8791): landing, storm, ripple, try, scorecard; 19 tests pass; craft-guard clean.

## Known gaps

- Not deployed and not on GitHub (classifier). Steps 1-2 above.
- Demo video not recorded.
- Song matching on Wikipedia sometimes falls back to the artist page (Goo Goo Muck resolves to The Cramps).
- Partners can be odd for small territories (empty lists for some countries).
- Teammates have spare keys if the monthly quota runs low (`X-RateLimit-Remaining-Month` was about 47,900 after the backtests).
