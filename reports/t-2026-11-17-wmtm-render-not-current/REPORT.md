# t-2026-11-17-wmtm-render-not-current

Base: hive/t-2026-11-17-wmtm-extra-rules-v2 at a70dc86 (passed, not merged; parent main 24b0442).

## Summary
andy asked for wordings for Not (Current x) and Not (Valid x), so that the extra rules' conclusions can be admitted, and for a shadow check of the admitted C/W/U and the count rule, with no live change. `pc_admit.render` now gives "x is no longer current" for (Not (Current x)) and "x no longer holds" for (Not (Valid x)). The negation is kept in the wording, x is rendered as is (like the existing shapes), and every other Not shape still renders as nothing. Both shapes are covered by new tests; the full suite passes.

Through the real admission path (`load_candidates`, trivial filter on, caps lifted as in the v2 report), the flag-on run now admits all 11 extra-rule conclusions: **10 correct, 0 wrong, 1 unclear (x10)**. Drops for `bad` fall from 11 to 0. Admitted with the flag on: **32C/1W/1U**, against 22C/1W/0U with the flag off. The count rule **holds** against live A (2C/2W) and against the flag-off run. With the flag off, nothing changes: the spec is byte-identical to 24b0442 and admission is identical to v2. One point for the operator: with the shipped caps (reasoner_max_admit 5), one run admits 5 conclusions (5C/0W), and these are seeded ones whether the flag is on or off. So under the live cap the extra conclusions would enter only over later runs, once the higher-ranked ones are known. Nothing live has changed, there were 0 parse calls, and nothing has been pushed.

## Change (a70dc86..HEAD)
- `wmtm/pc_admit.py`: `_NOT_TEXT` / `_NOT_GOAL`. They match only `(Not (Current <sym>))` and `(Not (Valid <sym>))` with one flat symbol. `render` tries the binary shapes first, unchanged, and then these two. `_GOAL` is not touched, so the goal fallback in `sources_for` is unchanged (tested).
- Wording (invented examples): `(Not (Current plan_a))` gives "plan_a is no longer current". `(Not (Valid claim_b))` gives "claim_b no longer holds". This follows the rule file's own meaning: what is superseded is no longer current, and what is contradicted no longer holds. Only the extra rules produce Current and Valid.
- `tests/test_render_not_current.py` (24 cases, invented symbols): both shapes render, and the negation is kept. The following stay None: un-negated Current/Valid, other Not shapes (Member, Patient, Coref, unknown heads), nested terms, arity 0 or 2, a double Not, a lowercase head, and stray spaces. Existing shapes are unchanged. `load_candidates` on a synthetic admit.json admits both shapes as positive candidates with the negated wording and drops an unrelated Not shape as `bad`.

## Shadow rerun (20 notes, cached parses, steps 30; tools/run_rnc.sh)
| check | result |
|---|---|
| parse calls | 0 (narrow_preload spy 0 for off/absent/on; parsed cache md5 unchanged) |
| spec flag off / key absent vs 24b0442 base spec | byte-identical (both) |
| spec flag on vs v2 on | byte-identical |
| worker queries, canary, neg vs v2 (timing excluded) | identical, off and on |
| admit.json results vs v2 (timing excluded) | identical, off and on (the render change does not touch the worker side) |
| runs | off 105/105 proved, on 116/116; 0 timeouts, add_fail, pred_fail; canary ok |
| render a70dc86 vs HEAD over all 116 goals | 11 changed, all extra-rule goals (x01-x11), all previously empty |

## Admission (load_candidates, trivial filter on, reasoner_max_admit 1000, gate_max_per_fact 0, as in v2)
| run | results | dropped bad | dropped trivial (reason) | other drops | admitted | C/W/U |
|---|---|---|---|---|---|---|
| flag off | 105 | 0 | 82 (symmetry_restatement 77, coref_restatement 5) | 0 | 23 | 22/1/0 |
| flag on, v2 (a70dc86) | 116 | 11 | 82 | 0 | 23 | 22/1/0 |
| flag on, this task | 116 | **0** | 82 (the same 77 + 5) | 0 | **34** | **32/1/1** |

The trivial filter refuses none of the 11. Flag-off admission is identical to v2: same counts, same drops.

## Newly admitted (flag on)
| id | rule | verdict | strength | confidence |
|---|---|---|---|---|
| x01-x04 | xr_supersedes_not_current_ap | C x4 | 1.0 | 0.8839 |
| x05 | xr_supersedes_not_current_bt | C | 1.0 | 0.8839 |
| x06 | xr_supersedes_not_current_bt | C | 1.0 | 0.0021 |
| x07 | xr_contradicts_not_ap | C | 1.0 | 0.8839 |
| x08 | xr_contradicts_not_bt | C | 1.0 | 0.8839 |
| x09 | xr_contradicts_not_bt | C | 1.0 | 0.0021 |
| x10 | xr_contradicts_not_bt | U | 1.0 | 0.8839 |
| x11 | xr_contradicts_not_bt | C | 1.0 | 0.8839 |

All 11 are admitted with positive polarity (strength 1.0 is at least reasoner_min_strength). Verdicts: 10 C, 1 U. They are PR 42's judgments, reused as in v2.

## Count rule (correct(B) >= correct(A) and wrong(B) <= wrong(A))
| line | C/W/U | vs live A 2C/2W | vs flag off |
|---|---|---|---|
| flag off, admitted | 22/1/0 | holds | - |
| flag on, admitted | 32/1/1 | **holds** | **holds** |
| flag off, admitted, shipped caps (max_admit 5, per-fact 3) | 5/0/0 | holds | - |
| flag on, admitted, shipped caps | 5/0/0 (no x ids) | holds | holds |

## Suite
Without the templates env: 1594 passed, 60 skipped, 5 xfailed. With WMTM_PC_SHADOW_SPH_TEMPLATES (sph 24e37182): 1609 passed, 45 skipped, 5 xfailed. Against v2 (1570 / 1585 passed), that is +24 each, the new tests. Targeted (render_not_current, render_master_goals, extra_rules, master_loader): 54 passed, 13 skipped in 0.22s (suite_noenv.log, suite_env.log, targeted.log).

## How REPORT.md was checked
tools/text_check_rnc.py (private temp dir) compares REPORT.md and the added diff lines against the 20 notes' cached sentence texts. It finds 0 shared 3-word sequences, leaving out the ones with numbers or task-id or path tokens, and 0 sk_ symbols that occur in the parses (the tests' sk_ symbols are invented). The 7 double-quoted spans are the two wordings, their two invented examples, and three short wording phrases in Limits. See text_check.json.

## Evidence
/srv/hive-evidence/t-2026-11-17-wmtm-render-not-current/ holds base.txt, head.txt, note_ids.txt, parsed.md5_before/after, off/, absent/ and on/ (spec.json, build.json, shadow.jsonl, admit.json, run.log; absent/ has no worker run), recompute_rnc.json, the suite logs, text_check.json, tools/ (run_rnc.sh, build_spec_v2.py, recompute_rnc.py, text_check_rnc.py) and SHA256SUMS. To recompute: `python3 tools/recompute_rnc.py <evidence dir> <repo at this commit>`. It prints ids and counts only and runs load_candidates in a private mode-700 temp dir. It reads the v2, PR 42, master-shadow-wiring and render-master-goals evidence for the base spec, the verdicts and live A.

## Limits
- The verdicts are reused from PR 42 and were not re-judged. The goals and proofs are byte-identical to v2's (checked above).
- "No longer" reads slightly more than a bare "not": it says the thing once was current or held. That matches what the two extra rules derive (from supersede and contradict). If Current or Valid ever came from another source, a plain "is not current" might be the better wording.
- Under the shipped per-run cap of 5, the 11 rank below the seeded conclusions. The default-caps line above covers one run only; it does not simulate several cycles with `known` dedup.
- x06 and x09 are admitted at confidence 0.0021, because there is no confidence cutoff (F1 item 3).
