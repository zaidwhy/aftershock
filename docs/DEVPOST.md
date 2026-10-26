# Devpost submission draft (Zaid reviews, edits and submits)

**Project name:** AFTERSHOCK

**Tagline:** When a show breaks out, AFTERSHOCK forecasts where it lands next and which songs it drags into the spotlight, then lets Netflix and Wikipedia grade it in public.

## Inspiration

In May 2022 Stranger Things 4 put Kate Bush's 1985 "Running Up That Hill" in front of a teenage audience. Its English Wikipedia page went from about 10,000 views a month to 909,926 in June. Saltburn did the same for "Murder on the Dancefloor" in 2023. Nobody outside Netflix saw these coming, and nobody outside Netflix knows where a show that just broke out in Japan will chart next. Agents are good at explaining the past; we wanted one that commits to the future and gets graded.

## What it does

Every week AFTERSHOCK reads Netflix's public per-country Top 10, finds titles that just broke out in one to three countries (35 in the week of 18 Oct 2026), and for each one:

- forecasts which of the other 90+ countries it charts in over the next four weeks, with the evidence ("Bangladesh joined 19 of 47 past breakouts that started in Pakistan", so Fukrey Returns gets 38% there);
- uses Qloo to name the local artists that title's audience already loves in each forecast country, as launch partners;
- for shows with known song placements, scores each song for spike potential: Qloo taste fit of the show's audience for the artist, times the age gap between the two audiences;
- locks every forecast in a hash-chained public ledger before the outcome exists, and grades it against the next Netflix chart and Wikipedia's daily pageviews.

You can also score your own show and songs on the Try page, and any MCP agent (Claude Desktop, Claude Code) can call `list_storms`, `spillover_forecast` and `ripple_score`.

## How we built it

Python (FastAPI, httpx), a vanilla JS front end with d3 for the map, an MCP server on the official Python SDK, deployed on Vercel. Data: Netflix Top 10 public TSV (94 countries, weekly since July 2021), Wikimedia Pageviews API, 516 real song placements from 44 titles collected with source URLs, and the Qloo Insights API: `/search`, `urn:demographics`, cross-domain artist affinity with `filter.results.entities`, and location-conditioned artist recommendations. Qloo responses are cached privately and never committed.

## What we learned (the honest part)

We tested every Qloo signal against a baseline before using it.

- Country spread: Netflix history alone reaches ROC AUC 0.817 on 829 held-out breakouts. Adding Qloo's in-country affinity gave 0.8182 vs 0.8188: no lift, because Qloo had an in-country value for only 1.8% of title-country pairs. So the probability is history-only, and Qloo does the job it is good at: who to partner with locally.
- Song ripples: on 105 placed songs in 17 shows, fit x age gap correlates with the measured spike at a mean within-show Spearman of 0.11 overall and 0.28 for 2024+ releases (permutation p = 0.053), against 0.15 / 0.16 for "how obscure the song was" and about 0 for random. Promising, not proven. Backtests here are biased by construction: Qloo's data is a current snapshot, so a song that already spiked now looks like a better fit and a smaller age gap than before release. That is why the ledger exists.

## Challenges

- `/search` always returns its nearest match, even for names Qloo does not know; we resolve only on an exact normalized name match.
- Qloo rescales affinity within each response, so fit is compared only within one show.
- Location-conditioned calls take seconds each; we batch entities per country and run five in flight under a 4 req/s cap.

## What's next

Grading the live ledger every week, adding scene prominence to RIPPLE, and pre-release mode: score a soundtrack before the show ships.

## Built with

python, fastapi, httpx, d3, mcp, qloo, netflix-top-10, wikimedia-pageviews, vercel

## Links

- Demo: https://aftershock.vercel.app (after deploy)
- Code: https://github.com/zaidwhy/aftershock (MIT)

## Testing instructions for judges

No login. Open the demo, pick any storm on the home page, or go to Try it and enter a show plus a few `song | artist` lines (for example `Stranger Things` with `Running Up That Hill | Kate Bush`). Live scoring is capped at 10 requests per visitor per hour so the shared key lasts through judging.
