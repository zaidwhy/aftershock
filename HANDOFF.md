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
3. Review the Devpost draft in `docs/DEVPOST.md` and submit it yourself.

## State (overnight, 27 Oct)

See the end of this file for the latest results; everything below is committed locally on `main`.

## Decisions taken overnight (and why)

- SPILLOVER decision test: Qloo location affinity adds no AUC (0.8188 history vs 0.8182 with Qloo; Qloo had a value for 1.8% of title-country pairs). Per the pre-set rule, the country forecast is history-only and Qloo is used for local partners instead.
- RIPPLE test is inconclusive on past data, and the reason is structural: Qloo's data is a snapshot taken after past spikes, which inflates fit and shrinks the age gap of songs that already spiked. The forward ledger is the real test, so forecasts are locked for new releases.
- Stayed with AFTERSHOCK rather than switching to READ THE ROOM: the product, data pipeline and ledger exist, the honesty of the measurement is itself the differentiator, and a rebuild in 3 days was the bigger risk.
- No paid LLM. The agentic parts: an autonomous weekly job (detect, resolve, forecast, lock, grade) and an MCP server so Claude and other agents can call the tools.

## Results log
