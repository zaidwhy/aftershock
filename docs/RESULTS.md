# What we measured, including what did not work

Every backtest and test number here comes from a script in this repo and a file in `data/results/`. Counts that describe the current week (kits, titles indexed) come from the weekly run's output, which holds Qloo-derived data and is not committed; the site and its Agent page show them.

**SPILLOVER** (`scripts/backtest_spillover.py` -> `spillover_backtest.json`; 8,696 training and 829 test breakouts, March to October 2026, 4-week horizon):

| Model | ROC AUC | Top-5 precision |
|---|---|---|
| Netflix history | 0.817 | 0.041 |
| Each country's general rate | 0.558 | 0.015 |
| Uniform | 0.500 | 0.012 |

ROC AUC 0.817 means the model ranks a country that went on to chart above one that did not 82% of the time.

**How much warning the spillover forecast gives** (`scripts/measure_lead_time.py` -> `lead_time.json`; a backtest on history-only forecasts, same 829 held-out breakouts, split, model and 4-week horizon as above; the forecast week is the breakout week and the model is fit on earlier breakouts only). Top-3 hit rate is the share of breakouts where at least one of the three forecast countries charted the title within 4 weeks; the baseline is the three countries with the highest overall join rate (the "general rate" row above: Maldives, Singapore, Malaysia for nearly every title).

| | Model's top 3 | Baseline top 3 |
|---|---|---|
| Breakouts with at least one hit | 81 of 829 (9.8%) | 34 of 829 (4.1%) |
| Per-pick precision | 131 of 2,487 (5.3%) | 49 of 2,487 (2.0%) |
| Lead time, median / mean (weeks) | 1 / 1.20 | 1 / 1.39 |
| Picks that charted after 1 / 2 / 3 / 4 weeks | 117 / 6 / 4 / 4 | 39 / 5 / 1 / 4 |

Only 113 of the 829 breakouts charted in any other country within 4 weeks, so the ceiling is low: counting all 829 breakouts the model's top 3 caught a charting country for 81 (9.8%) against 34 (4.1%) for the baseline, 2.4 times; of the 113 that spread, 81 of 113 against 34. Lead time counts only picks that charted (a miss has no lead time) and is measured from the breakout week, so most of the warning is one week. Three case studies were chosen by a rule fixed in the script before the results were read (the three held-out breakouts with the highest top-1 probability); they are on the Scorecard and in `lead_time.json`, and two of the three are misses.

Does Qloo help? `scripts/test_spillover_qloo.py` added each title's location-conditioned Qloo affinity as features on a 200-breakout subset (1,432 Qloo calls): AUC 0.8188 history-only vs 0.8182 with Qloo, so no lift. Qloo returned an in-country value for only 2.8% of title-country pairs (975 of 35,344, `qloo_value_coverage` in the same file); top-5 precision was identical (0.052) with and without Qloo, and 147 of the 200 test breakouts resolved in Qloo. The country forecast is therefore history-only.

**RIPPLE.** Ground truth: 490 songs from the official song soundtracks of 34 titles in MusicBrainz (`scripts/build_placements_musicbrainz.py` -> `data/placements.csv`; release and source per title in `data/placements_sources.csv`), with Wikipedia spikes in `data/ripple_truth.csv`. A placement here means "on the title's official song soundtrack", which is broader than "used in a scene". Main test (`scripts/test_ripple.py --outcome artist` -> `ripple_test_artist.json`): one row per artist per show, artists without a Qloo audience profile excluded, 229 artists in 24 shows with at least 4 scored artists. Mean within-show Spearman with the log spike, one-sided permutation p-value:

| Predictor | All 24 shows | 4 shows released 2024 or later |
|---|---|---|
| Qloo age gap | 0.02 (p 0.40) | 0.18 (p 0.22) |
| Qloo taste fit | 0.04 (p 0.29) | -0.27 (p 0.87) |
| obscurity (few Wikipedia views before release) | 0.22 (p 0.003) | 0.48 (p 0.03) |

Placebo control (`scripts/test_ripple_controls.py` -> `ripple_controls.json`): the same ratio measured entirely before release (days -60..-8 over days -120..-68), when the show cannot have caused anything. A predictor that also "predicts" the placebo is picking up regression to the mean, because the spike is a ratio over the same pre-release baseline that obscurity measures.

| | Real spike, all / 2024+ | Placebo spike, all / 2024+ |
|---|---|---|
| obscurity | 0.22 / 0.48 | 0.11 / 0.01 |
| Qloo age gap | 0.02 / 0.18 | -0.13 / -0.20 |

What this says: no Qloo signal predicts which soundtrack songs spike on this data. The age gap points the right way (real above placebo) but is not significant (real minus placebo p 0.14 on all shows, 0.15 on the 4 recent ones), and taste fit predicts nothing. Holding obscurity fixed, the age gap's partial correlation on the 4 recent shows is 0.42 (permutation p 0.07): suggestive, from 4 shows, not significant. Obscurity sits further above its placebo here than in the earlier data (0.22 against 0.11 on all shows), so part of its effect may be real attention from the show; we did not test that difference for significance.

**Qloo against an LLM** (`scripts/experiment_kits.py` -> `kit_experiment.json`, pre-registered in `docs/EXPERIMENT_KITS.md` on 27 Oct before any LLM answer existed). Same 81 title-country pairs, four arms (Qloo and Gemini `gemini-3.5-flash`, each with and without the title), scored by name overlap with no LLM judge.

| | Qloo | LLM |
|---|---|---|
| Title-specificity, all 81 pairs (primary) | 0.617 | 0.812 |
| Title-specificity, the 51 pairs where the LLM's picks resolve in Qloo | 0.575 | 0.831 |
| Cross-title distinctness, 62 title pairs (secondary) | 0.852 | 0.804 |

By the registered rule the LLM is more title-specific (paired difference -0.195, one-sided permutation p below 0.001 in the LLM's favour). This is the result we said we would report whichever way it landed, and it went against Qloo. Two things qualify it without reversing it: only 66% of the LLM's 1,620 picks resolve to a Qloo entity of the right type (the same 66% as the 1,067 of 1,615 names Qloo knows in the grounded check below; the rest may be real names Qloo lacks, or not audience taste at all, such as the title's own cast), and the LLM still leads when only resolving picks count. Qloo's lists differ more between titles in the same country, a secondary metric with no registered test. What we changed: nothing in the product claims a kit beats an LLM; each kit is compared with Qloo's country-only answer and the 33 of 81 that mostly match it are labelled countrywide on the storm page.

**The LLM proposes, Qloo grounds** (`scripts/measure_grounded_plan.py` -> `grounded_plan.json`; **exploratory, not pre-registered**: designed after the result above, on the same 81 pairs and the same cached Gemini answers, so it describes the idea and does not confirm it). The storm page's "AI plan, checked by Qloo" block (`aftershock/grounded_plan.py`) resolves each LLM-proposed name to a Qloo entity by exact name, then asks Qloo, in one filtered insights call per domain, which of them it places with this title's audience in this country. 1,615 proposed names (5 of the 1,620 were duplicates or unusable):

| Verdict | Share of the LLM's picks |
|---|---|
| Confirmed: Qloo places it with this audience | 28.6% (462) |
| Not placed: Qloo knows it, does not place it with this audience here | 37.5% (605) |
| Not in Qloo: no exact-name entity | 33.9% (548) |

| Mean title-specificity, 79 pairs where all three can be scored | |
|---|---|
| Qloo's own kit | 0.607 |
| The LLM's picks, all of them | 0.812 |
| The LLM's picks, confirmed only | 0.862 |

Of the 462 confirmed names, 47 were also in Qloo's own top-5 kit and 415 were not: about 5 per pair that the LLM adds and Qloo vouches for. Caveats: confirmed names carry Qloo's spelling while the control is the LLM's country-only list, and a smaller set can overlap less by chance, so 0.862 against 0.812 is not a clean comparison; "confirmed" means Qloo places the entity with this audience, not that the pick is good (no outcome data tests either); Qloo's kit here is scored against Qloo's country-only kit, so its 0.607 is on 79 pairs rather than the registered 81 (0.617). The measurement used 296 live Qloo calls and no new Gemini calls.

How we got here, for the record: an earlier version of this test used placement lists collected from Tunefind and showed a significant age-gap effect on releases from 2024 on. We then found that Tunefind's terms do not permit automated collection, discarded that data and everything computed from it, and rebuilt the ground truth from MusicBrainz (CC0). The effect did not replicate. The song score is therefore shown as an explorer, not a predictor, and nothing in the product claims otherwise.

## The ledger

`ledger/forecasts.jsonl` holds one line per forecast, each chained to the previous line's hash (`aftershock.ledger.verify()` checks the chain). For each breakout, every candidate country's probability is locked, not only the top rows, so AUC and calibration can be graded once its 4-week horizon passes. A RIPPLE forecast is locked only before the release's outcome window opens (release + 7 days) and only if at least 4 songs are scorable; releases found later are shown as an early read with the reason they were not locked. The chain proves the file was not edited line by line; the public timestamp comes from the git history on GitHub. Before its first push the ledger was rebuilt twice, after a scoring bug fix and after the locking rules above were tightened.

**Early read, defined before the data.** Each week, for every locked breakout, its single top forecast country is checked against Netflix's newest data: how many have already charted, against the number calibrated forecasts would expect and against a naive "busiest country" baseline (`docs/EARLY_GRADE.md`, committed and pushed to this public repo before the week of 25 Oct was published; "registered" here means that public commit, not an external registry). The full four-week grade lands on 15 Nov 2026.
