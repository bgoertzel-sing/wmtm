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
- `logs/*.summary.txt`: the pass/fail line and the top error for each GoalChainer suite run (raw logs were 34 MB, not committed).
- `probes/`: the probes and outputs that the report quotes. (About 130 other warm-up probes were not kept. Each one
  fixed a single failure.)

## Shim -> blocker map
| shim | file(s) | blocker it addresses (first error it moved past) |
|---|---|---|
| shim1 (`shim1_nested_arrows.py`) | every `(: name TYPE)` in metta/ | pymetta `metta_add_atom/3: cannot honour the annotated arrow for fold-semidet` (nested `-[c]->` parameter types). Rewrites the inner arrows to `->` |
| shim2 (`bootstrap.shim4b.diff`, part) | metta/bootstrap.metta | `import/1: No permission to import yall:(/)/3 into user (already imported from metta_engine)` |
| shim3 | lib/natives.pl, bootstrap | `declare-natives! is already registered from .../lib/natives.pl` (double registration) |
| shim4/4b | bootstrap.metta | `source_sink .../src/prolog/runtime_helpers.pl does not exist` (relative Prolog path resolves against the host cwd) |
| shim4c (`natives.shim4c.diff`) + shim14 | lib/natives.pl | `finally/3` calls `apply_fn1/3`, which exists only in the PeTTa translator and not in pymetta. Routed through `reduce/2` (`pc_apply_unit`) |
| shim5, shim7 | type decls (context-with-scope, particle-map-pairs) | further nested annotated arrows that shim1 missed (higher-order parameters) |
| shim6 | natives registration | `no predicate named sk-take! is loaded` (registration order) |
| shim8 (`evidence_chainer.py.diff`) | GoalChainer evidence_chainer.py:85 | PLN config moved: `logic_configs/pln` -> `core/logic_configs/pln` |
| shim9-12 (`runtime_helpers.shim9.diff`) | prolog/runtime_helpers.pl | `Unknown procedure 'bidirectional-implication-form?'/2`: Prolog calls a MeTTa function. shim11 was a bad edit (syntax error at :280), reverted |
| shim13 | prolog/ingestion.pl | forwarding wrappers in the module ingestion.pl loads into. Next error: `format/3: too many arguments` |
| shim15 | ~35 files (s15_files.txt) | `Atom`/precise return types -> `%Undefined%` (209 sites in total). pymetta type-checks returns that PeTTa ignores |
| shim17/18 | lib/collections.metta etc. | higher-order fold/map signatures (`fold-semidet`, `map-semidet`, `foreach-flat`, `any-flat?`) -> `%Undefined%`/`Expression` |
| shim19 | prefilter-premise-blocks? | `SkPattern` arg type -> `%Undefined%` |
| shim20 (`shim20.pl`) | prolog/*.pl | Prolog -> MeTTa forwarding stubs for every name in pl_calls.txt (`M:'name'(...)` in the MeTTa module) |
| shim21/22 | core/runtime_terms_keys.metta, prolog/term_index.pl | `prefix-key/3` is a MeTTa function, not exported as a Prolog predicate under pymetta. Added a Prolog def via `index-hash` |
| shim23 | runtime/backward/*, store/* | 52 `sk-*` / store signature relaxations (List X -> Expression) |
| `pc_store_access.pl` | prolog/space_store.pl, term_index.pl | space-row storage: PeTTa keeps rows as plain `Space(...)` facts; pymetta keeps them in `'$metta_atoms:<space>'` modules with an extra trailing token. `retractall(Space(..))` / direct `'&kb_prefix'(...)` calls see nothing. Prototype accessor `pc_row/2` |
| heapshim*.pl | runtime scheduling | `library(heaps)` predicates are not visible from the MeTTa module under pymetta. Five name variants were tried |
| probe63/68/75 tags | fact_index.metta, kb_publication.metta | pymetta `map-flat` drops partial applications; `superpose` does not evaluate its argument. Hashes are bound first |
| (probe 118, reverted) | evaluator/versions.metta | curried call with a Bool accumulator (`fold-flat (sk-gives-way-step p) false`) returns ()/BadArgType. An uncurried helper fixed one site; about 20 sites have the same pattern |
| (warmprobe 136/137, scratch add-atom) | runtime | `brand`/`the`/`data` are PeTTa builtins from rT PeTTa pr/compact-datatypes 3681b9b. The pymetta wheel lacks them |
| `goalchainer_pettachainer.metta.diff` | GoalChainer policy :44-45 | warm-up rules rewritten from Premises/Conclusions to bare `(Implication p c)`. rT dropped the Premises form |
