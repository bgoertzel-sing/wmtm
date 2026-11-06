# Proof kind and STV per arm B answer (P4 rev4; replaces rev3/PROOF_KINDS.md, review 1 of rev3)

Source: rev4/nwdef_ab/<variant>/shadow.jsonl, same spec, PeTTaChainer bdae8d7e. Variants: full = spec_B with nwdef defining rules; nonwdef = same spec with every nwdef_* atom removed; min_nw/min_no = single note (sp171, sp172, x5_implication, +/- nwdef_tree rule).

Correction: rev3 called every B proof "antecedent completion". That was wrong. In every full-variant proof the premise (e.g. sp172) is an asserted fact; the engine factored-revises it with an estimate obtained by inverting the nwdef rule from a prior of STV 0.5/0.0, and the revision lowers confidence from 0.7 to ~0.20. Removing the nwdef rules gives the same goals proved directly by the parser implication at 0.9/0.7. The nwdef rules are not the source of any proof.

| goal | full STV | full proof | nonwdef STV | nonwdef proof | judgment (rev3 W4) |
|---|---|---|---|---|---|
| (Member sk_coverage_1__i_ep_note_20261104T151833Z shown) | 0.9995/0.2017 | direct premise revised with inverted nwdef estimate (mem_inh) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261104T151833Z__c1_implication) | CORRECT |
| (Member sk_bundle_1__i_ep_note_20261103T203949Z whole) | 0.9995/0.2017 | direct premise revised with inverted nwdef estimate (mem_inh) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261103T203949Z__x2_implication) | CORRECT |
| (Member sk_commit_1__i_ep_note_20261028T185132Z staged) | 0.9995/0.2017 | direct premise revised with inverted nwdef estimate (mem_inh) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261028T185132Z__x2_implication) | CORRECT |
| (Member sk_commit_2__i_ep_note_20261028T185132Z single) | 0.9995/0.2017 | direct premise revised with inverted nwdef estimate (mem_inh) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261028T185132Z__x4_implication) | CORRECT |
| (Member sk_output_1__i_ep_note_20261028T185132Z verbatim) | 0.9995/0.2017 | direct premise revised with inverted nwdef estimate (mem_inh) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261028T185132Z__x9_implication) | CORRECT |
| (Member sk_tree_1__i_ep_note_20261103T004843Z working) | 0.9995/0.2017 | direct premise revised with inverted nwdef estimate (mem_inh) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261103T004843Z__x5_implication) | WRONG |
| (Member sk_diff_1__i_ep_note_20261104T051320Z tested) | 0.9995/0.2017 | direct premise revised with inverted nwdef estimate (mem_inh) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261104T051320Z__x6_implication) | CORRECT |
| (Member sk_check_py_1__i_ep_note_20261028T185959Z stdlib_only) | 0.9995/0.2017 | direct premise revised with inverted nwdef estimate (mem_inh) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261028T185959Z__x5_implication) | CORRECT |
| (Member sk_bundle_1__i_ep_note_20261028T190214Z acl_d) | 0.9995/0.2017 | direct premise revised with inverted nwdef estimate (mem_inh) | - | none (-) | CORRECT |
| (Member sk_config_1__i_ep_note_20261028T185132Z effective) | 0.9097/0.1008 | direct premise revised with inverted nwdef estimate (-) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261028T185132Z__x10_implication) | CORRECT |
| (Member sk_note_2__i_ep_note_20261028T153222Z closed) | 0.9995/0.2017 | direct premise revised with inverted nwdef estimate (mem_inh) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261028T153222Z__x2_implication) | CORRECT |
| (Member sk_config_1__i_ep_note_20261028T185959Z effective) | - | none (-) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261028T185959Z__x6_implication) | NOT PROVED |
| (Member hive_t_2026_10_28_goalchainer_v2_status local) | 0.9995/0.2017 | direct premise revised with inverted nwdef estimate (mem_inh) | 0.9/0.7 | direct (parser implication) (i_ep_note_20261028T190214Z__n7_implication) | WRONG |

Example (sk_tree_1, full): `(: (by mem_inh (conjunction (factored-revision sp172 (prior (STV 0.9999987373769259 0.99)) (((inverted nwdef_tree__nw_c435aca35a with cpu (prior (STV 0.5 0.0))) sp171))) i_ep_note_20261103T004843Z__x5_implication)) (Member sk_tree_1__i_ep_note_20261103T004843Z working) (STV 0.9994878785130816 0.20169698940218483))`
