# t-2026-11-12-wmtm-parser-master-adopt-v2 (revision 2, review 1 fixes)

Supersedes: t-2026-11-12-wmtm-parser-master-adopt

## Summary
The task was to adopt the Man Hin parser master recipe (sph 24e37182) in the WMTM shadow loader, re-parse the 20 f3-ab notes sentence by sentence, and compare the result with the old loader (M17 r1-r3) and with live F3 v3, using the pre-registered f3-ab criterion. The loader works: arm B proves all its goals (105/105, and 119/119 in the sensitivity run), the canary passes and the negative control does not fire. Every goal now has a hand verdict. Main arm: 97 correct, 4 wrong, 4 unclear. Sensitivity arm (which also builds goals from the parser's per-sentence adjective rules): 110 correct, 4 wrong, 5 unclear.

Recommendation: do not adopt yet. The pre-registered count rule (correct(B) >= correct(A) and wrong(B) <= wrong(A), A = live F3 v3 at 2C/2W) FAILS for both arms as a whole, because B has 4 wrong goals. It HOLDS for the 23 goals that are not restatements (22C/1W). 82 of the 105 goals are restatements (77 symmetry, 5 coref links) that the shipped trivial filter does not catch, and 3 of the 4 wrong goals are among them. Once labels are unique per note, no goal joins two notes (W1 = 0). Mesto §11: 10 earlier conclusions are dropped, and 4 of those are real losses of correct conclusions. Open decisions for a human: (1) whether to extend the trivial filter to the symmetry and coref-link restatements, after which the count rule would be re-run; (2) whether to seed the parser's per-sentence adjective implications as goal sources (the sensitivity arm), which recovers 8 of the 12 old-loader goals but also brings back the 2 goals F3 v3 judged wrong (see Disagreement).

## Review 1 findings, row by row
| finding | fix | where |
|---|---|---|
| R1 README flags table missing 2 flags; full suite | rows added; full suite 1356 passed, 49 skipped, 5 xfailed, exit 0 | bd03425 |
| R2 real parser atoms in report | this report uses goal ids (b01-b119), rule ids and shapes only; goal atoms and sentence wording are in EV armB/verdicts/wording.tsv (mode 640) | this file |
| R3 W1 multi-note came from label collisions | master_loader adds the note suffix to statement labels, with a test; reran both arms; multi-note = 0 in both; 29 goals with no note are KB-only so_sym | 53e5d9b; armB/full_s2, armB/sens_s2 |
| R4 per-goal C/W/U, trivial split, Mesto §11, W1, count rule vs both A arms | all 105 + 14 goals judged; tables below | armB/verdicts/*.tsv, countrule.txt, mesto_s11.tsv |
| R5 missing list ranked per note with ids/shapes, wording in EV | missing_ranked.tsv (10 rows, ranked) | armB/verdicts/missing_ranked.tsv |
| R6 rules sha + engine commits | seeded_rules.pettachainer-master.metta sha256 9c58f2e0...0454; PeTTa 3681b9b; PeTTaChainer b6aacc68 | armB/pins.txt |
| lesser: loader not wired in build_snapshot | stated: only the worker spec path (load_order=master_ops) uses master_loader; wmtm/pc_shadow.build_snapshot still calls _master_load (load_order=master) and does not use master_loader | Limits |
| lesser: 21 implications, not 14 | 21 adjective-class implication atoms, 21 distinct labels; 14 become goals; the 7 others are nested inside Theme/Directive or have an event consequent | armB/verdicts/impl_gap.txt |
| lesser: modes 640 | no evidence file is world-readable (find -perm /o+r = 0) | EV |
| lesser: Supersedes line | added at the top | this file |

## Commits (branch hive/t-2026-11-12-wmtm-parser-master-adopt-v2, unpushed)
- 47bbcd0 pins sph 24e37182 prompt sha (opt-in), master_meta in the shadow record
- 15fabb0 wmtm/master_loader.py + 3 synthetic tests (shared class once, name table, preds before load)
- f6439a9 pc_shadow load_order=master_ops; legacy path unchanged
- 7122df3 integration test (canary/neg gate, 0 add/pred fail)
- 46ad9f2 tools/recompute.py
- 1092085 report revision 1
- bd03425 README flags rows (R1)
- 53e5d9b per-note label suffix + test (R3)
- this commit: report revision 2, recompute.py extended (verdict counts, count rule, Mesto drop list)

## Pins (armB/pins.txt)
PeTTa 3681b9baa28d (clean); PeTTaChainer b6aacc686675 (only untracked examples/indprobe/); sph 24e37182e64a; seeded_rules.pettachainer-master.metta sha256 9c58f2e01f8db9a67553e3b5985de107d1bd5941b2ecb65337d45b4d0c2b0454 (280 rules, 165 KB predicates, 16 shared defs, 1935 ops); rules.yaml sha256 e2c37881...0dcb; prompt sha256 257425b2...4809; worker config armB/worker_config_B.json sha256 8ff675eb...0f76.

## Evidence
/srv/hive-evidence/t-2026-11-12-wmtm-parser-master-adopt-v2 (SHA256SUMS at the root). `python3 tools/recompute.py <EV>` checks the sums and reprints every count below, then RECOMPUTE_OK.

## Results
| run | notes | goals | proved | canary | neg | multi-note |
|---|---|---|---|---|---|---|
| whole-note A legacy / B master (full) | 19 | 13 / 13 | 13 / 13 | ok | not proved | - |
| sentence arm B full_s2 | 20 | 105 | 105 | ok | not proved | 0 |
| sentence sens_s2 (+ per-sentence adjective implications) | 20 | 119 | 119 | ok | not proved | 0 |

Sentence parse: 129 calls, 124 ok, at most 30 in any rolling hour, 0 rate-limit errors. Whole-note: one note failed 3/3 with an upstream internal error and was excluded; whole-note A/B measures load order only (0 diffs).

Rules that fired (full_s2): coref_sym 48, so_sym 29, coref_patient 5, coref_member 5, same_coref 3, coref_agent 3, coref_possession 3, coref_theme 2, coref_bearer 2, month_class 2, subset_is_part 1, partof_trans 1, becauseof_cause 1. sens_s2 adds 14 `sN_xM_implication` goals.

## Verdicts (hand-judged against the source sentence)
| group | goals | C | W | U | wrong / unclear ids |
|---|---|---|---|---|---|
| symmetry restatements | 77 | 72 | 1 | 4 | W b17 (pronoun linked to the wrong referent; b18 has the right one); U b15, b19, b30, b45 |
| coref links | 5 | 3 | 2 | 0 | W b62, b63 (event node equated with the note) |
| non-restatement | 23 | 22 | 1 | 0 | W b68 (modifier folded into the class name, parser artifact) |
| full_s2 total | 105 | 97 | 4 | 4 | |
| adjective implications (sens only) | 14 | 13 | 0 | 1 | U b114 (adjective attached to the task-id symbol, not the branch) |
| sens_s2 total | 119 | 110 | 4 | 5 | |

Of the 77 symmetry goals, 29 are KB-only ScaleOpposite symmetries (so_sym on shared pole defs, b74-b102) with no note.

## Count rule (PREREG t-2026-11-07-wmtm-f3-ab item 1)
| B set | C/W/U | vs A_v3 (live F3 v3) 2C/2W |
|---|---|---|
| full_s2, all | 97/4/4 | FAILS (4W > 2W) |
| full_s2, non-restatement | 22/1/0 | HOLDS |
| sens_s2, all | 110/4/5 | FAILS (4W > 2W) |

Old loader M17 r1/r2/r3 (9/11/8 goals, judged with the F3 v3 B_v3 verdicts): 5C/1W/3 not judged, 6C/1W/4 not judged, 5C/1W/2 not judged. The not-judged rows have no earlier verdict, so B cannot be scored against M17 under the count rule. M17 is used for the Mesto drop list only.

W1 (cross-note wrong conclusion): 0 in both arms. No proof uses premises from two notes.

Disagreement: F3 v3 judged the 2 "effective" goals (notes 185132Z and 185959Z; b116, b119 here) WRONG, under W1 through a shared nwdef symbol. Here they come from a same-sentence adjective implication with no cross-note join, and I judged them correct. If the F3 v3 verdict is kept, sens_s2 becomes 108C/6W/5U and still FAILS.

## Mesto §11: conclusions dropped by B (sens_s2), ranked (armB/verdicts/missing_ranked.tsv)
| rank | note | prior | kind | reason (shape) |
|---|---|---|---|---|
| 1 | 185132Z | B_v3 C, M17 x3 | lost correct | sentence worded differently; no adjective implication emitted |
| 2 | 185959Z | B_v3 C | lost correct | no adjective implication emitted for this class |
| 3 | live entity | A_v3 C | lost correct | parse gives Member witnesses, no flat Inheritance |
| 4 | live entity | A_v3 C | lost correct | no link from the live entry entity to the class |
| 5 | 153222Z | B_v3 C | variant | skolem number only; same referent kept as another skolem |
| 6 | 122745Z | M17 r2 only | weak prior | no adjective implication in s02/s03 parse |
| 7 | 104T051320Z | M17 r2 only | weak prior | no adjective implication in s02 parse |
| 8 | 190214Z | M17 r1 only | variant | spelling variant of a kept class |
| 9 | live entity | A_v3 W | dropped wrong | live-loader entity not in the sentence parse |
| 10 | live entity | A_v3 W | dropped wrong | live nwdef entity not in the sentence parse |

full_s2 keeps 0 of the 20 earlier conclusions; sens_s2 keeps 10.

## Limits
- The loader is wired only into the worker spec path (pc_shadow worker, load_order=master_ops). wmtm/pc_shadow.build_snapshot (the live shadow) does not use master_loader. Adoption would need that wiring as a separate change.
- The shipped trivial filter (pc_admit.trivial_reason) catches 0 of the 82 restatements.
- Verdicts are by one judge (me) against the source sentence; wording is in EV only.
- goalchainer is off in this offline A/B, so criterion items about goal escalations were not exercised.

## Open
- Decisions (1) and (2) from the Summary.
- Cleanup after review (/tmp/mav2, worktree back to main), only when a human OKs it.
