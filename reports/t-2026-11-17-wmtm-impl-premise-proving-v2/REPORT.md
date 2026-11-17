# t-2026-11-17-wmtm-impl-premise-proving-v2: drop the lowering stopgaps, make literal() same-note, amend C4

Supersedes: t-2026-11-17-wmtm-impl-premise-proving

## Summary

Andy asked for four things: remove the two lowering stopgaps, keep the note-implication premise flag (off by default) but check premises only against the implication's own note, correct the C4 reason in the variable-implication-test report, and rerun the 20 notes with the flag off and on. All four are done. The stopgap code, tests, docs and tools are gone. `literal()` now reads only the implication's own note, and 3 new tests cover it. The C4 entry now says that `coref_member` does bridge the two skolems. C4 actually needed the missing thing premise and 300 steps.

The rerun used cached parses (0 parse calls). With the flag off, the specs are byte-identical to 9a8f693. Flag off: 119 goals, 119 proved. Flag on: 155 goals, 119 proved, with 36 premise goals built and 0 of them proved. Admitted C/W/U is 36/1/0 in both arms, and the count rule holds. The goal set is the same as in v1. Only the literal/not-literal split moved by one (15/26 → 14/27), because one premise had been stated literally only in another note. Still open for andy: the flag proves nothing new until Man Hin's lowering fix lands, so keep it off. The branch is local and unpushed, and a human merges it.

## Changes (branch hive/t-2026-11-17-wmtm-impl-premise-proving-v2, base 9a8f693)
- 08de1f2: squashed carry-over of v1 (732d860+3b80d10+2262628).
- e013274: removes `shadow_lowering_stopgaps` (master_loader, runtime_config SPEC, tests, README/docs, tools). `note_impl_premise_goals.literal()` takes `own_by_head` built from the implication's own note only (master_loader.py:423-457). New tests: `test_literal_premise_in_other_note_does_not_block`, `test_literal_premise_in_own_note_still_left_to_one_step_builder`, `test_no_stopgap_code`. Amends C4 in reports/t-2026-11-17-wmtm-variable-implication-test/REPORT.md. Adds a superseded banner to the v1 report.
- Full suite: 1611 passed, 70 skipped, 5 xfailed.

## 20-note rerun (evidence /srv/hive-evidence/t-2026-11-17-wmtm-impl-premise-proving-v2)
| arm | goals | proved | timeouts | premise goals built / proved | new proved vs base C/W/U | admitted C/W/U | trivial refused |
|---|---|---|---|---|---|---|---|
| base | 105 | 105 | 0 | 0 / 0 | 0/0/0 | 22/1/0 | 82 |
| off | 119 | 119 | 0 | 0 / 0 | 14/0/0 | 36/1/0 | 82 |
| ip | 155 | 119 | 0 | 36 / **0** | 14/0/0 | 36/1/0 | 82 |

- The base and off spec.json files are byte-identical to the 9a8f693 builds in v1's evidence. The ip spec differs from v1 only in the `note_impl_premise` stats (premise_literal 15→14, premise_not_literal 26→27). goal_rule is identical (155 keys).
- Shadow query results are identical to v1 in all three arms once timings are ignored.
- parsed.jsonl md5 is unchanged before and after the run. All canaries passed.
- Count rule: admitted and non-restatement HOLD against base, live A, and off in the off and ip arms.
