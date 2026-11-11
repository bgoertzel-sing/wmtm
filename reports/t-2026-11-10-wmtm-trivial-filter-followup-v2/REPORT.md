# t-2026-11-10-wmtm-trivial-filter-followup-v2

## Summary
This order asked for five fixes to the trivial-restatement filter. All five are done. The most important finding came from fix 1. The old non-trivial control was itself fail-open. The committed evidence/controls_s49.json had empty `rules` for all 98 rows, so the old "49/49 admitted" result proved nothing. `proof_rules` only collected Implication atoms, but the s49 proofs cite Inheritance facts as rules. Now that this is fixed, both s49 runs (run_snap, run_live) admit 49/49 with rules mapped for every row: 67 steps, 0 missing, 0 refused. So the control now admits because each step was classified. The B result does not change: r1/r2/r3 refuse 12/14/10 of 12/14/10, all narrow_echo, and the count rule still FAILS after the filter.

No live changes, 0 parse calls, nothing pushed. Full suite: 901 passed, 41 skipped, 7 xfailed. tests/test_trivial_filter.py: 36 passed. Still open for a human: B needs parses that yield non-echo rules before it can pass the count rule. This is unchanged from the parent report.

## Supersedes
Supersedes: t-2026-11-10-wmtm-trivial-filter-followup
Supersedes: t-2026-11-10-wmtm-trivial-filter

## Base
Branch hive/t-2026-11-10-wmtm-trivial-filter-followup-v2, off 22738f6 (trivial-filter head). Hive base 27c1a41. Not pushed.

## The five items
1. **Real non-trivial control (frozen KB, with rule atoms).**
   - `proof_rules` now also maps the `(: L (Inheritance ..))` atoms that proofs cite as rules. Only Implication atoms can still be defining rules.
   - New `pc_admit.step_coverage(proof, rules)` returns {steps, known, missing}.
   - controls_s49.json is regenerated from /tmp/s49/<run>/spec.json atoms, with the same goals in the same order (checked). make_evidence.py now writes it, and SUMMARY.json controls carry with_rules/steps/missing.
   - recompute.py requires with_rules == results and missing == 0 and prints RECOMPUTE_OK.
   - The s49 snapshot matches the legacy full_Bf3 shadow (same ok-proof set).
   - Kept ids (cited atoms, 43, identical on both runs): sp20 sp30 sp34 sp45 sp52 sp54 sp74 sp78 sp81 sp91 sp92 sp104 sp118 sp119 sp131 sp134 sp146 sp166 sp188 sp209 sp215 sp240 sp246 sp255 sp259 sp262 sp267 sp279 sp284 sp293 sp328 sp348 sp353 sp360 sp362 sp380 sp382 sp388 sp413 sp418 sp433 sp453 sp457.
2. **nwdef by exact shape.**
   - `_is_nwdef_shape` matches only the exact `pc_shadow.narrow_defining_rules` atom: variable subject, premise `<B>__nw_<10 hex>` whose base is exactly the conclusion class B, and TV `(CTV (STV 1.0 0.99) (STV 0.0 0.0))`. The label is not used.
   - Tests: the parser rule r1 (pilot -> person) is admitted, both through trivial_reason and through load_candidates. The narrow_defining_rules output is recognised. Five near-shapes are admitted (wrong tv, not CTV, base != B, ground subject, bad hash). The echo base must come from an exact nwdef.
3. **pc_admit rule header** comment corrected. Inverted steps are classified like `by` steps. Weighted branches with any other head fail open. "Defining rule" means the exact shape.
4. **Guard refusals logged.**
   - `WMTMOrchestrator._note_guard_refusals` copies `_is_trivial` refusals made during admit_pc_candidates into info, tagged `by="guard"`, and adds them to trivial_refused_n, trivial_refused_guard_n and dropped["trivial"]. `log_admission` then writes them to admit_log.jsonl.
   - When no guard refusal happens, info keeps its old shape.
   - Tests: test_guard_refusals_reach_admit_log, test_no_guard_refusal_leaves_info_shape.
5. **Canaries as tests.**
   - Frozen B runs r1/r2/r3 must refuse 12/14/10, all narrow_echo, through trivial_reason and through load_candidates.
   - The s49 control must admit 49/49 with non-empty rules and 0 missing steps. This test failed on the old controls_s49.json, which is how the fail-open was found.
   - Plus a unit test for step_coverage.

## Numbers (recompute.py)
| run | result |
|---|---|
| r1 | 12 goals, refused 12 narrow_echo, load_candidates off/on 12/0 |
| r2 | 14 goals, refused 14 narrow_echo, load_candidates off/on 14/0 |
| r3 | 10 goals, refused 10 narrow_echo, load_candidates off/on 10/0 |
| s49_run_snap / s49_run_live | 49 results, with_rules 49, steps 67, missing 0, refused 0 |
| A_v3 / A_v3r1 | 4 proved, 0 refused (weak control: no rule atoms, fails open by design) |

admit.json sha256s are unchanged (s49_run_live b7125a49…, s49_run_snap 1467d078…).

## Disclosure
The parent report's "s49 keeps 49/49" claim was vacuous: rules were empty, so the filter failed open on every row. This report replaces that claim with the figures above.

## Parse calls: 0. Live changes: none.
