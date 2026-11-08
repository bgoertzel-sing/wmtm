# Item B: native queries of B's KB for each of A's 4 dropped conclusions
Engine: PeTTa 3681b9b + PeTTaChainer /tmp/f3/pc, steps=30, timeout_sec=0 (same as pc_shadow.py:63). KB = built full_B spec of each run (398 atoms, 0 add_fail).
Runs: v3r1, v3r2, v3r3, v3r4, v3r5 (v3 first run: built spec not kept on disk). Counts identical across runs: True.

| For A conclusion | Query | n | Result |
|---|---|---|---|
| chat_send valid | `(Inheritance chat_send valid)` | 0 | - |
| chat_send valid | `(Member chat_send valid)` | 0 | - |
| chat_send valid | `(Inheritance chat_send $c)` | 1 | (: (conditional-implication (ctx proof 1)) (Inheritance chat_send chat_send) (STV 1.0 0.9999)) |
| chat_send valid | `(Member chat_send $c)` | 0 | - |
| chat_send valid | `(Member $x valid)` | 0 | - |
| goalchainer_v2 branch | `(Member hive_t_2026_10_28_goalchainer_v2_status branch)` | 1 | (: (factored-revision (merge/revision (merge/revision (by nwdef_branch__nw_af7c55181b sp121) (by nwdef_branch_ |
| goalchainer_v2 branch | `(Member hive_t_2026_10_28_goalchainer_v2_status $c)` | 8 | (: (factored-revision (merge/revision (merge/revision (by nwdef_branch__nw_af7c55181b sp121) (by nwdef_branch_ |
| progress_report report | `(Inheritance hive_progress_report report)` | 0 | - |
| progress_report report | `(Member hive_progress_report report)` | 0 | - |
| progress_report report | `(Inheritance hive_progress_report $c)` | 1 | (: (conditional-implication (ctx proof 3)) (Inheritance hive_progress_report hive_progress_report) (STV 1.0 0. |
| progress_report report | `(Member hive_progress_report $c)` | 0 | - |
| turn_without_send entry | `(Member turn_without_send_entry entry)` | 0 | - |
| turn_without_send entry | `(Member turn_without_send_entry $c)` | 0 | - |
| turn_without_send entry | `(Member $x entry)` | 0 | - |
| turn_without_send entry | `(Inheritance ltm_entry entry)` | 0 | - |

Reading:
- chat_send valid (A: WRONG): no class-level or exact proof in B; the only answer for `(Inheritance chat_send $c)` is the reflexive (Inheritance chat_send chat_send).
- goalchainer_v2_status branch (A: WRONG): B's answer is factored-revision/merge-revision over the asserted sp118-sp121 (sp118 asserts it directly). Under item C that is not a derivation, so B does not conclude it; the wrong claim is a stored B fact.
- hive_progress_report report (A: CORRECT): no proof, exact or class-level; only reflexive Inheritance. Lost correct conclusion (B parses report as Member sk_report_* witnesses).
- turn_without_send_entry entry (A: CORRECT): no proof; `(Member $x entry)` and `(Inheritance ltm_entry entry)` also 0. Lost correct conclusion.
