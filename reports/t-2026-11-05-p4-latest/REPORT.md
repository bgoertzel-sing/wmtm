# t-2026-11-05-p4-latest: result 3 (rev3)

## Summary

Review 2 failed this task on six findings. The main one was that parsed notes could not chain into conclusions, because the shadow goal pool was built only from flat facts. Rev3 fixes that in wmtm. A new `rule_goal_pool` (`wmtm/pc_shadow.py:302`, called at `:462`) lets the parser's Implication rules and the F7 defining rules propose goals. A new real-engine test (`tests/test_p4_rule_goals.py::test_parsed_note_chains_on_real_engine`) parses a note and proves a conclusion on PeTTaChainer bdae8d7e. The pins are now changed in the code itself: PeTTaChainer bdae8d7e, semantic-parsing-hitl f44d7b74 as the default, and PETTA_PIN.md. F7 naming is treated as the design, with 0 STOPGAP markers left. Equivalence rules are dropped, and a test covers that. All evidence is committed under `reports/t-2026-11-05-p4-latest/`.

On the real notes, arm B (latest parser and engine) now proves 12 of 13 goals. I judged 10 of them correct and 2 wrong. Arm A has 2 correct and 2 wrong. That meets the A/B criterion as numbers. However, every B proof is an antecedent completion through an inverted nwdef defining rule, at STV 0.9995/0.2017, so confidence is low. None comes from a direct chain. **Open decision for andy:** do antecedent-completion answers at c≈0.20 count as "chaining into conclusions" for deployment? Until that is answered I propose deploy: **no**. The branch is local and unpushed; see the finding 5 row.

## One row per review 2 finding

| # | Review 2 finding | Rev3 change | Evidence (in this dir unless noted) |
|---|---|---|---|
| 1 | Goal pool uses flat facts only; parser rules never targeted; no real-engine test of a parsed note chaining | Commit 1aa85f8 adds `rule_goal_pool`: Implication and nwdef rules (And-premise, up to max_hops) propose goals, skipping function-term consequents. 1f8de8b and 552f400 keep goals about note-scoped witnesses `sk_<x>__i_<note>` (gate_scoped_witness, shadow_scoped_witness, default on). 9ebc2c5 adds a real-engine parsed-note test. 0224285 fixes the name_resolve "before" check | `rev3/new_tests.txt`, `rev3/gates/pytest_p4_rev3.txt` (5/5), `rev3/bdae8d7e/shadow_B.jsonl` (13 goals, 12 proved), `rev3/PROOF_KINDS.md` |
| 2 | Pins not replaced in the code | 23267b5: `runtime_config.py` pettachainer_dir defaults to pettachainer-bdae8d7e; `vendor_runtime.sh` PC_PIN=bdae8d7e; hitl PIN=f44d7b74 (1f1a7a6f kept as an accepted older pin); PETTA_PIN.md lists PeTTa 3681b9b (pr/compact-datatypes, as named by PeTTaChainer bdae8d7e pyproject) | `rev3/pins_in_code.txt` (git grep at HEAD) |
| 3 | F7 handled as a STOPGAP, against Track P 8cf5006; no proof kind or STV per answer | 3e3d573 and 6123847: no STOPGAP marker; docs/STOPGAPS.md emptied; README says F7 naming is the design. PROOF_KINDS.md gives the STV and proof kind for every A and B answer. Count of B antecedent-completion answers: 12 of 12 proved; 0 direct | `rev3/stopgap_grep.txt` (0), `rev3/PROOF_KINDS.md`, `rev3/B_W4_JUDGMENTS_bdae8d7e.md` |
| 4 | Stop-line not followed | Written up below. The structural cause is now fixed, not worked around. The remaining open point is raised as a decision, not deferred | this file, "Finding 4" |
| 5 | Evidence on pop-os, not reachable | All rev2 and rev3 evidence is committed inside the branch (1.5 MB; secret scan clean, since the "Bearer" hits are a MeTTa predicate name). Rev2 `check.py` runs from `rev2_evidence/`. A new `check.py` and `SHA256SUMS` are in this dir. The branch is not pushed (task order; no GitHub credentials on this host), so the reviewer needs the hive to fetch it or a human to push `hive/t-2026-11-05-p4-latest` | `check.py`, `SHA256SUMS`, `rev2_evidence/` |
| 6 | Equivalence silently fails; LICENSE test depends on host path; default 2 s run canary_fail | f84f7f2: `semparse_rules` drops Equivalence, and a test covers it. The hitl LICENSE is a test fixture, so the verify_checkout tests now run on any host. On bdae8d7e the default timeout of 2 s gives status ok: canary proved, negative is prior only, 12/13 (the rev2 canary_fail was on 202b9379 under load) | `rev3/bdae8d7e_default_t2/NOTE.md`, `shadow_B_t2.jsonl` |

## Finding 4: the stop-line, and why I did not block earlier

From result 1 onward, B returned 0 goals. I explained it by the parse gate rejecting sk_* subjects as placeholder_subject. I kept treating that as a parameter question, carried it through every checkpoint, and in result 2 I deferred it to "a separate task". That was wrong in two ways. First, the order says that when a blocker persists you stop working around it, write it up and block. I should have blocked after result 1 with the question "B has 0 goals; why?". Second, my diagnosis was incomplete. Relaxing the gate would not have helped, because the goal pool could never target a rule (review 2 finding 1). In rev3 that structural cause is removed in wmtm, which is what the order asked for. The one remaining question, whether low-confidence antecedent-completion answers are acceptable, is raised above as a decision for andy. I have not deferred it.

## Gates

- Full wmtm suite at HEAD on PeTTa 3681b9b and PeTTaChainer bdae8d7e: 753 passed, 25 skipped (`rev3/gates/pytest_full.log`). Skips depend on the environment.
- P4 rev3 subset: 5 passed (`rev3/gates/pytest_p4_rev3.txt`).
- Commits: `rev3/commits.txt` (base b317ff1; rev3 = 9 commits on 0875c96).
