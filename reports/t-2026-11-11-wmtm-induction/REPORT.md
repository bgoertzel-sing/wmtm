# t-2026-11-11-wmtm-induction: REPORT (rev2, after review 1)

## Summary

The task was to give the WMTM shadow reasoner induction goals and to measure what they add in B on the frozen stores. Review 1 said I had checked only the weak engine path. The engine has two induction paths at the pins (PeTTaChainer b6aacc68, PeTTa 3681b9b). The weak one is implication-instance-fold: it works from shared Member instances and gives confidence of about 0.001 per instance. The strong one is conditional-implication over merge/revision. It builds a general rule from class rules that share structure (the §9.1b shape). In a probe, the strong path gave STV 0.60 at confidence 0.70 when base rates were set. With a few Member facts and no base rates, it gave confidence 0.016. With rules only, it gave no answer. On the frozen stores, though, it has nothing to work on. I scanned all 4 stores (Nov5, r1, r2, r3): every class rule is an nwdef alias rule, and every antecedent class has exactly one consequent. So no two rules share structure in the way the strong path needs.

Result: when I run with the shipped threshold (min_shared=3), induction adds no goals on any store. With min_shared=2, it adds one goal, (Inheritance cleanup done), on Nov5, r1 and r3 (Nov5 had the reverse direction). It is proved at STV 1.0 conf 0.0024, and it is now admitted with the correct premise ids: both ep-note sources and all 4 Member facts. Before rev2 these came out wrong. **Propose deploy: no.** Keep `shadow_induction` off. Induction will only matter in two cases: (a) the parser emits class rules that share antecedents or consequents, or (b) wmtm supplies base rates and supports variable Implication goals (see "What variable goals need"). Neither is in place today, and both need a decision from you.

## Review 1 findings, one row each
| # | finding | rev2 action | evidence |
|---|---|---|---|
| 1 | Engine check missed the conditional-implication (§9.1b) path | I probed it at the pins: rules only gives no answer; with base rates, 0.60/0.70; with Member facts, 0.59/0.016. I scanned the frozen stores for rule pairs sharing structure and found 0. I also probed frozen-store goals: cleanup→done (fold, 1.0/0.0024) and the result alias (merge/revision of nwdef + fold, 1.0/0.99, a trivial result). | `evidence/probe_rev2/{a,b,c,d,e}*.metta`, `.answer.txt`, `run.sh`, `run2.sh`; `evidence/scan/rules_scan.jsonl`; `tools/scan_rules.py` |
| 2 | Fold proofs got wrong premise ids (goal-symbol fallback) | `sources_for` (`wmtm/pc_admit.py:83`): for a fold proof with no labels, it now takes the ids from the facts in the goal's `goal_meta` chain. The new `proof_facts` (`pc_admit.py:107`) fills `facts` from that chain. The admitted (Inheritance cleanup done) now has 2 sources and 4 facts, where before it had only one side. | `tests/test_goal_induction.py::test_fold_proof_sources_and_facts_from_chain`; `evidence/summary_rev2.tsv` |
| 3 | Evidence was counts only, not reproducible, and the store claim had no artefact | Committed `shadow.jsonl`, `admit.json` and `spec.json` for 12 runs (4 stores × off / on min3 / on min2), a generator, and a per-goal table (goal, proved STV, admitted, sources, facts). The member-overlap scan is committed too. | `evidence/runs_rev2/*`; `evidence/summary_rev2.tsv` (from `tools/summarize_rev2.py`); `evidence/scan/members_scan.jsonl` (`tools/scan_members.py`); runners `tools/run_b_ind.sh`, `tools/all.sh`, `tools/all_min2.sh`; `tools/cmpruns.py` |
| 4 | No test of the build_snapshot flag path; symmetric pair doubled goal slots | Added flag-on and flag-off tests through `build_snapshot`. `induction_goal_pool` (`pc_shadow.py:363`) now proposes one direction per pair: A→B where the shared set covers more of A, with ties broken by sorted order. | `tests/test_goal_induction.py` (10 pass); full suite 911 passed, 41 skipped, 7 xfailed |

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
In every run, the canary (Member grace person) is proved, the negative (Member grace robot) is not proved, and the gate rejected broad_category once. All goals were proved. I re-ran the 8 off and min3 runs with the rev2 code and compared them to the pre-rev2 runs. Apart from timing fields, `admit.json` is the same. `shadow.jsonl` differs only in `start_ts`, plus one prio_end check count in r1_False (4 vs 3, a timing-dependent loop count).
The direction of cleanup/done differs because Nov5 has more `done` members than r1/r3. The coverage rule picks the direction where the shared set covers more of the antecedent.

## What variable goals need (to use the §9.1b path from wmtm)
1. Goal shape. `_GOAL` (`pc_admit.py:45`) matches only ground binary atoms, so `(Implication (Member $x A) (Member $x B))` is never parsed or admitted. It needs a new goal kind with a variable, mapped to a WMTM rule item, not a fact item.
2. Premise ids. Proofs name rule labels (`by r3`, `inverted r1`). Those labels need to map to item ids, the same way fact labels (sp/wm) do now.
3. Base rates. wmtm emits no `set-base-rate` (I grepped `wmtm/` and found none). Without base rates the path gives no answer, or confidence about 0.016 when it falls back on Member facts. Empirical base rates from Member counts would need a design choice on what population to count over.
4. Trivial filter. An nwdef-only derivation such as probe e must be classed as trivial. The filter already handles the nwdef shape for ground goals, but it would need extending to Implication goals.
5. Input. Even with 1 to 4 in place, the current parser output has no rule pairs sharing structure, so the parser side would need to change too.

## Code (diff vs 1415160)
- `wmtm/pc_admit.py`: chain-based `sources_for` fallback for fold proofs; new `proof_facts`.
- `wmtm/pc_shadow.py`: one direction per pair in `induction_goal_pool`.
- `tests/test_goal_induction.py`: flag-path tests and the chain-sources test.
- `tools/run_b_ind.sh`: optional 6th argument, `shadow_induction_min`.

## Deviations
- The min2 runs go beyond the order. The shipped default stays at 3. I ran min2 only to exercise the admit and premise-id path on real data.
- v1 evidence (`summary.tsv`, `runs_v1_NOTES.txt`) is kept as history.
