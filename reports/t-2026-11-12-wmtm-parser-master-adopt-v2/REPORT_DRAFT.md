# t-2026-11-12-wmtm-parser-master-adopt-v2 (DRAFT, numbers pending full s1)

## Summary
(pending: full s1 sentence parse, arm B on all complete notes, hand verdicts, comparison vs old-loader M17 r1-r3 and F3 v3 A_v3 2C/2W)

## Done so far
- Recipe loader wmtm/master_loader.py (15fabb0): KB preds once, 280 seeded master rules, per-sentence lowering with shared name table, preds before statements, shared kind__/by_ defs once.
- pc_shadow load_order=master_ops (f6439a9); integration test (7122df3); test_pc_shadow 25 passed.
- Recompute script tools/recompute.py (46ad9f2), RECOMPUTE_OK on current evidence.
- Whole-note A/B: canary 0/0, pilot 4/4 both arms, full 13/13 both arms; canary ok, neg not proved in all.
- Arm B pilot (5 complete notes from s1): 785 ops, 0 add/pred fail, 39/39 goals proved; by rule so_sym 29, coref_sym 6, same_coref 2, coref_bearer 2.

## Findings
- F1 trivial-filter gap: pc_admit.trivial_reason knows only nwdef_head_noun / narrow_echo; catches 0 of 39 B pilot goals. Structurally 35 symmetry restatements (bi-forward), 4 coref links; 0 join two notes.

## Open
- Full s1 (ETA ~18:10 at 30/h share), missing-conclusions list, SHA256SUMS, final verdict.
