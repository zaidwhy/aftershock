# Devpost submission draft (Zaid reviews, edits and submits)

**Project name:** AFTERSHOCK

**Tagline:** When a show breaks out in one country, AFTERSHOCK forecasts where it charts next and uses Qloo to say what that audience loves there and which cities to start in. Every forecast is locked in public before the result exists.

## Inspiration

In 2022 Stranger Things 4 put Kate Bush's 1985 "Running Up That Hill" in front of a new, younger audience; its English Wikipedia page went from about 10,000 views a month to 909,926 in June. Wednesday did something similar for The Cramps' "Goo Goo Muck" (from about 11 views a month to 14,858). Shows now break out country by country, and the people outside the streamer who could act on it (a local distributor, a music publisher, a promoter) find out after the fact. We wanted an agent that tells them where a breakout goes next and what to pair it with there, commits to that forecast before the outcome exists, and gets graded.

## What it does

Every week the agent reads Netflix's public per-country Top 10, finds titles that just broke out in one to three countries (35 in the week of 18 Oct 2026), and for each one:

- **Where next:** the probability that each other country charts it within four weeks, with the evidence ("Bangladesh joined 19 of 47 past breakouts that started in Pakistan", so Fukrey Returns got 38% there in the week of 18 Oct 2026).
- **What this audience loves there (Qloo launch kit):** in each of the top three forecast countries, the artists, shows, films and brands that title's audience over-indexes on, as candidate partners and cross-promotions.
- **Whether that is really about the title:** each kit is compared with what Qloo returns for the whole country with no title. Names the whole country likes anyway are greyed out, and each kit is labelled "title-specific" or "mostly countrywide taste" (this week 48 of 81 kits are title-specific).
- **Where in each country (Qloo Hotspots):** the cities where that title's audience concentrates, from Qloo's heatmap, on a small map per country.
- **This week's map and a lookup for any title:** a world map shaded by how many of this week's breakouts are likely to reach each country, and a search over the 8,721 titles that charted since 2024 (when and where each first charted, and where a title that is still spreading may go next).
- **Sync Scout:** for a music supervisor. Type a show; Qloo returns artists its audience loves whose own audience sits outside the show's age groups. A shortlist, not a forecast.
- **A public record:** every country's probability is locked in a hash-chained file in the repo before the outcome exists. A weekly GitHub Action runs the loop (detect breakouts, resolve titles in Qloo, forecast, build kits and hotspots, lock) and commits the ledger; grading starts when the first four-week horizons close on 15 Nov 2026.

Any MCP agent (Claude Desktop, Claude Code) can call it: `list_storms`, `spillover_forecast`, `launch_kit`, `ripple_score`, `sync_scout`, `netflix_history`, `ask`.

## How we built it

Python (FastAPI, httpx), a vanilla JS front end with d3 maps, an MCP server on the official Python SDK, Vercel, GitHub Actions. Data: Netflix Top 10 public TSV (94 countries, weekly since July 2021), the Wikimedia Pageviews API, 490 songs from the official soundtracks of 34 titles in MusicBrainz (CC0), OpenStreetMap Nominatim for place names, and Qloo: `/search` with a strict name check; `/v2/insights` for `urn:demographics` (shows and artists), cross-domain recommendations (`urn:entity:artist`, `tv_show`, `movie`, `brand`) with and without a title signal, conditioned on a country with `signal.location.query`, and `urn:heatmap` with `filter.location.query` for hotspots. Raw Qloo responses are cached privately and never committed.

## What we measured, including what did not work

- **Where next:** Netflix history alone reaches ROC AUC 0.817 on 829 held-out breakouts (top-5 precision 0.041, against 0.012 for a uniform guess). Adding Qloo's in-country affinity to the probability gave no lift (0.8182 vs 0.8188 on a 200-breakout subset), so the probability is history-only. Qloo's job is the part history cannot answer: what this audience loves in each country, and where they are.
- **Is the kit about the title?** Measured against Qloo's country-only answer: 48 of 81 kits this week are title-specific; the other 33 mostly repeat the country's general taste, and the site labels them so.
- **Qloo against an LLM:** pre-registered before any data was collected (`docs/EXPERIMENT_KITS.md`): the same 81 title-country pairs, four arms (Qloo with and without the title, an LLM with and without the title), scored by overlap, not by an LLM judge. Result: by the registered rule the LLM's kits were more title-specific (0.812 against Qloo's 0.617, permutation p below 0.001), and it still led when only picks Qloo could resolve were counted. We report it as registered. Only 66% of the LLM's picks resolve to a Qloo entity, and Qloo's lists differed more between titles; neither reverses the verdict. The product consequence is the countrywide label on kits that mostly match Qloo's country-only answer.
- **Which songs spike:** we tested whether Qloo signals predict which soundtrack songs get a burst of Wikipedia attention, with a placebo window measured before release. On 229 artists from 24 soundtracks none did (age gap p 0.14 against the placebo; taste fit about 0). So Sync Scout is a discovery tool, and we do not present it as a forecast.
- **Graded in public, with the rules fixed first:** how many of last week's top picks have already charted is reported every week against a calibrated expectation and a naive baseline, defined in `docs/EARLY_GRADE.md` before the data existed.
- **We threw away our best result.** An earlier version of that song test, built on placement lists collected from Tunefind, showed a significant Qloo effect. When we read Tunefind's terms and saw they do not allow automated collection, we deleted that data and everything computed from it, rebuilt the ground truth from MusicBrainz, and reran the identical test. The effect did not replicate, and the site says so.

## Challenges

- `/search` always returns its nearest match, even for names Qloo does not know; we resolve only on an exact name and prefer the full title over a subtitled spin-off.
- For titles with little signal, Qloo's location-conditioned answer falls back to the country's general taste; we added the country-only control so this is visible instead of hidden.
- Qloo rescales affinity within each response, so affinity is compared only within one request.
- Some Qloo names arrive with broken accents (UTF-8 read as Mac Roman); we repair them only when the round trip is clean.
- Many 2026 titles and new artists have no Qloo audience profile yet, and Qloo has no heatmap for some titles; the site shows what exists and says so.

## Who would pay, and why now

The users are the people outside a streamer who act on a breakout: a local distributor or dubbing studio deciding which markets to back, a music publisher or label whose catalogue is in the show, a promoter or brand looking for a tie-in. Today they learn about a breakout after it peaks. The product they would pay for is the weekly brief this site already produces (where next, with the reason; what the audience there loves, with the generic picks flagged; which cities), delivered per territory or per catalogue, with the public ledger as the reason to trust it. The agent costs a few hundred Qloo calls a week to run, and every forecast it has ever made stays checkable.

## What's next

Grade the ledger weekly as horizons close and publish the hit rate; lock a Qloo-informed country ranking next to the history-only one so the two are graded head to head; check whether launch-kit and hotspot suggestions match where a title actually grows; and send the weekly brief to a first few distributors and publishers to learn which parts they act on.

## Built with

python, fastapi, httpx, d3, mcp, qloo, musicbrainz, openstreetmap, netflix-top-10, wikimedia-pageviews, github-actions, vercel

## Links

- Demo: https://aftershock-qloo.vercel.app
- Code: https://github.com/zaidwhy/aftershock (MIT)

AFTERSHOCK is not affiliated with Netflix or Qloo.

## Testing instructions for judges

No login, nothing to install. Five minutes on https://aftershock-qloo.vercel.app:

1. **Home:** the worked example on the right shows this week's clearest case: where a title broke out, where it is likely to chart next and why, what its audience there loves (Qloo), and which cities to start in.
2. **Ask the agent:** click the example "What should ... pair with in ...?" (it uses this week's clearest breakout) or type your own question. The agent picks its tools and lists every step it took ("How the agent answered").
3. **The map:** hover a country under "Where this week's breakouts are heading", or use "Look up any title" for any show or film.
4. **Song check:** click "Stranger Things + 3 songs" to see which songs reach a new crowd (a first run takes about 10 seconds).
5. **Agent, Scorecard and Ledger:** what the agent did on its weekly run; what we measured, including what did not work and the pre-registered tests; and every locked forecast.

To use it from an AI agent: the MCP server (`python -m aftershock.mcp_server`, README section 5) exposes the same seven tools. Live lookups are capped per visitor so the shared Qloo key lasts through judging.
