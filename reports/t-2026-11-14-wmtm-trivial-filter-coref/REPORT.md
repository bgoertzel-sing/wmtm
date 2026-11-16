# t-2026-11-14-wmtm-trivial-filter-coref

## Summary
The question was whether the parser-master-adopt-v2 B set passes the count rule once the trivial filter also refuses symmetry restatements and plain coreference links, checked against live A (F3 v3, 2C/2W) and against the old loader (M17 r1/r2/r3), under andy's narrow split (a) and the wide split (b). The wide split also counts all six coref role rules as restatements. The filter change is in place and tested, and the full suite is green.

Against live A, the count rule HOLDS under both splits, for the main arm and for the sensitivity arm. Against the old loader, the two splits DISAGREE for the main arm. Under the narrow split, B keeps 22 correct and 1 wrong and the rule HOLDS against r1, r2 and r3. Under the wide split, B keeps only 6 correct and 0 wrong, so the rule FAILS against all three runs (8C, 10C and 7C), because B has fewer correct conclusions. The sensitivity arm HOLDS under both splits. Applying the filter drops no earlier conclusion that B had kept (Mesto §11 is unchanged), and W1 stays 0.

Two findings matter for the deploy decision. First, the shipped filter already refuses every old-loader M17 conclusion, all 28 as narrow_echo, and did so before this change. Scored under the same filter, the old loader admits 0C/0W, and the verdicts flip: narrow FAILS (1W > 0W) and wide HOLDS. The tables above use the M17 counts as judged in v2. Second, through the real admission path (load_candidates), none of the B conclusions reach the filter today. 98 of 105 are dropped as "bad" because their goal heads cannot be rendered, and the other 7 have no live source. A human needs to decide the split and whether the M17 baseline should be filtered; I did not choose either.

## Base and refs
- Code base: wmtm main **ddd2096** (origin/main after fetch). The accept message named e59ab57, an older main; the order names ddd2096, so I used that.
- Branch: `hive/t-2026-11-14-wmtm-trivial-filter-coref` (staged, not pushed per the order).
- Commits: a0cd323 (filter, tests, README row, guard docstring); the next commit adds this report and the tools.
- Inputs: v2 evidence /srv/hive-evidence/t-2026-11-12-wmtm-parser-master-adopt-v2 (branch at 785baf3; not merged, its tools' scoring logic re-implemented in tools/rescore.py around the shipped pc_admit). All 16 copied v2 inputs match the v2 SHA256SUMS byte for byte (provenance/inputs_vs_v2_SHA256SUMS.txt). Live A proofs: reports/t-2026-11-08-wmtm-f3-ab-v3/runs/v3_A.shadow.jsonl at ddd2096.
- 0 parse calls.

## 1. Filter change (pc_admit.trivial_reason)
The line was fixed in the order before any scoring, and it is matched by rule id (the label in a proof step):
- symmetry_restatement: coref_sym, so_sym
- coref_restatement: same_coref, coref_bearer
- not trivial: coref_agent, coref_patient, coref_theme, coref_member, coref_possession

A proof is a restatement when every inference step uses one of the four listed rules and every leaf is an asserted atom label. A chain of listed rules (for example, a symmetry over a coref link) also counts, and so does a merge or revision of such chains. The engine forms `(by (bi-forward R) ..)` and `(conjunction ..)` are read for these four rules only. Any other step, such as a role rule, month_class, nwdef or a parser rule, means not trivial. Proofs that contain no listed rule are classified exactly as before. No new flag was added: the existing admit_trivial_filter (default on) covers both the primary path and the orchestrator guard. `trivial_reason(proof, rules, restatement_rules=None)` takes an optional evaluation hook, which only the wide-split scoring passes and no runtime flag reads. The admit log's step list now reads R out of `(by (bi-forward R) ..)`.

This is the first rule in the filter that reads a name rather than a shape. The order drew the line by rule id, so the match is exact (`coref_sym2`, `xcoref_sym` and similar names are not matched; tested).

Tests: tests/test_trivial_filter_coref.py, 24 tests.
- Each of the 4 listed rules' restatements is trivial, in the engine's real proof forms and with sp<n> premises.
- Each of the 5 role rules' conclusions is not trivial, in 3 forms each.
- A restatement of a role-rule conclusion is not trivial.
- Chains and revisions of restatements are trivial.
- Only exact ids match, and non-label premises fail open.
- A mix with another rule is not trivial.
- The wide hook refuses role rules but does not change the default.
- The forms added for the listed rules (bi-forward, conjunction, non-sp labels) do not open the old nwdef and narrow_echo paths.
- Through load_candidates, a coref_sym restatement is refused and logged with reason symmetry_restatement and step coref_sym, while a coref_agent conclusion is admitted.

The existing tests/test_trivial_filter.py is unchanged and passes.

Full suite, with the engine env as in v2 (WMTM_PC_PETTA, WMTM_PC_VENDOR, WMTM_PC_SHADOW_SPH_TEMPLATES): branch **1473 passed, 28 skipped, 5 xfailed, exit 0**. Base ddd2096: 1449 passed, 28 skipped, 5 xfailed. The difference of +24 is the new file, and the skips are the same environment-only skips as in v2 (suite/).

## 2. Re-score: both splits side by side
The filter was run on every proved B proof (main arm full_s2 105, sensitivity arm sens_s2 119) with the v2 hand verdicts. A = live F3 v3 A_v3 at 2C/2W. The new filter refuses 0 of its 4 proofs under either split: they carry no rule steps, so A stays 2C/2W. M17 counts are as judged in v2: r1 8C/1W, r2 10C/1W, r3 7C/1W.

### Count rule (correct(B) >= correct(base) and wrong(B) <= wrong(base))
| arm | split | refused | admitted C/W/U | vs A_v3 2C/2W | vs M17 r1 8C/1W | vs M17 r2 10C/1W | vs M17 r3 7C/1W |
|---|---|---|---|---|---|---|---|
| full_s2 (105) | (a) narrow | 82 | 22/1/0 | HOLDS | HOLDS | HOLDS | HOLDS |
| full_s2 (105) | (b) wide | 99 | 6/0/0 | HOLDS | **FAILS** (6 < 8 C) | **FAILS** (6 < 10 C) | **FAILS** (6 < 7 C) |
| sens_s2 (119) | (a) narrow | 82 | 35/1/1 | HOLDS | HOLDS | HOLDS | HOLDS |
| sens_s2 (119) | (b) wide | 99 | 19/0/1 | HOLDS | HOLDS | HOLDS | HOLDS |

**The splits disagree** for the main arm against the old loader: (a) HOLDS and (b) FAILS on correct count. They agree everywhere else.

### What each split refuses and admits (full_s2; sens_s2 refuses the same 82/99, and the 14 adjective-implication goals are admitted in both splits)
| split | refused by rule | refused C/W/U | refused wrong ids | admitted by rule | admitted wrong / unclear ids |
|---|---|---|---|---|---|
| (a) narrow | coref_sym 48, so_sym 29, same_coref 3, coref_bearer 2 | 75/3/4 | b17, b62, b63 | coref_member 5, coref_patient 5, coref_agent 3, coref_possession 3, coref_theme 2, month_class 2, subset_is_part 1, partof_trans 1, becauseof_cause 1 | W b68 |
| (b) wide | the above + coref_patient 5, coref_member 4, coref_agent 3, coref_possession 3, coref_theme 2 | 91/4/4 | b17, b62, b63, b68 | month_class 2 (b72, b73), subset_is_part 1 (b103), partof_trans 1 (b104), becauseof_cause 1 (b105), coref_member 1 (b67) | none (sens adds U b114) |

Difference from v2's goal-rule split: v2 counted 5 strict survivors (5C/0W). The proof-based filter keeps b67 as well, a coref_member goal whose proof runs through a factored-revision derivation rather than straight over asserted labels. It is therefore not a pure restatement, which gives 6C/0W here. The verdict is the same either way: it HOLDS against A and FAILS against M17.

### Mesto §11 (earlier conclusions: A_v3 4, B_v3 11 and the M17 runs, 20 distinct)
| arm | split | earlier kept | dropped | newly dropped by the filter |
|---|---|---|---|---|
| full_s2 | (a) / (b) | 0 / 0 | 20 / 20 | 0 / 0 |
| sens_s2 | (a) / (b) | 10 / 10 (b110-b119) | 10 / 10 | 0 / 0 |

The 10 kept conclusions are adjective implications, which neither split touches, so v2's ranked drop list stands unchanged. That list has 10 rows, 4 of which are real losses of correct conclusions (v2 armB/verdicts/missing_ranked.tsv).

### W1 (cross-note conclusions among admitted goals)
0 under both splits in both arms, and 0 wrong ones, as in v2.

## 3. Findings outside the count (for the decision)
1. **The old-loader baseline is already filtered to nothing.** The shipped filter (ddd2096, before this change) refuses all 28 M17 conclusions as narrow_echo (r1 9/9, r2 11/11, r3 8/8), and this change does not alter that. If M17 is scored under the same filter as B, it admits 0C/0W. Against that baseline the verdicts invert: (a) FAILS in both arms (1W > 0W) and (b) HOLDS in both arms. The tables above follow v2 and the order and use M17 as judged, so this is reported, not substituted.
2. **The production admission path does not reach the filter for these goals.** Through pc_admit.load_candidates, with admit.json as written, full_s2 drops 98 results as "bad" because their goal heads cannot be rendered (render knows Inheritance, Member, Implies, Similarity and Evaluation only). The remaining 7 are dropped as no_live_source because the shadow wrote no sources. sens_s2 drops 98 bad and 21 no_live_source. Trivial refusals there: 0. The canary therefore swaps in a renderable synthetic goal and a live source while keeping each proof and its rules unchanged. Through load_candidates it refuses 82 in each arm (77 symmetry_restatement, 5 coref_restatement), which equals the direct count, so the deployed path classifies these proofs the same way. Before B conclusions could be admitted live, rendering and sources for the master goal heads are needed. That is a separate change.

## Evidence
/srv/hive-evidence/t-2026-11-14-wmtm-trivial-filter-coref/ (default umask, with hive-reviewer read through the folder ACL).
- SHA256SUMS
- README.txt
- inputs/: note-derived byte copies, kept apart
- tables/goals_full_s2.tsv and tables/goals_sens_s2.tsv: goal id, rule id, proved, split (a) reason, split (b) reason, verdict, note count
- tables/counts.json
- provenance/
- suite/

Run `python3 reports/t-2026-11-14-wmtm-trivial-filter-coref/tools/recompute.py /srv/hive-evidence/t-2026-11-14-wmtm-trivial-filter-coref` from the branch. It checks SHA256SUMS and re-runs the filter from this repo over inputs/. It then checks that the result equals the stored tables, runs the load_candidates canary and recounts every table above from the id/count tables. It ends with RECOMPUTE_OK (last run: OK). The committed reports/.../SHA256SUMS equals the evidence copy. tools/rescore.py writes the tables.

## Limits
- Verdicts are v2's (one judge); no goal was re-judged here.
- Matching on rule id assumes the pinned master rules file (sph 24e37182) keeps these ids and meanings. A renamed or redefined rule would not be caught.
- A_v3 is 4 goals whose proofs carry no rule steps, so the filter can only fail open on them; the comparison with A is weak on that side (as noted in the 11-10 trivial-filter report).
- Split (b) is scored through the evaluation hook only. The shipped default is split (a), as the order fixed.
- Report, tables and this file carry ids, rule ids and counts only; note-derived text stays in EV inputs/.
