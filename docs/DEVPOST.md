# Devpost submission draft (Zaid reviews, edits and submits)

**Project name:** AFTERSHOCK

**Tagline:** An AI's launch plan sounds right. Qloo checks it. AFTERSHOCK forecasts which country a Netflix breakout reaches next, plans the launch there, and keeps only the names Qloo confirms for that audience.

### Results at a glance

| Question | Result |
|---|---|
| Qloo alone, an LLM alone, an LLM checked by Qloo | How specific to the title the picks are (0 to 1, same 81 title-country pairs): Qloo alone 0.62, LLM alone 0.81, LLM checked by Qloo 0.86 (exploratory, not pre-registered). 71% of the LLM's names are not backed by Qloo. Of 1,615 names an AI proposed, Qloo could back 29% (462): it links them to that audience in that country. 66% are names Qloo knows; 71% are not backed, of which 34% (548) Qloo has no data on (a gap in Qloo's coverage, not proof the name is wrong) and 37% (605) Qloo knows but does not place with that audience. Only confirmed names ship in a plan. |
| Forecast backtest (829 held-out breakouts) | Counting all 829: its top 3 named a next country for 9.8% of breakouts against 4.1% for the three busiest countries, 2.4 times the baseline. Of the 113 that spread at all: 72% against 30%. For scale, a typical country charts a given breakout about 1% of the time (758 of 76,760 held-out pairs), so the featured 14% for Sweden is about 14 times that. A case where it worked: an Arabic series broke out in Kuwait in April 2026; its top two forecasts, Saudi Arabia (30%) and Oman (19%), both charted one week later. |
| Forecasts locked in public | 3,240 so far, each fixed before its outcome exists; grading starts 15 Nov 2026. |

## Why this only works with Qloo

An AI asked what a title's audience in a country loves answers fluently, and most of it cannot be told apart from a guess. Qloo is the check. It does three things a language model cannot:

- **It checks each name for one audience in one country.** Is this artist, brand, show or film linked to the viewers of this title in Sweden? Qloo confirms or does not, name by name, and only confirmed names reach the plan.
- **It maps where that audience lives.** Qloo's heatmap gives the cities where a title's audience concentrates, and the same call gives them for each artist.
- **It overlaps two audiences.** Where an artist's heatmap and the title's heatmap meet gives a city for a quick activation that no list of names can give.

## Inspiration: two kinds of aftershock

A breakout travels country by country: that is what we forecast from Netflix history. The culture around it travels too: that is what Qloo maps. When Stranger Things 4 Volume 1 came out on 27 May 2022, English Wikipedia's article on Kate Bush's "Running Up That Hill" went from 349 views on 26 May to 43,521 on 31 May (Wikimedia Pageviews REST API, en.wikipedia, user agents, daily). The people who could act on that, a label, an artist, a brand, usually find out after the peak. Netflix itself now reports that its placements send songs back up the charts ([Music on Netflix: New and Nostalgic Songs Storm the Charts](https://about.netflix.com/news/music-on-netflix-new-and-nostalgic-songs-storm-the-charts)).

## What it does

- **Plan a launch (start here).** Pick a breakout and a country. The agent works through visible steps, each with what it found and the rule it applied: forecast, ask Qloo what the audience likes, ask an AI for more names, check every AI name against Qloo, find the cities, match artists to cities, write the Launch Brief. When Qloo's own kit is clearly specific to the title (at least 60% different from the country's general taste), the partners lead with Qloo's kit and the AI names Qloo confirmed follow, labelled as such; platform brands such as Spotify are left out. The brief names partners to approach (artists and brands), what the audience also watches (for creative and ad targeting), quick-turn activation ideas, and what the evidence does not support. Download, print or share it.
- **Live check box.** Type any artist, brand, show or film on the plan page; Qloo confirms or rejects it for that audience, now. Names Qloo has no data on are listed separately, never struck through.
- **For artists.** Every artist Qloo links to a breakout's audience has a page: which titles' viewers over-index on their music, where, and the cities where both audiences concentrate. Artists that appear only in countrywide kits are tagged.
- **World map.** Follow one title and the map recolours by its chance in each country.
- **Public ledger.** Every week's forecasts are locked in a hash-chained ledger before the outcome exists, then graded. An MCP server exposes the same tools to any agent.

## Qloo calls we make

| Endpoint and parameters | What the agent decides with it |
|---|---|
| `GET /search` with `types`, then a strict name check | Resolves a typed or AI-proposed name. Only an exact normalized name counts, because `/search` always returns its nearest hit, even for names Qloo does not know. |
| `GET /v2/insights` with `filter.type` = `urn:entity:artist`, `tv_show`, `movie` or `brand`, `signal.interests.entities` = the title, `signal.location.query` = the country | The launch kit: what this title's audience over-indexes on there. |
| The same without `signal.interests.entities` | The country-only control: a kit that mostly repeats it is labelled countrywide, not title-specific. |
| The same with `filter.results.entities` = the ids of the AI's names | Confirms or rejects each AI name for this audience in this country. Also what the live check box asks. |
| `filter.type=urn:heatmap` with `signal.interests.entities` = the title and `filter.location.query` = the country | The cities where the title's audience concentrates (hotspots). |
| The same with an artist as the signal | Each partner artist's cities; a title city within 30 km of one of the artist's 5 strongest cells becomes an activation idea. |
| `filter.type=urn:demographics` with a show or artist as the signal | Age bands for Song check; with `urn:entity:artist` candidates, the ranking in Sync Scout. |

## Who would pay

Each buyer has one move that fits in the week between a breakout and its peak:

- **Labels:** push an artist's catalogue and a playlist to listeners in the cities where Qloo links that artist to the title's viewers.
- **Artists:** a post, a DJ set or a playlist push aimed at those cities while the title is charting.
- **Brand marketers:** local ads in the title's hotspot cities, only for brands Qloo confirms for that audience.

Local media and creators can act fastest, on the same cities. We have no customers or pilots. **Pricing hypothesis (untested):** a weekly per-territory brief for labels and agencies, artist pages free. We have not tested it with anyone.

## What it can't do

- Titles that launch worldwide on day one are not breakouts, so it would not have flagged Stranger Things 4 or Wednesday.
- The warning is about a week. That suits short activations, playlist pushes and local ads, not tours, which are booked months ahead.
- The country forecast uses Netflix history only. Qloo added no lift to it in our test.
- It watches Netflix only, because Netflix is the one major streamer we found that publishes a weekly Top 10 for each of 94 countries, back to 2021; we found no comparable per-country charts from other streamers, and third-party chart scrapers carry terms risk. The Qloo half (kits, city maps, artist overlap, the live check) works for any title Qloo knows, from any platform.
- Launch kits and activation ideas are not yet validated against outcomes, and forecasts are graded only from 15 Nov 2026.

## What we measured, including what did not work

- **Qloo against an LLM (pre-registered in `docs/EXPERIMENT_KITS.md` before any data):** on 81 title-country pairs the LLM's kits were more title-specific than Qloo's (0.812 against 0.617, permutation p below 0.001), and it still led when only picks Qloo could resolve were counted. We report it as registered. Qloo's lists differed more between titles. The consequence is the design above: the LLM proposes, Qloo decides. The checked plan is the most title-specific of the three (0.86, exploratory: designed after the registered result).
- **Where next:** Netflix history alone reaches ROC AUC 0.817 on 829 held-out breakouts. Adding Qloo's in-country affinity gave no lift (0.8182 against 0.8188 on a 200-breakout subset), so the probability is history-only.
- **How much warning:** most breakouts never spread (113 of 829 did). When a pick did chart, the median lead was one week.
- **A result we threw away:** soundtrack-song spikes were not predicted by any Qloo signal on 229 artists (age gap p 0.14 against a placebo window). An earlier version built on Tunefind placements looked significant; when we read Tunefind's terms we deleted that data, rebuilt the ground truth from MusicBrainz and reran. The effect did not replicate, and the site says so.

## Data rights

Netflix's public Top 10 (credited; we use the published per-country lists), Qloo responses cached privately and never committed, MusicBrainz (CC0), Wikimedia pageviews, OpenStreetMap Nominatim (ODbL, credited), Tunefind data dropped over its terms. We claim no permission beyond what each source publishes. AFTERSHOCK is not affiliated with Netflix or Qloo.

## Testing instructions for judges

No login, nothing to install. Five minutes on https://aftershock-qloo.vercel.app:

1. **Plan a launch:** open https://aftershock-qloo.vercel.app/#/plan/nightwatch-demons-are-forever/SE (Nightwatch: Demons Are Forever in Sweden). Watch the steps replay, then read, download or print the Launch Brief.
2. **Check a name live:** in the box under step 4, type any artist, brand, show or film; Qloo confirms or rejects it for this audience, now. Live lookups are capped per visitor.
3. **Home, the map:** click a "Follow one title" button; click a country for its cities and Qloo-checked picks.
4. **Any storm page:** the launch kit per country and "AI plan, checked by Qloo".
5. **For artists:** https://aftershock-qloo.vercel.app/#/artist/veronica-maggio.
6. **Scorecard and Ledger (under More):** what we measured, including what went against us, and every locked forecast.

From an AI agent: the MCP server (`python -m aftershock.mcp_server`, README section 5).

## Links

- Demo: https://aftershock-qloo.vercel.app
- Code: https://github.com/zaidwhy/aftershock (MIT)
- Demo video: (YouTube link to be added)  <!-- PLACEHOLDER for Zaid: paste the unlisted YouTube link before submitting -->

**Built with:** a fixed plan of tool calls with visible decision rules; the LLM (Gemini `gemini-3.5-flash`) only proposes names and drafts a validated summary. python, fastapi, httpx, d3, mcp, qloo, gemini, musicbrainz, openstreetmap, netflix-top-10, wikimedia-pageviews, github-actions, vercel
