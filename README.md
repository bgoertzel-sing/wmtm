# WMTM — Working Medium-Term Memory

Mutable active memory layer between short-term context and the long-term
PeTTa/MeTTa journal: recall, ECAN-style attention, inference (PLN-style
deduction/induction/abduction), forgetting and writeback.

Extracted from the ProtoCosmo2 Iter tree (snapshot `83ea611`, branch
`agent/protocosmo2-live-snapshot-20261015`) with the `wmtm/` git history
(subtree split). `v0.1.0` is byte-identical package code to that snapshot.

- Package: `wmtm/` (internal layout unchanged from the Iter tree for now).
- Tests: `python3 -m pytest` (no LLM, no network).
- PeTTa requirement: see `PETTA_PIN.md` (v1.0.5).
- Design notes and audits: `docs/`.
- `scripts/benchmark_wmtm.py`: micro-benchmark (run with `PYTHONPATH=.`).

Known external coupling: `wmtm/goalchainer_bridge.py` adds a hardcoded
OmegaClaw-GoalChainer path to `sys.path` (tests mock it). To be made
configurable.
