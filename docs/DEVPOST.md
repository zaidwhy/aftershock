# Devpost submission draft (Zaid reviews, edits and submits)

**Project name:** AFTERSHOCK

**Tagline:** When a show breaks out, AFTERSHOCK forecasts where it charts next and which of its songs reach a new audience, and lets Netflix and Wikipedia grade it in public.

## Inspiration

In 2022 Stranger Things 4 put Kate Bush's 1985 "Running Up That Hill" in front of a new, younger audience; its English Wikipedia page went from about 10,000 views a month to 909,926 in June. Wednesday did something similar for The Cramps' "Goo Goo Muck" (from about 11 views a month to 14,858). Nobody outside Netflix sees these coming, or knows where a show that just broke out in Japan will chart next. We wanted an agent that commits to forecasts before the outcome exists, gets graded, and is honest about what it cannot see.

## What it does

Every week AFTERSHOCK reads Netflix's public per-country Top 10, finds titles that just broke out in one to three countries (35 in the week of 18 Oct 2026), and for each one:

- forecasts the probability that each other country charts it within four weeks, with the evidence ("Bangladesh joined 19 of 47 past breakouts that started in Pakistan", so Fukrey Returns gets 38% there);
- names, from Qloo, the artists that title's audience already loves in each forecast country, as local launch partners;
- locks every country's probability in a hash-chained ledger, graded later against Netflix's own charts.

For songs placed in a show, it scores each one with the Qloo age gap: how far the artist's audience sits from the show's audience by age band. Try it on any show and songs, optionally as of a past release date. Any MCP agent (Claude Desktop, Claude Code) can call `list_storms`, `spillover_forecast` and `ripple_score`, and a weekly GitHub Action runs the whole loop and commits the ledger.

## How we built it

Python (FastAPI, httpx), a vanilla JS front end with d3 for the map, an MCP server on the official Python SDK, Vercel. Data: Netflix Top 10 public TSV (94 countries, weekly since July 2021), the Wikimedia Pageviews API, 516 real song placements from 44 titles collected with source URLs, and Qloo: `/search` with a strict name check, `urn:demographics` for shows and artists, cross-domain artist affinity with `filter.results.entities`, and location-conditioned artist recommendations. Qloo responses are cached privately and never committed.

## What we learned (the honest part)

We tested every Qloo signal against a baseline and a control before shipping it.

- Countries: Netflix history alone reaches ROC AUC 0.817 on 829 held-out breakouts. On a 200-breakout subset, adding Qloo's in-country affinity gave 0.8182 against 0.8188 without it: no lift, because Qloo had an in-country value for about 1.8% of title-country pairs. So the probability is history-only, and Qloo does what it is good at there: local partners.
- Songs, on 195 artists placed in 24 shows: Qloo taste fit, the obvious feature, predicted nothing (Spearman about 0.00). How unknown a song was before release looked strongest (0.27), but a placebo spike measured entirely before release showed it is mostly regression to the mean (0.19 on the placebo; 0.28 vs 0.29 on 2024+ releases). The Qloo age gap is the one signal that tracks the real spike and not the placebo: 0.28 on 2024+ releases (p 0.02), -0.11 on the placebo, real minus placebo p 0.03. That is in-sample on 24 shows, with the subset chosen after looking, so we treat it as a mechanism worth testing forward, not a proven model.
- What it cannot see: how a scene uses a song. It would not have picked Running Up That Hill, which was already well known; the spike came from the scene.

## Challenges

- `/search` always returns its nearest match, even for names Qloo does not know; we resolve only on an exact name and prefer the full title over a subtitled spin-off.
- Qloo rescales affinity within each response, so affinity is compared only within one request.
- Many 2026 titles and new artists have no Qloo audience profile yet, which limits live song scoring.
- Location-conditioned calls take seconds each; we batch entities per country and run five in flight under a 4 req/s cap.

## What's next

Grade the ledger weekly as horizons close, add scene prominence to the song score, and score soundtracks before release, which is the clean forward test.

## Built with

python, fastapi, httpx, d3, mcp, qloo, netflix-top-10, wikimedia-pageviews, github-actions, vercel

## Links

- Demo: https://aftershock.vercel.app (after deploy; check it loads before submitting)
- Code: https://github.com/zaidwhy/aftershock (MIT)

## Testing instructions for judges

No login. Open the demo and pick any storm on the home page, or go to Try it and enter a show plus a few `song | artist` lines. To replay a past release, set "Score as of": for example Wednesday as of 2022-11-23 with `Space Song | Beach House`, `Non, Je Ne Regrette Rien | Edith Piaf`, `Physical | Dua Lipa`, `Don't Worry, Be Happy | Bobby McFerrin`, `In Dreams | Roy Orbison` (measured spikes 4.2x, 2.1x, 1.1x, 0.8x, 1.3x). Live scoring is capped per visitor so the shared key lasts through judging.
