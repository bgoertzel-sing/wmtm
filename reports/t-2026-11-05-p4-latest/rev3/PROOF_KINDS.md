# Proof kind and STV for every A and B answer (P4 rev3, review 2 finding 3 / Track P 8cf5006 requirement)
A = P3 arm A (/tmp/p3_out/ab/A/run/pc_shadow/shadow.jsonl, PeTTaChainer 202b9379, live parser path, timeout 2 s).
B = P4 rev3 arm B (bdae8d7e/shadow_B.jsonl, PeTTaChainer bdae8d7e, parser f44d7b74, timeout 10 s).
"direct" = forward rule chain over asserted facts (inh_trans / mem_inh). "antecedent completion" = proof uses an inverted nwdef_* defining rule.

| arm | goal | STV | proof kind | rule | judgment |
|---|---|---|---|---|---|
| A | (Inheritance chat_send valid) | 0.92/0.83 | direct | inh_trans | see P3_W4_JUDGMENTS.md |
| A | (Member hive_task_ref_ca2632 branch) | 1.0/0.99 | direct | mem_inh | WRONG (task id is not a branch) |
| A | (Inheritance hive_progress_report report) | 1.0/0.99 | direct | inh_trans | see P3_W4_JUDGMENTS.md |
| A | (Member turn_without_send_entry entry) | 1.0/0.99 | direct | mem_inh | see P3_W4_JUDGMENTS.md |
| B | (Member sk_coverage_1__i_ep_note_20261104T151833Z shown) | 0.9995/0.2017 | antecedent completion | nwdef inverted | CORRECT |
| B | (Member sk_bundle_1__i_ep_note_20261103T203949Z whole) | 0.9995/0.2017 | antecedent completion | nwdef inverted | CORRECT |
| B | (Member sk_commit_1__i_ep_note_20261028T185132Z staged) | 0.9995/0.2017 | antecedent completion | nwdef inverted | CORRECT |
| B | (Member sk_commit_2__i_ep_note_20261028T185132Z single) | 0.9995/0.2017 | antecedent completion | nwdef inverted | CORRECT |
| B | (Member sk_output_1__i_ep_note_20261028T185132Z verbatim) | 0.9995/0.2017 | antecedent completion | nwdef inverted | CORRECT |
| B | (Member sk_tree_1__i_ep_note_20261103T004843Z working) | 0.9995/0.2017 | antecedent completion | nwdef inverted | WRONG |
| B | (Member sk_diff_1__i_ep_note_20261104T051320Z tested) | 0.9995/0.2017 | antecedent completion | nwdef inverted | CORRECT |
| B | (Member sk_check_py_1__i_ep_note_20261028T185959Z stdlib_only) | 0.9995/0.2017 | antecedent completion | nwdef inverted | CORRECT |
| B | (Member sk_bundle_1__i_ep_note_20261028T190214Z acl_d) | 0.9995/0.2017 | antecedent completion | nwdef inverted | CORRECT |
| B | (Member sk_config_1__i_ep_note_20261028T185132Z effective) | 0.9097/0.1008 | antecedent completion | nwdef inverted | CORRECT |
| B | (Member sk_note_2__i_ep_note_20261028T153222Z closed) | 0.9995/0.2017 | antecedent completion | nwdef inverted | CORRECT |
| B | (Member sk_config_1__i_ep_note_20261028T185959Z effective) | - | none | - | NOT PROVED |
| B | (Member hive_task_ref_ca2632 local) | 0.9995/0.2017 | antecedent completion | nwdef inverted | WRONG |
