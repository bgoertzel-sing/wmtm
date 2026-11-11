# t-2026-11-11-wmtm-induction: REPORT (rev3, after review 2)

## Summary

The task was to give the WMTM shadow reasoner induction goals (design §9.1b) and to measure what they add in B on the frozen parses. At the pins (PeTTaChainer b6aacc68, PeTTa 3681b9b), the engine has no separate inheritance-induction rule. `register-inheritance-induction!` does nothing (`runtime/ingest.metta:8`). A class link is folded over its instances by `compile-implication-instance-adds` (`compiler/rules.metta:286`), and the proof is named `implication-instance-fold`. Rule-level generalization uses `conditional-implication` (`compiler/query_lowering.metta:235/315`) together with `merge/revision`. The fold's strength is the design's weighted average. In a 3-instance probe with unequal antecedent mass, it gives 0.5913, which matches the mass-weighted average exactly (the plain mean would be 0.533). A test now checks this.

On the frozen parses, at the shipped threshold (min_shared=3), induction adds no rule. With min_shared=2, it adds one rule on Nov5, r1 and r3: cleanup/done, built from 2 instances at STV 1.0 conf 0.0024. The mechanical W1 check flags it (2 notes plus sk_ facts). But each note holds the same class-level pair (sk_cleanup_1 in cleanup and in done), and the order says that case is NOT W1. So I judge it UNCLEAR. Every other B goal is trivial and refused by the real reader. **The count rule FAILS on all 4 parses (B 0C/0W against A's 2C/2W), the same as in the parent report.** **Propose deploy: no.** Keep `shadow_induction` off. Open decision for you: induction only becomes useful if the parser emits class rules or instances that share structure, or if wmtm adds base rates and variable Implication goals (see "What variable goals need").

## Review 2 findings, one row each
| # | finding | rev3 action | evidence |
|---|---|---|---|
| 1 | No C/W/U verdict, no trivial split, no count rule | Added the verdict for each parse and rule: mechanical W1, then the order's class-level exception, then a hand verdict. Every rule is UNCLEAR. Trivial/non-trivial split from the real reader. Count-rule line for each parse: FAILS on all 12 runs. | `evidence/verdicts_rev3.tsv` (`tools/judge_induced.py`), `evidence/hand_verdicts.json`, `evidence/reader_replay.tsv` |
| 2 | Strength not tested or compared to the design | Probe f (3 instances, masses 0.81/0.45/0.81, consequent strengths 1.0/0.2/0.4) gives 0.591304, which equals Σw·s/Σw with w = m·c_a·c_b (`ImplicationInstanceAcc`, `third_party/pln_formulas/metta/truth_values.metta:243`). The test asserts this and also asserts that the result differs from the plain mean. Control g (1 instance) gives 1.0 at conf 0.0010, below the 3-instance conf. | `evidence/probe_rev3/{f_weighted_fold,g_one_instance}.metta/.answer.txt`, `run3.sh`; `tests/test_goal_induction.py::test_engine_fold_strength_is_mass_weighted_average`, `::test_engine_fold_one_instance_control` |
| 3 | Direction sentence inverted | Fixed. Nov5 has 3 cleanup members and 2 done members; r1/r3 have 2 of each. | section B runs below |
| 4 | runs_v2_pre not committed | Committed `evidence/runs_v2_pre/` (8 runs) and made `cmpruns.py` path-relative. Re-run: admit.json is the same in all 8 once timing fields are ignored. shadow.jsonl is the same in 5 of 8; in nov5_False, r1_False and r1_True it differs only in the `prio_end` checks/resets loop counters. | `evidence/cmpruns.txt`, `tools/cmpruns.py` |
| 5 | Admitted column not via the reader | Replayed `pc_admit.load_candidates` (default config, trivial filter on, cap 5) over all 12 runs. Admitted = only the induced rule on the 3 min2 runs; nothing anywhere else. | `evidence/reader_replay.tsv` (`tools/replay_reader.py`) |

## Induced rules per parse (min_shared=2; at min3 there are none)
| parse | rule | STV | premise notes | premise facts | mech W1 | identical class-level pair per note | verdict | B goals: trivial / non-trivial | B C/W | count rule vs A 2C/2W |
|---|---|---|---|---|---|---|---|---|---|---|
| nov5 | (Inheritance done cleanup) | 1.0/0.0024 | ep-note-20261028T190214Z; ep-note-20261104T051925Z | 4 Member (sk_cleanup_1 per note, in cleanup and done) | yes | yes, so NOT W1 | UNCLEAR | 9 / 1 | 0/0 | FAILS |
| r1 | (Inheritance cleanup done) | 1.0/0.0024 | same 2 notes | same 4 | yes | yes | UNCLEAR | 12 / 1 | 0/0 | FAILS |
| r2 | none | - | - | - | - | - | - | 14 / 0 | 0/0 | FAILS |
| r3 | (Inheritance cleanup done) | 1.0/0.0024 | same 2 notes | same 4 | yes | yes | UNCLEAR | 10 / 1 | 0/0 | FAILS |
Why UNCLEAR and not CORRECT: the 2 instances are two notes' own skolems for the same cleanup/done pair. The rule generalizes this to all cleanup (or done) items at conf 0.0024, and the store can neither confirm nor refute that. On Nov5 a third cleanup member (note ...194242Z) is not in done. That would contradict cleanup→done, so the coverage rule picks done→cleanup there (2/2). The trivial goals are all refused by the reader's trivial filter (`narrow_echo` shape, as in the parent report). The off and min3 runs have the same trivial counts and add no rule.

## Strength vs design ("weighted average")
- Fold (`implication-instance-fold`): this is the design's weighted average over instances, with weights equal to antecedent mass. Probe f and the test show it.
- `merge/revision` (`merge-stv-fields`, `truth_values.metta:684`): averages strengths weighted by evidence count, so it is also a weighted average.
- `conditional-implication`, probe b (0.60): the two paths are not the rule strengths themselves. Each path is inversion with base-rate priors followed by deduction (which adds the not-s_i term), and only then are the paths revised together. So 0.60 is not the 0.7 average of 0.8 and 0.6. The design's weighted average applies at the revision step, not to the raw input rules. I did not decompose 0.60 term by term. No wmtm-side stopgap was needed, because the engine already provides the fold.

## Review 1 findings (rev2), one row each
| # | finding | rev2 action | evidence |
|---|---|---|---|
| 1 | Engine check missed the conditional-implication (§9.1b) path | I probed it at the pins: rules only gives no answer; with base rates, 0.60/0.70; with Member facts, 0.59/0.016. I scanned the frozen stores for rule pairs sharing structure and found 0. I also probed frozen-store goals: cleanup→done (fold, 1.0/0.0024) and the result alias (merge/revision of nwdef + fold, 1.0/0.99, a trivial result). | `evidence/probe_rev2/{a,b,c,d,e}*.metta`, `.answer.txt`, `run.sh`, `run2.sh`; `evidence/scan/rules_scan.jsonl`; `tools/scan_rules.py` |
| 2 | Fold proofs got wrong premise ids (goal-symbol fallback) | `sources_for` (`wmtm/pc_admit.py:83`): for a fold proof with no labels, it now takes the ids from the facts in the goal's `goal_meta` chain. The new `proof_facts` (`pc_admit.py:107`) fills `facts` from that chain. The admitted (Inheritance cleanup done) now has 2 sources and 4 facts, where before it had only one side. | `tests/test_goal_induction.py::test_fold_proof_sources_and_facts_from_chain`; `evidence/summary_rev2.tsv` |
| 3 | Evidence was counts only, not reproducible, and the store claim had no artefact | Committed `shadow.jsonl`, `admit.json` and `spec.json` for 12 runs (4 stores × off / on min3 / on min2), a generator, and a per-goal table (goal, proved STV, admitted, sources, facts). The member-overlap scan is committed too. | `evidence/runs_rev2/*`; `evidence/summary_rev2.tsv` (from `tools/summarize_rev2.py`); `evidence/scan/members_scan.jsonl` (`tools/scan_members.py`); runners `tools/run_b_ind.sh`, `tools/all.sh`, `tools/all_min2.sh`; `tools/cmpruns.py` |
| 4 | No test of the build_snapshot flag path; symmetric pair doubled goal slots | Added flag-on and flag-off tests through `build_snapshot`. `induction_goal_pool` (`pc_shadow.py:363`) now proposes one direction per pair: A→B where the shared set covers more of A, with ties broken by sorted order. | `tests/test_goal_induction.py` (10 pass); full suite (rev2) 911 passed, 41 skipped, 7 xfailed |

## Engine probe, conditional-implication path (KB: s1→b, s2→b, s1→c 0.8, s2→c 0.6; goal `(Implication (Member $x b) (Member $x c))`)
| case | answer |
|---|---|
| a: rules only, no base rates | none |
| b: rules + `set-base-rate` for the 4 classes | `conditional-implication (merge/revision (by r4 (inverted r2 ..)) (by r3 (inverted r1 ..)))`, STV 0.6006 conf 0.6999 |
| c: rules + Member facts, no set-base-rate | same proof shape, prior from the facts, STV 0.5916 conf 0.0161 |
| d: frozen Nov5 store, `cleanup→done` | `implication-instance-fold`, STV 1.0 conf 0.0024 |
| e: frozen Nov5 store, `result__nw_b5881f6f23→result` | `merge/revision nwdef_.. (implication-instance-fold)`, STV 1.0 conf 0.99. This only restates the nwdef rule, so it is trivial. |

## Store scans
Rules (`scan/rules_scan.jsonl`): there are 76, 63, 71 and 64 class rules in Nov5, r1, r2 and r3. All of them are nwdef. Each antecedent class has at most 1 consequent, and 0 pairs share a class on either side. So the frozen stores give conditional-implication nothing to work on.
Members (`scan/members_scan.jsonl`): the most members any class pair shares is 3 on Nov5 (result vs result__nw_b5881f6f23, an alias) and 2 elsewhere. The only non-alias pair sharing 2 or more members is cleanup/done (2 shared, on Nov5, r1 and r3).

## B runs (sandbox, frozen stores, no parse calls, no live changes)
Full table: `evidence/summary_rev2.tsv`.
| store | off goals | on min3 goals | on min2 goals | induction goal at min2 | STV | admitted, sources / facts |
|---|---|---|---|---|---|---|
| nov5 (1f1a7a6f) | 9 | 9 | 10 | (Inheritance done cleanup) | 1.0 / 0.0024 | yes, 2 ep-notes / 4 Member facts |
| r1 (533c2274) | 12 | 12 | 13 | (Inheritance cleanup done) | 1.0 / 0.0024 | yes, 2 / 4 |
| r2 | 14 | 14 | 14 | none | - | - |
| r3 | 10 | 10 | 11 | (Inheritance cleanup done) | 1.0 / 0.0024 | yes, 2 / 4 |
In every run, the canary (Member grace person) is proved, the negative (Member grace robot) is not proved, and the gate rejected broad_category once. All goals were proved. Pre-rev2 comparison: see review 2 row 4 (`evidence/cmpruns.txt`, committed `runs_v2_pre`).
The direction of cleanup/done differs because Nov5 has more `cleanup` members (3) than r1/r3 (2); `done` has 2 everywhere. The coverage rule picks the direction where the shared set covers more of the antecedent.

## What variable goals need (to use the §9.1b path from wmtm)
1. Goal shape. `_GOAL` (`pc_admit.py:45`) matches only ground binary atoms, so `(Implication (Member $x A) (Member $x B))` is never parsed or admitted. It needs a new goal kind with a variable, mapped to a WMTM rule item, not a fact item.
2. Premise ids. Proofs name rule labels (`by r3`, `inverted r1`). Those labels need to map to item ids, the same way fact labels (sp/wm) do now.
3. Base rates. wmtm emits no `set-base-rate` (I grepped `wmtm/` and found none). Without base rates the path gives no answer, or confidence about 0.016 when it falls back on Member facts. Empirical base rates from Member counts would need a design choice on what population to count over.
4. Trivial filter. An nwdef-only derivation such as probe e must be classed as trivial. The filter already handles the nwdef shape for ground goals, but it would need extending to Implication goals.
5. Input. Even with 1 to 4 in place, the current parser output has no rule pairs sharing structure, so the parser side would need to change too.

## Code (diff vs 1415160; rev3 adds tests and report tools only)
- `wmtm/pc_admit.py`: chain-based `sources_for` fallback for fold proofs; new `proof_facts`.
- `wmtm/pc_shadow.py`: one direction per pair in `induction_goal_pool`.
- `tests/test_goal_induction.py`: flag-path tests and the chain-sources test.
- `tools/run_b_ind.sh`: optional 6th argument, `shadow_induction_min`.

## Deviations
- The min2 runs go beyond the order. The shipped default stays at 3. I ran min2 only to exercise the admit and premise-id path on real data.
- v1 evidence (`summary.tsv`, `runs_v1_NOTES.txt`) is kept as history.
- Rev3: test suite 913 passed, 41 skipped, 7 xfailed; tests/test_goal_induction.py 12 passed. The trivial filter is still on (`admit_trivial_filter` default True).
- Review 2 did not run the engine probes (no swipl on its host). They reproduce here with `probe_rev2/run.sh`, `run2.sh` and `probe_rev3/run3.sh`, under PeTTa 3681b9b at PeTTaChainer b6aacc68.
