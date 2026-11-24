# t-2026-11-24-wmtm-s1-shadow-bundle: the passed shadow features measured together, with a switch plan (no switch)

## Summary
The task asked whether the shadow features that each passed review alone still hold the count rule when they run together, whether they raise the reader pass beyond run-to-run noise, and what switch plan would take them live safely. The features are R-01/R-11 extra rules with Not Current/Valid wording, R-12 note-implication goals (premise flag off), P-03 label replace, and P-01 class links. I ran them on the 5 frozen Clerk A/B parse runs (A0, A1, r1–r3) in 6 arms each: all off, each feature alone, and all on. That is 30 shadow runs, with 0 parse calls and no live change.

**The count rule holds on every run.** With all features on, each run gains 23–30 new conclusions: 22–29 correct, 1 uncertain and 0 wrong. Admitted conclusions go from 19–25 C / 1–2 W to 41–50 C / 1–2 W, so the wrong count does not change. No conclusion appears only with the full bundle on, none vanishes, and no shared goal changes its proof status, so there are no interactions. The gain comes from R-01 (+9 to +11) and R-12 (+13 to +19). P-03 replaces 1–3 labels per run but changes no conclusion. P-01 adds 29–36 links but no goals, which matches the P-01 finding.

**The reader pass does not rise under the strict method.** The strict Clerk A/B score (a note+rule row appearing among the proved goals) is 7–8 of 75 in every arm, the same as the run-to-run range, so the gain is 0. The sentence-level upper bound used in the earlier feature tasks goes from 7–8 to 20–21 of 75 with all on. That number is an upper bound, not a score.

**Switch plan.** It is in docs/SWITCH_PLAN_S1.md and has not been carried out. One point needs andy's attention: the live package d506783 contains none of these flags, so a flags edit alone does nothing. The switch needs a package and pin move to a main commit at fd48815 or later, followed by a flags delta of 4 keys on flags file f9e59f74. I recommend doing it in two steps, each with its own rollback, and leaving class_links off. **andy decides** whether to switch.

## Per-run, per-arm table
Columns, in order: admitted C/W/U/unjudged · narrow (non-restatement) · wide (all proved) · new vs off (n, C/W/U/?) · reader strict /75 · reader upper bound /75.

| run | off | xr (R-01/R-11) | ni (R-12) | lr (P-03) | cl (P-01) | all |
|---|---|---|---|---|---|---|
| A0 | 22/1/0/0 · 22/1/0/0 · 97/4/4/0 · 0 · 8 · 8 | 32/1/1/0 · 32/1/1/0 · 107/4/5/0 · 11: 10/0/1/0 · 8 · 16 | 36/1/0/0 · 36/1/0/0 · 111/4/4/0 · 14: 14/0/0/0 · 8 · 14 | = off · 8 · 8 | = off · 8 · 8 | 46/1/1/0 · 46/1/1/0 · 121/4/5/0 · 25: 24/0/1/0 · 8 · 21 |
| A1 | 19/1/0/11 · 20/1/0/11 · 84/2/2/22 · 0 · 7 · 7 | 27/1/1/11 · 28/1/1/11 · 92/2/3/22 · 9: 8/0/1/0 · 7 · 14 | 33/1/0/11 · 34/1/0/11 · 98/2/2/22 · 14: 14/0/0/0 · 7 · 13 | = off · 7 · 7 | = off · 7 · 7 | 41/1/1/11 · 42/1/1/11 · 106/2/3/22 · 23: 22/0/1/0 · 7 · 20 |
| r1 | 21/1/0/6 · 22/1/0/6 · 92/1/3/14 · 0 · 8 · 8 | 31/1/1/6 · 32/1/1/6 · 102/1/4/14 · 11: 10/0/1/0 · 8 · 16 | 36/1/0/6 · 41/1/0/6 · 111/1/3/14 · 19: 19/0/0/0 · 8 · 15 | = off · 8 · 8 | = off · 8 · 8 | 46/1/1/6 · 51/1/1/6 · 121/1/4/14 · 30: 29/0/1/0 · 8 · 21 |
| r2 | 23/2/1/6 · 23/2/1/6 · 93/4/5/13 · 0 · 8 · 8 | 32/2/2/6 · 32/2/2/6 · 102/4/6/13 · 10: 9/0/1/0 · 8 · 15 | 36/2/1/6 · 36/2/1/6 · 106/4/5/13 · 13: 13/0/0/0 · 8 · 14 | = off · 8 · 8 | = off · 8 · 8 | 45/2/2/6 · 45/2/2/6 · 115/4/6/13 · 23: 22/0/1/0 · 8 · 20 |
| r3 | 25/2/0/0 · 25/2/0/0 · 99/4/4/4 · 0 · 7 · 7 | 35/2/1/0 · 35/2/1/0 · 109/4/5/4 · 11: 10/0/1/0 · 7 · 15 | 40/2/0/0 · 44/2/0/0 · 118/4/4/4 · 19: 19/0/0/0 · 7 · 14 | = off · 7 · 7 | = off · 7 · 7 | 50/2/1/0 · 54/2/1/0 · 128/4/5/4 · 30: 29/0/1/0 · 7 · 20 |
| **range** | adm C 19–25 W 1–2; reader 7–8 | new 9–11, W 0 | new 13–19, W 0 | 0 change | 0 change | new 23–30, **W 0**; reader strict 7–8, ub 20–21 |

- Admitted counts were scored with pc_admit.load_candidates with the cap lifted to 1000, so that every candidate is visible. Live uses reasoner_max_admit 5.
- The unjudged entries (A1 11, r1 6, r2 6) are off-arm coref goals of those parse runs that have no earlier verdict. They are identical in every arm, so they cancel out in every on/off comparison. Every **new** conclusion is judged: 0 unjudged.
- Verdict sources:
  - seeded b01–b105 (master-shadow-wiring);
  - clerk-ab verdicts_unmatched and verdicts_new_varruns;
  - extra-rules verdicts_xr (all 9–11 xr goals per run matched);
  - nimpl-v2 verdicts_nimpl;
  - 11 new note-implication goals judged in this task (`verdicts_s1.tsv`, u01–u11, all correct, each read from the note's own sentence).
- The 1 U in xr/all is the same extra-rules goal on every run. It was judged U in t-2026-11-17-wmtm-extra-rules.

## Interactions (Do 2)
- Spec level: goals in the all-on arm minus the union of the single arms = 0 on all 5 runs. The union minus all-on = 0.
- Proof level: shared goals whose proved status changes against off = 0 in every arm on every run.
- So there are no conclusions that appear or vanish only with the full bundle on. Nothing needs explaining.
- Inside the bundle, P-03 and P-01 act on the KB without changing any goal. R-01 and R-12 goals are disjoint.

## Acceptance
1. The per-run, per-arm table with ranges is above. Every new conclusion is judged (0 unjudged).
2. The count rule holds: bundle against all-off on every run, with 0 new W and admitted W unchanged (1–2).
3. Reader pass: strict 7–8 of 75 in every arm, equal to the run-to-run range of 7–8, so the gain is 0. The sentence upper bound goes from 7–8 to 20–21, and is labelled as an upper bound.
4. docs/SWITCH_PLAN_S1.md covers:
   - the package and pin precondition;
   - the flags delta on f9e59f74;
   - 7 pre-checks, including the off and on spec canaries;
   - rollback to f9e59f74 and pin 7acf09f1;
   - triggers T1–T7 with the L-11 idle and budget states listed as non-triggers (share_full/cap_full/budget_zero, a full admit cap, 429 only in the HTTP status field, tracebacks only under the package path);
   - first-notes, +6 h and +24 h checks.
5. Flags off: the off spec built at this branch is byte-identical to the one built at base fd48815 on all 5 runs (basecheck.out). The A0 off spec is also byte-identical to the archived steps-3-5 off spec. Full test suite: 1631 passed, 70 skipped, 5 xfailed.

## Details
- Base: wmtm fd48815. Branch hive/t-2026-11-24-wmtm-s1-shadow-bundle, worktree projects/omegaclaw/s1/wmtm-wt. Not pushed.
- class_links is not in main. I cherry-picked it from the passed hive commit b14f9ef (as 45fa6a8) and wired it into master_loader.plan(class_links=) and pc_shadow behind the existing `class_links` flag (default off; meta key only when on). Each note's full lowered set, shared definitions included, is passed to derive.
- Pins: templates sph-24e37182, rules 9c58f2e0, PeTTa (mh-rules-on-roman) and vendor PeTTaChainer ~/scratch/ppv/pc, the same as the Nov-17 feature tasks. Parse files are unchanged by md5 (parsed.md5_before == parsed.md5_after).
- Run log: run_all.sh stopped silently during r2/ni with no rc written. The partial output is kept as runs/r2/ni/shadow.interrupted.jsonl, and tools/resume.sh reran r2 ni..all and all of r3. All 30 final runs: rc 0, status ok, canary ok, 0 timeouts, 0 skipped_budget, 0 add/pred failures.
- Wall time per shadow run: off 13.1–17.5 s, all 17.7–24.1 s. All-on prequery is 8.9–14.7 s against budget 20 s. The plan's pre-check 5 covers this.
- Evidence: /srv/hive-evidence/t-2026-11-24-wmtm-s1-shadow-bundle/ (tools/, runs/, score.json, reader.json, reader_ub.json, verdicts_s1.tsv, basecheck.out, recompute.sh, recompute.out, SHA256SUMS). recompute.sh is counts-only, runs in a mktemp dir and reproduces score/reader/reader_ub byte for byte.
