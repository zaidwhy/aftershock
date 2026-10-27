# Pre-registered experiment: does Qloo's launch kit beat an LLM's?

Registered 27 Oct 2026, before any LLM kit or country-only kit was collected. This file is committed first; the git timestamp is the registration. Results go to `data/results/kit_experiment.json` and are reported whatever they show.

## Question

The hackathon rule: the agent "should outperform generic LLM-only approaches because it has access to Qloo". For the launch kit (what a breakout title's audience over-indexes on in a forecast country), does Qloo give answers that are more specific to the title, and grounded in real entities, than an LLM asked the same question?

## Pairs

Every title-country row that has a launch kit in this week's forecast run (week of 18 Oct 2026): 81 rows, 27 titles, 42 countries. No pairs are chosen by hand.

## Arms

For each pair and each of the four kit domains (artist, tv_show, movie, brand), up to 5 names:

| Arm | Source |
|---|---|
| Q | Qloo, title + country: `/v2/insights` with the title as `signal.interests.entities` and `signal.location.query` (the shipped kit) |
| Qc | Qloo, country only: same call without the title signal |
| L | LLM (Gemini, `gemini-3.5-flash`, temperature 0), title + country: asked for the 5 names per domain that this title's audience in that country particularly likes, given the title's name, type and the country |
| Lc | LLM, country only: the same prompt without the title |

The LLM gets the same information Qloo gets (title, type, country), in batches, never anything about Qloo's answers or our forecasts.

## Metrics (objective, no LLM judge)

Names are compared after lower-casing and stripping punctuation.

1. **Title-specificity** (primary). Per pair and domain: 1 minus the Jaccard overlap between the title kit and the same source's country-only kit (Q vs Qc; L vs Lc). Averaged over domains, then over pairs. Higher means the answer depends more on the title.
2. **Cross-title distinctness** (secondary). For every two titles forecast in the same country: 1 minus the Jaccard overlap of their kits, per source.
3. **Grounding** (secondary). Share of L picks that resolve to a Qloo entity of the right type with an exact normalized name match via `/search` (the same strict rule the product uses). Q picks are Qloo entities by construction. A pick that does not resolve may be a real entity Qloo lacks, or an invented one; we report the share, not a verdict.

## Decision rule

- Qloo "is more title-specific" if the mean paired difference Q minus L in metric 1 is above 0 with a one-sided sign-flip permutation p below 0.05 (10,000 flips, seed 7).
- The same rule, reversed, says the LLM is more title-specific.
- Otherwise: no difference shown.
- Metric 1 is also reported on grounded L picks only, because an LLM can look title-specific by naming things that do not exist or are not audience taste (for example the title's own cast).

## Product rule fixed in advance

A shipped kit is labelled **generic** when its overlap with the Qloo country-only kit is 0.6 or more (title-specificity 0.4 or less), and **title-specific** otherwise. The label is computed from Qc and shown on the storm page regardless of how the comparison with the LLM comes out.

## Known limits

81 pairs from one week; one LLM, one prompt; the metrics measure specificity and grounding, not whether a kit would work for a marketing team (no ground truth for that exists yet). Qloo's data is a current snapshot.
