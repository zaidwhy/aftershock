## Inspiration

On 26 May 2022, the Wikipedia page for Kate Bush's *Running Up That Hill* got **349** views. Five days later, after *Stranger Things 4* dropped, it got **43,521**. A 37-year-old song had just been struck by lightning.

Here is the part that bugged us: the people who could have done something with that wave (a label, an artist's team, a promoter, a local brand) mostly found out *after* the peak. By the time the playlist pitch is written, the moment has passed.

Then we noticed something about how hits move now. A show doesn't always explode everywhere at once. Often it breaks out in **one country**, and a week later it turns up in the next one, and the next. Like an earthquake and its aftershocks.

So we asked: if you can see the first tremor, can you say where the next one lands, and who should be standing there when it does?

## What it does

**Every hit has an aftershock.** AFTERSHOCK watches Netflix's public Top 10 lists for 94 countries every week and catches titles that just broke out in one to three of them. Then it does three things:

1. **Forecasts where it lands next.** From Netflix's own history, with a reason you can read: *"Norway joined 12 of 67 past breakouts that started in Denmark."*
2. **Asks an AI for a launch plan, then lets Qloo decide.** Gemini proposes artists, brands, shows and films that the audience in that country should love. Qloo's taste graph checks every single name for *that* audience in *that* country. What Qloo backs stays; what it can't back gets struck out on screen, in public.
3. **Hands you a Launch Brief.** The window, the cities where the audience actually lives (from Qloo's heatmaps), quick activations where an artist's fans and the show's viewers overlap, one move each for a label, an artist, a brand and a distributor. Each claim comes with what supports it and, in amber, what is still unproven.

And because not everything starts on Netflix: **Plan a release.** Type a film, an album, a comedy special, or an artist going on tour, even one that isn't out yet (give it a few look-alikes). Qloo ranks the countries, maps the cities, finds the comedy clubs, concert halls or cinemas there, and tells you what that audience also loves locally. Type *Kevin Hart* and you get Orlando, Miami and Las Vegas, plus SAK Comedy Lab and Jimmy Kimmel's Comedy Club.

Wrapped around it: a 3D globe where the breakouts pulse and the arcs fly, an **Ask AFTERSHOCK** chat that answers from the site's own tools and shows its working, a guided tour, and a public ledger of every forecast.

The one sentence we kept coming back to: **the AI proposes, Qloo decides.**

## How we built it

- **The forecast.** Weekly per-country Top 10 lists going back to 2021. For each breakout, a model learned from history how often each country follows each origin. We held out 829 breakouts it never saw and asked it to name its top 3 next countries. The fair opponent is the obvious guess: the 3 countries that chart the most titles.

$$\text{lift} = \frac{\text{AFTERSHOCK's hit rate}}{\text{obvious guess}} = \frac{9.8\%}{4.1\%} \approx 2.4\times$$

  For the 113 breakouts that spread at all, its top 3 named a next market **72%** of the time, against 30%. It also ranks a country that went on to chart above one that didn't 82% of the time (ROC AUC 0.82).
- **The Qloo half.** `/v2/insights` for what an audience over-indexes on in a country; the same call *without* the title as a control, so a kit that just repeats the country's general taste is labelled countrywide; a filtered call (`filter.results.entities`) that confirms or rejects each AI name; `urn:heatmap` for the cities; `urn:entity:destination` to rank countries for a new release; `urn:entity:place` with venue tags for the venues.
- **The agent.** A fixed plan of visible steps. We chose that on purpose: a brief someone acts on has to say why every name is in it, and an agent that picks its own steps could quietly skip the Qloo check.
- **The stack.** Python and FastAPI on Vercel, a vanilla JavaScript front end with a three.js globe (globe.gl) and d3 maps, a GitHub Action that runs every week, an MCP server with ten tools so any AI agent can use it, and a hash-chained ledger where each forecast carries a fingerprint of the one before. 433 automated tests.

## Challenges we ran into

- **An AI that sounds right.** Ask an LLM what Swedish viewers of a Danish horror film love, and it answers beautifully. Then we checked 1,615 of those names against Qloo: only **29%** were ones Qloo links to that audience in that country. 37% Qloo knows but doesn't place with those viewers; 34% Qloo has no data on at all. That single number became the reason the AI only gets to propose.
- **Qloo's search is too helpful.** `/search` always returns its nearest match, even for names it has never heard of. We had to build a strict name check, or the agent would have "confirmed" impostors.
- **Travel brochures, not tour plans.** Our first city list for a musician started with Agra (a lovely place, the Taj Mahal is there, not a tour stop). Qloo's destination data is travel-flavoured, so we now keep only the cities where Qloo's *audience heatmap* is densest, with a popularity floor to drop villages.
- **The suburb problem.** Our featured brief said to start in *Lidingö*. Very nice island. Nobody's marketing plan says Lidingö. Each hotspot is now named after the best-known city within 35 km, so it reads *Stockholm*. (At 50 km, Neuchâtel turned into Bern, so 35 it is.)
- **A comedy club that was also a homeopath.** Real Qloo place tags: *Comedy club, Mental health service, Homeopath*. We now drop any venue whose tags aren't a real stage.
- **오징어 게임.** A teammate typed *Squid Game* in Korean and got nothing. Qloo knew the title all along under its alternate names; our matcher didn't. Fixed, and now any script works.
- **One stray parenthesis** took the whole site down on the night before a review. We now have a test that parses every front-end file.

## Accomplishments that we're proud of

- **We kept the result that went against us.** We registered our main experiment in the public repo before running it. The LLM's lists came out *more* title-specific than Qloo's (0.81 against 0.62). We published that, and it changed the design: the LLM proposes for specificity, Qloo verifies for grounding. The combined plan scored highest, 0.86 (labelled exploratory, because we designed it after seeing the result).
- **We threw away our best-looking result.** An early song test looked significant. Then we read the terms of the site we had collected it from, deleted every byte, rebuilt the data from MusicBrainz and reran. The effect didn't replicate. The site says so.
- **Every forecast is on the record.** 3,240 forecasts, locked in a public ledger before Netflix published the weeks they are graded on. No quiet edits.
- **One real hit from the backtest that we love:** an Arabic series broke out in Kuwait in April 2026. AFTERSHOCK's top two picks, Saudi Arabia (30%) and Oman (19%), both charted the very next week.

## What we learned

- **Grounding beats fluency.** An LLM is a great idea generator and a poor source of truth about a specific audience in a specific place. Qloo is the opposite kind of tool, and the two together beat either alone.
- **Most breakouts never travel** (only 113 of 829 did). So a good forecast is a triage tool, not a crystal ball, and saying that plainly makes people trust the rest.
- **The window is about a week** (117 of the 131 forecast countries that charted did so one week after the breakout). That is too short for a tour and just right for a playlist push, a post, a club night or a local ad. Knowing who it is *not* for sharpened who it *is* for.
- **Read the terms before you build on the data.** It cost us our headline once. Never again.

## What's next for AFTERSHOCK

- **Grade it live.** The first forecasts are graded from 15 November, in public, misses included.
- **More charts, with permission.** Netflix is the only streamer we found that publishes per-country weekly charts. Any other chart (music, video, other platforms) plugs straight into the same forecast once its terms allow it.
- **Demand where there is no release.** With streaming-availability data, flag countries where Qloo sees the audience but the title isn't offered yet, so a distributor can license it there.
- **Tours and live shows.** Plan a release already handles comedians and touring artists. Next: event calendars, so a promoter sees open dates next to the audience.
- **A first real test with a label or promoter**, to measure what no backtest can: whether acting on a brief actually moves streams, tickets or sales. Until then, every output is a shortlist for research, not a promise.
