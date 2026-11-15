## Summary
andy asked for the master-adopt-v2 load order (arm B) to be wired into the real shadow path instead of a hand-built spec: build_snapshot builds the master_ops spec itself from cached sentence parses, behind a flag that is off by default, and the shadow worker loads it through master_loader.apply. Done. On the 20 v2 notes, with cached parses only (0 parse calls, 0 notes missing a parse), the wired path proves 105/105 goals with add_fail 0, pred_fail 0 and 0 timeouts. Every query, canary and neg result matches the render task's armB full_s2 run, ignoring timing (7.88s vs 7.88s).

Nothing needs a decision. Nothing live has changed: the default stays `shadow_load_order=legacy`, and the branch is staged but not pushed.

## Base and code
- Base: hive/t-2026-11-14-wmtm-render-master-goals @ 4193844. Branch hive/t-2026-11-15-wmtm-master-shadow-wiring: 580d394 (snapshot builder) and 988579f (worker uses apply), then the report commit. Not pushed.
- wmtm/pc_shadow.py `_master_ops_snapshot`: when `shadow_load_order=master_ops`, build_snapshot reads the cached parses (`shadow_master_parsed`), walks each note with tmpl.blocks, calls master_loader.plan for the recipe load order and gets goals from master_loader.rule_goals. It reads the cache only. A note without a complete cached parse adds nothing and is counted in `unparsed_items`. It fails loudly if `shadow_sph_templates` is unset.
- wmtm/master_loader.py: adds `notes_from_parsed`, `seeded_rules` and `rule_goals` (moved here from the ad-hoc v2 script).
- wmtm/workers/pc_shadow.py: the master_ops branch now calls `master_loader.apply(h, ops)`, so there is only one apply path. The inline loop is gone.
- wmtm/runtime_config.py + README: new key `shadow_master_parsed` (WMTM_PC_SHADOW_MASTER_PARSED); `shadow_load_order` documents `master_ops`.
- tests/test_master_loader.py: 7 tests (need WMTM_PC_SHADOW_SPH_TEMPLATES); 7 passed.
- Suite: 1482 passed, 53 skipped, 5 xfailed (without templates env).

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
/srv/hive-evidence/t-2026-11-15-wmtm-master-shadow-wiring/: run/ (spec.json, shadow.jsonl, run.log, ref_render_armB_full_s2.shadow.jsonl), run_apply/, diff_4193844_988579f.patch, tools/recompute.py, SHA256SUMS.
