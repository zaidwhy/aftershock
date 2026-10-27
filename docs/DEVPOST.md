# Devpost submission draft (Zaid reviews, edits and submits)

**Project name:** AFTERSHOCK

**Tagline:** A Qloo taste agent for breakout shows: it spots a title breaking out in one country, forecasts where it lands next, and says what travels with it there, then lets Netflix and Wikipedia grade it in public.

## Inspiration

In 2022 Stranger Things 4 put Kate Bush's 1985 "Running Up That Hill" in front of a new, younger audience; its English Wikipedia page went from about 10,000 views a month to 909,926 in June. Wednesday did something similar for The Cramps' "Goo Goo Muck" (from about 11 views a month to 14,858). When a show breaks out, the people who could act on it (a streamer's regional marketing team, a music publisher's sync team, a promoter) find out after the fact. We wanted an agent that commits to a forecast before the outcome exists, says what to do about it, and gets graded.

## What it does

Every week the agent reads Netflix's public per-country Top 10, finds titles that just broke out in one to three countries (35 in the week of 18 Oct 2026), and for each one:

- **Where next:** the probability that each other country charts it within four weeks, with the evidence ("Bangladesh joined 19 of 47 past breakouts that started in Pakistan").
- **What travels with it (Qloo launch kit):** in each of the top forecast countries, the artists, shows, films and brands that title's audience over-indexes on there, so a marketing team knows who to partner with and what to cross-promote.
- **Where in each country (Qloo Hotspots):** the cities where that title's audience concentrates, from Qloo's heatmap, on a small map per country.
- **Sync Scout:** for a music supervisor. Type a show; Qloo returns the artists its audience loves, ranked by how far each artist's own audience sits outside the show's age groups: on-taste candidates that could reach new listeners.
- **A public, graded ledger:** every country's probability is locked in a hash-chained file before the outcome exists. A weekly GitHub Action runs the loop (detect, resolve in Qloo, forecast, build launch kits and hotspots, lock, grade) and commits the ledger.

Any MCP agent (Claude Desktop, Claude Code) can call it: `list_storms`, `spillover_forecast`, `launch_kit`, `ripple_score`, `sync_scout`.

## How we built it

Python (FastAPI, httpx), a vanilla JS front end, an MCP server on the official Python SDK, Vercel, GitHub Actions. Data: Netflix Top 10 public TSV (94 countries, weekly since July 2021), the Wikimedia Pageviews API, 490 songs from the official soundtracks of 34 titles in MusicBrainz (CC0), OpenStreetMap Nominatim for place names, and Qloo: `/search` with a strict name check; `/v2/insights` for `urn:demographics` (shows and artists), cross-domain recommendations (`urn:entity:artist`, `tv_show`, `movie`, `brand`) conditioned on a country with `signal.location.query`, artist affinity with `filter.results.entities`, and `urn:heatmap` with `filter.location.query` for hotspots. Qloo responses are cached privately and never committed.

## What we measured, including what did not work

We tested every signal against a baseline and a placebo before shipping it, and we report the misses.

- **Where next:** Netflix history alone reaches ROC AUC 0.817 on 829 held-out breakouts. Adding Qloo's in-country affinity gave no lift (0.8182 vs 0.8188 on a 200-breakout subset), so the probability is history-only and Qloo does what history cannot: what to do in each country and where.
- **Which songs spike:** on 229 artists from 24 soundtracks, no Qloo signal predicted which songs spike in Wikipedia attention. The age gap points the right way against a placebo measured before release, but is not significant (p 0.14), and taste fit predicted nothing. So Sync Scout is a discovery tool, and we do not sell it as a forecast.
- **We threw away our best result.** An earlier version of the song test, built on placement lists collected from Tunefind, showed a significant Qloo effect. When we read Tunefind's terms and saw they do not allow automated collection, we discarded that data and everything computed from it, rebuilt the ground truth from MusicBrainz, and reran the identical test. The effect did not replicate, and we say so on the site.
- **The forward test is public.** 3,240 country forecasts are locked in the ledger; the first four-week horizons close on 15 Nov 2026.

## Challenges

- `/search` always returns its nearest match, even for names Qloo does not know; we resolve only on an exact name and prefer the full title over a subtitled spin-off.
- Qloo rescales affinity within each response, so affinity is compared only within one request.
- Audiences can lean two ways at once (Wednesday's leans both 24 and younger and 55 and older), so explanations name every band, not the top one.
- Many 2026 titles and new artists have no Qloo audience profile yet, and Qloo has no heatmap for some titles; the site shows what exists and says so.
- We probed seven Qloo domains for the launch kit and dropped podcasts (identical across titles), books and places (from other countries).

## What's next

Grade the ledger weekly as horizons close, lock a Qloo-informed country ranking next to the history-only one so the two are graded head to head in public, and measure whether launch-kit and hotspot suggestions match where a title actually grows.

## Built with

python, fastapi, httpx, d3, mcp, qloo, musicbrainz, openstreetmap, netflix-top-10, wikimedia-pageviews, github-actions, vercel

## Links

- Demo: https://aftershock-qloo.vercel.app
- Code: https://github.com/zaidwhy/aftershock (MIT)

## Testing instructions for judges

No login. Open the demo and pick any storm on the home page: where it is forecast to chart next and why, then the Qloo launch kit and hotspot map for each of the top three countries. Sync Scout: type a show, for example Stranger Things (about 15 seconds the first time). Try it: enter a show and one song per line as `Song by Artist`, for example Stranger Things with `Running Up That Hill by Kate Bush`; optionally set "Score as of" to a past date. Live scoring is capped per visitor so the shared key lasts through judging.
