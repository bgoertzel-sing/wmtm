# t-2026-11-10-wmtm-trivial-filter

## Summary
The order asked for a named admission rule in pc_admit that refuses a derived conclusion when its proof is only an nwdef head-noun step, or only an echo of the Narrow restriction in its own premise, applied to facts already in the store. It also asked for the GAP-5 strict xfail to flip and for B to be rerun on the frozen parses r1/r2/r3. All of that is done. The rule `trivial_restatement` is controlled by the flag `admit_trivial_filter`, which defaults to on. It classifies the proof term and the rule atoms that proof cites, never symbol names. Each refusal is logged to admit_log.jsonl and counted. There are 20 synthetic tests, each trivial shape with a negative control, and two-step and cross-rule conclusions are still admitted. GAP-5 now passes and the full suite passes (889 passed, 41 skipped, 7 xfailed; the 7 are the other GAP xfails). 0 parse calls.

On r1/r2/r3 the filter refuses 12/14/10 of 12/14/10 B conclusions, all `narrow_echo`, with 0 disagreements against narrow-preload's independent trivial_echo labels. **The count rule therefore fails on all three parses after the filter** (0C < A's 2C): every B conclusion on these parses was trivial, so "no non-trivial conclusion refused" holds but is vacuous here (0 non-trivial existed). The non-trivial check comes from controls: the s49 snapshot (49 real conclusions with their cited rules) keeps 49/49. Open for a human: with the filter on, B on the 533c2274 parses contributes nothing new. That is the intended effect, but it means B needs parses that yield non-echo rules before it can pass the count rule.

## Base and pins
- Branch hive/t-2026-11-10-wmtm-trivial-filter (not pushed): from hive/t-2026-11-10-wmtm-narrow-preload f442045, merged hive/t-2026-11-10-wmtm-design-gap-check 265062e (merge 24cd760, no conflicts), then the code commit 8849379 and the report commit. Hive base 27c1a41.
- PeTTaChainer b6aacc68 (~/scratch/ppv/pc), PeTTa 3681b9b, Man Hin parser 533c2274 (prompt 1585e873).

## The rule (pc_admit.py, `TRIVIAL_RULE = "trivial_restatement"`)
Trivial proof shapes, exactly:
1. **nwdef_head_noun**: every step is `(by L ...)` or a weighted `(inverted L ...)` through a defining rule `(: L (Implication (Member $x S) (Member $x B)) (CTV ..))`.
2. **narrow_echo**: a step through a rule `(Implication (Member v S) (Member v C))` (same subject v on both sides) where S is the deterministic named form (`narrow_symbol`) of `(Narrow B (Member C))` or `(Narrow B (Mod C))`, and B comes from S's own defining rule. The rule only restates the restriction already inside its premise. Steps may also be nwdef steps.
In both cases every step must be applied **directly** to asserted fact labels (sp<n>/wm<n>), alone or revised together (merge/revision, factored-revision). A factored-revision branch whose prior has confidence 0 contributes nothing and is skipped.
Not trivial (admitted, fail-open): any other rule; a step over a derived premise (two-step chain); two different rules revised together (cross-rule); a weighted branch that is not an `inverted` rule step (e.g. `reported`); unknown proof heads; missing rule atoms; fact-only proofs (those are already dropped as `asserted`).
The decision reads the parsed proof term plus the cited rule atoms and compares symbols structurally (S against narrow_symbol of the reconstructed Narrow form). A label named `nwdef_*` is not trusted (test `test_control_ordinary_rule_with_nwdef_like_label_admitted`).

Where it runs:
- Worker side, `write_admit_file`: each result now carries `rules`, the cited rule atoms plus the defining rule of each cited rule's premise class (`proof_rules`).
- Cycle side, `load_candidates`: refused before the caps, so a restatement takes no slot. `dropped["trivial"]` (present only when >0, so existing dropped records keep their shape), `trivial_refused_n`, `trivial_refused` = [{rule, reason, goal, steps}], written to admit_log.jsonl by `log_admission`.
- `WMTMOrchestrator._admit_derived`: the same check (`_is_trivial`) guards any pc_deduction candidate with a proof, so admission paths other than load_candidates cannot bypass it. It is counted in `trivial_refused_n` and keeps the last 200 refusals. `admit_reasoner` and `admit_on_snapshot` set the guard from the same flag.
- Flag `admit_trivial_filter` (`WMTM_ADMIT_TRIVIAL_FILTER`, bool, default true), with a README flags-table row. Not set in the live flags file (no live flag change).
- Utility, eviction and promotion are untouched.

## Tests
- tests/test_trivial_filter.py (20): each shape refused (nwdef over a fact, nwdef over revised facts, Narrow echo on the r1 proof shape, Mod restriction, weighted inverted nwdef), each with a negative control (ordinary rule with an nwdef-like label; rule concluding a class other than the restriction; echo rule without its defining rule). Also admitted: two-step chain, two trivial steps chained, cross-rule revision, weighted non-inverted branch, missing atoms, fact-only proof. Plus proof_rules collection, load_candidates refuse+log+count, flag off admits, flag default on, orchestrator guard, admit_on_snapshot honours the flag.
- GAP-5 (tests/test_design_s12_gapcheck.py): xfail removed. **Disclosure:** the test's two candidates had no proof (provenance was only `{"reasoner": "pettachainer"}`). A real PeTTaChainer candidate always carries its proof term, and the filter classifies proof shape, so I gave them realistic provenance: an nwdef step over a fact for "an apple_tree is a tree", and a two-step chain for "cats are animals". The texts, sources, the forget loop and the assertion are unchanged. The trivial one is now refused, so `t is None` holds.
- Full suite: 889 passed, 41 skipped, 7 xfailed (tests/ plus normaliser-v2 tools). The two failures in my first run (test_pc_admit dropped-dict shape; README flags sync) are fixed as described above.

## Frozen rerun (acceptance 3)
Same frozen stores as narrow-preload (/tmp/npl/store/<r>_after), same run_b.sh with outputs redirected to ~/scratch/trivf, WMTM_EVAL_FROZEN_STORE guard on, canary ok, 0 timeouts, 0 add_fail. Goals and proved counts are identical to narrow-preload (12/14/10, all proved). Judged with F3 v3 W1-W4, DEVIATION_1 and the v2 W1 rule (narrow-preload judge inputs). A = 2C/2W.

| parse | before: goals, C/W/U/unjudged | trivial / non-trivial | refused (reason) | after: kept, C/W | count rule before → after |
|---|---|---|---|---|---|
| r1 | 12, 6/0/1/5 | 12 / 0 | 12 (narrow_echo 12) | 0, 0/0 | HOLDS → FAILS |
| r2 | 14, 6/2/1/5 | 14 / 0 | 14 (narrow_echo 14) | 0, 0/0 | HOLDS → FAILS |
| r3 | 10, 5/0/1/4 | 10 / 0 | 10 (narrow_echo 10) | 0, 0/0 | HOLDS → FAILS |

- Non-trivial refused: 0 on every parse. There were 0 non-trivial conclusions to refuse, so this is vacuous on r1-r3.
- The real admission path (load_candidates, flag off vs on) admits 12/14/10 vs 0/0/0, with trivial_refused_n 12/14/10.
- The trivial/non-trivial split uses narrow-preload's independently computed trivial_echo label. The filter agrees with it on all 36 (0 disagreements).
- nwdef_head_noun alone never occurs in these runs (the goal ranker does not propose head-noun goals there). That shape is covered by synthetic tests only.
- Mesto §11: every B conclusion is dropped, each for the same reason, "trivial_restatement / narrow_echo" (per goal in evidence/SUMMARY.json parses.*.rows). A's four conclusions are unaffected (see controls).

Non-trivial controls:
- s49 snapshot (/tmp/s49 run_snap and run_live, t-2026-11-10-wmtm-score-49-goals, real KB with cited rules): 49/49 and 49/49 admitted, 0 refused. Proofs and cited atoms are in evidence/controls_s49.json.
- A (f3-ab-v3, 4 proved each in A_v3 and A_v3r1): 0 refused. Weak control: those shadow records carry no rule atoms, so the filter fails open by design.

## Parse calls: 0
No parser or LLM path ran. run_b.sh reads frozen stores only, with the frozen-store guard on.

## Evidence (ids, parser symbols, counts, hashes; no note text)
- evidence/SUMMARY.json, runs/r{1,2,3}/admit.json and shadow.jsonl, controls_s49.json.
- `python3 reports/t-2026-11-10-wmtm-trivial-filter/tools/recompute.py` (repo root) re-derives every number above through `trivial_reason` and `load_candidates` and prints RECOMPUTE_OK. It checks the admit.json sha256s.
- Tools: make_evidence.py, recompute.py, run_b.sh.
