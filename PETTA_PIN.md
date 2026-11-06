# PeTTa pin

## Current pin (t-2026-11-04-p1-engine)
- PeTTa: rTreutlein/PeTTa 3681b9baa28d005dfbad21ad9b5d46b243b1e323 (compact datatypes), vendored as `petta-3681b9b`.
- PeTTaChainer (wmtm PC shadow worker): rTreutlein/PeTTaChainer bdae8d7ee0bc38ef93528ea3e9d3dcc47c5b8c95, vendored as `pettachainer-bdae8d7e`, no dedup-import patch (P4 rev3, review 2 finding 2). Previous pin 202b93791f23a04c5ef7670625dc8a803ada09f6 (`pettachainer-202b9379`) is superseded.
- The pin is recorded in `wmtm/runtime_config.py` (`petta_dir`, `pettachainer_dir`), `scripts/vendor_runtime.sh` (`PETTA_PIN`, `PC_PIN`) and `docs/GOALS_V2.md`. If they disagree with this file, those are authoritative.
- GoalChainer is NOT on the wmtm PeTTaChainer pin: its PeTTaChainer gitlink stays at 38b1473 (option c; pymetta 0.9.4+goalchainer.native.2 refuses rT 202b9379, PY1-PY5 in `upstream/pettachainer/`; bdae8d7e not tried with pymetta).

## History: v1.0.4 / v1.0.5 era (Oct 2026, superseded by the pin above)
- Omega c6dc842 Dockerfile pins `ARG PETTA_REF=v1.0.4` (lacks 21be21f swrite backslash fix).
- Build with `--build-arg PETTA_REF=v1.0.5` (df313cd, 2026-07-23). v1.0.5 contains 21be21f (+ #200 follow-up d9a437c).
- v1.0.4..v1.0.5 = 14 commits (swrite fix, import overhaul, commit-pinned git imports, overapplication error, specializer fix).

Verified (local swipl 9.3.36, wmtm codec cases, 14 strings):
- v1.0.4 sread->swrite->sread round trip: 7/14 OK (all backslash cases broken).
- v1.0.5 round trip: 14/14 OK. sread on codec encodings unchanged.
- v1.0.5 examples atomops, and_or, add_atom_fun_space pass; `repr` keeps backslashes.

`docs/petta_parser_swrite_backslash.patch` is OBSOLETE (kept only for history; do not apply on v1.0.5).

## Boot check (Omega c6dc842 on PeTTa v1.0.5)
- lib_omegaclaw.metta loads to completion (rc=0, sentinel printed) on v1.0.5 + swipl 9.3.36; no new errors from the import overhaul.
- c6dc842 lib_omegaclaw.metta:26 imports `./src/context`, which does not exist in Omega history, so c6dc842 silently skips context. Not a v1.0.5 regression.
- chromadb git-import on v1.0.5: `git-import!` of patham9/petta_lib_chromadb (@2184848) + `(library petta_lib_chromadb lib_chromadb)` loads, rc=0 (python chromadb 1.5.9).
- py-call runtime on v1.0.5: `(py-call (math.sqrt 16))` -> 4.0, rc=0.
- Not covered: full agent loop (needs LLM keys/channel).
