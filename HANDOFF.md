# AFTERSHOCK handoff

Deadline: Devpost, 30 Oct 2026 11:45pm EDT = 31 Oct 09:15 IST. Judges: 2-5 Nov (Discord says keys live to 16 Nov); top 3 present on air 5 Nov.

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

## Team plan (27 Oct)

- Teammate 1: Claude Desktop MCP demo with their own Qloo key; second tester. Optional short video for the Devpost gallery.
- Teammate 2: Devpost draft, team membership, gallery screenshots, Discord questions.
- Teammate 3 (first hackathon): phone test, friend test, number check against README, cover image.
- Site frozen for screenshots by 30 Oct 14:00 IST.

## State (overnight, 27 Oct)

See the end of this file for the latest results; everything below is committed locally on `main`.

## Decisions taken overnight (and why)

- SPILLOVER: Qloo in-country affinity added no AUC (0.8188 history vs 0.8182 with Qloo on 200 breakouts; Qloo had a value for 1.8% of pairs). The country forecast is history-only; Qloo supplies the partners list.
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
