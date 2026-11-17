# t-2026-11-17-wmtm-extra-rules (revision 2, after review 1)

## Summary
andy asked for a wmtm-owned file of extra PeTTaChainer rules for five gap kinds (hour_order, supersedes_not_current, contradicts_not, directive_inherit, passed_closes). The rules load after the seeded master rules behind a flag that is off by default. The order also asked for a shadow run on the 20 v2 notes with every new conclusion judged. Done: there are 8 rules behind `shadow_extra_rules`. With the flag off, the spec and every query match the reference exactly. Review 1 found two problems, and both are fixed: the extra rules now only fire on facts from one note, and the flag no longer changes how seeded rules are evaluated. With the flag on, 125 of 125 goals are proved and the 105 seeded goals are unchanged. The 20 new conclusions are judged **15 correct, 1 wrong, 4 unclear**, and the trivial filter refuses none of them. The reader-pass score goes from **8 to 16 of 75**.

Count rule: **with all 8 rules on, it fails against the flag-off run**. On the non-restatement goals the result is 34C/2W/4U against 22C/1W/0U. The one new wrong conclusion comes from directive_inherit. **Without directive_inherit it holds** against both live A (2C/2W) and flag-off: 32C/1W/1U on the non-restatement goals, and 110C/4W/5U against 97C/4W/4U on all goals. On all goals the count still fails against live A, but that was already true with the flag off (4W > 2). Decision needed: (1) drop directive_inherit, or keep it out of any live use. I recommend dropping it. (2) passed_closes is **not delivered as ordered**. The review-gated form is unsound on these parses, because the pass and the close share no variable. The shipped close_closes is a restatement and is not credited for passed_closes. Keeping the gate needs a parser link between the two events. (3) hour_order has no inputs on these notes. Nothing is pushed and nothing live has changed.

## Changes in revision 2 (review 1 finding -> fix)
| # | review 1 finding | fix | evidence |
|---|---|---|---|
| 1 | new conclusions not judged; no trivial filter, admit, count rule or score of 75 | 20 conclusions judged C/W/U with rule id, reader row and premise labels; shipped `pc_admit.trivial_reason` run on each proof (0 refusals); count rule computed 4 ways; reader pass 8 -> 16 of 75 | on/verdicts_xr.tsv, countrule_xr.txt, recompute_xr.json |
| 2 | directive_inherit: 69 cross-note joins, none of its 3 rows covered | `rule_goals(scoped=...)`: an extra rule's binding is kept only when every bound symbol carries at most one note suffix (named individuals carry none). directive_inherit goes from 75 to 6, all in one note. Its 3 rows are still not reached, because those notes have no `Member task` atom. The count rule is stated with and without this rule | on/, superseded_unscoped/on_v2 |
| 3 | passed_closes not as ordered; close_closes credited for both rows; steps 300 and 1000 probe not in the evidence | close_closes marked as a restatement and not credited for the passed_closes rows (gap_coverage.tsv rebuilt). The steps 30/100/300/1000 probe was re-run into the evidence: 0/3, 0/3, 2/3, then 3 timeouts | superseded_passed_closes/probe_steps |
| 4 | the flag also evaluated Compute in seeded rules | Compute premises are evaluated only for the scoped (extra) rule ids, so seeded rules behave the same with the flag on or off. New test `test_compute_not_applied_to_unscoped_rules`; README entry updated | tests/test_extra_rules.py |
| 5 | parser entity symbol in REPORT.md | removed; the report names notes by id only | this file |

## Base and code
- Base wmtm 24b0442. Branch hive/t-2026-11-17-wmtm-extra-rules: 0c63ade (rules, loader, flag), 91612e0 (review 1: scoping, Compute only for the extra rules), then the report commit. Diff from the base to HEAD in wmtm/, tests/ and README: 7 files, +196/-7.
- `wmtm/rules/extra_rules.pettachainer-master.metta`: xr_hour_order, xr_minute_order, xr_supersedes_not_current_ap/_bt, xr_contradicts_not_ap/_bt, xr_directive_inherit, xr_close_closes. CTVs follow the seeded style: (STV 1.0 0.9) for definitional readings, and (STV 1.0 0.8) for directive_inherit because it is a defeasible generalisation. Premise predicates exist in the parser output (counts in on/spec master_ops): Member supersede 8, contradict 7, close 7, task 5, pass 3; Directive 32; Past 51; Time 10; Hour 5; Minute 4; Patient 42; Theme 26.
- `wmtm/master_loader.py`: `extra_rules()`; `plan(extra=)`; `rule_goals(compute=, scoped=)` with `_one_note`. `wmtm/pc_shadow.py` passes the extra rule ids as `scoped`.
- Tests: tests/test_extra_rules.py has 12 tests, including the new scoping and seeded-Compute tests. tests/test_master_loader.py has +1.
- Suite: 1574 passed / 59 skipped / 5 xfailed without the templates env, and 1588 / 45 / 5 with WMTM_PC_SHADOW_SPH_TEMPLATES (suite_*.log).

## Shadow run (20 v2 notes, cached parses: 0 parse calls, narrow_preload 0, cache md5 unchanged; steps 30)
| run | ops | goals | proved | timeouts | add_fail | pred_fail | canary/neg |
|---|---|---|---|---|---|---|---|
| off | 1935 | 105 | 105 | 0 | 0 | 0 | ok / not proved |
| on | 1943 | 125 | 125 | 0 | 0 | 0 | ok / not proved |
Flag off is identical to the master-shadow-wiring reference, and a fresh rebuild (off_v3) gives the same result. With the flag on, the 105 seeded queries are identical to flag off.

## New conclusions (verdicts_xr.tsv; ids and counts only)
| rule | goals | C | W | U | trivial-filter refusals | note |
|---|---|---|---|---|---|---|
| supersedes_not_current (ap+bt) | 6 | 6 | 0 | 0 | 0 | |
| contradicts_not (ap+bt) | 5 | 4 | 0 | 1 | 0 | U: the reader marked the row uncertain (whole note vs its claim) |
| directive_inherit | 6 | 2 | 1 | 3 | 0 | all in 185132Z; W = a switch-back directive bound to the other task; U = a general prohibition whose task scope is unstated |
| close_closes | 3 | 3 | 0 | 0 | 0 | restatements of the parsed close |
| hour/minute_order | 0 | | | | | no candidates |
| total | 20 | 15 | 1 | 4 | 0 | none multi-note |
Admitted = the conclusions not refused: all 20 (15C/1W/4U). The shipped filter does not know the xr_ rules, so I mark the 3 close_closes conclusions as restatements by hand.

## Count rule (correct(B) >= correct(A) and wrong(B) <= wrong(A))
| line | C/W/U | vs live A 2C/2W | vs flag-off |
|---|---|---|---|
| flag off, all | 97/4/4 | fails (already failing before this task) | - |
| flag on, all | 112/5/8 | fails | fails |
| flag on, non-restatement | 34/2/4 | holds | **fails** (wrong 2 > 1) |
| flag on minus directive_inherit, all | 110/4/5 | fails (as with flag off) | holds |
| flag on minus directive_inherit, non-restatement | 32/1/1 | holds | holds |

## Reader pass (of 75)
Flag off: 8 rows. Flag on: 16 rows. The 8 new rows are 5 supersedes and 3 contradicts; 7 of them are C and 1 is U. Rows for the five kinds: 22, of which 8 are reached (gap_coverage.tsv). Not reached: 1 supersedes and 1 contradicts row (no supersede or contradict event in the parse), 2 passed_closes rows (not credited), 3 directive_inherit rows (no task atom in those notes), and 7 hour_order rows (only one event has both Time and Hour).

## Evidence
/srv/hive-evidence/t-2026-11-17-wmtm-extra-rules/: off/, off_v3/, on/ (spec, shadow, run.log, build.json, verdicts_xr.tsv), countrule_xr.txt, gap_coverage.tsv, recompute_xr.json (made from a private temp copy by tools/recompute_xr.py), superseded_unscoped/ (the revision 1 run), superseded_passed_closes/ (on_v1 and probe_steps at 30/100/300/1000), suite logs, diff_24b0442_HEAD.patch, tools/, SHA256SUMS.
