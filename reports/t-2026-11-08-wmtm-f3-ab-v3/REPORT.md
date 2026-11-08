# t-2026-11-08-wmtm-f3-ab-v3: F3 A/B, review items A-D + criterion-5 extras

Supersedes: t-2026-11-08-wmtm-f3-ab-v2
Supersedes: t-2026-11-07-wmtm-f3-ab

## Summary
This round finishes the review items on the F3 A/B, which compares live wmtm (A) with the fork that has no wmtm-side rules (B, 3288bf2). Items C and D are fixed in commit 1571d80. is_derivation now refuses to count a factored-revision or merge-revision over facts that are already stored as a derivation, and there are negative controls for this. The kbA/kbD/kbH tests now check the exact truth values. Item B is done: in 5 runs I queried B's knowledge base directly for each of A's 4 dropped conclusions, and the results were the same every time. B has no exact or class-level proof for 3 of them. For the fourth (goalchainer_v2_status branch), B only revises a fact it already stores, so it is not a new conclusion. The evidence is committed without note text, and a stdlib recompute re-derives W1-W3 from the 12 committed shadow records. The result is the same as v2: B has 8 correct, 2 wrong (both W1) and 1 unclear, A has 2 correct and 2 wrong, and gate 1 holds in every run.

Propose deploy: no, not yet. The count rule and the warm-up and budget gates hold. But this offline A/B did not exercise criterion 5 (goal escalations, evictions, recent-focus use): goalchainer is off in both arms, and the shadow never calls the cleanup or context code. B also still loses A's 2 correct flat-Inheritance conclusions. Open for a human: (1) whether a replay with goalchainer and the context path turned on should be run before deploy, (2) the W1 reading of the cross-note "config effective" pair, (3) whether the parser should emit flat Inheritance.

## §11 per-conclusion diff, inline (ids/hashes only)
| A conclusion | A premises (sp id; source note id) | A verdict | B native query result (ITEM_B.md, 5/5 runs identical) | Why B drops it |
|---|---|---|---|---|
| (Inheritance chat_send valid) | sp108, sp110; ep-note-20261028T185959Z | WRONG | 0 proofs exact; class-level `(Inheritance chat_send $c)` gives only the reflexive chat_send chat_send; `(Member $x valid)` 0 | B emits 0 flat Inheritance; no premise. Dropping a WRONG conclusion is a gain |
| (Member hive_t_2026_10_28_goalchainer_v2_status branch) | sp61, sp62; ep-note-20261028T190214Z | WRONG | 1 answer: factored-revision/merge-revision over asserted sp118-sp121 via nwdef_branch__nw_* | Stored as B fact sp118 (not a goal); per item C the revision answer is not a derivation. Wrong claim remains a stored fact |
| (Inheritance hive_progress_report report) | sp24, sp25; ep-note-20261104T181709Z | CORRECT | 0 exact, 0 Member; class-level gives only the reflexive | B parses "report" as Member sk_report_* witnesses. Lost correct conclusion |
| (Member turn_without_send_entry entry) | sp106, sp107; ep-note-20261028T185959Z | CORRECT | 0; `(Member $x entry)` 0; `(Inheritance ltm_entry entry)` 0 | No ltm_entry -> entry link in B. Lost correct conclusion |

## Commits (branch hive/t-2026-11-08-wmtm-f3-ab-v3, on v2 head 61c2568)
- 1571d80 items C+D: wmtm/pc_admit.py is_derivation, tests/test_f3v2_native_chain.py (+47), wmtm/workers/pc_shadow.py docstring, docs/RUNTIME.md.
- 00fa834 evidence: ITEM_B.md + item_b_queries.py, CRITERION5.md, runs/ (12 shadow records), extract.json (premise id -> source note id/fact, nw-symbol -> notes, gate rejects), W4.json, JUDGMENTS.json (reasons replaced by "hand-judged", no note text), worker_config_A/B.json, RUNS_TABLE.md, B_CHECKOUT.txt, recompute.py.

## Gates (PREREG t-2026-11-07-wmtm-f3-ab)
1. Count rule: B 8C/2W/1U and A 2C/2W in all 6 runs per arm. HOLDS. W1 is now re-derived mechanically: the shared symbol nwdef_config__nw_b1a247bbd8 joins notes 185132Z and 185959Z.
2. §11: inline above.
3. Warm-up: B is at most 2.93 s, against a 120 s limit. HOLDS.
4. Budget: unchanged from Nov7 (parse 1.535x, 66.6 s median, 0 429). B query total is at most 3.66 s. HOLDS.
5. Criterion-5 extras: NOT EXERCISED (CRITERION5.md).

## Reproduce
`env -i PATH=/usr/bin:/bin python3 -S reports/t-2026-11-08-wmtm-f3-ab-v3/recompute.py` prints RECOMPUTE_OK.
Item B: `python3 item_b_queries.py v3rN` on pop-os (needs the private built specs under /tmp/f3/ab).
Engine: PeTTa 3681b9b + PeTTaChainer bdae8d7e (WMTM_PC_PETTA / WMTM_PC_VENDOR).
Full suite on 00fa834 with engine env: 817 passed, 26 skipped (113 s). A premises in the §11 table re-checked against extract.json (v3r1).

## Branch state
hive/t-2026-11-08-wmtm-f3-ab-v3 is committed locally on pop-os and NOT pushed: pop-os has no GitHub credentials (push fails with "could not read Username"). A human with credentials must push it; nothing goes to main.
