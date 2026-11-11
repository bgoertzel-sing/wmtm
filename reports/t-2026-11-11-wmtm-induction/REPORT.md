# t-2026-11-11-wmtm-induction: REPORT

## Summary

The task was to give the WMTM shadow reasoner induction goals, meaning (Inheritance A B) proposed when classes A and B share Member instances, and to measure what they add in B on the frozen stores. The engine does support induction at the pins (PeTTaChainer b6aacc68, PeTTa 3681b9b). It answers through implication-instance-fold, but the confidence is very low: about 0.001 per shared instance (3 shared gave STV 0.8 at confidence 0.003). I added an induction goal generator. It is off by default behind the flags `shadow_induction` and `shadow_induction_min` (default 3).

Result: on the 4 frozen stores (Nov5, r1, r2, r3), induction adds **no real goals**. My first run added 2 goals on Nov5. Both were nwdef alias restatements (result vs result__nw_*), and the trivial filter does not catch that proof shape. The generator now skips alias pairs. After that, goal counts and canary, neg and gate results are the same with induction on and off. **Propose deploy: no.** Leave the flag off until the parser produces classes that share 3 or more real members. Today the stores have at most 2 shared members, and only in trivial pairs. Open for the reviewer: should the trivial filter in pc_admit also refuse nwdef alias Inheritance proofs (outside this task's scope)?

## Engine probe (pins PC b6aacc68, PeTTa 3681b9b)
| case | result |
|---|---|
| 3 shared instances (2 strong, 1 weak) | (Inheritance cat pet) via implication-instance-fold, STV 0.8 conf 0.0030 |
| 1 shared instance | STV 1.0 conf 0.0010 |
| unrelated dog/fish (control) | no answer |
raveninduction example passes; test_pln_induction 20 pass / 0 fail. The probe file was removed after use.

## Store scan
Nov5/r1/r2/r3: no class pair shares 3 or more members. The maximum is 2, and those pairs are all trivial (X vs X__nw_* alias, done/cleanup).

## Code
- `wmtm/pc_shadow.py`: `induction_goal_pool(rel, min_shared, skolem_goals, max_pool, pool)`. It is called from `build_snapshot` only when `shadow_induction` is on. It skips asserted pairs, skolem classes (unless skolem_goals is set) and nwdef alias pairs.
- `wmtm/runtime_config.py` and the README flags table: `shadow_induction` (bool, False) and `shadow_induction_min` (int, 3).
- `tests/test_goal_induction.py`: 6 synthetic tests. 3 shared instances propose a goal; 1-shared control; unrelated control; asserted and skolem pairs skipped; ranked alongside chain goals; nwdef alias skipped.
- Full suite: 907 passed, 41 skipped, 7 xfailed.

## B runs (sandbox, frozen stores, no parse calls, no live changes)
`evidence/summary.tsv` (v1 = before the alias skip, v2 = final):
| store | goals off | goals on v1 | goals on v2 |
|---|---|---|---|
| nov5 (parse 1f1a7a6f) | 9 | 11 (2 alias) | 9 |
| r1 (533c2274) | 12 | 12 | 12 |
| r2 | 14 | 14 | 14 |
| r3 | 10 | 10 | 10 |
Canary (Member grace person) ok, neg (Member grace robot) not proved, and gate rejected broad_category 1 in every run.
Tools: `tools/run_b_ind.sh`, `tools/all.sh`. Run notes: `evidence/runs_v1_NOTES.txt`, `evidence/runs_v2_NOTES.txt`.

## Deviations
- Added the nwdef alias skip after the first B run (v1 evidence kept).
