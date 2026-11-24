# t-2026-11-24-wmtm-p05-questions-goals: questions in notes as reasoner goals (P-05) and an admission confidence floor (R-10), shadow over the S1 bundle

## Summary
The order asked two things. First, if questions in notes become reasoner goals, do we get correct answers on top of the S1 bundle without new wrong ones? Second, does a confidence floor at admission (R-10) cut wrong or weak conclusions without losing correct ones?

**Questions: no gain, because the frozen parses contain no parsed questions.** The feature works: on synthetic questions a parsed question becomes a PeTTaChainer query and adds no fact. On all 5 frozen runs, though, the parser produced 0 question records (0 question-family instances). The only "?" sentence per run (1 per run) is left unmapped by the parser (code G00, a subjectless "should we do X?" proposal) with no content instances, so no goal can be built from it. Result: 0 goals, 0 answers, 0 new C/W/U, spec goals identical to the bundle. The count rule holds trivially. The gain is 0, so nothing to set against noise. The limit is the parser not producing question units for note-style questions, not the reasoner.

**Confidence floor: it loses far more correct conclusions than wrong ones; recommend no floor.** Bundle admitted confidences sit at 0.70, 0.88, 0.90, 0.95 and 0.98 (plus 2 near-0 per run on 4 runs). At 0.75 the floor drops 14–17 admitted C per run and 0 W/U. At 0.89 it drops 23–26 C and 0 W, 1 U. Only at 0.95 does it remove the bundle's 1–2 W per run, at a cost of 37–45 C (admitted falls from 48–55 to 4–6). The strict reader pass among admitted conclusions falls from 6–7 to 6–7 / 5–6 / 3–4 of 75. The bundle's wrong conclusions survive the 0.89 floor and fall at 0.95, so they sit at confidence 0.90, the same tier as most correct ones: confidence does not separate W from C here. Both flags stay off by default.

## Ranges across the 5 runs (A0, A1, r1, r2, r3)
Arms: s1 = S1 bundle (baseline); q = question goals; fNNN = floor 0.NN at admission on the s1 run; qfNNN = both. Admitted with reasoner_max_admit 1000 and the per-fact cap lifted, as in S1/R-02.

| arm | admitted | adm C | adm W | adm U | below floor | bundle-admitted dropped C | dropped W+U | reader proved /75 | reader admitted /75 |
|---|---|---|---|---|---|---|---|---|---|
| s1 | 48–55 | 41–50 | 1–2 | 1–2 | 0 | 0 | 0 | 7–8 | 6–7 |
| q | 48–55 | 41–50 | 1–2 | 1–2 | 0 | 0 | 0 | 7–8 | 6–7 |
| f075 | 32–40 | 27–33 | 1–2 | 1–2 | 14–17 | 14–17 | 0 | 7–8 | 6–7 |
| f089 | 22–31 | 18–25 | 1–2 | 0–1 | 24–27 | 23–26 | 1 | 7–8 | 5–6 |
| f095 | 4–6 | 4–6 | 0 | 0 | 44–50 | 37–45 | 2–4 | 7–8 | 3–4 |
| qf075 | 32–40 | 27–33 | 1–2 | 1–2 | 14–17 | 14–17 | 0 | 7–8 | 6–7 |
| qf089 | 22–31 | 18–25 | 1–2 | 0–1 | 24–27 | 23–26 | 1 | 7–8 | 5–6 |
| qf095 | 4–6 | 4–6 | 0 | 0 | 44–50 | 37–45 | 2–4 | 7–8 | 3–4 |

- Proving is identical in every arm (the floor acts only at admission, and q adds no goals): goals 130–141, all proved, 0 timeouts, 0 skipped, 0 new goals vs the bundle, 0 changed status. Narrow and wide C/W/U are therefore identical to s1 in every arm.
- Count rule (narrow and wide): **holds in every arm**, 0 new W. No failing conclusions to show.
- Unjudged: 0 new conclusions are unjudged. The "?" column in A1 (11) and r1/r2 (6) are baseline admitted conclusions without an earlier verdict, carried over unchanged from S1; the same in every arm (f095 drops them too, which is why "dropped" on those runs includes ?).
- Questions per run (q arm): {"A0": {"dup_goal": 0, "found": 0, "goals": 0, "malformed": 0, "queries": 0, "unmapped_g00": 1}, "A1": {"dup_goal": 0, "found": 0, "goals": 0, "malformed": 0, "queries": 0, "unmapped_g00": 1}, "r1": {"dup_goal": 0, "found": 0, "goals": 0, "malformed": 0, "queries": 0, "unmapped_g00": 1}, "r2": {"dup_goal": 0, "found": 0, "goals": 0, "malformed": 0, "queries": 0, "unmapped_g00": 1}, "r3": {"dup_goal": 0, "found": 0, "goals": 0, "malformed": 0, "queries": 0, "unmapped_g00": 1}}.

## Floor trade-off
| floor | bundle-admitted C dropped / run | W dropped | U dropped | reader admitted /75 |
|---|---|---|---|---|
| 0 (off) | 0 | 0 | 0 | 6–7 |
| 0.75 | 14–17 | 0 | 0 | 6–7 |
| 0.89 | 23–26 | 0 | 1 | 5–6 |
| 0.95 | 37–45 | 1–2 | 1–2 | 3–4 |

At 0.95 the unjudged baseline conclusions are dropped too (A1 11, r1 6, r2 6). At 0.75 the C lost includes the 2 near-0-confidence correct conclusions on A0, r1, r2, r3. No tested value removes a W without also removing at least 37 C. A floor is not useful on this corpus.

## Per-run, per-arm table
Columns: goals/proved/timeouts/skipped · admitted n C/W/U/? · below floor · bundle-admitted dropped C/W/U/? · narrow C/W/U/? · wide C/W/U/? · new vs bundle · reader proved /75 · reader admitted /75.

| run | arm | g/p/to/sk | admitted | below | dropped | narrow | wide | new | rd proved | rd admitted |
|---|---|---|---|---|---|---|---|---|---|---|
| A0 | s1 | 130/130/0/0 | 48 46/1/1/0 | 0 | 0/0/0/0 | 46/1/1/0 | 121/4/5/0 | 0 | 8 | 7 |
| A0 | q | 130/130/0/0 | 48 46/1/1/0 | 0 | 0/0/0/0 | 46/1/1/0 | 121/4/5/0 | 0 | 8 | 7 |
| A0 | f075 | 130/130/0/0 | 32 30/1/1/0 | 16 | 16/0/0/0 | 46/1/1/0 | 121/4/5/0 | 0 | 8 | 7 |
| A0 | f089 | 130/130/0/0 | 22 21/1/0/0 | 26 | 25/0/1/0 | 46/1/1/0 | 121/4/5/0 | 0 | 8 | 6 |
| A0 | f095 | 130/130/0/0 | 4 4/0/0/0 | 44 | 42/1/1/0 | 46/1/1/0 | 121/4/5/0 | 0 | 8 | 4 |
| A0 | qf075 | 130/130/0/0 | 32 30/1/1/0 | 16 | 16/0/0/0 | 46/1/1/0 | 121/4/5/0 | 0 | 8 | 7 |
| A0 | qf089 | 130/130/0/0 | 22 21/1/0/0 | 26 | 25/0/1/0 | 46/1/1/0 | 121/4/5/0 | 0 | 8 | 6 |
| A0 | qf095 | 130/130/0/0 | 4 4/0/0/0 | 44 | 42/1/1/0 | 46/1/1/0 | 121/4/5/0 | 0 | 8 | 4 |
| A1 | s1 | 133/133/0/0 | 54 41/1/1/11 | 0 | 0/0/0/0 | 42/1/1/11 | 106/2/3/22 | 0 | 7 | 6 |
| A1 | q | 133/133/0/0 | 54 41/1/1/11 | 0 | 0/0/0/0 | 42/1/1/11 | 106/2/3/22 | 0 | 7 | 6 |
| A1 | f075 | 133/133/0/0 | 40 27/1/1/11 | 14 | 14/0/0/0 | 42/1/1/11 | 106/2/3/22 | 0 | 7 | 6 |
| A1 | f089 | 133/133/0/0 | 30 18/1/0/11 | 24 | 23/0/1/0 | 42/1/1/11 | 106/2/3/22 | 0 | 7 | 5 |
| A1 | f095 | 133/133/0/0 | 4 4/0/0/0 | 50 | 37/1/1/11 | 42/1/1/11 | 106/2/3/22 | 0 | 7 | 3 |
| A1 | qf075 | 133/133/0/0 | 40 27/1/1/11 | 14 | 14/0/0/0 | 42/1/1/11 | 106/2/3/22 | 0 | 7 | 6 |
| A1 | qf089 | 133/133/0/0 | 30 18/1/0/11 | 24 | 23/0/1/0 | 42/1/1/11 | 106/2/3/22 | 0 | 7 | 5 |
| A1 | qf095 | 133/133/0/0 | 4 4/0/0/0 | 50 | 37/1/1/11 | 42/1/1/11 | 106/2/3/22 | 0 | 7 | 3 |
| r1 | s1 | 140/140/0/0 | 54 46/1/1/6 | 0 | 0/0/0/0 | 51/1/1/6 | 121/1/4/14 | 0 | 8 | 7 |
| r1 | q | 140/140/0/0 | 54 46/1/1/6 | 0 | 0/0/0/0 | 51/1/1/6 | 121/1/4/14 | 0 | 8 | 7 |
| r1 | f075 | 140/140/0/0 | 37 29/1/1/6 | 17 | 17/0/0/0 | 51/1/1/6 | 121/1/4/14 | 0 | 8 | 7 |
| r1 | f089 | 140/140/0/0 | 27 20/1/0/6 | 27 | 26/0/1/0 | 51/1/1/6 | 121/1/4/14 | 0 | 8 | 6 |
| r1 | f095 | 140/140/0/0 | 4 4/0/0/0 | 50 | 42/1/1/6 | 51/1/1/6 | 121/1/4/14 | 0 | 8 | 4 |
| r1 | qf075 | 140/140/0/0 | 37 29/1/1/6 | 17 | 17/0/0/0 | 51/1/1/6 | 121/1/4/14 | 0 | 8 | 7 |
| r1 | qf089 | 140/140/0/0 | 27 20/1/0/6 | 27 | 26/0/1/0 | 51/1/1/6 | 121/1/4/14 | 0 | 8 | 6 |
| r1 | qf095 | 140/140/0/0 | 4 4/0/0/0 | 50 | 42/1/1/6 | 51/1/1/6 | 121/1/4/14 | 0 | 8 | 4 |
| r2 | s1 | 138/138/0/0 | 55 45/2/2/6 | 0 | 0/0/0/0 | 45/2/2/6 | 115/4/6/13 | 0 | 8 | 7 |
| r2 | q | 138/138/0/0 | 55 45/2/2/6 | 0 | 0/0/0/0 | 45/2/2/6 | 115/4/6/13 | 0 | 8 | 7 |
| r2 | f075 | 138/138/0/0 | 40 30/2/2/6 | 15 | 15/0/0/0 | 45/2/2/6 | 115/4/6/13 | 0 | 8 | 7 |
| r2 | f089 | 138/138/0/0 | 31 22/2/1/6 | 24 | 23/0/1/0 | 45/2/2/6 | 115/4/6/13 | 0 | 8 | 6 |
| r2 | f095 | 138/138/0/0 | 6 6/0/0/0 | 49 | 39/2/2/6 | 45/2/2/6 | 115/4/6/13 | 0 | 8 | 4 |
| r2 | qf075 | 138/138/0/0 | 40 30/2/2/6 | 15 | 15/0/0/0 | 45/2/2/6 | 115/4/6/13 | 0 | 8 | 7 |
| r2 | qf089 | 138/138/0/0 | 31 22/2/1/6 | 24 | 23/0/1/0 | 45/2/2/6 | 115/4/6/13 | 0 | 8 | 6 |
| r2 | qf095 | 138/138/0/0 | 6 6/0/0/0 | 49 | 39/2/2/6 | 45/2/2/6 | 115/4/6/13 | 0 | 8 | 4 |
| r3 | s1 | 141/141/0/0 | 53 50/2/1/0 | 0 | 0/0/0/0 | 54/2/1/0 | 128/4/5/4 | 0 | 7 | 6 |
| r3 | q | 141/141/0/0 | 53 50/2/1/0 | 0 | 0/0/0/0 | 54/2/1/0 | 128/4/5/4 | 0 | 7 | 6 |
| r3 | f075 | 141/141/0/0 | 36 33/2/1/0 | 17 | 17/0/0/0 | 54/2/1/0 | 128/4/5/4 | 0 | 7 | 6 |
| r3 | f089 | 141/141/0/0 | 27 25/2/0/0 | 26 | 25/0/1/0 | 54/2/1/0 | 128/4/5/4 | 0 | 7 | 6 |
| r3 | f095 | 141/141/0/0 | 5 5/0/0/0 | 48 | 45/2/1/0 | 54/2/1/0 | 128/4/5/4 | 0 | 7 | 4 |
| r3 | qf075 | 141/141/0/0 | 36 33/2/1/0 | 17 | 17/0/0/0 | 54/2/1/0 | 128/4/5/4 | 0 | 7 | 6 |
| r3 | qf089 | 141/141/0/0 | 27 25/2/0/0 | 26 | 25/0/1/0 | 54/2/1/0 | 128/4/5/4 | 0 | 7 | 6 |
| r3 | qf095 | 141/141/0/0 | 5 5/0/0/0 | 48 | 45/2/1/0 | 54/2/1/0 | 128/4/5/4 | 0 | 7 | 4 |

## Design
- `shadow_question_goals` (bool, default false). In `master_loader.plan(questions=True)`, a block record with kind `question` (the sph templates set it when the parse holds a `question`-family instance) is lowered with `tmpl.lower.question` under the note's symbol table. Each query pattern becomes a goal (rule id `question`); its home note and sentence are recorded. The question adds no fact (same ops as with the flag off). `pc_shadow` adds the goals and writes counts (found, malformed, unmapped_g00, queries, goals, dup_goal) to the spec. An answer is admitted only when proved, through the normal admission path. Unmapped G00 spans ending in "?" are counted as questions the parser could not map. The first version counted every G00 (the parser's general no-template code, ~130 per run); it was corrected before any run was scored.
- Restatement guard: a question's query asks about the same pattern as its own sentence, and plan() never loads the question's content as a fact, so an answer must come from other sentences or rules. With 0 real questions this was only exercised synthetically.
- `reasoner_conf_floor` (float, default 0.0 = off) in `pc_admit.load_candidates`: a conclusion with engine confidence below the floor is dropped and counted as `below_floor` (the key appears only when the floor is on). Values 0.75, 0.89, 0.95 were picked from the observed confidence levels so each removes one more tier.
- Tests: `tests/test_question_goals.py` (6, synthetic only): flag off unchanged with no meta key; a question becomes a query and adds no fact; floor off by default; floor at 0.5/0.75/0.95. README flags rows added.

## Acceptance
1. **Flag off is byte-identical** to the bundle: s1 specs built at this branch equal the s1 specs built at 7fa69af and the archived R-02 s1 specs on all 5 runs (basecheck.out, 10/10). The q specs have the same goals and master_ops as s1.
2. **Count rule holds** in every arm: 0 new W, narrow and wide.
3. **Gain vs noise:** questions gain 0 (0 questions parsed). The floor gains nothing: it only removes conclusions, and it costs correct ones at every value; the W it removes at 0.95 (1–2 per run) cost 37–45 C. Neither is an improvement.
4. **No note-derived content in git:** git holds code, synthetic tests, README rows, this report, and counts/ids only (score.json, reader.json with note-timestamp and rule ids, basecheck.out, recompute.out, EVIDENCE_SHA256SUMS). No verdict file was needed (0 new conclusions). The added lines were scanned for parser atoms before commit.

## Details
- Branch hive/t-2026-11-24-wmtm-p05-questions-goals in projects/omegaclaw/p05/wmtm-wt, on the S1 branch 7fa69af (unmerged; the baseline the order names), base wmtm fd48815. Not pushed.
- Pins: templates sph-24e37182 (rules 9c58f2e0), PeTTa mh-rules-on-roman, vendor PeTTaChainer ~/scratch/ppv/pc. 0 parse calls (spy), parse files unchanged (md5 before = after).
- 10 shadow runs (5 runs × s1, q), all rc 0, status ok, canary ok; floor arms are admission-side on those runs. run_all.sh ends with a completion-count assertion (10/10).
- Full suite (with the sph templates set): 1662 passed, 45 skipped, 5 xfailed in 120.21s (0:02:00).
- Evidence: /srv/hive-evidence/t-2026-11-24-wmtm-p05-questions-goals/ (tools/, runs/, score.json, reader.json, basecheck.out, recompute.sh, recompute.out, suite.out, SHA256SUMS). recompute.sh is counts-only, runs in a mktemp dir and reproduces score.json and reader.json byte for byte.
