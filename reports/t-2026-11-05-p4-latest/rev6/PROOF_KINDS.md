# Proof kind and STV for every A and B answer (P4 follow-up, criterion 3)

Kinds are read from each answer's proof term by `rev6/proof_kind.py` (stdlib; the classifier uses no confidence threshold. Admission in wmtm does: MIN_CONFIDENCE=0.05, see NWDEF_FLAG.md):
- **derivation**: rules applied to asserted facts (`rule-proof` / `by <rule>` over `sp*` / parser rule atoms).
- **antecedent completion**: the term contains an `(inverted <rule> ...)` node, i.e. a premise was estimated by running an implication backwards from its consequent.
- **population prior**: a `(prior ...)` node is itself a premise of an inference step (not the cpu prior of an `inverted`/`reported` estimate, not the revision prior of a `factored-revision`).
A term can contain several kinds; all are listed. No new parses or engine runs: the terms come from the committed shadow outputs (A: P3's arm A run, copied as `rev6/A_shadow.jsonl` with task slugs aliased).

Runs:
- A: P3 arm A, PeTTaChainer 202b9379, live parser path (`rev6/A_shadow.jsonl`)
- B: P4 arm B, PeTTaChainer bdae8d7e, parser f44d7b74, nwdef on (P4 default) (`rev3/bdae8d7e/shadow_B.jsonl`)
- B flag-off: same B spec, WMTM_PC_SHADOW_NWDEF=false (P4 deploy proposal) (`rev5/nonwdef_flag/shadow.jsonl`)

| arm | goal | STV | proof kind | rules in term | W4 judgment (unchanged) |
|---|---|---|---|---|---|
| A | `(Inheritance chat_send valid)` | 0.92/0.83 | derivation | conjunction, inh_trans | see P3_W4_JUDGMENTS.md |
| A | `(Member hive_task_ref_ca2632 branch)` | 1/0.99 | derivation | conjunction, mem_inh | WRONG (task id is not a branch) |
| A | `(Inheritance hive_progress_report report)` | 1/0.99 | derivation | conjunction, inh_trans | see P3_W4_JUDGMENTS.md |
| A | `(Member turn_without_send_entry entry)` | 1/0.99 | derivation | conjunction, mem_inh | see P3_W4_JUDGMENTS.md |
| B | `(Member sk_coverage_1__i_ep_note_20261104T151833Z shown)` | 0.9995/0.2017 | derivation + antecedent completion | mem_inh, nwdef_gain__nw_a3ba169ff4 | CORRECT |
| B | `(Member sk_bundle_1__i_ep_note_20261103T203949Z whole)` | 0.9995/0.2017 | derivation + antecedent completion | mem_inh, nwdef_bundle__nw_55d808a06f | CORRECT |
| B | `(Member sk_commit_1__i_ep_note_20261028T185132Z staged)` | 0.9995/0.2017 | derivation + antecedent completion | mem_inh, nwdef_commit__nw_37671a54d2 | CORRECT |
| B | `(Member sk_commit_2__i_ep_note_20261028T185132Z single)` | 0.9995/0.2017 | derivation + antecedent completion | mem_inh, nwdef_commit__nw_9faa872aae | CORRECT |
| B | `(Member sk_output_1__i_ep_note_20261028T185132Z verbatim)` | 0.9995/0.2017 | derivation + antecedent completion | mem_inh, nwdef_output__nw_75b08ab768 | CORRECT |
| B | `(Member sk_tree_1__i_ep_note_20261103T004843Z working)` | 0.9995/0.2017 | derivation + antecedent completion | mem_inh, nwdef_tree__nw_c435aca35a | WRONG |
| B | `(Member sk_diff_1__i_ep_note_20261104T051320Z tested)` | 0.9995/0.2017 | derivation + antecedent completion | mem_inh, nwdef_diff__nw_935b46b959 | CORRECT |
| B | `(Member sk_check_py_1__i_ep_note_20261028T185959Z stdlib_only)` | 0.9995/0.2017 | derivation + antecedent completion | mem_inh, nwdef_check_py__nw_f28383ce3a | CORRECT |
| B | `(Member sk_bundle_1__i_ep_note_20261028T190214Z acl_d)` | 0.9995/0.2017 | derivation + antecedent completion | mem_inh, nwdef_bundle__nw_45e8b22875, nwdef_bundle__nw_70fead3df8, nwdef_bundle__nw_b5c34d67f4, nwdef_bundle__nw_ec97102765, nwdef_bundle__nw_f10e7aa1ad | CORRECT |
| B | `(Member sk_config_1__i_ep_note_20261028T185132Z effective)` | 0.9097/0.1008 | derivation + antecedent completion | i_ep_note_20261028T185132Z__x10_implication, mem_inh, nwdef_config__nw_b1a247bbd8 | CORRECT |
| B | `(Member sk_note_2__i_ep_note_20261028T153222Z closed)` | 0.9995/0.2017 | derivation + antecedent completion | mem_inh, nwdef_note__nw_1a426631a3 | CORRECT |
| B | `(Member sk_config_1__i_ep_note_20261028T185959Z effective)` | - | not proved | - | NOT PROVED |
| B | `(Member hive_task_ref_ca2632 local)` | 0.9995/0.2017 | derivation + antecedent completion | mem_inh, nwdef_branch__nw_50b94ee13a, nwdef_branch__nw_a33c0de6a2, nwdef_branch__nw_af7c55181b | WRONG |
| B flag-off | `(Member sk_coverage_1__i_ep_note_20261104T151833Z shown)` | 0.9/0.7 | derivation | i_ep_note_20261104T151833Z__c1_implication | CORRECT |
| B flag-off | `(Member sk_bundle_1__i_ep_note_20261103T203949Z whole)` | 0.9/0.7 | derivation | i_ep_note_20261103T203949Z__x2_implication | CORRECT |
| B flag-off | `(Member sk_commit_1__i_ep_note_20261028T185132Z staged)` | 0.9/0.7 | derivation | i_ep_note_20261028T185132Z__x2_implication | CORRECT |
| B flag-off | `(Member sk_commit_2__i_ep_note_20261028T185132Z single)` | 0.9/0.7 | derivation | i_ep_note_20261028T185132Z__x4_implication | CORRECT |
| B flag-off | `(Member sk_output_1__i_ep_note_20261028T185132Z verbatim)` | 0.9/0.7 | derivation | i_ep_note_20261028T185132Z__x9_implication | CORRECT |
| B flag-off | `(Member sk_tree_1__i_ep_note_20261103T004843Z working)` | 0.9/0.7 | derivation | i_ep_note_20261103T004843Z__x5_implication | WRONG |
| B flag-off | `(Member sk_diff_1__i_ep_note_20261104T051320Z tested)` | 0.9/0.7 | derivation | i_ep_note_20261104T051320Z__x6_implication | CORRECT |
| B flag-off | `(Member sk_check_py_1__i_ep_note_20261028T185959Z stdlib_only)` | - | not proved | - | CORRECT |
| B flag-off | `(Member sk_bundle_1__i_ep_note_20261028T190214Z acl_d)` | 0.9957/0.0419 | derivation | i_ep_note_20261028T190214Z__x1_implication, mem_inh | CORRECT |
| B flag-off | `(Member sk_config_1__i_ep_note_20261028T185132Z effective)` | 0.9/0.7 | derivation | i_ep_note_20261028T185132Z__x10_implication | CORRECT |
| B flag-off | `(Member sk_note_2__i_ep_note_20261028T153222Z closed)` | 0.9/0.7 | derivation | i_ep_note_20261028T153222Z__x2_implication | CORRECT |
| B flag-off | `(Member sk_config_1__i_ep_note_20261028T185959Z effective)` | 0.9/0.7 | derivation | i_ep_note_20261028T185959Z__x6_implication | NOT PROVED |
| B flag-off | `(Member hive_task_ref_ca2632 local)` | 0.9/0.7 | derivation | i_ep_note_20261028T190214Z__n7_implication | WRONG |

## Counts

- A: 4 answers, 4 proved; 0 with antecedent completion, 4 derivation only, 0 with a population prior.
- B: 13 answers, 12 proved; 12 with antecedent completion, 0 derivation only, 0 with a population prior.
- B flag-off: 13 answers, 12 proved; 0 with antecedent completion, 12 derivation only, 0 with a population prior.
