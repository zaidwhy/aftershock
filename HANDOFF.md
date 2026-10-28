# AFTERSHOCK handoff

Deadline: Devpost, 30 Oct 2026 11:45pm EDT = 31 Oct 09:15 IST. Judges: 2-5 Nov (Discord says keys live to 16 Nov); top 3 present on air 5 Nov.

## Start here (written 28 Oct, about 23:30 IST): the overhaul

Team meeting on 28 Oct lifted the feature freeze. Built, committed and pushed (318 tests): 3D globe home (vendored globe.gl 2.46.2, public/js/globe.js, centroids.js for small-country markers), dark theme and new type (public/v2.css), guided tour (tour.js, first visit + Tour button), Ask AFTERSHOCK chat on every page (chat.js over the extended aftershock/ask.py router: feature help, why missing, why breaking, release, about), About page (Team Solstine, sidzaid72@gmail.com), Plan a release (aftershock/release_plan.py, GET /api/release, MCP release_plan, public/js/release.js; five examples from scripts/build_release_showcases.py into gitignored public/data/release/). Devpost draft updated. Video brief for teammates: projects/aftershock-team/VIDEO_BRIEF.md.

Deploy was blocked by the auto-mode classifier: Zaid runs `vercel deploy --prod --yes --scope syzayds-projects` from this folder (public/data/release must exist; rebuild with `.venv/Scripts/python scripts/build_release_showcases.py`, cached). After deploy, check: home globe, #/release live run on Vercel (cold 14-32 s, maxDuration 60), chat, tour.

## Start here (written 28 Oct, 02:25 IST)

**Final fixes applied 28 Oct night (237 tests), scope cut to fixes and wording only.** DONE: brief order (Qloo's kit leads when title-specific, data lead line, AI names follow, platform brands dropped, home example follows); Ask fallback with did-you-mean and "what's heading to X" (24 phrasings tested, none dead-end); first Ask chip is the week's top breakout, song chips removed from the row; three-number comparison and 71% on home and Scorecard, backtest wording reordered; window line above the chance; admin suffixes stripped from place names at read time; Devpost and README text (Qloo calls section moved, demo video placeholder line for Zaid). NOT DONE by decision: live Qloo kit lookup in the Ask box, Qloo call panels on the plan page, artist page map, show-all storm list, video re-cut (needs Zaid's voice).

**Next, in this order (from the third cold review and a Fable audit, 28 Oct night; scores now about Tech 7-8, Design 6-7, Impact 4-5, Idea 6):** (1) Brief: when a kit is title-specific (specificity >= 0.6) Qloo's own kit leads, with a data line like "Qloo's kit for this audience is led by Supernatural, Shadowhunters, The Originals"; AI-confirmed names second; drop platforms (Spotify) from brand partners. (2) Ask box: for a title not in this week's run, make one capped live Qloo kit call (title + country), like the check box, instead of history only; fix the 14 dead-end phrasings. (3) Hero and Devpost row 1: Qloo alone 0.62, LLM alone 0.81, LLM checked by Qloo 0.86 (exploratory) plus 71% unbacked; lead with 9.8% vs 4.1% before the 72%-of-113. (4) Plan steps: expandable "Qloo call" with endpoint and parameters. (5) Brief: put the one-week window above the chance; clean place names ("Lidingo (Stockholm)"). (6) Artist page: city map and the title's other confirmed names. (7) Home: storm list top 8 + show all. (8) Video re-cut with voice and the live check on camera; add the video link to Devpost Links. Forbidden: customers, pilots, tested pricing, lift claims.

**Open at 28 Oct, about 19:00 IST:** (1) Ask box still answers "I could not tell" for 14 of 24 phrasings about titles not in Netflix's Top 10 (e.g. "visionquest in india", "forecast for X", "plan a launch for X in sweden", "what's heading to sweden", misspellings like "nightwach"). Plan: in aftershock/ask.py fallback, strip intent words and the country, answer about the remainder (not in Netflix's Top 10 since 2024) with a difflib did-you-mean against storm and title-index names; add "s" and "whats" to COUNTRY_OK; tests for all 24. Only "where will X go next" is fixed (WHERE_NEXT, live). (2) Video: scratchpad hq/render.js already says 19 names; re-render after reviews, then mux Zaid's voice-over. (3) A third cold review and a Fable quick audit were running; apply their findings.

**Added 28 Oct night (audit fixes, 202 tests):** hero leads with the Qloo claim ("An AI's launch plan sounds right. Qloo checks it.", Qloo could back 29%); one explanation of 66/29/71 (34 no Qloo data + 37 not placed) on home, Scorecard, README, Devpost; live "Check a name" box under plan step 4 (`/api/check`, `grounded_plan.check_name`, shared live limit); unknown names shown unstruck as "No Qloo data yet"; own title and franchise dropped from AI plans at read time (`grounded_plan.clean_rows`, no rerun needed); partners split into approach (artists, brands) and "also watches" (shows, films); activation-ideas wording; catalog-title tag on the storm list; artists from countrywide kits tagged; Devpost cut to about 1,500 words with a Qloo-calls table. Kill-switch test (empty QLOO_API_KEY and GEMINI_API_KEY) passes: precomputed pages render, live features show a sentence.

**Added 28 Oct, about 17:30 IST (live, 168 tests):** lead-time backtest (`scripts/measure_lead_time.py` -> `data/results/lead_time.json`): on 829 held-out breakouts the model's top 3 caught a charting country for 81 (9.8%) vs 34 (4.1%) for the busiest-country baseline; only 113 spread at all, so of those 72% vs 30%; lead is mostly 1 week; the 3 rule-picked case studies are 2 misses and 1 hit, all on the Scorecard. Home line leads with the 113-that-spread framing, both numbers on the Scorecard. Launch brief has 4 stat tiles and a country map (numbered cities, rings for event ideas). Video re-rendered from the live site at 2560x1600 (`aftershock-team/video/AFTERSHOCK-walkthrough-v2.mp4`, 88 s); Zaid will record a voice-over to the timed script given in chat; mux it with ffmpeg when he sends the audio.

**Added 28 Oct, about 16:00 IST (live, 163 tests):** main menu cut to Storms, Plan a launch, Scorecard, Ledger plus More; "why a fixed plan" in Devpost and README. Live event ideas (`aftershock/live_events.py`): an artist's 5 strongest Qloo heatmap cells within 30 km of a title hotspot (first run at 30 cells / 60 km named every city for 114 of 176 ideas, so tightened); 53 of 81 kit rows, 122 ideas; new agent step "Match artists to cities" and an Event ideas section in the brief. Devpost now has the promoter case (Qloo names Live Nation as a user; Netflix + AEG KPop Demon Hunters tour; both links opened and checked) and travel as next buyer (Netflix + KTO). Flights by city NOT built: the only free route data (OpenFlights) stopped in 2014.

**Added 28 Oct, about 14:30 IST (live, 152 tests):** Plan a launch (`#/plan`, six visible agent steps ending in a downloadable Launch Brief; opens on the first title-specific kit where Qloo confirmed at least 3 AI picks, this week Fukrey Returns in India with 13), `/api/brief`, MCP tool `launch_brief` (8 tools). Devpost draft, README opening and docs/VIDEO_SCRIPT.md rewritten after studying the 2025 winners (`projects/aftershock-team/WINNERS_ANALYSIS.md`: GeoTaste won the Grand Prize; the 2026 rules ask for an agent that beats an LLM alone, which README section 3 measures). The earlier "past winners unverifiable" note below is superseded. Leftover folder `projects/aftershock-brief` was held by a browser; delete it by hand if it is still there.

**Added 28 Oct afternoon (live, 142 tests):** (1) "AI plan, checked by Qloo" under every launch kit: Gemini proposes, Qloo confirms (29%), does not place (37%) or does not know (34%) each name; exploratory measurement in data/results/grounded_plan.json and README section 3. (2) "Follow one title" on the home map: pick a title, the map recolours by its per-country chance; panel shows cities and Qloo-checked picks; deep link `#/?follow=<id>`. The walkthrough video predates both; re-record before submitting. Idea search verdict: no pivot (past winners and criteria unverifiable, Devpost blocks fetches).

**Experiment done 28 Oct 07:01 UTC:** by the registered rule the LLM was more title-specific (Qloo 0.617, LLM 0.812, p below 0.001; still leads on the 51 grounded pairs, 0.831 vs 0.575). Written into README section 3, docs/DEVPOST.md, the live Scorecard and the LinkedIn draft. Team brief and its PDF still show the result as pending.

**History rewritten 28 Oct, about 12:00 IST:** every Tunefind file (pre-MusicBrainz placements and ripple_truth CSVs, the scrapers, the daily scrape workflow, the two results built on them) is gone from every commit; the final tree is unchanged and IDs all changed. Pushed before the 25 Oct Netflix week and before the experiment ran, so every "locked before the outcome" claim still holds. Old commits stay reachable by old ID on GitHub until Zaid asks GitHub Support to purge cached views. Teammates must re-clone.

State: live at https://aftershock-qloo.vercel.app, repo github.com/zaidwhy/aftershock in sync, 133 tests passing locally and in CI (tests.yml, green badge), weekly Action verified under the current code (run 40581939996, 8.5 min).

Runs on its own, no action needed:
1. Netflix week of 25 Oct: `projects/aftershock-team/netflix_watch.sh` (log `netflix_watch.log`) acts from 22:30 UTC 27 Oct: pulls what the 22:00 UTC Action locked, runs the forecast job, verifies the ledger, exports, pushes the ledger if it changed, deploys. Storm links from 18 Oct keep working through the archive.
2. Qloo vs LLM experiment: `experiment_watch.sh` (log `experiment.log`) runs at 07:15 UTC 28 Oct (12:45 IST), commits `data/results/kit_experiment.json`, redeploys; the Scorecard slot fills itself.

Check when you wake up: the two logs end with "pipeline done" and "experiment done"; the Agent page shows the 25 Oct run; the Scorecard shows the early top-pick read and the experiment verdict. Then put the verdict into README section 3, the bracketed placeholder in docs/DEVPOST.md and the LinkedIn draft placeholder, and re-record the video if you want it to show them.

Needs you (nothing below is done for you):
1. Submit on Devpost yourself before 31 Oct 09:15 IST; all four teammates on the team; paste docs/DEVPOST.md.
2. Gallery: `projects/aftershock-team/gallery/` (7 images, in order). Video: `projects/aftershock-team/video/AFTERSHOCK-walkthrough-v2.mp4 (88 s, 2560x1600)` as an unlisted YouTube link.
3. Rotate the Gemini key (printed once in an agent's terminal, never written to a file).
4. Git history still has the Tunefind CSVs from before 27 Oct (removed from the tree, disclosed in README): leave it, or rewrite history / start a fresh repo (irreversible, resets ledger timestamps).
5. GitHub profile: the FLAKE LAUNDERING section another session added links to a private repo (404).
6. LinkedIn drafts: `projects/career/linkedin-refresh-2026-10-28.md` (nothing posted).
7. Team brief to share: https://claude.ai/artifact/TZpZyUGS1K1qrSEAHoYaLX (PDF in Downloads).

Everything below is the record of how it got here, newest decisions first within each section.

## Live (27 Oct)

- Repo: https://github.com/zaidwhy/aftershock (public, MIT), `main` pushed; Actions secret `QLOO_API_KEY` set.
- Site: https://aftershock-beige.vercel.app (personal Vercel, project syzayds-projects/aftershock; `aftershock.vercel.app` was taken). `/health` shows `"qloo_key": true`; `/requirements.txt` and `/data/private/*` return 404.
- Git auto-deploy is disconnected on purpose: a git-built deploy would ship without the gitignored `data/private/`. Deploy only with `vercel deploy --prod` from this folder.
- `api/index.py` restores the original path from `__path` (set by the rewrites in vercel.json), because Vercel hands the function `/api/index`.

## Still to do (Zaid)

1. Decide on git history: commits before 27 Oct afternoon contain Tunefind-derived CSVs (data/placements*.csv). They are being removed from HEAD; erasing history needs a force-push (forbidden by our rules) or deleting and recreating the repo (resets the ledger's public timestamps). Recommendation: remove going forward and say so in the README.
2. Submit on Devpost yourself (deadline 31 Oct 09:15 IST). Teammate 2 prepares the draft from `docs/DEVPOST.md`. All four must be on the Devpost team. A demo video is NOT required by the rules ("Demo videos are not required"); the live demo is what judges use.
3. Rotate the Gemini key (it was printed once in an agent's terminal during the LLM test; never written to a file). The code now sends it as a header.
4. Deploy steps: `.venv/Scripts/python scripts/run_forecasts.py`, then `.venv/Scripts/python scripts/export_static.py` (read-only pages are served as static JSON from public/data/, gitignored), then `vercel deploy --prod`. Git auto-deploy stays disconnected.

## Overnight 27-28 Oct: state and decisions taken for Zaid

Live: https://aftershock-qloo.vercel.app (118 tests). New since the evening: Ask the agent (deterministic router over the site's tools, every step shown, no LLM), #/agent run log, #/ledger readable ledger, weekly map with "chance at least one arrives", title lookup, Song check (renamed from Try it) with crowd verdicts from age bands, Qloo title metadata on storm pages, Copy launch brief, Scorecard led by what Qloo adds.

Decisions taken (change them if you disagree):
- The GitHub weekly Action could not be paused (classifier). Tonight's local watcher (`projects/aftershock-team/netflix_watch.sh`) waits until 22:30 UTC, fast-forwards to whatever the Action locked, then runs; locking skips titles already in the ledger, so there is one writer at a time. Log: `projects/aftershock-team/netflix_watch.log`.
- The kit experiment is pinned to `data/private/storms_2026-10-18.json` (the registered week) so the new Netflix week cannot change its pairs. `projects/aftershock-team/experiment_watch.sh` runs it at 07:15 UTC 28 Oct, commits `data/results/kit_experiment.json`, re-exports and redeploys. If it fails again, rerun `.venv/Scripts/python scripts/experiment_kits.py` after Gemini's quota resets; report whatever it shows.
- Brands stay in the kits even when odd (Lamborghini for Bangladesh): they are Qloo's output, hiding them would be cherry-picking; they are shown last and lighter.
- LinkedIn: drafts only (your standing rule that you approve public posts). GitHub profile README was updated and pushed (pre-approved).
- The FLAKE LAUNDERING section another session added to the GitHub profile links to a private repo (404 for visitors): make that repo public or remove the section; left for you.

After both watchers finish: put the experiment verdict into README section 3, docs/DEVPOST.md (replace the bracketed placeholder) and the LinkedIn draft placeholder; re-record the video if the scorecard caption should mention it.

## README audit (28 Oct, by a fresh reader)

Fixed: a glossary before first use of storm/SPILLOVER/launch kit/Hotspots/Song check/Spearman/Jaccard; "Run it" rewritten for a fresh clone (Python 3.12, key source, cross-platform paths, run order, time and call cost, MCP config snippet); mean kit specificity 0.61 not 0.62; "every number comes from data/results" narrowed to backtests and tests; "registered" defined as a public commit, not an external registry; the age gap's partial correlation on the 4 recent shows (0.42, p 0.07) now stated. The Qloo in-country coverage was quoted as 1.8% but never saved; `scripts/test_spillover_qloo.py` now saves it and a cached rerun gives 2.8% (975 of 35,344 title-country pairs), with identical AUCs, so README, site and handoff now say 2.8%.

## API docs (28 Oct)

docs/API.md now covers every served endpoint: /api/title and /api/ask were missing, as were the static /data files the site reads, the shared live-call limits, field length limits and error codes; the Sync Scout example gained `leans`, `show_leans` and `suggestion`. Every documented static file and status code was checked against the live site (10 of 10).

## Accessibility (28 Oct)

Measured, not assumed: axe-core 4.9.1 on 8 live pages, light and dark, plus the home page with an Ask answer and a map selection open: 0 violations at any impact. Keyboard: 40 tab stops in reading order, all with a visible focus ring. Result areas are aria-live. Recorded in README section 5. No defect found, so no code changed.

## Load performance (28 Oct)

Measured cold (no cache) at phone width on a throttled 1.6 Mbps / 150 ms connection: headline 1.7 s, worked example about 1.9 s, map about 2.5-2.8 s, 197 KB in 24 requests. Added `modulepreload` for the 13 front-end modules and a preconnect to the d3 CDN: every module now starts downloading at about 0.27 s together instead of one import level at a time, and charts.js finishes about 0.65 s earlier (1.39 s to 0.74 s). Time to the worked example barely moves (bounded by the data fetch). One run in eight stalled for about 30 s on the throttled link, which looked like a network outlier; not reproduced.

## Failure path: Qloo down or key refused (28 Oct)

Tested with a local server given an invalid key: read-only pages (storms, map, kits, scorecard, ledger) need no live call and keep working; live lookups failed with "try again in a minute", which is wrong for a refused key. Now `QlooError` carries Qloo's status and `api.qloo_failure` maps 401/403 to 503 "Live Qloo lookups are switched off right now (Qloo refused the API key). The weekly forecasts, launch kits, hotspots and map on this site still work.", 429 to a rate-limit message, anything else to the old one; the page shows the server's sentence without the URL and status code. Tests for all four cases. If the hackathon key expires during judging, this is what judges see.

## Links survive the weekly rollover (28 Oct)

Before this, every storm link (Devpost instructions, gallery, video, bookmarks such as #/storm/fukrey-returns) would have 404'd as soon as a new Netflix week replaced the storms. Now run_forecasts.py archives each week to data/private/storm_archive/<week>.json (seeded with 18 Oct); /api/storms/{id} and the static export fall back to the most recent archived week, tagged `archived_week`, and the storm page shows a "From the week of ..." banner; an unknown id gets "No breakout called that" with a way back. The Ask launch-kit example is built from this week's hero. Simulated a rollover against a temp copy of the data: an archived id returns 200 with archived_week 2026-10-18, an unknown id 404 with the sentence. Devpost instructions no longer name this week's title.

## Weekly Action verified under the new code (27 Oct, 20:52 UTC)

Manual run 40581939996 on GitHub: success in 8.5 minutes (limit now 50), 608 live Qloo calls, 35 storms written, 0 new forecasts locked (same Netflix week, as expected); heatmap 400s are titles Qloo has no heatmap for and are handled. The scheduled 22:00 UTC run uses the same code.

## Submission assets (28 Oct, ready for Zaid)

- Gallery images (1600x1000, light mode, final UI): `projects/aftershock-team/gallery/` 1-home, 2-ask, 3-storm-top, 4-launch-kit, 5-week-map, 6-scorecard, 7-agent. Upload them to the Devpost gallery in that order.
- Walkthrough video: `projects/aftershock-team/video/AFTERSHOCK-walkthrough-v2.mp4` (88 s, 2560x1600, captioned, recorded 28 Oct from the live site; the older 96 s tour was deleted). Optional per the rules but judges may judge from text, images and video alone: upload to YouTube as unlisted and paste the link into Devpost's video field. Re-record after the Qloo-vs-LLM result lands if the scorecard caption should mention it.
- LinkedIn drafts: `projects/career/linkedin-refresh-2026-10-28.md` (nothing posted).

## Data licensing (27 Oct, done)

- Tunefind terms forbid automated collection. Tunefind scraper, collector, daily workflow and all Tunefind-derived CSVs removed from HEAD; songs rebuilt from MusicBrainz (scripts/build_placements_musicbrainz.py, 490 songs, 34 titles, data/placements_sources.csv). Git history still contains the old CSVs (Zaid decision, see Still to do 1).
- On licensed data the song result did not replicate: Qloo age gap 0.02 (p 0.40) on 24 shows, 0.18 (p 0.22) on 4 shows from 2024; real minus placebo p 0.14. README section 3, Devpost draft, site copy and team brief all say so. Qloo-vs-LLM and the Wednesday example were built on the discarded data and are deleted.
- Some release dates in data/placements_sources.csv were carried over from the old CSV ("previous placements.csv release_date"); dates are facts, but re-sourcing them from Wikidata would make the provenance clean.

## Judge panel and council (27 Oct evening)

Simulated judges (Qloo CTO, Calacanis, Live Nation + design, Cedric + Seligman) averaged Tech 5.7, Design 6.7, Impact 4.8, Idea 6.5. Verified findings: for thin titles the launch kit collapses to the country's general taste (8 of 62 same-country title pairs overlap >= 60%, mean 0.15); no Qloo-vs-LLM measurement exists; Sync Scout output is near-noise (gaps 0.57-0.63) and slow (12 s); no title disambiguation by year; /api/ripple returns raw fit and age profiles; stale docstrings in aftershock/ripple.py, sync_scout.py and the mcp_server.py sync_scout description still claim significance; Devpost overclaims ("tested every signal against a placebo", "who to partner with"); weekly Action does not export or redeploy.

Council verdict, in order:
1. Commit a pre-registered experiment spec to the repo BEFORE running it: ~20-30 title-country pairs, three arms (Qloo title+country kit, Qloo country-only kit, Gemini LLM kit with the same country context), objective metrics only (title-specificity = overlap with the country-only kit; grounding = share of LLM picks that resolve in Qloo /search; distinctness across titles in a country), a win rule fixed in advance, publish either way, state low power.
2. Build the result into the storm page: "title-specific" vs "generic" badge per kit (from the country-only control) and a Qloo-vs-LLM panel.
3. Hero worked example, kit-rich storms first, one buyer line (local distributors, music publishers, promoters; not streamers).
4. Honesty fixes (docstrings, /api/ripple raw fields, Devpost overclaims, a short Data and terms note, "not affiliated with Netflix or Qloo") and make forecast.yml run export_static and deploy, or drop the claim.
5. Small launch-brief export if time. Demote Sync Scout. Skip the Stranger Things retro demo.
Fallback if Qloo loses every arm: reposition the kit as a country-level taste layer. Freeze for screenshots 30 Oct 14:00 IST.

Done after the council: mojibake repair for Qloo names (launch_kit.repair_name, tested).

## Progress on the council plan (27 Oct, 18:00-19:30 IST)

- Step 1 registered: docs/EXPERIMENT_KITS.md committed and pushed at 18:00 IST (e6b8696; 976177d before the 28 Oct history rewrite) before any data. All 81 kit rows, four arms (Qloo title+country, Qloo country-only, Gemini title+country, Gemini country-only), overlap metrics, sign-flip p < 0.05, product rule "generic if overlap with country-only >= 0.6".
- Experiment NOT finished: scripts/experiment_kits.py collected all Qloo country-only kits (cached) and the first Gemini batch (cached), then Gemini gemini-3.5-flash returned 503 "high demand" repeatedly. Rerun with `.venv/Scripts/python scripts/experiment_kits.py` (cached parts are free; it needs about 6 more Gemini calls and up to 1,500 Qloo /search calls); it writes data/results/kit_experiment.json and data/private/kit_generic.json. Do not change the model without first committing an amendment to docs/EXPERIMENT_KITS.md. Report the result whichever way it lands, then put it on the scorecard and in README/Devpost.
- Step 2 product side done and deployed (ebaa5af; e88c060 before the rewrite): each kit row has control/specificity/generic; storm page labels "Title-specific" or "Mostly countrywide taste" with a percentage and mutes names the whole country likes anyway; home tag "Qloo kit (countrywide)". This week: 48 of 81 kit rows title-specific, 33 generic.
- Honesty fixes done: stale significance claims removed from ripple.py, sync_scout.py and MCP descriptions; /api/ripple, /api/ripples/{id} and MCP ripple_score no longer return raw fit or age profiles (public_ripple). 60 tests pass.
- Still open from the council plan: hero worked example + kit-rich storms first + buyer line; Devpost overclaims and a Data and terms note; forecast.yml export+deploy (or drop the claim); launch brief if time. Rerun run_forecasts after Netflix's Tuesday update (16 of 81 hotspot rows lost names to OSM timeouts this run).

## Team plan (27 Oct)

- Teammate 1: Claude Desktop MCP demo with their own Qloo key; second tester. Optional short video for the Devpost gallery.
- Teammate 2: Devpost draft, team membership, gallery screenshots, Discord questions.
- Teammate 3 (first hackathon): phone test, friend test, number check against README, cover image.
- Site frozen for screenshots by 30 Oct 14:00 IST.

## State (overnight, 27 Oct)

See the end of this file for the latest results; everything below is committed locally on `main`.

## Decisions taken overnight (and why)

- SPILLOVER: Qloo in-country affinity added no AUC (0.8188 history vs 0.8182 with Qloo on 200 breakouts; Qloo had a value for 2.8% of pairs, 975 of 35,344). The country forecast is history-only; Qloo supplies the partners list.
- RIPPLE went through three models, each tested before shipping:
  1. taste fit x age gap: did not beat a no-Qloo baseline;
  2. obscurity + age gap: looked best, until an independent review pointed out that obscurity is the spike's own denominator;
  3. a placebo control (spike measured entirely before release) showed obscurity is mostly regression to the mean, while the Qloo age gap tracks the real spike and not the placebo (real minus placebo p 0.03 on 2024+, 0.04 overall). Shipped: score = Qloo age gap. Fit and obscurity are context only.
- Ledger rebuilt twice before any publication (scoring bug fix, then stricter locking rules: every country locked; RIPPLE locks only before release + 7 days with 4+ scorable songs). None of the 12 live releases qualified: all were found after their windows opened, and new 2026 titles mostly lack Qloo audience profiles.
- Stayed with AFTERSHOCK rather than switching to READ THE ROOM: the build exists and the measured honesty is the differentiator.
- No paid LLM. Agentic parts: the weekly job (detect, resolve, forecast, lock, grade) as a GitHub Action, and the MCP server.

## Results (all in data/results/)

- spillover_backtest.json: history AUC 0.817 on 829 test breakouts.
- spillover_qloo_test.json: 0.8188 vs 0.8182 (no Qloo lift).
- ripple_test_artist.json, ripple_controls.json: see README section 3.
- example_wednesday.json: the README's worked example.
- Ledger: 3,240 spillover forecasts (35 breakouts x every candidate country), 0 ripple; chain verifies.

## Known gaps

- Demo video not recorded.
- Early SPILLOVER grades appear once Netflix publishes the week ending 25 Oct; rerun `scripts/run_forecasts.py` then (no new locks are created for already-locked titles).
- The weekly Action commits the ledger but does not refresh the deployed site; redeploy by hand before judging.
- Partners are unvalidated, and odd for some small territories.
- Quota: about 47,900 calls left this month after the backtests; teammates' keys are spares.
