# B (P4 rev3) hand judgments on PeTTaChainer bdae8d7e (current pin), written 2026-11-05 ~17:56 PDT by protocosmo2
Run: bdae8d7e/shadow_B.jsonl (real worker wmtm.workers.pc_shadow, timeout 10 s, budget 200 s, add_fail 0, canary OK, negative OK).
Supersedes the 202b9379 run (superseded_202b9379/shadow_B.jsonl, judged in B_W4_JUDGMENTS.md). Same goal set (13 goals, all from rule_goal_pool, 1 hop).
Caveat: NOT blind (judge saw the arm and the STVs). Same rule as P3_W4_JUDGMENTS.md: CORRECT if the source note supports the fact as stated, WRONG if the source contradicts it or the parse changes its meaning.
Judgments for goals 1-10 and 13 are unchanged from B_W4_JUDGMENTS.md (same atoms; only the STV changed).
| # | goal | STV (bdae8d7e) | proof kind | judgment |
|---|---|---|---|---|
| 1 | (Member sk_coverage_1__i_ep_note_20261104T151833Z shown) | 0.9995/0.2017 | inverted nwdef (antecedent completion) | CORRECT |
| 2 | (Member sk_bundle_1__i_ep_note_20261103T203949Z whole) | 0.9995/0.2017 | inverted | CORRECT (weak) |
| 3 | (Member sk_commit_1__i_ep_note_20261028T185132Z staged) | 0.9995/0.2017 | inverted | CORRECT |
| 4 | (Member sk_commit_2__i_ep_note_20261028T185132Z single) | 0.9995/0.2017 | inverted | CORRECT |
| 5 | (Member sk_output_1__i_ep_note_20261028T185132Z verbatim) | 0.9995/0.2017 | inverted | CORRECT |
| 6 | (Member sk_tree_1__i_ep_note_20261103T004843Z working) | 0.9995/0.2017 | inverted | WRONG ("working tree" is a compound noun) |
| 7 | (Member sk_diff_1__i_ep_note_20261104T051320Z tested) | 0.9995/0.2017 | inverted | CORRECT |
| 8 | (Member sk_check_py_1__i_ep_note_20261028T185959Z stdlib_only) | 0.9995/0.2017 | inverted | CORRECT |
| 9 | (Member sk_bundle_1__i_ep_note_20261028T190214Z acl_d) | 0.9995/0.2017 | inverted | CORRECT |
| 10 | (Member sk_config_1__i_ep_note_20261028T185132Z effective) | 0.9097/0.1008 | inverted | CORRECT |
| 11 | (Member sk_note_2__i_ep_note_20261028T153222Z closed) | 0.9995/0.2017 | inverted | CORRECT. Source: "The 05:52 CLOSED note supersedes it" (timed out on 202b9379, proved here) |
| 12 | (Member sk_config_1__i_ep_note_20261028T185959Z effective) | - | none | NOT PROVED (10 s timeout; proved on 202b9379). Not counted |
| 13 | (Member hive_t_2026_10_28_goalchainer_v2_status local) | 0.9995/0.2017 | inverted | WRONG (the local BRANCH is local; the task id is not a branch; same conflation as A #0) |
Totals on bdae8d7e: B proved 12/13, correct 10, wrong 2. A (P3): 4 proved, correct 2, wrong 2.
Proof kinds: 12/12 B answers are antecedent completion (inverted nwdef_* rule), 0 direct.
Quality caveat: all B answers are 1-hop restatements of a modifier attached to a per-note witness (low information); A's were cross-note claims. B reaches A's correct count, but the content is not comparable.
