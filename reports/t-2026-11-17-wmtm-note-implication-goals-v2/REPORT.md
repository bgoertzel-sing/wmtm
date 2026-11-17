# t-2026-11-17-wmtm-note-implication-goals-v2

## Summary
The task asked whether wmtm should also ask the conclusions of Implication/BiImplication statements that a note itself states, using that note's own Member facts. A new flag, `shadow_note_impl_goals` (off by default), does this. It only asks conclusions inside one note: a binding that joins two notes is dropped. Of 41 note implications, 14 give a goal. All 14 are proved and all 14 are correct, but every one restates something the note already says, one step from its own implication. Together with the extra rules (minus directive_inherit, which the new `shadow_extra_rules_drop` flag can leave out), the shadow run proves 130/130 goals with no timeouts. The count rule holds against base: 121C/4W/5U against 97C/4W/4U.

Recommendation: the flag is safe to turn on together with the extra rules minus directive_inherit, because it adds no wrong conclusions. It adds little new knowledge, though: of the 75 reader rows it reaches 6 more (14 in total, 20 with the extra rules; this is a sentence-level upper bound). Still open: whether to count note-implication conclusions as restatements in the count rule. Either way the rule holds (32C/1W/1U or 46C/1W/1U against base 22C/1W/0U and live A 2C/2W).

## Change (230b48c on hive/t-2026-11-17-wmtm-note-implication-goals-v2, parent 3334538)
- wmtm/pc_shadow.py, wmtm/master_loader.py: note_impl_goals. Labels come from `atom_src`, and seeded and extra rules are excluded. Member premises are matched within the same note (cross_note bindings are dropped and counted). Conclusions the note already states, and goals already made by rule_goals, are skipped. Only works with `shadow_load_order=master_ops`.
- wmtm/runtime_config.py: `shadow_note_impl_goals` (bool, false) and `shadow_extra_rules_drop` (str, "").
- README.md: flag table rows added (the README sync test passes).
- tests/test_note_impl_goals.py: 7 tests (one step, cross-note drop, names in no note, missing premise or stated conclusion, BiImplication, seeded rules ignored, flags off by default).
- Full suite: 1581 passed / 59 skipped / 5 xfailed (no templates env); 1595 / 45 / 5 (with templates env).

## Build counts (both/build.json note_impl)
41 note implications: 14 ground, 27 with variables, 0 Bi, 5 with an And premise. Premise in KB: 15; premise missing: 26. 1 cross-note binding dropped. Goals: 14.

## Shadow runs (WMTM_PC_SHADOW_STEPS=30, same parsed.jsonl md5, canary ok, neg not proved in every arm)
| arm | goals | proved | timeouts |
|---|---|---|---|
| base | 105 | 105 | 0 |
| nimpl | 119 | 119 | 0 |
| xr (minus directive_inherit, close_closes, hour/minute_order) | 116 | 116 | 0 |
| both | 130 | 130 | 0 |

## Verdicts (both/verdicts_nimpl.tsv)
14 note-implication goals: 14C (all are a one-step restatement from the note's own implication and its own Member fact). The 11 new extra-rule goals: 10C/1U.

## Count rule (countrule_nimpl.txt)
| line | C/W/U | vs live A 2C/2W | vs base |
|---|---|---|---|
| base, all | 97/4/4 | fails (already before) | - |
| nimpl, all | 111/4/4 | fails (as base) | holds |
| both, all | 121/4/5 | fails (as base) | holds |
| both, non-restatement (nimpl as restatement) | 32/1/1 | holds | holds |
| both, non-restatement (nimpl counted) | 46/1/1 | holds | holds |

## Reader pass (reader_pass_nimpl.txt, of 75, sentence-level upper bound)
Before: 8 rows. nimpl: 14 rows (6 new: 043925Z.s02, 153222Z.s02-s04, 185959Z.s04, 190214Z.s01, 190214Z.s02, 203949Z.s02). both: 20 rows.

## Evidence
/srv/hive-evidence/t-2026-11-17-wmtm-note-implication-goals-v2/: base/ nimpl/ xr/ both/ (spec, build.json, shadow.jsonl, admit.json, run.log, parsed.md5), countrule_nimpl.txt, reader_pass_nimpl.txt, suite logs, diff_24b0442_HEAD.patch, diff_3334538_HEAD.patch, tools/ (build_spec_ni.py, run_build.sh, run_shadow.sh), superseded_unscoped/ (an earlier run without the one-note scope, 15 goals), SHA256SUMS. No note text is in the repo.
