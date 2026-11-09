## Summary
This round finishes the review items on the F3 A/B, which compares live wmtm (A) with the fork that has no wmtm-side rules (B, 3288bf2). Item D is fixed in commit 1571d80: the kbA/kbD/kbH tests check exact truth values. For item C, the real safeguard is goal selection. An asserted fact is never a goal, so B never asks for or admits a revision of its own stored facts, and a new test covers this. The 1571d80 is_derivation change only rejects synthetic revision shapes. On the term the engine actually returns, it still says True, so this is now listed as a follow-up design question and not claimed as a fix. Item B is done: in 5 runs I queried B's knowledge base directly for each of A's 4 dropped conclusions, and the results were the same every time. B has no exact or class-level proof for 3 of them. For the fourth (goalchainer_v2_status branch), B returns STV 1.0 0.99 only by revising facts it already stores (sp118-sp121); that fact is never a goal, so it is not a new conclusion. The evidence is committed without note text, and a stdlib recompute re-derives W1-W3 from the 12 committed shadow records. The result is the same as v2: B has 8 correct, 2 wrong (both W1) and 1 unclear, A has 2 correct and 2 wrong, and gate 1 holds in every run.

Propose deploy: no, not yet. The count rule and the warm-up and budget gates hold. But this offline A/B did not exercise criterion 5 (goal escalations, evictions, recent-focus use): goalchainer is off in both arms, and the shadow never calls the cleanup or context code. B also still loses A's 2 correct flat-Inheritance conclusions. Open for a human: (1) whether a replay with goalchainer and the context path turned on should be run before deploy, (2) the W1 reading of the cross-note "config effective" pair, (3) whether the parser should emit flat Inheritance.

# t-2026-11-08-wmtm-f3-ab-v3: F3 A/B, review items A-D + criterion-5 extras

Supersedes: t-2026-11-08-wmtm-f3-ab-v2
Supersedes: t-2026-11-07-wmtm-f3-ab

## §11 per-conclusion diff, inline (ids/hashes only)
| A conclusion | A premises (sp id; source note id) | A verdict | B native query result (ITEM_B.md, 5/5 runs identical) | Why B drops it |
|---|---|---|---|---|
| (Inheritance chat_send valid) | sp108, sp110; ep-note-20261028T185959Z | WRONG | 0 proofs exact; class-level `(Inheritance chat_send $c)` gives only the reflexive chat_send chat_send; `(Member $x valid)` 0 | B emits 0 flat Inheritance; no premise. Dropping a WRONG conclusion is a gain |
| (Member hive_t_2026_10_28_goalchainer_v2_status branch) | sp61, sp62; ep-note-20261028T190214Z | WRONG | 1 answer at (STV 1.0 0.99), 5/5 runs: `(factored-revision (merge/revision (merge/revision (by nwdef_branch__nw_af7c55181b sp121) (by nwdef_branch__nw_a33c0de6a2 sp120)) (by nwdef_branch__nw_50b94ee13a sp119)) (prior (STV 1.0 0.993)) (((reported with cpu (prior (STV 0.5 0.0))) sp118)))` | B asserts it directly as fact sp118, so it is never a goal: build_goals/goal_pool/rule_goal_pool skip asserted triples (wmtm/pc_shadow.py; test_asserted_fact_is_never_a_goal). That is the safeguard. is_derivation would return True on this engine-shaped term (test_engine_shaped_revision_documented_as_admitted), see Follow-up 1. The wrong claim stays a stored fact |
| (Inheritance hive_progress_report report) | sp24, sp25; ep-note-20261104T181709Z | CORRECT | 0 exact, 0 Member; class-level gives only the reflexive | B parses "report" as Member sk_report_* witnesses. Lost correct conclusion |
| (Member turn_without_send_entry entry) | sp106, sp107; ep-note-20261028T185959Z | CORRECT | 0; `(Member $x entry)` 0; `(Inheritance ltm_entry entry)` 0 | No ltm_entry -> entry link in B. Lost correct conclusion |

## Criterion 8: B columns side by side (F3 result 1 vs this result)
| | A (live wmtm) | B b62b0f6 + PC 13c6c9c5 (F3 result 1, Nov7, 7 runs) | B 3288bf2 + PC 13c6c9c5 (v2/v3, 6 runs) |
|---|---|---|---|
| facts / goals | 141 / 4 | 251 / 11 | 251 / 11 |
| proved | 4 | 7-8 | 11 |
| timeouts | 0 | 2-3 per run (set varies) | 0 |
| correct / wrong / unclear | 2 / 2 / 0 | 5-6 / 1-2 / 1 | 8 / 2 (W1) / 1 |
| wmtm-rule proofs | 4 (inh_trans/mem_inh) | present (mem_inh/inh_trans loaded) | 0 |
| warm-up | <= 0.93 s | <= 3.5 s (2.73 s in v2) | <= 2.93 s |
| query total | small | ~25 s (24.8 s v2), over budget_s 20 | <= 3.66 s |
Source for the b62b0f6 column: t-2026-11-07-wmtm-f3-ab REPORT and RUNS_TABLE (B_v2 row: 5C 2W 1U, 3 timeouts, warm 2.729, total 24.832).

## Criterion 7: paths that still load mem_inh / inh_trans / imp_trans
Grep for rule definitions/loads (`(: mem_inh|inh_trans|imp_trans` or the quoted names) over wmtm/, scripts/, tests/ at this head:
- scripts/pettachainer/pc_fullkb.py, pc_retest.py, pc_scale.py, pc_timeout.py (offline experiment scripts)
- tests/test_f3v2_native_chain.py (kbD repro, puts the rules back on purpose), tests/test_f1_s11_subunit.py (older test fixture)
No production path: wmtm/pc_admit.py only keeps the names in the legacy `_RULE` regex, and wmtm/pc_shadow.py / wmtm/workers/pc_shadow.py mention them in comments only.

## Deviations
- DEVIATION_1 (declared after results): the W1 rule was extended. P4/F3 result 1 derived W1 from premise source notes plus parser-rule note ids. Native proofs no longer name the other note's premises, so v3's recompute also joins notes through shared `nwdef_*` narrow-class symbols (`nw_symbol_notes` in extract.json). This change is conservative (more WRONG, not fewer). Gate 1 holds either way: B 8C/2W with the extension, 10C/0W without it, against A 2C/2W. Details are in DEVIATION_1.md.

## Item B provenance (finding 4)
- B KB: KB_B_atoms.json (398 atoms; 251 facts, 75 nwdef rules, parser implications; sha256 b558b2b9e8cef5da… identical across v3r1-r5). A KB: KB_A_atoms.json (141, ab52d5b121c50422…). These are parsed atoms (ids and predicates only, no note text).
- Engine for item B: /tmp/f3/pc = PeTTaChainer 13c6c9c5a6f50bae08c08d8e28b0f88d991f5b41 (clean tree), PeTTa 3681b9b.
- Branch answer TV: (STV 1.0 0.99) for the exact goal in all 5 runs. The three narrowed classes branch__nw_* come back at (STV 0.99999937 0.99180110).

## Follow-up (design questions, not fixed here)
1. Should a `(by nwdef_… spN)` restatement, or a `reported with cpu`-wrapped label, count as a derivation in is_derivation? Today it does (also `(settled sp)` / `(given sp)`). This only matters if an asserted fact could ever become a goal.
2. A replay with goalchainer on and the context path turned on, to measure criterion 5.
3. Whether the parser should emit flat Inheritance (B loses A's 2 correct conclusions).

## Commits (branch hive/t-2026-11-08-wmtm-f3-ab-v3, on v2 head 61c2568)
- 1571d80 items C+D: wmtm/pc_admit.py is_derivation, tests/test_f3v2_native_chain.py (+47), wmtm/workers/pc_shadow.py docstring, docs/RUNTIME.md.
- fd02402 review-1 fixes: tests/test_f3v2_native_chain.py (+2 tests: engine-shaped revision term documented as is_derivation True; asserted fact never a goal), DEVIATION_1.md, KB_A/B_atoms.json, ITEM_B.md TV + engine commit, JUDGMENTS.json hygiene, extract.json per-record shas, SHA256SUMS, this report.
- 00fa834 evidence: ITEM_B.md + item_b_queries.py, CRITERION5.md, runs/ (12 shadow records), extract.json (premise id -> source note id/fact, nw-symbol -> notes, gate rejects), W4.json, JUDGMENTS.json (reasons replaced by "hand-judged", no note text; A rows fixed in fd02402), worker_config_A/B.json, RUNS_TABLE.md, B_CHECKOUT.txt, recompute.py.

## Gates (PREREG t-2026-11-07-wmtm-f3-ab)
1. Count rule: B 8C/2W/1U and A 2C/2W in all 6 runs per arm. HOLDS. W1 is now re-derived mechanically: the shared symbol nwdef_config__nw_b1a247bbd8 joins notes 185132Z and 185959Z.
2. §11: inline above.
   - W1 rule: see Deviations (DEVIATION_1.md).
3. Warm-up: B is at most 2.93 s, against a 120 s limit. HOLDS.
4. Budget: unchanged from Nov7 (parse 1.535x, 66.6 s median, 0 429). B query total is at most 3.66 s. HOLDS.
5. Criterion-5 extras: NOT EXERCISED (CRITERION5.md).

## Reproduce
`env -i PATH=/usr/bin:/bin python3 -S reports/t-2026-11-08-wmtm-f3-ab-v3/recompute.py` prints RECOMPUTE_OK.
Item B: `python3 item_b_queries.py v3rN` on pop-os (needs the private built specs under /tmp/f3/ab).
Engine: PeTTa 3681b9b + PeTTaChainer bdae8d7e (WMTM_PC_PETTA / WMTM_PC_VENDOR).
Full suite on fd02402 with engine env: 819 passed, 26 skipped (53.7 s; 00fa834 was 817/26, +2 new tests). A premises in the §11 table re-checked against extract.json (v3r1).

## Evidence hygiene (finding 5)
JUDGMENTS.json: all reasons now read "hand-judged against the source note (text not committed)", and A rows keep only the P3 W4 row number. extract.json: each record has its own record_sha256 and spec_atoms_sha256. The shared input_sha256 is the one 20-note raw input that every run used, and that is intended. SHA256SUMS lists every file in this directory.

## Branch state
hive/t-2026-11-08-wmtm-f3-ab-v3 is committed locally on pop-os and NOT pushed: pop-os has no GitHub credentials (push fails with "could not read Username"). A human with credentials must push it; nothing goes to main.
