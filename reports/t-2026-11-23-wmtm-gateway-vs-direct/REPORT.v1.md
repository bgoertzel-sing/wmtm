# t-2026-11-23-wmtm-gateway-vs-direct: direct Anthropic (D) vs OpenClaw gateway (G)

## Summary
The question was whether the WMTM clerk's parse results change when the same model and the same catalog prompt are called directly through Anthropic (D) instead of through the OpenClaw gateway (G, the earlier A1 runs). They don't, not in any way I could measure. On all 124 sentences, D's agreement with the gateway runs (mean pairwise Jaccard 0.772) matches the gateway runs' agreement with each other (0.771). The paired difference is -0.000, 95% CI [-0.031, 0.029]. Two D runs agree with each other slightly more than gateway runs do (0.805 vs 0.776 on the 107 sentences both D runs covered). That gap (+0.029, CI [-0.021, 0.078]) is not significant. Neither path produced any malformed outputs.

What this means: the gateway is not the source of the run-to-run variance we saw in A1. That variance most likely comes from the model itself: temperature 0 reaches neither path when thinking is on. Two things are still open. D2 covers only 107 of 124 sentences because it stopped cleanly at the $30 cap. D's cost per call (~$0.13, measured) is higher than the gateway's table estimate (~$0.076), and this report does not settle where that gap comes from.

## Setup
- D: Anthropic Messages API, claude-opus-5-5, effort medium, max_tokens 16000, no temperature sent. Catalog `templates/generated/PROMPT_CATALOG.txt` sha256 2826a9c35b29942f… (same as A1). Driver `tools/d_drive.py`, runner `tools/run_d12.sh`. Hard stop on 429/usage limit (no retry) or when spent + next-call estimate > $30.
- G: the A1 variance runs r1–r3 (`t-2026-11-18-wmtm-clerk-ab/scratch/a1varfull`, 3 × 124 sentences, model openclaw/protocosmo2, temperature 0 requested but dropped because thinking was on; see STEP1-FINDINGS.md). No new spend on G.
- Metric (same as a1varfull): instance signature = (t, span), with non-string spans JSON-dumped. Per-sentence Jaccard (empty/empty = 1). iu = |∩| / |∪| over 3 runs.

## Sanity gate
- Canary: `score_d.py` recomputes the G numbers and reproduces the published a1varfull values exactly: pair_mean 0.772 and iu_mean 0.681.
- Pilot: 3 calls, $1.33, before the long run. D1 was seeded from the pilot.
- Structural check: struct_bad = 0 for D1, D2, G1, G2 and G3.

## Results (`score/d_vs_g_summary.json`)
| measure | value |
|---|---|
| coverage D1 / D2 / G1–3 | 124 / 107 / 124 each |
| within-G pairwise Jaccard (124) | 0.771 |
| D1 vs G pairwise Jaccard (124) | 0.772 |
| cross − within, paired (124) | −0.000, CI95 [−0.031, 0.029] (bootstrap 5000, seed 0) |
| within-D (D1–D2), 107 sentences | 0.805 |
| within-G, same 107 sentences | 0.776 |
| within-D − within-G, paired (107) | +0.029, CI95 [−0.021, 0.078] |
| D vs G cross, 107 sentences | 0.777 |
| iu over G1–G3 (124) | 0.681 |
| iu over D1, D2, G1 (107) | 0.741 |
| signatures per sentence (107 subset) | D1 5.53, D2 5.66, G1 5.82, G2 6.19, G3 5.97 |
| mean output tokens per call | D1 1375, D2 1332, G1 1523 |

D extracts slightly fewer instances (about 5%) and writes slightly shorter outputs than G. This does not change agreement.

## Cost
- D: 231 calls (124 D1 + 107 D2, pilot included in D1), $29.88. Every call read the 172,270-token catalog from cache; the only cache write was the pilot's first call. Mean cost was ~$0.129 per call.
- G (from STEP1, gateway price table): ~$0.076 per call. The figures come from different sources (the gateway's own table vs a per-call estimate from Anthropic usage), so this report does not explain the gap. The basis for the D figure is in `tools/d_drive.py`.

## Open
- D2 is partial (107/124) because it hit the spend cap. The within-D figure is measured on those 107 sentences only.
- The cost basis difference between D and G is not resolved.

## Recompute
`python3 tools/score_d.py <this dir> /home/openclaw/work/t-2026-11-18-wmtm-clerk-ab/scratch` writes `score/d_vs_g_summary.json`. It also writes the bootstrap CIs (paired per-sentence diffs, random.seed(0), 5000 resamples) under `boot_seed0_5000`. No note text appears in this report; per-sentence output is keyed by id only.
