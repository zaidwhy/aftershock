# Devpost submission draft (Zaid reviews, edits and submits)

**Project name:** AFTERSHOCK

**Tagline:** Shows travel. See where next. When a Netflix show gets popular in one country, AFTERSHOCK predicts which country is next and plans the launch there, keeping only the partners Qloo's audience data supports.

### Results at a glance

*As of submission (Netflix week of 18 Oct 2026).*

| Question | Result |
|---|---|
| Qloo alone, an AI alone, an AI checked by Qloo | How specific to the show the picks are (0 to 1, same 81 show-and-country pairs): Qloo alone 0.62, AI alone 0.81, AI checked by Qloo 0.86 (exploratory, not pre-registered). Of 1,615 names an AI proposed, Qloo's data supported 29% (462): it links them to that audience in that country. 66% are names Qloo knows; 71% are not supported, of which 34% (548) Qloo has no data on (a gap in Qloo's coverage, not proof the name is wrong) and 37% (605) Qloo knows but does not link to that audience. Only supported names go into a plan. |
| Next-country prediction, tested on 829 past cases it never saw | Counting all 829: its top 3 named a next country for 9.8% of cases against 4.1% for the three busiest countries, 2.4 times the baseline. Of the 113 that spread at all: 72% against 30%. For scale, a typical country charts a given show about 1% of the time (758 of 76,760 held-out pairs), so the featured 14% for Sweden is about 14 times that. Of the three held-out cases it was most sure about (a fixed rule), one hit: an Arabic series got popular in Kuwait in April 2026, and its top two predictions, Saudi Arabia (30%) and Oman (19%), both reached the Top 10 one week later. The other two did not spread. |
| Predictions recorded in advance | 3,240, each recorded before Netflix published the week it is graded on; grading is paused until Netflix permits reading its newer files. |

## Why it needs Qloo

An AI asked what a show's audience in a country loves answers fluently, and most of it cannot be told apart from a guess. Qloo is the check. It does three things a language model cannot:

- **It checks each name for one audience in one country.** Is this artist, brand, show or film linked to the viewers of this show in Sweden? Qloo confirms or does not, name by name, and only confirmed names reach the plan.
- **It maps where that audience lives.** Qloo's audience map gives the cities where a show's audience concentrates, and the same call gives them for each artist.
- **It overlaps two audiences.** Where an artist's audience map and the show's audience map meet gives a city for a quick event that no list of names can give.

## Inspiration: two kinds of aftershock

A trending show travels country by country: that is what we predict from Netflix history. The culture around it travels too: that is what Qloo maps. When Stranger Things 4 Volume 1 came out on 27 May 2022, English Wikipedia's article on Kate Bush's "Running Up That Hill" went from 349 views on 26 May to 43,521 on 31 May (Wikimedia Pageviews REST API, en.wikipedia, user agents, daily). The people who could act on that, a label, an artist, a brand, usually find out after the peak. Netflix itself now reports that its placements send songs back up the charts ([Music on Netflix: New and Nostalgic Songs Storm the Charts](https://about.netflix.com/news/music-on-netflix-new-and-nostalgic-songs-storm-the-charts)).

## What it does

- **Launch plans (start here).** Pick a trending show and a country. The agent works through visible steps, each with what it found and the rule it applied: prediction, ask Qloo what the audience likes, ask an AI for more names, check every AI name against Qloo, find the cities, match artists to cities, write the launch plan. When Qloo's own picks are clearly specific to the show (at least 60% different from the country's general taste), the partners lead with Qloo's picks and the AI names Qloo confirmed follow, labelled as such; platform brands such as Spotify are left out. The plan names partners to approach (artists and brands), what the audience also watches (for creative and ad targeting), quick-turn event ideas, and what the evidence does not support. Download, print or share it.
- **Live check box.** Type any artist, brand, show or film on the plan page; Qloo confirms or rejects it for that audience, now. Names Qloo has no data on are listed separately, never struck through.
- **For artists.** Every artist Qloo links to a trending show's audience has a page: whose viewers like their music far more than average, where, and the cities where both audiences concentrate. Artists that appear only in whole-country picks are tagged.
- **The globe.** The home page is a 3D globe of this week's trending shows: each country where a show just got popular pulses, arcs carry each show to its likeliest next countries, and clicking any country gives its chance and the reason in one line from Netflix history ("12 of 67 shows popular first in Denmark later reached Norway's Top 10 too"). Follow one show and Qloo's map of where its fans live rises out of the surface where that audience lives. Small countries (Malta, Singapore, Bahrain) get clickable markers.
- **Find my audience (new).** For something that has not launched yet, a film, series, album or comedy special, or an artist or comedian going on tour: Qloo ranks 24 countries (or every country in a region you pick) by Qloo's match score, maps the cities in the top three, finds venues there (comedy clubs, live music venues or cinemas, by Qloo place tag) and names the local shows, films and artists this audience also loves. If Qloo does not know the show yet, up to three comparables stand in for it. It asks what the release is, its goal (tour, premiere or digital only), a region to look deeper in, a home market to leave out, and the release month, which turns the plan into a dated schedule. The result is a world audience map of every country checked with a ranked list, city maps with each city's numbers, venues filtered to real performance spaces, and a "Why this ranking" panel that walks through each number. Every Qloo call the plan made is listed with its parameters. Names in other scripts work ("오징어 게임" finds Squid Game). Worked examples: Zakir Khan, Kevin Hart, Dua Lipa, and two unreleased shows planned from comparables.
- **Ask AFTERSHOCK.** A chat on every page answers from the site's own tools, no language model: where a show goes next, why it is heading to a country, why a show is not here, where a release could work, what any feature does. Every answer shows the steps it took.
- **Guided tour.** A 60-second tour that first says what AFTERSHOCK is, then highlights each feature; it runs on a first visit and from the Tour button.
- **Prediction history.** Each week's predictions were locked in a hash-chained prediction history before Netflix published the weeks they are graded on; grading waits for Netflix's permission. An MCP server exposes the same tools to any agent.

## Qloo calls we make

| Endpoint and parameters | What the agent decides with it |
|---|---|
| `GET /search` with `types`, then a strict name check | Resolves a typed or AI-proposed name. Only an exact normalized name counts, because `/search` always returns its nearest hit, even for names Qloo does not know. |
| `GET /v2/insights` with `filter.type` = `urn:entity:artist`, `tv_show`, `movie` or `brand`, `signal.interests.entities` = the title, `signal.location.query` = the country | The launch kit: what this title's audience over-indexes on there. |
| The same without `signal.interests.entities` | The country-only control: a kit that mostly repeats it is labelled countrywide, not title-specific. |
| The same with `filter.results.entities` = the ids of the AI's names | Confirms or rejects each AI name for this audience in this country. Also what the live check box asks. |
| `filter.type=urn:heatmap` with `signal.interests.entities` = the title and `filter.location.query` = the country | The cities where the title's audience concentrates (hotspots). |
| The same with an artist as the signal | Each partner artist's cities; a title city within 30 km of one of the artist's 5 strongest cells becomes an activation idea. |
| `filter.type=urn:entity:destination` with `signal.interests.entities` = the release (or its comparables) and `filter.geocode.country_code`, once per candidate country | Find my audience: ranks 24 countries by their best city's affinity for this audience. |
| `filter.type=urn:entity:destination` with `filter.geocode.country_code` and no signal | Names hotspot cells by the most popular Qloo destination within 35 km (popularity at least 0.5), so a brief says Stockholm, not the suburb Lidingö. |
| `filter.type=urn:entity:place` with `filter.tags` (comedy club, live music venue, concert hall or movie theater) near a city | Find my audience: venues that fit the kind of release in the top cities. |
| `filter.type=urn:demographics` with a show or artist as the signal | Age bands for Song check; with `urn:entity:artist` candidates, the ranking in Sync Scout. |

## Who would pay

Each buyer has one move that fits in the week between a trending show and its peak:

- **Brand marketers:** moment marketing on a show before it trends in their country (a meme, a scene, a line), and local ads in the show's fan cities, only for brands Qloo supports for that audience. The Head of Marketing at Nobero, a fashion brand, seeing it for the first time: *"Seeing in one glance what's trending."* What would make him trust it with budget: *"Previous success rate."* He said yes to trying one plan on a real campaign later (interest, not a pilot).
- **Labels:** push an artist's catalogue and a playlist to listeners in the cities where Qloo links that artist to the show's viewers.
- **Artists:** a post, a DJ set or a playlist push aimed at those cities while the show is in the Top 10.

Local media and creators can act fastest, on the same cities. Promoters use Find my audience to choose which cities to research for a tour.

What each output does not prove is written next to it: the launch plan has an "Evidence behind each claim" table (the claim, what supports it, what is still missing), and opens with the decision it supports. Every output is a shortlist for further research, a predicted opportunity, not a confirmed business one: we have not shown that any recommendation lifts streams, tickets or sales. We have no customers or pilots. **Business model hypothesis (untested):** a weekly per-country launch plan for brands, labels and agencies; artist pages free. We have not tested it with anyone.

## What it can't do

- Shows that launch worldwide on day one are not what it looks for (it needs a show popular in one country first), so it would not have flagged Stranger Things 4 or Wednesday.
- The warning is about a week. That suits short campaigns, memes, playlist pushes and local ads, not tours, which are booked months ahead.
- The country prediction uses Netflix history only. Qloo added no lift to it in our test.
- It watches Netflix only, because Netflix is the one major streamer we found that publishes a weekly Top 10 for each of 94 countries, back to 2021; we found no comparable per-country charts from other streamers, and third-party chart scrapers carry terms risk. That history is also what makes the prediction testable: it is how we backtested on 829 past cases and how every new prediction gets graded in public. The Qloo half (Qloo's picks, city maps, artist overlap, the live check) works for any show Qloo knows, from any platform.
- Qloo's picks and event ideas are not yet validated against outcomes, and grading of the locked predictions is paused until Netflix permits reading its newer files.

## What we measured, including what did not work

- **Qloo against an LLM (pre-registered in `docs/EXPERIMENT_KITS.md` before any data):** on 81 title-country pairs the LLM's kits were more title-specific than Qloo's (0.812 against 0.617, permutation p below 0.001), and it still led when only picks Qloo could resolve were counted. We report it as registered. Qloo's lists differed more between titles. The consequence is the design above: the LLM proposes, Qloo decides. The checked plan is the most title-specific of the three (0.86, exploratory: designed after the registered result).
- **Where next:** Netflix history alone reaches ROC AUC 0.817 on 829 held-out breakouts. Adding Qloo's in-country affinity gave no lift (0.8182 against 0.8188 on a 200-breakout subset), so the probability is history-only.
- **How much warning:** most breakouts never spread (113 of 829 did). When a pick did chart, the median lead was one week.
- **A result we threw away:** soundtrack-song spikes were not predicted by any Qloo signal on 229 artists (age gap p 0.14 against a placebo window). An earlier version built on Tunefind placements looked significant; when we read Tunefind's terms we removed that data from the product and the current repo (older commits still hold it, as the README states), rebuilt the ground truth from MusicBrainz and reran. The effect did not replicate, and the site says so.

## Data rights

Netflix publishes its weekly Top 10 lists on its Top 10 site, with download links for the files. We read the per-country file each week and credit Netflix; on 29 Oct 2026 we stopped every automated download until we have Netflix's permission. We have not asked Netflix for permission, and nothing here means Netflix approves of, endorses or is connected with AFTERSHOCK. Netflix's Terms of Use (section 1.8) restrict reproducing information from the Netflix service, automated access and data extraction, and use in connection with machine learning; whether they cover the public Top 10 files is not something we can settle, so this is a hackathon prototype, and any use beyond it would need Netflix's permission first. Qloo responses are cached privately and never committed. MusicBrainz (CC0), Wikimedia pageviews, OpenStreetMap Nominatim (ODbL, credited). Tunefind data dropped over its terms.

## Testing instructions for judges

**In a hurry? 30 seconds:** open https://aftershock-qloo.vercel.app in a private window. A five-second intro tells the idea; press "I'll explore", scroll to **See it in action** (a real prediction from this week: Nightwatch, popular in Denmark, 17% likely next in Norway, with the reason and the partners Qloo supports), then click **Open the full launch plan for Norway**.

**Try it on your own name, 1 minute:** open https://aftershock-qloo.vercel.app/#/release (Find my audience), type a comedian, artist or film and press Find its audience. It calls Qloo live (10 to 30 seconds; 10 live lookups per visitor per hour). Cedric the Entertainer, for example, comes back with the United States first (Atlanta, Memphis), then Nigeria and Mexico.

**The full tour, about eight minutes, no login, nothing to install:**

1. **Home:** the intro says what AFTERSHOCK is in three points, then a 60-second tour (both start on a first visit). Read the real prediction under "See it in action", then pick a show in the "Follow one show" row and click a country on the globe.
2. **Find my audience:** https://aftershock-qloo.vercel.app/#/release opens a worked example; type your own show (and comparables if Qloo does not know it yet). A live plan makes about 40 Qloo calls and takes 10 to 30 seconds.
3. **Ask AFTERSHOCK** (bottom right): try "why isn't Squid Game here?" or "why is Nightwatch heading to Norway?".
4. **Launch plans:** open https://aftershock-qloo.vercel.app/#/plan/nightwatch-demons-are-forever/NO (Nightwatch: Demons Are Forever in Norway, the example on the home page). The launch plan is at the top; download or print it, then watch the agent's steps replay underneath.
5. **Check a name live:** in the box under step 4, type any artist, brand, show or film; Qloo confirms or rejects it for this audience, now. Live lookups are capped per visitor.
6. **Any show's page:** Qloo's picks per country and "AI plan, checked by Qloo".
7. **For music artists:** https://aftershock-qloo.vercel.app/#/artist/veronica-maggio.
8. **Prediction results (top menu) and Prediction history (under More):** what we measured, including what went against us, and every recorded prediction.

From an AI agent: the MCP server (`python -m aftershock.mcp_server`, README section 5).

## Links

- Demo: https://aftershock-qloo.vercel.app
- Code: https://github.com/zaidwhy/aftershock (MIT)
- Demo video: (YouTube link to be added)  <!-- PLACEHOLDER for Zaid: paste the unlisted YouTube link before submitting -->

**Built with:** a fixed plan of tool calls with visible decision rules; the AI (Gemini `gemini-3.5-flash`) only proposes names and drafts a validated summary. python, fastapi, httpx, three.js (globe.gl), d3, mcp, qloo, gemini, musicbrainz, openstreetmap, netflix-top-10, wikimedia-pageviews, github-actions, vercel
