# PeTTaChainer migration research (rTreutlein/PeTTaChainer 49ca6f3)

Research material only. Nothing here is loaded by wmtm. Everything was produced on pop-os in /tmp/pcmig between
2026-11-03 14:20 and 21:24 PDT, while working on t-2026-11-03-pettachainer-migration-plan (cancelled) and its
replacement t-2026-11-04-pettachainer-migration-report. See REPORT.md for the findings.

Setup: GoalChainer v2 checkout (engine runtime pymetta-native.2), with its external/PeTTaChainer replaced by rT 49ca6f3
(`rt49ca`). The shims are scratch edits to that tree. Paths are relative to the scratch root, with /tmp/pcmig/ removed.

Note: wmtm's .gitignore:30 (`pettachainer-*/`) matches this directory name, so the files were force-added
(`git add -f`). Add any new file the same way. .gitignore was left alone (the scope is this directory only).

## Layout
- `shims/rt49ca-vs-shimmed.diff`: the full diff, pristine rT 49ca6f3 against the final shimmed tree. 66 files,
  about 1.4k added lines. Each edited line carries a `; shimNN` or `pcmig probeNN` tag.
- `shims/*.diff`: the individual early shims, each against its .orig.
- `shims/*.pl`, `shims/shim1_nested_arrows.py`: standalone shim files.
- `shims/s15_files.txt`: the files touched by the type-rewrite shims (15/17/18/23).
- `shims/pl_calls.txt`: MeTTa-only functions that Prolog code calls (the input to shim20).
- `shims/LOCATIONS.md`: every hunk of the full diff, grouped by shim tag, with file and line ranges.
- `logs/failed_ids/*.ids`: the sorted failing test IDs from each suite log (`grep '^FAILED '`, cut at ` - `).
- `shims/recovered/`: diffs for shims later overwritten or reverted (shim4c, shim6, shim7, probe118), rebuilt from scratch-tree backups (.orig, .pre118, .prefa, .fa-current, .pre-finally), plus the first error of each shim5-8 run.
- `evidence/fitness/`: the fitness report (t-2026-11-03-pettachainer-fitness) and the pytest logs whose counts this report quotes (186; 117/69; 242; 240+2).
- `evidence/fitness/lineage.txt`, `pc_shadow_andform*.diff`, `pytest_pc_*_andform_floor.txt`: engine/branch lineage and the tested pc_shadow proof-acceptance fix (W8).
- `logs/*.summary.txt`: the pass/fail line and the top error for each GoalChainer suite run (raw logs were 34 MB, not committed).
- `probes/`: the probes and outputs that the report quotes. (All 139 probe scripts are in `probes/all/` and all 148 probe outputs are in `probes/all_out/`.)

## Shim -> blocker map (with locations)
Paths are relative to external/PeTTaChainer/ unless marked GoalChainer. Line numbers are on the shimmed side of `shims/rt49ca-vs-shimmed.diff`. `shims/LOCATIONS.md` lists every hunk per tag (583 hunks, 67 files, generated mechanically from the tags on the edited lines; 14 untagged hunks are listed at its end). The diff also contains two scratch backup files (`kb_publication.metta.orig62`, `.orig68`). They are noise, not shims.

| shim | blocker | location (shimmed tree, file:line) |
|---|---|---|
| shim1 (`shim1_nested_arrows.py`), shim5, shim7 | nested annotated arrows refused (`fold-semidet`, `context-with-scope`, `particle-map-pairs`) | script over every `(: name TYPE)`; surviving untagged hunks: `pettachainer/metta/compiler/source_lowering.metta:623`, `:732`; `pettachainer/metta/runtime/evaluator/folds.metta:77`, `:122`; `pettachainer/metta/core/natives.metta:310` (context-with-scope, shim5); the other rewrites were later overwritten by shim15/17/18 at the same lines (see LOCATIONS.md). shim7 (particle-map-pairs, particle-map2-inner and 2 more): `third_party/pln_formulas/metta/distributions.metta:333`, `:341`, `:350-365`, `:455` (recovered: `shims/recovered/shim7_distributions.metta.diff`, a vendored file outside pettachainer/ and so outside the main diff) |
| shim2, shim4, shim4b | duplicate yall import; relative Prolog path | `pettachainer/metta/bootstrap.metta:33-34` (removed `import_prolog_functions_from_file`; `bootstrap.shim4b.diff` hunk :30-39); `pettachainer/metta/prolog/runtime_helpers.pl:6-11` (yall, tagged shim3) |
| shim3 | double `declare-natives!` registration | `pettachainer/metta/lib/natives.pl:19-37` (removed clause) |
| shim4c, shim14 | `apply_fn1/3` missing under pymetta (`finally/3`) | `pettachainer/metta/lib/natives.pl:28-36` (`pc_apply_unit`), `:81-85` (shim14) |
| shim6 | `sk-take!` not loaded (registration order) | `pettachainer/metta/lib/natives.pl:16-19`: `declare-forward!` routed to `declare-natives!` so forward decls such as `sk-take!` (`pettachainer/metta/core/natives.metta:315`) register (recovered: `shims/recovered/shim6_vs_liborig.diff`; file mtime 14:41:14 falls between the shim6 run 14:39:45 and shim7 run 14:42:50, see `shims/recovered/shim5-8_first_errors.txt`) |
| shim8 | PLN config path moved | GoalChainer `src/goal_chainer/evidence_chainer.py:85` (hunk :82-88) |
| shim9-12 | `bidirectional-implication-form?/2` called from Prolog | `runtime_helpers.shim9.diff` hunk :3-9; forwarding stub in `pettachainer/metta/prolog/ingestion.pl:326-354` |
| shim13, shim20 | Prolog -> MeTTa forwarding (`format/3`, pl_calls.txt) | `pettachainer/metta/prolog/ingestion.pl:326-354`; `pettachainer/metta/lib/natives.metta:13-32` |
| heapshim | library(heaps) not visible | `pettachainer/metta/lib/natives.metta:13-14` (heap arity decls; `empty_heap`/`add_to_heap` type decls removed); standalone `shims/heapshim*.pl` |
| shim15 / shim15b | return types -> `%Undefined%` | 146 hunks / 36 files and 18 hunks / 8 files; e.g. `pettachainer/metta/compiler/rules.metta:611`, `pettachainer/metta/runtime/backward/execution.metta:3`; full list LOCATIONS.md |
| shim17 | higher-order fold/map signatures | `pettachainer/metta/compiler/source_lowering.metta:108`, `:293`; `pettachainer/metta/lib/collections.metta:2-36` |
| shim18 | `List X` -> `Expression` | 290 hunks / 50 files; e.g. `pettachainer/metta/compiler/query_lowering.metta:142`, `:157`, `:412`; full list LOCATIONS.md |
| shim19 | `SkPattern` etc. -> `%Undefined%` | 388 hunks / 23 files; e.g. `pettachainer/metta/compiler/fold_sources.metta:3`, `:20`; full list LOCATIONS.md |
| shim21, shim22 | `prefix-key/3` not a Prolog predicate | `pettachainer/metta/runtime/store/fact_index.metta:28`; `pettachainer/metta/prolog/term_index.pl:108-110` |
| shim23 | 52 `sk-*`/store signature relaxations | `pettachainer/metta/core/natives.metta`: 14 hunks, lines 7-25 ... 324-341 (LOCATIONS.md) |
| pc_store_access | space-row storage under pymetta | new `pettachainer/metta/prolog/pc_store_access.pl:1-21`; `pettachainer/metta/prolog/context_overlay.pl:27`, `:48`, `:56-66`; `pettachainer/metta/prolog/space_store.pl:7`, `:17`, `:36` |
| probe63/68/75 | `map-flat` partial apps; `superpose` arg | `pettachainer/metta/runtime/kb_publication.metta:44-61` |
| probe118 (reverted) | curried Bool accumulator returns () | `pettachainer/metta/runtime/evaluator/versions.metta`; `:163` and `:460` (the two `fold-flat ... false` Bool-accumulator sites). Recovered snapshots: `shims/recovered/probe118_pre118_vs_prefa.diff` (the inlined `foldl-atom` form at both sites), `probe118_prefa_vs_facurrent.diff`, `probe118_facurrent_vs_final.diff` (the revert). The first variant (helper `sk-any-gives-way`) was replaced at the same two sites before a snapshot was taken. The preserved `foldl-atom` form is the same fix, written inline |
| brand/the/data | compact-datatypes builtins missing | no file edit (scratch `add-atom` at runtime, warmprobe136/137) |
| G2 (GoalChainer) | warm-up rules Premises -> bare Implication | GoalChainer `src/goal_chainer/policy/goalchainer_pettachainer.metta:44-45` (hunk :41-48) |
