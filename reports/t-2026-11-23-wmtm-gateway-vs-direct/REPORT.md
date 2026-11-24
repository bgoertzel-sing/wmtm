# t-2026-11-23-wmtm-gateway-vs-direct: direct Anthropic (D) vs OpenClaw gateway (G), result 2

## Summary
The question was whether the WMTM clerk's parses, and the conclusions loaded from them, change when the same model and the same catalog prompt are called directly through Anthropic (D) instead of through the OpenClaw gateway (G). G is the four A1 runs: a1frozen plus r1–r3. Both D runs now cover all 124 sentences.

**Agreement does not change, but the amount extracted does.** D agrees with G about as well as the G runs agree with each other: mean pairwise Jaccard 0.764 against 0.770, a paired difference of −0.007 with 95% CI [−0.037, 0.022].

D extracts fewer instances per sentence: 5.77 for D1 and 5.92 for D2, against 6.34–6.59 for G. The paired difference for D1 is −0.65, CI [−1.05, −0.29], about 10% fewer. Each single G run sits within ±0.22 of the other G runs, so this gap lies outside the G spread. D also reports fewer issues (−0.26 per sentence, CI [−0.34, −0.17]) and slightly more unmapped spans (+0.12, CI [+0.02, +0.23]).

**Downstream, D loses a few correct conclusions; wrong ones stay low.** In clerk-ab's pinned load and score pipeline, D1 and D2 score 21 and 19 correct on the narrow count rule, against 22–25 for G. Both have 1 wrong, against 1–6 for G. Reader pass is 7/75 for both (G: 7–8). Class-to-class Inheritance is 82 for both (G: 77–84). Only the number of correct conclusions falls just below G's range.

So the gateway does not add parse noise, but the path makes a small, real difference in how much gets extracted. The cause is not settled. Both arms most likely ran Opus 5.5 at medium thinking, but the two request shapes differ (see "Model settings").

**Spend:** $17.99 at Anthropic's published Opus 5.5 rates (248 calls, 0 failures). Result 1 used Opus 5 rates by mistake; that wrong cap is what cut D2 short, and the cut has now been fixed.

## Changes since review 1
| finding | fix |
|---|---|
| 1 item 2 missing | D1 and D2 loaded through clerk-ab's pinned `pins/load_arm.py` (sha 75c0a91d) + `pins/goals_arm.py` (b868a3db), pinned rules sha 9c58f2e0, PeTTaChainer bdae8d7, PeTTa 3681b9b, templates 24e37182 (`tools/run_dload.sh`, same env as `a1varload/run.sh`). Scored with `tools/dload_score.py`, which uses the a1varload methods. Canary: on r1–r3 it reproduces FINDING2 exactly (24/1/0, 25/6/1, 25/2/0; reader 8/8/7; cc 77/77/81; wide 5/7/5), output in `dload/canary_a1var.txt`. |
| 2 G has 3 runs | G = 4 runs: a1frozen (G0) + r1–r3 (G1–G3); `tools/score_d_v2.py`. |
| 3 wrong price table | Repriced at the published Opus 5.5 rates: $4 input, $20 output, $0.20 cache read, $5 five-minute cache write, per Mtok (source: OpenClaw `docs/providers/anthropic.md`; no invoice). Driver v2 prices every logged call from usage (`tools/d_drive.py`; v1 kept as `tools/d_drive.v1-opus5prices.py`). The cap stayed at $30, including D1 and the pilot. D2 was resumed for the 17 sentences v1 cut, using the same driver, pins and catalog, with the cache warm again after one write. |
| 4 "no measurable change" overstated | Instance-count, issues and unmapped gaps are reported with paired CIs and set against the spread within G; headline corrected. |
| 5 thinking not shown | Section "Model settings". |
| 6 items 1/3 partial | Unmapped spans, issues and latency added. |
| 7 unreadable files | `step1_gateway.txt` and `tools/d_drive.py` now mode 660, the same as the other evidence. |

## Model settings (both arms)
- D request body, from every `reply.request_config`: `{"model":"claude-opus-5-5","max_tokens":16000,"output_config":{"effort":"medium"}}`. No temperature or thinking field is sent; Opus 5.5 thinking is adaptive and always on (semantic-parse.py Anthropic docstring).
- G request body, from every record in all 4 runs: `{"model":"openclaw/protocosmo2","stream":true,"stream_options":{"include_usage":true},"temperature":0.0}`. The chat-completions provider sends no thinking or effort field. The `effort: low` in G records is the driver argument, which this provider does not send. The gateway resolves the model: `step1_gateway.txt` (trajectory of a gateway parse call) shows `provider anthropic, name claude-opus-5-5, api anthropic-messages, thinkLevel medium, reasoningLevel off`.
- So both arms ran Opus 5.5 at medium effort. They differ in how the request is built:
  - G passes through the gateway: the catalog sits in the gateway's system prompt with a 1-hour cache, and the gateway's own wrapper is added.
  - D sends the catalog as a single system block with a 5-minute cache.
- I cannot see whether the gateway's mapping of thinkLevel medium produces exactly `output_config.effort=medium` at the API, because the trajectory truncates the request. That mapping, or the different wrapper, could explain the instance-count gap. This report does not separate the two.

## Results: parse level (`score/d_vs_g4_summary.json`, 124 sentences, 0 malformed in all 6 runs)
| measure | value |
|---|---|
| within-G pairwise Jaccard (4 runs) | 0.770 |
| D1 vs G pairwise Jaccard | 0.764 (D1–G0 0.741, G1 0.802, G2 0.767, G3 0.746) |
| cross − within, paired | −0.007, CI95 [−0.037, 0.022] |
| within-D (D1–D2) | 0.809 |
| within-D − within-G, paired | +0.039, CI95 [−0.004, 0.083] |
| D2 vs G | 0.774 |
| instances / sentence | D1 5.77, D2 5.92; G0 6.36, G1 6.34, G2 6.59, G3 6.40 |
| D1 − mean G instances, paired | −0.65, CI95 [−1.05, −0.29] |
| mean D − mean G instances, paired | −0.58, CI95 [−0.89, −0.29] |
| each G run − other G runs | G0 −0.09, G1 −0.11, G2 +0.22, G3 −0.02 (all CIs include 0) |
| unmapped / sentence | D1 2.21, D2 2.15; G 2.05–2.13 (D1 − G +0.12, CI [0.02, 0.23]) |
| issues / sentence | D1 0.44, D2 0.40; G 0.67–0.76 (D1 − G −0.26, CI [−0.34, −0.17]) |
| latency per call, mean (median) | D1 14.7 s (13.2), D2 14.7 s (13.0); G0 19.7 (17.8), G1 20.2 (17.9), G2 22.9 (20.2), G3 23.7 (21.9) |

## Results: downstream (clerk-ab pinned pipeline; `dload/score/dload.json`)
| run | records ok | atoms | narrow C/W/U | wide strict C/W | reader /75 | Inheritance (inst / class-class) |
|---|---|---|---|---|---|---|
| D1 | 123/124 | 1074 | 21/1/0 | 4/0 | 7 | 110 (28 / 82) |
| D2 | 124/124 | 1086 | 19/1/0 | 4/0 | 7 | 107 (25 / 82) |
| G0 a1frozen (= A1 official) | — | 1177 | 22/6/0 | 5/0 | 7 | 121 (37 / 84) |
| G1 r1 | 122/124 | 1160 | 24/1/0 | 5/0 | 8 | 110 (33 / 77) |
| G2 r2 | 122/124 | 1188 | 25/6/1 | 7/0 | 8 | 121 (44 / 77) |
| G3 r3 | 123/124 | 1182 | 25/2/0 | 5/0 | 7 | 114 (33 / 81) |
G rows are taken from clerk-ab FINDING2 and reproduced by the canary.

- The G range is: correct 22–25, wrong 1–6, reader 7–8, class-to-class Inheritance 77–84, wide 5–7.
- D is inside that range on wrong, reader and class-to-class Inheritance. It is just below the range on narrow correct (21 and 19) and wide strict (4 and 4), and has about 8% fewer atoms. This fits the instance-count gap.
- With two D runs and four G runs the downstream difference is small and not tested statistically. It is a direction, not a significant result.
- New verdicts: 4 D goals had no prior ruling. All 4 were judged correct and are listed with sentence evidence in `dload/verdicts_new_d.tsv` (ids, rules and goals only). Without them, D1 would be 20/1/1 and D2 16/1/3.
- Reader pass is out of 75 expected rows. These are 41 distinct (note, rule) pairs that are not GAP rows; this is the same denominator as clerk-ab.

## Cost
- 248 D calls: D1 124, including the 3-call pilot; D2 124, of which 107 were in the first pass and 17 resumed. There were 0 failures, 0 limit errors and no retries.
- At published Opus 5.5 rates: D1 $9.02, D2 $8.97, **total $17.99**, about $0.073 per call, which is close to G's ~$0.076 per call from the gateway's own figures.
- The v1 figures ($29.88 total, ~$0.129 per call) used Opus 5 rates. This is the "cost gap" left open in result 1, and it is now explained.
- The `usd` field in v1 call records still holds the v1 price. `tools/score_d_v2.py` and the driver v2 reprice every call from its usage.

## Sanity gate
- Agreement canary: `tools/score_d.py` reproduces the published a1varfull pair_mean 0.772 and iu_mean 0.681.
- Downstream canary: as described in the changes table.
- The 3-call pilot ran before the long runs.
- The structural check is in the summary JSON: struct_bad = 0 for all 6 runs.

## Recompute
- `python3 tools/score_d_v2.py <this dir> /srv/hive-evidence/t-2026-11-18-wmtm-clerk-ab /home/openclaw/work/t-2026-11-18-wmtm-clerk-ab/scratch` gives `score/d_vs_g4_summary.json`.
- `tools/run_dload.sh d1 d2` followed by `python3 tools/dload_score.py <this dir> d1 d2` gives `dload/score/dload.json` (in /srv evidence; the repo carries the counts-only `dload/dload_counts.json`; goal lists and verdict evidence stay in /srv because they derive from note text).
- `tools/score_d.py` gives the v1 3-run summary, which is kept.
- Per-sentence output is keyed by id only. No note text appears in the repo commit.

## Open
- What causes the roughly 10% instance-count gap: the gateway's mapping of thinkLevel to effort, or the gateway's prompt wrapper and caching. Separating them would need a direct D run that copies the gateway's request exactly, or a gateway call with its request body captured. Neither was in this order.
