## Summary
andy asked for the master-adopt-v2 load order (arm B) to be wired into the real shadow path instead of a hand-built spec: build_snapshot builds the master_ops spec itself from cached sentence parses, behind a flag that is off by default, and the shadow worker loads it through master_loader.apply. Done. On the 20 v2 notes, with cached parses only (0 parse calls, 0 notes missing a parse), the wired path proves 105/105 goals with add_fail 0, pred_fail 0 and 0 timeouts, and every query, canary and neg result matches the render task's armB full_s2 run (timing excluded). At the admit level the result is the same as well. The worker writes its own admit.json, using sources from the built spec rather than spec_maps applied afterwards. load_candidates drops 82 (all trivial: 77 symmetry, 5 coref restatement) and admits 23 (22 correct, 1 wrong, b68, 0 unclear), and the count rule HOLDS against A_v3 (2C/2W) and all three old-loader M17 runs. That equals the render task's table row exactly.

Revision 2 (review 1): the evidence is now group-readable and recomputable. Added: the admit-level comparison, 4 build_snapshot master_ops tests, a legacy byte diff through the worker (old 4193844 vs new head: identical spec, identical results apart from timing), and the driver that built the spec. The run used `shadow_max_goals=0` (no cap). With the default cap of 60, the first 60 of the 105 goals are asked, and none of the 29 sourceless ScaleOpposite goals are among them. Nothing needs a decision. Nothing live has changed: the default stays `shadow_load_order=legacy`, and the branch is staged but not pushed.

## Base and code
- Base: hive/t-2026-11-14-wmtm-render-master-goals @ 4193844. Branch hive/t-2026-11-15-wmtm-master-shadow-wiring: 580d394 (snapshot builder) and 988579f (worker uses apply), then the report commit. Not pushed.
- wmtm/pc_shadow.py `_master_ops_snapshot`: when `shadow_load_order=master_ops`, build_snapshot reads the cached parses (`shadow_master_parsed`), walks each note with tmpl.blocks, calls master_loader.plan for the recipe load order and gets goals from master_loader.rule_goals. It reads the cache only. A note without a complete cached parse adds nothing and is counted in `unparsed_items`. It fails loudly if `shadow_sph_templates` is unset.
- wmtm/master_loader.py: adds `notes_from_parsed`, `seeded_rules` and `rule_goals` (moved here from the ad-hoc v2 script).
- wmtm/workers/pc_shadow.py: the master_ops branch now calls `master_loader.apply(h, ops)`, so there is only one apply path. The inline loop is gone.
- wmtm/runtime_config.py + README: new key `shadow_master_parsed` (WMTM_PC_SHADOW_MASTER_PARSED); `shadow_load_order` documents `master_ops`.
- tests/test_master_loader.py: 11 tests (need WMTM_PC_SHADOW_SPH_TEMPLATES); 11 passed. The 4 added in rev 2 call build_snapshot with `shadow_load_order=master_ops` on a synthetic parsed.jsonl. They cover recipe order (KB preds first, then seeded rules), atoms and preds unique, a shared definition loaded once, sources in atom_src/label_fact, complete/incomplete/absent notes, a deterministic result regardless of store order, 0 narrow_preload calls, the goal cap, RuntimeError without templates, and flag off (unset/legacy/empty with a bogus parsed path) giving no master_ops.
- Suite: 1482 passed, 57 skipped, 5 xfailed without the templates env; 1494 passed, 45 skipped, 5 xfailed with it.

## Results (20 v2 notes, steps 30, timeout 2.0, budget 20)
| run | code | load_order | goals | proved | add_fail | pred_fail | timeouts | total_s | queries/canary/neg = ref (excl. timing) |
|---|---|---|---|---|---|---|---|---|---|
| ref: render task armB full_s2 | 4193844 hand spec | master_ops | 105 | 105 | 0 | 0 | 0 | 7.88 | - |
| run | 580d394 inline loop | master_ops | 105 | 105 | 0 | 0 | 0 | 7.97 | yes/yes/yes |
| run_apply | 988579f master_loader.apply | master_ops | 105 | 105 | 0 | 0 | 0 | 7.88 | yes/yes/yes |
Spec: 1935 master_ops, 105 goals; semparse_items 20, unparsed_items 0, derived 0.

## Checks
- The built spec matches the stored spec: master_ops are equal after a JSON round trip (in memory they are tuples, on disk lists), and goals are equal.
- narrow_preload stays on the legacy path only: with a spy on semparse_adapter.narrow_preload, building the master_ops snapshot made 0 calls.
- Parse calls: 0. Only the cache (/srv/hive-evidence/t-2026-11-12-wmtm-parser-master-adopt-v2/sentence_parse/parsed.jsonl) was read.
- Engine: PeTTa /home/openclaw/scratch/mh-rules-on-roman/PeTTa, PeTTaChainer /home/openclaw/scratch/ppv/pc (the same as the v2 arm B).
- Recompute: `python3 tools/recompute.py [run|run_apply]` reads only the evidence JSON and prints PASS for both.

## Evidence
/srv/hive-evidence/t-2026-11-15-wmtm-master-shadow-wiring/: run/ (spec.json, shadow.jsonl, run.log, ref_render_armB_full_s2.shadow.jsonl), run_apply/ (+ admit.json, admit_compare.json in both), inputs/, legacy_bytediff/, driver/, diff_4193844_HEAD.patch, tools/ (recompute.py, admit_compare.py, build_spec.py, legacy_bytediff.py), SHA256SUMS.

## Review 1 findings, row by row
| # | finding | fix | evidence |
|---|---|---|---|
| 1 | evidence mode 600, not recomputable | `chmod -R g+rX` on the evidence dir; SHA256SUMS regenerated | `sha256sum -c SHA256SUMS` (all files) |
| 2 | no admit-level comparison | worker-written admit.json for both runs; `tools/admit_compare.py EV run|run_apply` runs pc_admit.load_candidates (default trivial filter, live ids = 20 note ids, private temp dir) and scores verdicts b01..b105 from the trivial-filter-coref judgments | run/admit_compare.json, run_apply/admit_compare.json: dropped trivial 82 (symmetry 77, coref 5), admitted 23 = 22C/1W/0U (W: b68), vs A_v3 HOLDS, vs M17 r1/r2/r3 HOLDS, results with sources 76/105; `equal_to_render_armB_full_s2: true` (exit 0) |
| 3 | no build_snapshot master_ops tests | 4 tests in tests/test_master_loader.py (see Base and code) | suite numbers above |
| 4 | no legacy byte diff through the worker | `tools/legacy_bytediff.py`: synthetic store (tests' fake semparse, no note content), flag unset, build_snapshot then `wmtm.workers.pc_shadow` at 4193844 and at the new head | legacy_bytediff/old, legacy_bytediff/new: spec.json byte-identical; shadow.jsonl and admit.json differ only in timing fields (s, prequery_s, warm_s, total_s, ts, start_ts) |
| 5 | how the spec was built; goal cap | `tools/build_spec.py NOTE_IDS PARSED TEMPLATES OUT [MAX_GOALS]` is the driver: a store with the 20 note ids, then build_snapshot with master_ops. The run used `shadow_max_goals=0` (no cap; runtime default 60) | driver/spec_rebuilt.json equals run/spec.json except ts; driver/spec_cap60.json: 60 of 105 goals, 0 of the 29 sourceless ScaleOpposite goals among them |

Inputs copied for recompute (inputs/): note_ids.txt, verdicts/, f3v3_JUDGMENTS.json, f3v3_v3_A.shadow.jsonl, old_loader/, old_loader_goals.txt, tfc_counts.json (from the render task's evidence). These are ids, counts and judgments only. The A_v3/M17 baselines are read from the render task's group-readable evidence.
