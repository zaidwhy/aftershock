**In three lines.** When a Netflix show gets popular in one country, it often spreads to the next. AFTERSHOCK predicts which country is next, from Netflix's own history. Then an AI suggests launch partners for that audience, Qloo's taste data decides which ones stay, and you get a launch plan you can act on inside the one-week window.

**Shows travel. See where next.**

| The old way | With AFTERSHOCK |
|---|---|
| A marketer notices a show is trending after it peaks | The show is spotted the week it enters one country's Top 10 |
| The next country is a gut call | The next country is ranked from Netflix's own history, with the reason shown |
| Partners come from a brainstorm or a chatbot | An AI suggests; Qloo keeps only the names its data supports for that audience in that country |
| Cities and venues are researched by hand | Qloo's audience maps and places name the cities and the venues |

Parrot Analytics measures how much a country wants a show; Chartmetric tracks which artists and songs are rising. Neither is built to say who to partner with, in which city, this week.

*Numbers are as of submission (Netflix week of 18 Oct 2026).*

## Inspiration

On 26 May 2022, the Wikipedia page for Kate Bush's *Running Up That Hill* got **349** views. Five days later, after *Stranger Things 4* came out, it got **43,521**. A 37-year-old song had just been struck by lightning, and almost everyone who could have used that moment (a label, the artist's team, a promoter, a local brand) found out after the peak.

That one was a worldwide release, so it hit everywhere at once. But most shows don't move like that. They get popular in **one country** first, and a week later they turn up in the next one, then the next. Like an earthquake and its aftershocks. That gave us the name, and a question:

*If you can feel the first tremor, can you say where the next one lands, and who should be standing there when it does?*

So we tested it the hard way. We hid 829 past cases from our model and, by a rule fixed in advance, took the three it was most sure about. One was an Arabic series, *دروب أريكة*, popular in Kuwait in the week of 26 Apr 2026: AFTERSHOCK's top two picks, Saudi Arabia (30%) and Oman (19%), both reached their Top 10 the very next week. The other two never left home. That is the honest shape of the problem: most shows never travel, and when one does, the prediction usually names where.

## What it does

AFTERSHOCK reads Netflix's weekly Top 10 lists for 94 countries and spots shows and films that just got popular in only one to three of them. Then it does three things:

1. **Predicts the next country.** From Netflix's own history, with a reason anyone can read: *"12 of 67 shows popular first in Denmark later reached Norway's Top 10 too."*
2. **Lets an AI suggest, and Qloo decide.** Gemini suggests artists, brands, shows and films that the audience in that country should love. Qloo checks every single name against *that* audience in *that* country. What Qloo's data supports stays; what it can't support is struck out on screen, in public.
3. **Hands you a launch plan.** The window, the cities where the fans actually live (from Qloo's audience maps), quick event ideas where an artist's fans and the show's viewers overlap, and one move each for a brand, a label, an artist and a distributor. Each claim comes with what supports it and, in amber, what is still unproven.

And because not everything starts on Netflix: **Plan my release.** Type a film, an album, a comedy special or an artist going on tour, even one that isn't out yet (give it a few look-alikes). Qloo ranks the countries, maps the cities, finds the comedy clubs, concert halls or cinemas there, and tells you what that audience also loves locally. Type *Kevin Hart* and you get Orlando, Miami and Las Vegas, plus SAK Comedy Lab and Jimmy Kimmel's Comedy Club.

Around it: a 3D globe where this week's shows glow and the arcs fly to where they go next, a real prediction you can read in ten seconds on the home page, an **Ask AFTERSHOCK** chat that answers from the site's own tools and shows its working, a guided tour that starts by saying what the product is, and a public history of every prediction.

The one sentence we kept coming back to: **the AI suggests, Qloo decides.**

## A real marketer's first look

We showed the site to the Head of Marketing at Nobero, a fashion brand, as a first-time visitor. In his words:

- What he found valuable: *"Seeing in one glance what's trending."*
- What he would do with a plan: *"Will see if we can pickup anything from that show / movie and use it in our marketing. Example a relevant meme or relevant dialogue or image / scene"*, for the brand's moment marketing.
- What he would use most: *"Next likely country."*
- What would make him trust it with budget: *"Previous success rate."* That is exactly why every prediction is tested on past cases and recorded in advance (below).

He also said yes to trying one plan on a real campaign later. That is interest, not a pilot, and we say so. His feedback also made us rewrite the whole site in plain words: "trending show" instead of our own jargon.

## How we built it

- **The prediction.** Weekly per-country Top 10 lists going back to 2021. For each show that got popular in one country, a model learned from history how often each other country follows. We held out 829 cases it never saw and asked it to name its top 3 next countries. The fair opponent is the obvious guess: the 3 countries where the most shows chart.

$$\text{lift} = \frac{\text{AFTERSHOCK's hit rate}}{\text{obvious guess}} = \frac{9.8\%}{4.1\%} \approx 2.4\times$$

  For the 113 shows that spread at all, its top 3 named the next country **72%** of the time, against 30%. It also ranks a country that went on to chart above one that didn't 82% of the time (ROC AUC 0.82, where 0.5 is a coin flip).
- **The Qloo half.** `/v2/insights` for what an audience likes far more than average in a country; the same call *without* the show as a control, so picks that just repeat the country's general taste are labelled as such; a filtered call (`filter.results.entities`) that supports or rejects each AI name; `urn:heatmap` for the cities; `urn:entity:destination` to rank countries for a new release; `urn:entity:place` with venue tags for the venues.
- **The agent.** A fixed plan of visible steps. We chose that on purpose: a plan someone acts on has to say why every name is in it, and an agent that picks its own steps could quietly skip the Qloo check.
- **The stack.** Python and FastAPI on Vercel, a vanilla JavaScript front end with a three.js globe (globe.gl) and d3 maps, a weekly GitHub Action (paused until Netflix permits it), an MCP server with ten tools so any AI agent can use it, and a hash-chained prediction history where each line carries a fingerprint of the one before. 436 automated tests.

## Challenges we ran into

- **An AI that sounds right.** Ask an AI what Swedish viewers of a Danish horror film love, and it answers beautifully. Then we checked 1,615 of those names against Qloo: only **29%** were ones Qloo links to that audience in that country. 37% Qloo knows but doesn't link to those viewers; 34% Qloo has no data on at all (a gap, not proof they are wrong). That one number is why the AI only gets to suggest.
- **Qloo's search is too helpful.** `/search` always returns its nearest match, even for names it has never heard of. We built a strict name check, or the agent would have "confirmed" impostors.
- **Travel brochures, not tour plans.** Our first city list for a musician started with Agra (lovely, the Taj Mahal is there, not a tour stop). Qloo's destination data is travel-flavoured, so we keep only the cities where Qloo's audience map is densest, with a popularity floor to drop villages.
- **The suburb problem.** Our featured plan said to start in *Lidingö*. Very nice island. Nobody's marketing plan says Lidingö. Each city is now named after the best-known place within 35 km, so it reads *Stockholm*. (At 50 km, Neuchâtel turned into Bern, so 35 it is.)
- **A comedy club that was also a homeopath.** Real Qloo place tags: *Comedy club, Mental health service, Homeopath*. We now drop any venue whose tags aren't a real stage.
- **오징어 게임.** A teammate typed *Squid Game* in Korean and got nothing. Qloo knew the title all along under its other names; our matcher didn't. Fixed, and any script works now.
- **Our own jargon.** A first-time visitor told us he couldn't tell what the site was. We had written "breakouts", "kits" and "ledgers" everywhere. We rewrote every page so it answers three questions in five seconds: what is this, what makes it special, why try it.

## Accomplishments that we're proud of

- **We kept the result that went against us.** We registered our main experiment in the public repo before running it. The AI's lists came out *more* specific to the show than Qloo's (0.81 against 0.62). We published that, and it changed the design: the AI suggests for specificity, Qloo checks for grounding. The combined plan scored highest, 0.86 (labelled exploratory, because we designed it after seeing the result).
- **We threw away our best-looking result.** An early song test looked significant. Then we read the terms of the site we had collected it from, removed that data from the product and the current repo (older commits still hold it, and the README says so), rebuilt the data from MusicBrainz and reran. The effect didn't replicate. The site says so.
- **Every prediction is on the record.** 3,240 predictions, recorded before Netflix published the weeks they are checked against. No quiet edits.
- **A real user's words on the home page**, quoted exactly, with his permission.

## What we learned

- **Grounding beats fluency.** An AI is a great idea generator and a poor source of truth about a specific audience in a specific place. Qloo is the opposite kind of tool, and the two together beat either alone.
- **Most shows never travel** (only 113 of 829 did). So a good prediction is a shortlist, not a crystal ball, and saying that plainly makes people trust the rest.
- **The window is about a week** (117 of the 131 predicted countries a show reached were reached one week after it got popular). Too short for a tour; just right for a meme, a post, a playlist push, a club night or a local ad.
- **Plain words win.** The product didn't change when we rewrote the site; whether a newcomer understood it did.
- **Read the terms before you build on the data.** It cost us our headline once. Never again.

## What's next for AFTERSHOCK

- **Permission first.** We have no permission from Netflix and claim none; its Terms of Use restrict automated access and reuse. On 29 Oct we stopped every automated download. Before AFTERSHOCK is anything more than a prototype, we would ask Netflix, and any other chart (music, video, other platforms) plugs in only once its terms allow it.
- **Grade it in public, once permitted.** Then the 3,240 recorded predictions are checked against what really happened, misses included.
- **Demand where there is no release.** With streaming-availability data, flag countries where Qloo sees the audience but the show isn't on Netflix there yet, so a distributor can license it.
- **Tours and live shows.** Plan my release already handles comedians and touring artists. Next: event calendars, so a promoter sees open dates next to the audience.
- **A first real test with a brand, a label or a promoter**, to measure what no backtest can: whether acting on a plan moves streams, sales or tickets. Until then, every plan is a shortlist to research, not a promise.
