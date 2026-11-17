# t-2026-11-17-wmtm-extra-rules

## Summary
andy asked for extra PeTTaChainer rules for the five gap kinds from the master-adopt-v2 reader pass: hour_order, supersedes_not_current, contradicts_not, directive_inherit and passed_closes. They load after the seeded master rules behind a flag that is off by default, and come with tests and a shadow run on the 20 v2 notes with the flag off and on, from cached parses only. Done: `wmtm/rules/extra_rules.pettachainer-master.metta` has 8 rules behind `shadow_extra_rules` (default off). With the flag off, the spec and every query match the master-shadow-wiring reference exactly. With the flag on, 194 of 194 goals are proved with 0 timeouts, and the 105 seeded goals are unchanged. 10 of the 22 GAP rows for these kinds are now covered from facts in their own note.

Open points for a decision: (1) passed_closes had to become **close_closes**. The pass-gated form joined a pass in one note to a close in another, because the parses share no variable between the two events. The review gate needs a parser change. (2) directive_inherit is **loose**: 69 of its 75 proofs pair a directive with a task from another note. I recommend keeping it off, or scoping it per note, before any live use. (3) hour_order has 0 candidates on these notes: only one event has both Time and Hour, so it needs the parser to emit Time on more events. Not pushed, no live change.

## Base and code
- Base wmtm 24b0442, which contains master-shadow-wiring 950d18a. Branch hive/t-2026-11-17-wmtm-extra-rules, commit 0c63ade (code) plus the report commit. Diff: 7 files, +155/-4.
- `wmtm/rules/extra_rules.pettachainer-master.metta`: xr_hour_order, xr_minute_order, xr_supersedes_not_current_ap/_bt (Agent/Patient and Bearer/Theme frames), xr_contradicts_not_ap/_bt, xr_directive_inherit, xr_close_closes. The premises use only predicates the parser emits under pettachainer-master. The conclusions use new predicates: `(Not (Current x))`, `(Not (Valid x))` and `(Applies f t)`. I used Valid because master `Holds` is 2-ary (Holds state prop), so the order's `(Not (Holds c))` does not fit it. `(Member t closed)` reuses the class symbol the parser already emits.
- `wmtm/master_loader.py`: `extra_rules()`; `plan(..., extra=False)` loads them right after the seeded rules and before any note; `rule_goals(..., compute=False)` evaluates numeric `(Compute OP (a b) -> true)` premises only when compute=True, so the goal set with the flag off cannot change.
- `wmtm/pc_shadow.py` `_master_ops_snapshot`: reads `shadow_extra_rules`. `wmtm/runtime_config.py` and the README flags table: the new key `shadow_extra_rules` (WMTM_PC_SHADOW_EXTRA_RULES, bool, false).
- Tests: `tests/test_extra_rules.py` has 10 tests on synthetic facts: each rule, both frames, the negative controls, flag off, Compute only on numbers, and close_closes needing Past. `tests/test_master_loader.py` gains 1 test: with extra=True the extra rules sit right after the seeded rules, the flag-off ops are a prefix, and the runtime default is False.
- Suite: without the templates env, 1572 passed, 59 skipped, 5 xfailed. With WMTM_PC_SHADOW_SPH_TEMPLATES, 1586 passed, 45 skipped, 5 xfailed (suite_noenv.log, suite_env.log).

## Shadow run (20 v2 notes, steps 30, timeout 2.0, budget 20; PeTTa scratch/mh-rules-on-roman/PeTTa, PeTTaChainer scratch/ppv/pc)
| run | ops | goals | proved | timeouts | add_fail | pred_fail | canary/neg | total_s |
|---|---|---|---|---|---|---|---|---|
| off | 1935 | 105 | 105 | 0 | 0 | 0 | ok/not proved | 9.07 |
| on | 1943 | 194 | 194 | 0 | 0 | 0 | ok/not proved | 13.21 |

- Off == the master-shadow-wiring reference (run/spec.json and run_apply/shadow.jsonl): the same master_ops, goals, and per-query goal/ok/n/stv/proof, with the same canary and neg.
- On: the 8 xr_ atoms are the only added ops, at index 445, right after the last seeded rule. Removing them gives the off ops exactly. The 105 seeded goals have the same results as with the flag off.
- Per rule (proved/goals): supersedes_not_current 6/6, contradicts_not 5/5, directive_inherit 75/75, close_closes 3/3, hour/minute_order 0 candidates.
- Parse calls 0: the spec is built from the cached `parsed.jsonl` only, its md5 is unchanged (off/parsed.md5), and the narrow_preload spy counted 0 (build.json).

## GAP coverage (gap_coverage.tsv; a row counts when an xr_ proof uses premises from that note)
| gap | rows | covered in-note | cross-note only | not covered |
|---|---|---|---|---|
| supersedes_not_current | 6 | 5 | 0 | 1 |
| contradicts_not | 4 | 3 | 0 | 1 |
| passed_closes | 2 | 2 | 0 | 0 |
| directive_inherit | 3 | 0 | 1 | 2 |
| hour_order | 7 | 0 | 0 | 7 |
| total | 22 | 10 | 1 | 11 |

## Findings
1. **passed_closes, pass-gated form, unsound on these parses.** The rule (pass by a review, past) + (close of a task, past) -> closed has no variable shared between the pass and the close. Note 051925Z has no pass atom at all, so its close was joined to the review_4 pass from 190214Z. In the probe (superseded_passed_closes/on_v1), 0 of 3 proved at steps 30 and 100, 2 of 3 at steps 300 (both through the 190214Z pass), and all 3 timed out at steps 1000. I replaced it with xr_close_closes. Upstream ask: the parser should link the pass to the closing (for example a Cause or Because between the two events).
2. **directive_inherit is loose.** It is Directive x every `Member t task` with no note scope, which gives 75 goals and 69 cross-note. The KB has no note or scope predicate the rule could join on. Options: per-note suffix scoping in the loader, or a parser `Scope` link. Until then, keep it behind the flag.
3. **hour_order and minute_order have no inputs.** There are 4 Time atoms and 2 notes with Hour/Minute, and only 190214Z has both on one event, so no pair forms. The rules are tested on synthetic facts. They assume the same day, because most Hour atoms have no Year, Month or Day.
4. The uncovered supersedes and contradicts rows (051925Z by time range, 151833Z the stale line) have no supersede or contradict event in their parse.

## Evidence
/srv/hive-evidence/t-2026-11-17-wmtm-extra-rules/: off/ and on/ (spec.json, shadow.jsonl, run.log, build.json), off/parsed.md5, superseded_passed_closes/on_v1, gap_coverage.tsv, suite_noenv.log, suite_env.log, diff_24b0442_HEAD.patch, tools/ (build_spec.py from shadow-wiring, build_spec_xr.py with the extra flag and the narrow_preload spy), SHA256SUMS.
Rebuild: `python3 tools/build_spec_xr.py NOTE_IDS PARSED TEMPLATES OUT 0 {0|1} REPO`, then `WMTM_PC_SHADOW_STEPS=30 python3 -m wmtm.workers.pc_shadow --spec OUT --out ... --petta ... --vendor ... --keep-spec`.
