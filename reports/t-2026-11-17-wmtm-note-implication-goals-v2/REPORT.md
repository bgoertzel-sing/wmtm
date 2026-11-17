# t-2026-11-17-wmtm-note-implication-goals-v2 (rev2)

Supersedes: t-2026-11-17-wmtm-note-implication-goals

## Summary
The task asked whether wmtm should also ask the conclusions of Implication/BiImplication statements that a note itself states, using that note's own Member facts. A new flag, `shadow_note_impl_goals` (off by default), does this inside one note only: a binding that joins two notes is dropped (1 was dropped). Of 41 note implications, 14 give a goal. All 14 are proved and all 14 are correct, but each one restates the note, one step from its own implication. The extra-rules arm drops four rules (xr_directive_inherit, xr_close_closes, xr_hour_order, xr_minute_order) through the new `shadow_extra_rules_drop` flag. With both on, the shadow run proves 130/130 goals with 0 timeouts, and the count rule holds against base in every arm and on every line.

Recommendation: the flag is safe to turn on together with the extra rules minus those four, because it adds no wrong conclusions and the shipped trivial filter refuses none of the new goals. It adds little new knowledge, though. Reader rows reached, of 75 (sentence-level upper bound): base 8, nimpl 14, xr 15, both 20. Open decision: whether note-implication conclusions count as restatements in the count rule. The rule holds either way.

## Rev2 (review 1 findings)
1. Counts-only recompute: tools/recompute_ni.py -> recompute_ni.json (all numbers below come from it).
2. xr arm count-rule lines and reader-pass score added.
3. Supersedes line added.
4. The 11 extra-rule verdicts are cited from t-2026-11-17-wmtm-extra-rules on/verdicts_xr.tsv (not from this task's both/verdicts_nimpl.tsv, which holds only the 14 nimpl rows).
5. Per-arm trivial-filter refusals and admitted C/W/U added.
6. Prose now names the four dropped rules.

## Change (230b48c on hive/t-2026-11-17-wmtm-note-implication-goals-v2, parent 3334538)
- wmtm/pc_shadow.py, wmtm/master_loader.py: note_impl_goals. Labels from `atom_src`; seeded and extra rules excluded. Member premises matched within the same note (cross_note bindings dropped and counted). Conclusions the note already states, and goals already made by rule_goals, are skipped. Needs `shadow_load_order=master_ops`.
- wmtm/runtime_config.py: `shadow_note_impl_goals` (bool, false), `shadow_extra_rules_drop` (str, "").
- README.md flag table rows; tests/test_note_impl_goals.py (7 tests).
- Full suite: 1581 passed / 59 skipped / 5 xfailed (no templates env); 1595 / 45 / 5 (templates env).

## Build counts (both/build.json note_impl)
41 note implications: 14 ground, 27 with variables, 0 Bi, 5 with an And premise. Premise in KB 15, missing 26. 1 cross-note binding dropped. Goals 14.

## Per arm (recompute_ni.json; STEPS=30, parsed.jsonl md5 9417e2e2… in all arms, canary ok, neg not proved)
| arm | goals (seeded/nimpl/xr) | proved | timeouts | new C/W/U | trivial refused (new) | admitted C/W/U | reader rows of 75 (new) |
|---|---|---|---|---|---|---|---|
| base | 105 (105/0/0) | 105 | 0 | - | 82 (0) | 22/1/0 | 8 (0) |
| nimpl | 119 (105/14/0) | 119 | 0 | 14/0/0 | 82 (0) | 36/1/0 | 14 (6) |
| xr | 116 (105/0/11) | 116 | 0 | 10/0/1 | 82 (0) | 22/1/0 | 15 (7) |
| both | 130 (105/14/11) | 130 | 0 | 24/0/1 | 82 (0) | 36/1/0 | 20 (12) |

The 82 refusals are all seeded goals (same as base). The 11 xr goals are not admitted in xr/both: the admit layer drops them as `bad` because pc_admit.render gives no text for them, the same as in t-2026-11-17-wmtm-extra-rules-v2 (recompute_v2.json). xr rules that fired: supersedes_not_current_ap 4, supersedes_not_current_bt 2, contradicts_not_bt 4, contradicts_not_ap 1.

## Verdicts
- 14 note-implication goals: this task's both/verdicts_nimpl.tsv, 14C, all one-step restatements (STV 0.9/0.7).
- 11 extra-rule goals: /srv/hive-evidence/t-2026-11-17-wmtm-extra-rules/on/verdicts_xr.tsv, 10C/1U, matched by goal through that run's query order (assert in recompute_ni.py).
- 105 seeded goals: t-2026-11-14-wmtm-trivial-filter-coref verdicts (master-shadow-wiring inputs/verdicts).

## Count rule (C/W/U; vs live A 2C/2W | vs base)
| arm | all | non-restatement (nimpl = restatement) | non-restatement (nimpl counted) | admitted |
|---|---|---|---|---|
| base | 97/4/4 (fails, as before / -) | 22/1/0 (holds / -) | 22/1/0 (holds / -) | 22/1/0 (holds / -) |
| nimpl | 111/4/4 (fails / holds) | 22/1/0 (holds / holds) | 36/1/0 (holds / holds) | 36/1/0 (holds / holds) |
| xr | 107/4/5 (fails / holds) | 32/1/1 (holds / holds) | 32/1/1 (holds / holds) | 22/1/0 (holds / holds) |
| both | 121/4/5 (fails / holds) | 32/1/1 (holds / holds) | 46/1/1 (holds / holds) | 36/1/0 (holds / holds) |

## Evidence
/srv/hive-evidence/t-2026-11-17-wmtm-note-implication-goals-v2/: base/ nimpl/ xr/ both/ (spec, build.json, shadow.jsonl, admit.json, run.log, parsed.md5), tools/ (build_spec_ni.py, run_build.sh, run_shadow.sh, recompute_ni.py), recompute_ni.json, inputs/note_ids.txt, countrule_nimpl.txt and reader_pass_nimpl.txt (rev1, superseded by recompute_ni.json), suite logs, diffs vs 24b0442 and 3334538, superseded_unscoped/, SHA256SUMS. Rerun: `python3 tools/recompute_ni.py . <repo at this branch>`. No note text is in the repo.
