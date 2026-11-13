# t-2026-11-12-wmtm-parser-master-adopt-v2 (revision 5, review 4 fixes)

Supersedes: t-2026-11-12-wmtm-parser-master-adopt

## Summary
The task was to adopt the Man Hin parser master recipe (sph 24e37182) in the WMTM shadow loader, re-parse the 20 f3-ab notes sentence by sentence, and compare the result with the old loader (M17 r1-r3) and with live F3 v3, using the pre-registered f3-ab criterion. The loader works: arm B proves all its goals (105/105, and 119/119 in the sensitivity run), the canary passes and the negative control does not fire. Every goal now has a hand verdict. Main arm: 97 correct, 4 wrong, 4 unclear. Sensitivity arm (which also builds goals from the parser's per-sentence adjective rules): 110 correct, 4 wrong, 5 unclear.

Recommendation: do not adopt yet. The pre-registered count rule (correct(B) >= correct(A) and wrong(B) <= wrong(A), A = live F3 v3 at 2C/2W) FAILS for both arms as a whole, because B has 4 wrong goals. It HOLDS for the 23 goals that are not restatements (22C/1W). 82 of the 105 goals are restatements (77 symmetry, 5 coref links) that the shipped trivial filter does not catch, and 3 of the 4 wrong goals are among them. Once labels are unique per note, no goal joins two notes (W1 = 0). Mesto §11: 10 earlier conclusions are dropped, and 4 of those are real losses of correct conclusions. Against the old loader (M17 r1/r2/r3, now fully judged: 8C/1W, 10C/1W, 7C/1W) the count rule also FAILS for B as a whole (4W > 1W) and HOLDS for the non-restatement goals (22C/1W). The per-note label suffix makes a fact that two notes share verbatim count as separate evidence (41 extra copies in s2); no proof in the main arm cites one of them. Open decisions for a human: (1) whether to extend the trivial filter to the symmetry and coref-link restatements, after which the count rule would be re-run; (2) whether to seed the parser's per-sentence adjective implications as goal sources (the sensitivity arm), which recovers 8 of the 12 old-loader goals but also brings back the 2 goals F3 v3 judged wrong (see Disagreement).

Reader-expectation pass (revision 5, order Do item 5): for each of the 20 notes I listed the conclusions a reader would expect, 75 in all (52 firm, 23 uncertain), each with the rule id from the pinned rules file or, where no rule exists, the missing rule shape. B got 8 of the 75. For 33 a rule exists but B did not derive it, almost always because the parse never produced the premise (32 of 33; most often month_class with no Month fact, rank_orders, becauseof_cause). 34 need a rule the file does not have; the most common shapes are clock-time order (hour_order, 7), "superseded means no longer current" (6), sums of counts (5) and "contradicted means no longer holds" (4).
## Review 4 findings, row by row
| finding | fix | where |
|---|---|---|
| 1 Do item 5 / Acceptance 4 not delivered | done: reader-expectation pass over all 20 notes, 75 expected conclusions (3 to 6 per note), each with a rule id or a gap shape, certainty firm/uncertain, B goal id where B got it, and a status (got / rule exists, premise not parsed / rule exists, premise loaded, not derived / no rule). Paraphrases of note text stay on pop-os; the report carries only ids, rule names and counts. recompute.py recounts it | section "Reader-expectation pass"; armB/verdicts/reader_expect.tsv |
| 2 stopgap not named | Limits now says the narrow_preload stopgap in wmtm/semparse_adapter.py stays in place and build_snapshot only knows the whole-note master path | Limits |
| 3 ids of correct non-restatement goals | listed: strict-split survivors b72, b73 (month_class), b103 (subset_is_part), b104 (partof_trans), b105 (becauseof_cause) | Count rule section |
| 4 lesser | duplicate master_meta assignment removed; the worker now calls master_loader.apply instead of its own copy of the loop (tests/test_master_loader.py + tests/test_pc_shadow.py with the pinned engine: 29 passed, 0 skipped). Evidence was produced before this refactor; the load ops and their order are unchanged. Parse use at exactly 30/hour noted as at the cap, not over | wmtm/workers/pc_shadow.py |

## Review 3 findings, row by row
| finding | fix | where |
|---|---|---|
| 1 SHA256SUMS not committed, not readable | SHA256SUMS regenerated (154 files), read granted to hive-reviewer (ACL r--, mask r--; every file in the folder now carries the hive-reviewer entry), and the same file committed as reports/.../SHA256SUMS. recompute.py checks that the committed copy equals the evidence copy | SHA256SUMS (repo and EV); recompute.py "committed SHA256SUMS equals" line |
| 2 stale recompute copy in EV | EV tools/recompute.py replaced by the committed rev4 script (identical bytes; hash in SHA256SUMS) | EV tools/recompute.py |
| 3 off-by-one (6 vs 5 M17 hand verdicts) | corrected to 5 (verdicts_m17_extra.tsv has 5 rows; recompute.py prints the count). Per-run counts unchanged | Review 2 table row 1; Count rule section |
| 4 missing list narrower than Do item 5 | stated as a limit: the list covers only the 10 conclusions earlier runs derived that B dropped (7 notes or entities), not a reader-expectation pass over all 20 notes. Certainty is now an explicit column | Mesto section; Limits |
| 5 loader not wired into the live shadow | unchanged, stated in Limits; acceptance noted as explicit | Limits |
| 6 restatement split uneven | alternative split computed: counting all six coref role rules (bearer, agent, patient, theme, member, possession) as coref-link restatements leaves 5 non-restatement goals, 5C/0W. That HOLDS vs A_v3 (2C/2W) and FAILS vs each M17 run (fewer correct). So the 22C/1W HOLDS line depends on the split; the headline (FAILS as a whole) does not | recompute.py "alt non-restatement" lines; Count rule section |
| 7 review 2 finding 6 truncated | still open; neither worker nor reviewer has its text | Open |

## Review 2 findings, row by row
| finding | fix | where |
|---|---|---|
| 1 count rule against the old loader (M17) not delivered | the 5 M17 goals with no earlier verdict are now hand-judged (all correct). M17 r1/r2/r3 = 8C/1W (9), 10C/1W (11), 7C/1W (8). Count rule: full_s2 all FAILS against each run (C holds, 4W > 1W); full_s2 non-restatement 22C/1W HOLDS against each run; sens_s2 all FAILS against each run | armB/verdicts/verdicts_m17_extra.tsv; recompute.py "M17" lines |
| 2 line-up of A and B note/goal sets not stated | A_v3's 4 goals come from 3 notes (185959Z x2, 190214Z, 104T181709Z). B's goals and proofs touch 15 notes in both arms (same 15 for goals and for proofs; the review's 13 counted proofs that cite a note directly). All 3 A_v3 notes are among B's 15. Per A_v3 goal: 2 DROP (1 wrong, 1 correct: the parse shape changed), 1 ASSERTED as a parsed fact, so never a derived goal (was wrong in A, not counted for or against B), 1 ASSERTED under a new entity name for the same referent (correct content kept, not as a derivation). This corrects the rev2 Mesto reasons for rows 4 and 9 | armB/verdicts/lineup_A_v3_vs_B.tsv |
| 3 suite run skipped the engine | rerun with WMTM_PC_PETTA / WMTM_PC_VENDOR / WMTM_PC_SHADOW_SPH_TEMPLATES set: 1378 passed, 28 skipped, 5 xfailed, exit 0 (total 1411). All 28 remaining skips depend on the environment: WMTM_TEST_GC2_PYTHON (4), WMTM_SEMPARSE_HITL checkout (20), WMTM_REPLAY_DATA (3), PETTA_PARSER/SWIPL for the codec (1). No engine test is skipped; the two new master_loader engine tests ran and passed | suite/suite_rev3_rs.txt (pytest -rs) |
| 4 label suffix changes evidence counting | stated as a consequence. In s2, 29 atom shapes occur under more than one note label: 70 labels, 41 extra copies (s1r had 30 extra). The spec gains 11 atom ops from s1r to s2 (1410 to 1421; 514 preds unchanged), which is the 1924 to 1935 rise. 0 of the 105 full_s2 proofs cite a duplicated label; 20 goals name a duplicated entity and are proved through coref atoms. A fix (one shared label per identical shape, or merge on load) is not made here: it changes what counts as evidence and needs a decision | armB/verdicts/suffix_dupes.tsv; Limits |
| 5 loader not wired into the live shadow | unchanged and stated: order item 2 is only partly met; wiring build_snapshot is a separate change | Limits |
| 6 (text cut off after "He" in both copies received) | pending: the full text of finding 6 did not reach me; it will be addressed when it does | Open |

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
- bbb27b1 report revision 2, recompute.py extended (verdict counts, count rule, Mesto drop list)
- 575cb7e report revision 3 (review 2), recompute.py checks M17 count rule, line-up and suffix duplicates
- 63441e5 report revision 4 (review 3): SHA256SUMS committed, 5 M17 verdicts, alternative restatement split, missing-list scope
- this commit: report revision 5 (review 4): reader-expectation pass, stopgap named, strict-split ids, pc_shadow uses master_loader.apply

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

| B set | vs M17 r1 8C/1W | vs M17 r2 10C/1W | vs M17 r3 7C/1W |
|---|---|---|---|
| full_s2, all 97/4/4 | FAILS | FAILS | FAILS |
| full_s2, non-restatement 22/1/0 | HOLDS | HOLDS | HOLDS |
| sens_s2, all 110/4/5 | FAILS | FAILS | FAILS |

Old loader M17 goals are judged with the F3 v3 B_v3 verdicts plus 5 new hand verdicts (verdicts_m17_extra.tsv); revision 2 left these unjudged.

Restatement split sensitivity (review 3 finding 6): score.py counts only same_coref and coref_bearer as coref links. If all six coref role rules count as restatements, non-restatement is 5C/0W: HOLDS vs A_v3, FAILS vs M17 r1/r2/r3. The 22C/1W line rests on the narrower split. The 5 strict-split goals, all judged correct: b72 and b73 (month_class), b103 (subset_is_part), b104 (partof_trans), b105 (becauseof_cause).

W1 (cross-note wrong conclusion): 0 in both arms. No proof uses premises from two notes.

Disagreement: F3 v3 judged the 2 "effective" goals (notes 185132Z and 185959Z; b116, b119 here) WRONG, under W1 through a shared nwdef symbol. Here they come from a same-sentence adjective implication with no cross-note join, and I judged them correct. If the F3 v3 verdict is kept, sens_s2 becomes 108C/6W/5U and still FAILS.

## Mesto §11: conclusions dropped by B (sens_s2), ranked (armB/verdicts/missing_ranked.tsv)
| rank | note | prior | kind | certainty | reason (shape) |
|---|---|---|---|---|---|
| 1 | 185132Z | B_v3 C, M17 x3 | lost correct | firm | sentence worded differently; no adjective implication emitted |
| 2 | 185959Z | B_v3 C | lost correct | firm | no adjective implication emitted for this class |
| 3 | live entity | A_v3 C | lost correct | firm | parse gives Member witnesses, no flat Inheritance |
| 4 | live entity | A_v3 C | lost correct | firm | no link from the live entry entity to the class |
| 5 | 153222Z | B_v3 C | variant | uncertain (variant) | skolem number only; same referent kept as another skolem |
| 6 | 122745Z | M17 r2 only | weak prior | uncertain (weak prior) | no adjective implication in s02/s03 parse |
| 7 | 104T051320Z | M17 r2 only | weak prior | uncertain (weak prior) | no adjective implication in s02 parse |
| 8 | 190214Z | M17 r1 only | variant | uncertain (variant) | spelling variant of a kept class |
| 9 | live entity | A_v3 W | dropped wrong | firm | live-loader entity not in the sentence parse |
| 10 | live entity | A_v3 W | dropped wrong | firm | live nwdef entity not in the sentence parse |

full_s2 keeps 0 of the 20 earlier conclusions; sens_s2 keeps 10.

Scope: this list is the conclusions earlier runs derived that B dropped (10 rows, 7 notes or entities). The per-note reader-expectation pass follows.

## Reader-expectation pass over all 20 notes (armB/verdicts/reader_expect.tsv)
Method: I read every parsed sentence of each note and wrote down what a reader would conclude from it, beyond restating it. Each row names a rule id from seeded_rules.pettachainer-master.metta (sph 24e37182) or, where the file has no such rule, a gap shape (GAP:<shape>). Certainty is firm or uncertain. Status is computed: "got" if a proved B goal matches; otherwise, for a rule row, whether the rule's head premise predicate occurs among that note's loaded atoms (a loaded premise does not mean all premises are there). One reader's list, so it is a floor, not a full count.

Totals: 75 rows, 20 notes, 52 firm / 23 uncertain. got 8 (b02, b52, b64, b72, b73, b103, b104, b105); rule exists, premise not parsed 32; rule exists, premise loaded, not derived 1 (coref_theme, 122745Z); no rule 34.
Rule exists, not derived, by rule: month_class 13, rank_orders 5, becauseof_cause 4, measure_moreby 2, measure_same 2, coref_theme, days_before_day, subset_is_part, located_trans, located_in_part, unit_atmost, unit_measure 1 each.
No rule, by shape: hour_order 7, supersedes_not_current 6, sum_of_parts 5, contradicts_not 4, directive_inherit 3, group_distribute 2, passed_closes 2, evidence_to_not, note_adjective_impl, exclusive_location, negation_parse 1 each, none_needed_asserted 1 (a fact the parse already asserts; listed for completeness, not a missing rule).

| note | rows | got by B (goal ids) | rule exists, premise not parsed | rule exists, premise loaded, not derived | no rule (gap shape) |
|---|---|---|---|---|---|
| 004843Z | 4 | b52 | located_trans, month_class | - | sum_of_parts |
| 043925Z | 3 | - | located_in_part, month_class, unit_atmost | - | - |
| 045724Z | 3 | - | month_class, rank_orders | - | directive_inherit |
| 051320Z | 3 | - | month_class, rank_orders | - | directive_inherit |
| 051925Z | 3 | - | month_class | - | passed_closes, supersedes_not_current |
| 121808Z | 6 | b73 | measure_moreby | - | contradicts_not, hour_order, sum_of_parts, supersedes_not_current |
| 122745Z | 5 | - | - | coref_theme | directive_inherit, evidence_to_not, hour_order, supersedes_not_current |
| 151833Z | 3 | b02 | month_class | - | contradicts_not |
| 153222Z | 4 | b64 | measure_same | - | hour_order, supersedes_not_current |
| 154242Z | 3 | - | measure_moreby, month_class, rank_orders | - | - |
| 165705Z | 3 | - | month_class, rank_orders, unit_measure | - | - |
| 181709Z | 4 | b105 | month_class | - | negation_parse, sum_of_parts |
| 183317Z | 4 | b72 | days_before_day, subset_is_part | - | sum_of_parts |
| 185132Z | 5 | b103 | becauseof_cause | - | contradicts_not, hour_order, sum_of_parts |
| 185959Z | 5 | - | - | - | contradicts_not, group_distribute, hour_order, note_adjective_impl, supersedes_not_current |
| 190214Z | 4 | - | - | - | exclusive_location, hour_order, passed_closes, supersedes_not_current |
| 193449Z | 3 | - | becauseof_cause, month_class | - | group_distribute |
| 193740Z | 4 | b104 | becauseof_cause, month_class | - | none_needed_asserted |
| 194242Z | 3 | - | becauseof_cause, month_class | - | hour_order |
| 203949Z | 3 | - | measure_same, month_class, rank_orders | - | - |


## Limits
- The loader is wired only into the worker spec path (pc_shadow worker, load_order=master_ops). wmtm/pc_shadow.build_snapshot (the live shadow) does not use master_loader. Adoption would need that wiring as a separate change.
- Per-note label suffix: a statement two notes share verbatim is loaded once per note, so the engine counts it as separate evidence (41 extra copies in s2). No main-arm proof relies on one.
- The shipped trivial filter (pc_admit.trivial_reason) catches 0 of the 82 restatements.
- Verdicts are by one judge (me) against the source sentence; wording is in EV only.
- The reader-expectation pass is one reader's list (75 rows); status checks only the head premise predicate.
- The narrow_preload stopgap in wmtm/semparse_adapter.py stays in place; build_snapshot only knows the whole-note master path. The recipe path (master_ops) is reachable only through a built spec.
- goalchainer is off in this offline A/B, so criterion items about goal escalations were not exercised.

## Open
- Decisions (1) and (2) from the Summary, and whether duplicate shared statements should be merged (review 2 finding 4).
- Review 2 finding 6: text cut off, pending.
- Cleanup after review (/tmp/mav2, worktree back to main), only when a human OKs it.
