# t-2026-11-17-wmtm-extra-rules-v2

Supersedes: t-2026-11-17-wmtm-extra-rules

## Summary
andy asked for PR 42 to be redone. The order was to drop xr_directive_inherit, xr_close_closes, xr_hour_order and xr_minute_order, to write `master_meta.extra_rules` only when the flag is on, to keep REPORT.md to ids and counts, and to squash the work into one commit on main 24b0442. All of that is done. Four rules remain behind `shadow_extra_rules`, which is off by default: xr_supersedes_not_current_ap/_bt and xr_contradicts_not_ap/_bt. With the flag off, the spec built from the 20 notes is byte-identical to the 24b0442 build, `master_meta` included, and a new test checks this on synthetic notes. All tests pass.

With the flag on, the shadow run proves 116 of 116 goals: the same 105 seeded goals as with the flag off, plus 11 new goals. Those 11 are judged **10 correct, 0 wrong, 1 unclear** (x10). On the non-restatement goals the count rule **holds** against both live A (2C/2W) and the flag-off run: 32/1/1 against 22/1/0. The reader-pass score goes from **8 to 16 of 75**. One thing is open: at the admit level, the shipped `pc_admit.load_candidates` drops all 11 new results as `bad`, because `pc_admit.render` returns no text for `Not (Current _)` or `Not (Valid _)`. So the admitted set stays at 22C/1W/0U with the flag on. Making them admissible needs a renderer change, which would be a separate task. Nothing live has changed, there were 0 parse calls, and nothing has been pushed.

## Changes against PR 42 (operator request, Work msg 682)
| request | done | check |
|---|---|---|
| drop xr_directive_inherit, xr_close_closes, xr_hour_order, xr_minute_order | removed from the rules file, README/runtime_config text and tests. The `Compute` premise evaluation in `rule_goals` (`compute=`, `_compute_ok`) is removed as well: only hour/minute_order used it | `test_file_parses_and_ids_exact` (exactly 4 ids), `test_dropped_rules_absent` |
| meta extra_rules only when the flag is on | `plan(extra=False)` writes no `extra_rules` key | `test_extra_rules_after_seeded_rules_flag_off_by_default`; `test_build_snapshot_extra_rules_flag_off_byte_identical` (flag False vs key absent: same bytes; `master_meta` keys = base keys; flag on adds 4 ops after the seeded rules and nothing else moves); 20 notes: base/spec.json = off/spec.json = absent/spec.json (cmp) |
| REPORT.md: ids and counts only | this file names notes, reader rows and goals by id only | see the section How REPORT.md was checked |
| one squashed commit from main 24b0442 | one commit on hive/t-2026-11-17-wmtm-extra-rules-v2, parent 24b0442; none of the old branch's commits (0c63ade, 91612e0, f7db76c, 3334538) are ancestors | `git rev-list --count 24b0442..HEAD` = 1 |

## Code (diff from 24b0442)
- `wmtm/rules/extra_rules.pettachainer-master.metta`: 4 rules, CTV (STV 1.0 0.9).
- `wmtm/master_loader.py`: `extra_rules()`; `plan(extra=)` (meta key only when on); `rule_goals(scoped=)` with `_one_note`, so an extra rule's goal is kept only when its bindings come from one note.
- `wmtm/pc_shadow.py`: `_master_ops_snapshot` reads `shadow_extra_rules` and passes the extra rule ids as `scoped`.
- `wmtm/runtime_config.py`, `README.md`: flag `shadow_extra_rules` / `WMTM_PC_SHADOW_EXTRA_RULES`, bool, default false.
- Tests: `tests/test_extra_rules.py` (8, synthetic facts only), `tests/test_master_loader.py` (+2, one replacing PR 42's test).
- Suite: see the Suite section below.

## Shadow run (20 notes, cached parses, steps 30, timeout 2.0 s, budget 20 s)
| run | ops | goals | proved | timeouts | add_fail | pred_fail | canary | master_meta |
|---|---|---|---|---|---|---|---|---|
| off | 1935 | 105 | 105 | 0 | 0 | 0 | ok | kb_predicates 165, rules 280, shared_definitions 16, ops 1935 |
| on | 1939 | 116 | 116 | 0 | 0 | 0 | ok | the same + extra_rules 4, ops 1939 |

- 0 parse calls: build_snapshot reads the cache only, the narrow_preload spy counts 0, and the cache md5 is unchanged before and after.
- Flag off: queries, canary and neg are equal (timing excluded) to the master-shadow-wiring reference run_apply.
- Flag on: the 105 seeded queries are identical to flag off (timing excluded). The 11 extra goals and their query results are identical to PR 42's run for the same rule ids.

## New conclusions (ids, rule ids, counts)
| rule | goals | ids | C | W | U | confidence |
|---|---|---|---|---|---|---|
| xr_supersedes_not_current_ap | 4 | x01-x04 | 4 | 0 | 0 | 0.8839 x4 |
| xr_supersedes_not_current_bt | 2 | x05, x06 | 2 | 0 | 0 | 0.8839 (x05), 0.0021 (x06) |
| xr_contradicts_not_ap | 1 | x07 | 1 | 0 | 0 | 0.8839 |
| xr_contradicts_not_bt | 4 | x08-x11 | 3 | 0 | 1 (x10) | 0.8839 x3, 0.0021 (x09) |
| total | 11 | | 10 | 0 | 1 | strength 1.0 for all |

All 11 are proved, all 11 are derivations, and the shipped trivial filter refuses none of them (`trivial_reason` = None). None of them combines two notes. The verdicts are PR 42's judgments for the same goals; only the verdict column is reused.

## Count rule (correct(B) >= correct(A) and wrong(B) <= wrong(A))
| line | C/W/U | vs live A 2C/2W | vs flag off |
|---|---|---|---|
| flag off, all goals | 97/4/4 | fails (as at 24b0442) | - |
| flag on, all goals | 107/4/5 | fails (as with the flag off) | **holds** |
| flag off, non-restatement | 22/1/0 | holds | - |
| flag on, non-restatement | 32/1/1 | **holds** | **holds** |
| flag off, admitted (load_candidates) | 22/1/0 | holds | - |
| flag on, admitted (load_candidates) | 22/1/0 | holds | holds (no change: 11 dropped as bad) |

## Reader pass (of 75)
Flag off: 8. Flag on: 16. The 8 new rows are 121808Z.s01, 121808Z.s07, 122745Z.s02, 153222Z.s02-s04, 185132Z.s09, 185959Z.s02, 185959Z.s06 and 190214Z.s04. 7 of them have verdict C and 1 has U. The rows that only the dropped rules aimed at (directive_inherit 3, passed_closes 2, hour_order 7) were 0 reached in PR 42 and are 0 reached now.

## Suite
Without the templates env: 1570 passed, 60 skipped, 5 xfailed. With WMTM_PC_SHADOW_SPH_TEMPLATES (sph 24e37182): 1585 passed, 45 skipped, 5 xfailed. tests/test_master_loader.py + tests/test_extra_rules.py: 21 passed (suite_noenv.log, suite_env.log).

## How REPORT.md was checked
REPORT.md and the whole committed diff were checked by script against the 20 notes' cached sentence texts, in a private mode-700 temp dir removed afterwards. The script counted three things: 3-word sequences shared with a note sentence (leaving out sequences that contain a number or a task-id or path token: t, hive, evidence, stv), parser entity symbols (`sk_`), and double-quoted spans. Results (text_check.json): REPORT.md 0 note sequences, 0 `sk_` symbols, 0 quoted spans; diff added lines 0, 0, 0. The left-out sequences are 13 in REPORT.md and 40 in the diff, all task ids, paths or STV numbers. I also read the file by hand: it names notes, reader rows and goals by id and gives counts only.

## Evidence
/srv/hive-evidence/t-2026-11-17-wmtm-extra-rules-v2/ holds the following. base/ is the spec at 24b0442 plus the cache md5 before the runs. off/, absent/ and on/ each have spec.json, build.json, shadow.jsonl, admit.json and run.log (absent/ has no worker run). Also there: note_ids.txt, parsed.md5_after, recompute_v2.json, suite logs, text_check.json, tools/ (build_spec_v2.py, run_v2.sh, recompute_v2.py, text_check.py) and SHA256SUMS. To recompute: `python3 tools/recompute_v2.py <evidence dir> <repo at this commit>`. It prints ids and counts only and runs load_candidates in a private temp dir.

## Limits
- The verdicts are reused from PR 42's judgments; they were not re-judged. The goals and proofs are identical, as checked above.
- The admit-level gain is 0 until `pc_admit.render` handles `Not (Current _)` and `Not (Valid _)`. That change is outside this task.
- On these notes the supersedes and contradicts rows that the parse does not reach (1 each) stay unreached.
