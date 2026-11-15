## Summary
andy asked that the parser-master-adopt-v2 B conclusions reach the trivial filter through the real admission path (pc_admit.load_candidates) instead of being dropped as "bad" (98) or "no_live_source" (7 full_s2 / 21 sens_s2). They now do: on both arms bad = 0 and no_live_source = 0. With the coref filter on (default), 82 per arm are refused (77 symmetry_restatement, 5 coref_restatement) and the rest are admitted: full_s2 23 (22C/1W/0U), sens_s2 37 (35C/1W/1U). The count rule HOLDS against live A (2C/2W) and against each old-loader M17 run as judged in v2 (r1 8C/1W, r2 10C/1W, r3 7C/1W), on both arms.

Nothing is left for a decision. One note: the 29 ScaleOpposite goals rest only on seeded pole atoms (no note), so they have no source; all 29 are refused as so_sym restatements before the source check, so none reaches no_live_source. 0 parse calls.

## Base and code
- Base: hive/t-2026-11-14-wmtm-render-master-goals @ bdd0675 (contains 2fe5389 + merge of 53e5d9b master_loader). Code commit 89391c6; report/tool commit follows it. Not pushed.
- wmtm/pc_admit.py: `_MASTER_TEXT` adds Coref, ScaleOpposite, Agent, Patient, Theme, Bearer, Recipient, Experiencer, Possession, PartOf, Because (argument order as typed in sph generated/atom-types.metta; wording from rules.yaml meanings); `_GOAL` built from all heads, flat symbol args only (nested/unary/ternary stay unrenderable -> bad, as before). `proof_labels()` = legacy sp/wm labels plus any token that is a key of the spec map (no pattern guess for master labels). `sources_for` / `proof_facts` use it. `_with_master_maps()` lifts master_meta atom_src/label_fact to top level in write_admit_file for master_ops specs; legacy specs untouched.
- wmtm/master_loader.py: `plan()` meta now records atom_src (label -> note id) and label_fact (label -> fact) for every note-suffixed statement; `spec_maps(ops, note_ids)` rebuilds both for specs stored before this change; `_label_fact()` helper.
- tests/test_render_master_goals.py (22 tests, synthetic symbols): each new head rendered, unrenderable shapes stay None, spec_maps (seeded rule/pole labels get no source), sources/facts from master labels, legacy labels unchanged, write_admit_file -> load_candidates end to end.
- Suite: 1487 passed, 45 skipped, 5 xfailed (with WMTM_PC_SHADOW_SPH_TEMPLATES set); 1460/50 without.

## Goal-head shapes in the B set (S = plain symbol, SK = skolem)
| shape | full_s2 | sens_s2 | rendered before | now |
|---|---|---|---|---|
| (Coref SK SK) | 39 | 39 | no | yes |
| (Coref S SK) / (Coref SK S) / (Coref S S) | 10/1/1 | 10/1/1 | no | yes |
| (ScaleOpposite S S) | 29 | 29 | no | yes |
| (Member S S) / (Member SK S) | 4/3 | 5/16 | yes | yes |
| (Agent SK SK) | 3 | 3 | no | yes |
| (Patient SK SK) / (Patient SK S) | 3/2 | 3/2 | no | yes |
| (Theme SK SK) | 2 | 2 | no | yes |
| (Bearer SK SK) | 2 | 2 | no | yes |
| (Possession S SK) / (SK S) / (SK SK) | 1/1/1 | 1/1/1 | no | yes |
| (PartOf SK SK) / (PartOf SK S) | 1/1 | 1/1 | no | yes |
| (Because SK SK) | 1 | 1 | no | yes |
Unrenderable now: none.

## load_candidates (filter on, live ids = the 20 note ids)
| arm | stage | bad | no_live_source | trivial refused | admitted | C/W/U | vs A 2C/2W | vs M17 r1/r2/r3 |
|---|---|---|---|---|---|---|---|---|
| full_s2 | old code (2fe5389, as recorded) | 98 | 7 | 0 | 0 | - | - | - |
| full_s2 | render only (stored empty sources) | 0 | 23 | 82 | 0 | - | - | - |
| full_s2 | render + sources | 0 | 0 | 82 (77 sym, 5 coref) | 23 | 22/1/0 | HOLDS | HOLDS/HOLDS/HOLDS |
| sens_s2 | old code (as recorded) | 98 | 21 | 0 | 0 | - | - | - |
| sens_s2 | render only | 0 | 37 | 82 | 0 | - | - | - |
| sens_s2 | render + sources | 0 | 0 | 82 (77 sym, 5 coref) | 37 | 35/1/1 | HOLDS | HOLDS/HOLDS/HOLDS |
Admitted wrong id: b68 (both arms); unclear: b114 (sens_s2). Refused C/W/U: 75/3/4 per arm. Admitted by head: full_s2 Member 7, Patient 5, Agent 3, Possession 3, Theme 2, PartOf 2, Because 1; sens_s2 the same with Member 21. Unjudged admitted: 0.

## Checks
- Known-answer canary through the same path: synthetic coref_agent result with a master label admitted with derived_from = its note; synthetic coref_sym result refused (ok=true).
- Recompute temp dir: tempfile.mkdtemp, mode 0o700, removed at exit (recorded in counts.json).
- Inputs in the evidence dir are byte-identical copies (cmp) of the v2 / trivial-filter-coref evidence.

## Evidence
/srv/hive-evidence/t-2026-11-14-wmtm-render-master-goals/: inputs/ (note-derived copies, kept apart), tables/counts.json (ids/counts only), SHA256SUMS. Recompute: `python3 reports/t-2026-11-14-wmtm-render-master-goals/tools/recompute.py /srv/hive-evidence/t-2026-11-14-wmtm-render-master-goals`.
