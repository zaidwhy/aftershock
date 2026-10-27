# Devpost submission draft (Zaid reviews, edits and submits)

**Project name:** AFTERSHOCK

**Tagline:** A Qloo taste agent for breakout shows: it spots a title breaking out in one country, forecasts where it lands next, and says what travels with it there, then lets Netflix and Wikipedia grade it in public.

## Inspiration

In 2022 Stranger Things 4 put Kate Bush's 1985 "Running Up That Hill" in front of a new, younger audience; its English Wikipedia page went from about 10,000 views a month to 909,926 in June. Wednesday did something similar for The Cramps' "Goo Goo Muck" (from about 11 views a month to 14,858). When a show breaks out, the people who could act on it (a streamer's regional marketing team, a music publisher's sync team, a promoter) find out after the fact. We wanted an agent that commits to a forecast before the outcome exists, says what to do about it, and gets graded.

## What it does

Every week the agent reads Netflix's public per-country Top 10, finds titles that just broke out in one to three countries (35 in the week of 18 Oct 2026), and for each one:

- **Where next:** the probability that each other country charts it within four weeks, with the evidence ("Bangladesh joined 19 of 47 past breakouts that started in Pakistan").
- **What travels with it (Qloo launch kit):** in each of the top forecast countries, the artists, shows, films and brands that title's audience over-indexes on there, so a marketing team knows who to partner with and what to cross-promote.
- **Which songs could carry it to a new generation (RIPPLE):** for songs placed in a show, the Qloo age gap between each artist's audience and the show's.
- **Sync Scout:** the same signal in reverse for a music supervisor. Type a show; Qloo returns the artists its audience loves, ranked by how far their audience sits outside the show's generation.
- **A public, graded ledger:** every country's probability and every eligible song forecast is locked in a hash-chained file before the outcome exists. A weekly and a daily GitHub Action run the loop (detect, resolve in Qloo, forecast, lock, grade) and commit the ledger.

Any MCP agent (Claude Desktop, Claude Code) can call it: `list_storms`, `spillover_forecast`, `launch_kit`, `ripple_score`, `sync_scout`.

## How we built it

Python (FastAPI, httpx), a vanilla JS front end, an MCP server on the official Python SDK, Vercel, GitHub Actions. Data: Netflix Top 10 public TSV (94 countries, weekly since July 2021), the Wikimedia Pageviews API, 516 real song placements from 44 titles collected with source URLs, and Qloo: `/search` with a strict name check; `/v2/insights` for `urn:demographics` (shows and artists), cross-domain recommendations (`urn:entity:artist`, `tv_show`, `movie`, `brand`) conditioned on a country with `signal.location.query`, and artist affinity with `filter.results.entities`. Qloo responses are cached privately and never committed.

## Why Qloo, measured

We tested every Qloo signal against a baseline, a placebo and an LLM before shipping it.

- **Qloo beats an LLM at the song signal.** The Qloo age gap tracks real song spikes (within-show Spearman 0.28 on 2024+ releases, p 0.02) and not a placebo spike measured before release (real minus placebo p 0.03). We asked Gemini to guess the same 195 artists' and 24 shows' audiences from their names and ran the identical test: 0.03 on 2024+ (p 0.40), real minus placebo p 0.23. An LLM can guess who is famous; Qloo measures who actually listens.
- **The obvious baselines failed.** Qloo taste fit predicted nothing (about 0.00). How unknown a song was looked strongest (0.27) until the placebo showed it was mostly regression to the mean (0.28 vs 0.29 on 2024+).
- **Where Qloo did not help, we say so.** For the country probability, Netflix history alone reaches ROC AUC 0.817 on 829 held-out breakouts, and adding Qloo's in-country affinity gave no lift (0.8182 vs 0.8188 on a 200-breakout subset). So Qloo does what it is good at there: what to do in each country, not whether.
- All of this is in-sample on 24 shows, with the 2024+ subset chosen after looking; the ledger is the forward test. The score does not see how a scene uses a song: it would not have picked Running Up That Hill, which was already well known.

## Challenges

- `/search` always returns its nearest match, even for names Qloo does not know; we resolve only on an exact name and prefer the full title over a subtitled spin-off.
- Qloo rescales affinity within each response, so affinity is compared only within one request.
- Audiences can lean two ways at once (Wednesday's leans both 24 and younger and 55 and older), so explanations name every band, not the top one.
- Many 2026 titles and new artists have no Qloo audience profile yet, which limits live song scoring; we lock only when at least four songs are scorable.
- We probed seven Qloo domains for the launch kit and dropped podcasts (identical across titles), books and places (from other countries).

## What's next

Grade the ledger weekly as horizons close, score soundtracks before release as the clean forward test, and add scene prominence to the song score.

## Built with

python, fastapi, httpx, mcp, qloo, gemini, netflix-top-10, wikimedia-pageviews, github-actions, vercel

## Links

- Demo: https://aftershock-qloo.vercel.app
- Code: https://github.com/zaidwhy/aftershock (MIT)

## Testing instructions for judges

No login. Open the demo and pick any storm on the home page to see where it is forecast to chart next and its Qloo launch kit per country. Sync Scout: type a show, for example Stranger Things (about 15 seconds the first time). Try it: enter a show and one song per line as `Song by Artist`; set "Score as of" to replay a past release, for example Wednesday as of 2022-11-23 with `Space Song by Beach House`, `Non, Je Ne Regrette Rien by Edith Piaf`, `Physical by Dua Lipa`, `Don't Worry, Be Happy by Bobby McFerrin`, `In Dreams by Roy Orbison` (measured spikes 4.2x, 2.1x, 1.1x, 0.8x, 1.3x). Live scoring is capped per visitor so the shared key lasts through judging.
