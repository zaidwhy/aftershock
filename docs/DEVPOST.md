# Devpost submission draft (Zaid reviews, edits and submits)

**Project name:** AFTERSHOCK

**Tagline:** A launch agent for breakout shows. It forecasts which country a show reaches next, plans the launch there with Qloo, and throws out every AI suggestion Qloo cannot back.

## Inspiration

Shows now break out one country at a time. In the week of 18 Oct 2026, Fukrey Returns entered Netflix's Top 10 in Pakistan; history says Bangladesh is likely next (Bangladesh joined 19 of 47 past breakouts that started in Pakistan). The people who could act on that, a local distributor, a dubbing studio, a music label with songs in the show, a brand looking for a tie-in, usually find out after the peak, and then plan the launch from gut feel or a chatbot. We asked a chatbot. It answered fluently, and most of what it named was either unknown to Qloo or not something this audience in this country actually over-indexes on. That gap is the product.

## Why this only works with Qloo (measured, not claimed)

The hackathon asks for an agent that does better than an LLM alone. We tested that before building the answer, on the same 81 title-country pairs:

- **An LLM alone is specific but unreliable.** Gemini's picks depend more on the title than Qloo's do (0.81 against 0.62; pre-registered in `docs/EXPERIMENT_KITS.md` before any data, reported as registered). But 71% of what it names, Qloo cannot back: 34% are names Qloo does not know at all, and 37% are things Qloo knows but does not link to this audience in this country.
- **Qloo alone is reliable but sometimes generic.** For 33 of 81 kits, Qloo's answer mostly repeats what the whole country likes, whatever the title. We show that with a country-only control instead of hiding it.
- **So the agent uses both and checks every name.** The LLM proposes; Qloo confirms or rejects each proposal for that audience in that country; only confirmed names reach the plan, next to Qloo's own picks. On the same pairs, the confirmed plan is the most title-specific of the three (0.86, exploratory: designed after the registered result), and it adds about 5 names per country that Qloo vouches for but its own top 5 did not contain.

## What it does

**Plan a launch (the agent, start here).** Pick a breakout and a country. The agent works through seven steps on screen, each with what it found and the rule it applied:
1. **Forecast:** this country's chance of charting the title within four weeks, and its rank.
2. **Ask Qloo** what this title's audience over-indexes on here (artists, shows, films, brands), and whether that is about the title or just the country's general taste.
3. **Ask an AI** for more ideas for this audience.
4. **Check every AI idea against Qloo:** confirmed, not linked to these viewers, or unknown.
5. **Find the cities** where this audience concentrates (Qloo heatmap).
6. **Match artists to cities:** Qloo's heatmap for up to three partner artists against the title's cities, giving event ideas where both audiences concentrate.
7. **Write the Launch Brief:** where and when, the cities to start in, the partners and cross-promotions to approach (Qloo-checked), what the evidence does not support, and a two-sentence summary whose names and numbers are checked against the facts before it is shown. Download it, print it, or share the link.

**Follow one title on the world map.** One click and the map recolours by that title's chance in every country; click a country for the cities and the Qloo-checked picks.

**Every forecast is locked in public first.** Each week the agent reads Netflix's public per-country Top 10, finds the titles that just broke out in one to three countries (35 in the week of 18 Oct 2026), forecasts every other country, builds kits, plans and hotspots, and locks every probability in a hash-chained ledger before the outcome exists. A GitHub Action runs it every Tuesday; grading starts when the first four-week horizons close on 15 Nov 2026.

**For agents too.** An MCP server exposes the same tools (`list_storms`, `spillover_forecast`, `launch_kit`, `launch_brief`, `ripple_score`, `sync_scout`, `netflix_history`, `ask`), so Claude Desktop or any MCP agent can plan a launch.

**Also:** a lookup over the 8,721 titles that charted since 2024, and Sync Scout, which finds on-taste artists whose audience sits outside a show's age groups (a shortlist for a music supervisor, not a forecast).

## How we built it

**Why the agent follows a fixed plan instead of letting the LLM choose its own steps.** A brief someone acts on has to say why each name is in it. An LLM that picks its own tools can skip the Qloo check, call it on the wrong audience, or explain a step it never ran, and nobody can tell afterwards. So the order is fixed (forecast, Qloo kit, AI proposals, Qloo check, cities, brief), the LLM does what it is good at inside that order (proposing names, drafting the summary), and every decision is a rule printed next to the step it changed, such as "Qloo confirmed fewer than 3 AI picks, so the brief uses Qloo's own kit". The same steps run the same way for every title, which is what lets us measure them.

The agent is a fixed plan of tool calls with explicit decision rules, so every step can be shown and checked: Netflix history forecasts, Qloo builds the kit and the country-only control, Gemini (`gemini-3.5-flash`, batched, about ten calls a week) proposes names and drafts the brief summary, Qloo confirms each name with a filtered `/v2/insights` call for that title's audience in that country, and a validator rejects any summary that mentions a name or number not in the brief. Python (FastAPI, httpx), a vanilla JS front end with d3 maps, an MCP server on the official Python SDK, Vercel, GitHub Actions. Data: Netflix Top 10 public TSV (94 countries, weekly since July 2021), the Wikimedia Pageviews API, 490 songs from the official soundtracks of 34 titles in MusicBrainz (CC0), OpenStreetMap Nominatim for place names, and Qloo: `/search` with a strict name check; `/v2/insights` for `urn:demographics` (shows and artists), cross-domain recommendations (`urn:entity:artist`, `tv_show`, `movie`, `brand`) with and without a title signal, conditioned on a country with `signal.location.query`, and `urn:heatmap` with `filter.location.query` for hotspots. Raw Qloo responses are cached privately and never committed.

## What we measured, including what did not work

- **Where next:** Netflix history alone reaches ROC AUC 0.817 on 829 held-out breakouts (top-5 precision 0.041, against 0.012 for a uniform guess). Adding Qloo's in-country affinity to the probability gave no lift (0.8182 vs 0.8188 on a 200-breakout subset), so the probability is history-only. Qloo's job is the part history cannot answer: what this audience loves in each country, and where they are.
- **How much warning (backtest, history-only forecasts):** on the same 829 held-out breakouts (March to October 2026, each forecast made in the breakout week from earlier breakouts only; `scripts/measure_lead_time.py` -> `data/results/lead_time.json`), at least one of the model's top 3 countries charted the title within 4 weeks for 9.8% of them (81), against 4.1% (34) for the 3 countries that chart the most titles. Most breakouts never spread: only 113 of the 829 charted in any other country in 4 weeks, and the top 3 caught 81 of those 113. When a pick did chart, the median lead was 1 week (117 of 131 charted picks within 1 week, 6 at 2, 4 at 3, 4 at 4). That is modest warning, and the backtest does not show the Qloo part helps it.
- **Is the kit about the title?** Measured against Qloo's country-only answer: 48 of 81 kits this week are title-specific; the other 33 mostly repeat the country's general taste, and the site labels them so.
- **Qloo against an LLM:** pre-registered before any data was collected (`docs/EXPERIMENT_KITS.md`): the same 81 title-country pairs, four arms (Qloo with and without the title, an LLM with and without the title), scored by overlap, not by an LLM judge. Result: by the registered rule the LLM's kits were more title-specific (0.812 against Qloo's 0.617, permutation p below 0.001), and it still led when only picks Qloo could resolve were counted. We report it as registered. Only 66% of the LLM's picks resolve to a Qloo entity, and Qloo's lists differed more between titles; neither reverses the verdict. The product consequence: the countrywide label on kits that mostly match Qloo's country-only answer, and the agent design above, where the LLM proposes and Qloo decides.
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

The buyer is whoever spends money on a title in a market it has not reached yet: a local distributor or dubbing studio choosing which markets to back this month, a label or publisher whose songs are in the show, a brand or promoter looking for a tie-in. Their decision is which countries, which cities and which partners, and it has to be made in the weeks between a breakout and its peak.

| | Today | With AFTERSHOCK |
|---|---|---|
| When they know | after the title charts there | the week it breaks out anywhere |
| Where | gut feel, or the biggest markets | a probability per country with its reason, graded in public |
| With whom | a chatbot list nobody checked | partners Qloo confirms for this audience in this country |
| Which artist, which city | a promoter's hunch | event ideas where the show's audience and the artist's audience concentrate in the same city ("Yo Yo Honey Singh in Delhi and Jaipur" for Fukrey Returns in India) |
| Trust | none to inspect | every forecast locked before the outcome; every claim with its test |

What the warning is worth, measured: in the history-only backtest above, a buyer watching the model's top 3 countries for a breakout would have seen the title chart in one of them for 9.8% of breakouts (4.1% for the three countries that chart most titles), usually within a week. Most breakouts do not travel, so the value is in the minority that do: of the 113 that did, the top 3 caught 81 (72%). It is a backtest, not a promise.

Live events are the sharpest case. Qloo [names Live Nation among the companies using its technology](https://www.prnewswire.com/news-releases/qloo-recognized-in-the-set-diamonds-category-in-the-2026-gartner-emerging-tech-ai-to-watch-in-synthetic-popular-simulation-research-302878163.html), and a Netflix title becoming a ticketed tour already happens: Netflix and AEG Presents [announced a KPop Demon Hunters world tour](https://www.sherwood.news/culture/netflix-confirms-a-kpop-demon-hunters-world-concert-tour-is-on-the-way/). A promoter reacting to a breakout needs the artist and the city, and that pairing needs two audience maps, which an LLM does not have. We present these as ideas to investigate: they show where audiences overlap, not ticket demand.

The weekly run costs a few hundred Qloo calls and about ten LLM calls; the Launch Brief is the product, per territory or per catalogue.

## What's next

Grade the ledger weekly as horizons close and publish the hit rate; lock a Qloo-informed country ranking next to the history-only one so the two are graded head to head; check whether launch-kit and hotspot suggestions match where a title actually grows; and send the weekly brief to a first few distributors, promoters and publishers to learn which parts they act on. Travel is the next buyer: Netflix itself [partnered with the Korea Tourism Organization](https://about.netflix.com/news/netflix-partners-with-kto-to-promote-korean-tourism-globally) to turn viewers of Korean shows into visitors. The cities where a breakout's audience lives, in the countries it is spreading to, are a targeting list for a tourism board or airline promoting the show's destination; we have not built it because the only free route data we found stopped updating in 2014.

## Built with

python, fastapi, httpx, d3, mcp, qloo, gemini, musicbrainz, openstreetmap, netflix-top-10, wikimedia-pageviews, github-actions, vercel

## Links

- Demo: https://aftershock-qloo.vercel.app
- Code: https://github.com/zaidwhy/aftershock (MIT)

AFTERSHOCK is not affiliated with Netflix or Qloo.

## Testing instructions for judges

No login, nothing to install. Five minutes on https://aftershock-qloo.vercel.app:

1. **Plan a launch** (second item in the menu): it opens on this week's clearest breakout. Watch the seven steps, then read, download or print the Launch Brief. Pick another title or country from the two menus.
2. **Home, the map:** click one of the "Follow one title" buttons; the map recolours by that title's chance in each country. Click a country for its cities and Qloo-checked picks.
3. **Any storm page:** the launch kit per country, its "title-specific" or "countrywide" label, and under it "AI plan, checked by Qloo" with how many AI suggestions Qloo confirmed, did not link to these viewers, or did not know.
4. **Scorecard:** what we measured, including what went against us, and the pre-registered tests. **Ledger:** every locked forecast.

To use it from an AI agent: the MCP server (`python -m aftershock.mcp_server`, README section 5) exposes the same eight tools. Live lookups are capped per visitor so the shared Qloo key lasts through judging.
