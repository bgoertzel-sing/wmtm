# WMTM — Working Medium-Term Memory

Mutable active memory layer between short-term context and the long-term
PeTTa/MeTTa journal: recall, ECAN-style attention, inference (PLN-style
deduction/induction/abduction), forgetting and writeback.

Extracted from the ProtoCosmo2 Iter tree (snapshot `83ea611`, branch
`agent/protocosmo2-live-snapshot-20261015`) with the `wmtm/` git history
(subtree split). `v0.1.0` is byte-identical package code to that snapshot.

- Package: `wmtm/` (engine layout unchanged from the Iter tree for now).
- Public interface: `wmtm/api.py` (`WMTM`, `WMTMConfig`), see below.
- Tests: `python3 -m pytest` (no LLM, no network).
- PeTTa requirement: see `PETTA_PIN.md` (v1.0.5).
- Design notes and audits: `docs/`.
- `scripts/benchmark_wmtm.py`: micro-benchmark (run with `PYTHONPATH=.`).

Known external coupling: `wmtm/goalchainer_bridge.py` adds a hardcoded
OmegaClaw-GoalChainer path to `sys.path` (tests mock it). To be made
configurable.

## Interface (v0.2)

```python
from wmtm.api import WMTM, WMTMConfig
mem = WMTM(WMTMConfig(state_dir="memory"))          # journal defaults to PettaJournal(<state_dir>/_journal or $JOURNAL_DIR)
mem.observe({"user": user_text, "assistant": reply})  # reply only if it answered a real user message
ctx = mem.context_for(user_text)                      # "" -> automated fast path; returns block or None
mem.derive(note, source_ids)                          # explicit tool (flock-protected pending file)
mem.decide(request)                                   # GoalChainer tool
mem.save(); mem.close()
```

`WMTMConfig` injects `state_dir`, `journal` (any object with `read_lines()` /
`append(note, supersedes, about)`), `llm` (unused yet), `petta` (unused yet),
`use_goalchainer`, `reasoner` (`"python"` only), `capacity` (60), time budgets.

- `wmtm/context.py`: generic per-turn logic moved verbatim from Iter's
  `transformations/wmtm_context.py` (noise/duplicate filtering, stale cleanup,
  response feedback, relevance stimulus, formatting, automated fast path).
- `wmtm/journal.py`: default journal, moved from Iter's `_petta_journal.py`.
- `adapters/`: reference Iter files (NOT installed anywhere):
  `iter_transformation.py` (replacement for transformations/wmtm_context.py;
  Iter message parsing stays there), `iter_tool_wmtm_derive.py`,
  `iter_tool_goalchainer_decide.py`.
- CLI stub: `python -m wmtm context --state-dir DIR [--journal-dir DIR] < turn.json`,
  `python -m wmtm derive --state-dir DIR NOTE [IDS...]`.

## Replay equivalence

`tests/test_replay_equivalence.py` runs the original 83ea611 glue and the
adapter + `wmtm.api` in scratch Iter-shaped trees (frozen clock,
`PYTHONHASHSEED=0`) on a real state + journal copy over consecutive turns
(DMs, group context, attachments, autonomous/check-in prompts, injections,
derives, multi-day gaps, writeback) and requires byte-identical messages,
stderr, state file, pending file and journal appends after every step. It
includes a known-answer canary (journal-only codeword must reach the prompt,
survive one fast-path tick with exactly one 0.9 decay, and a derived note
must be admitted). Full live copies: set `WMTM_REPLAY_STATE`,
`WMTM_REPLAY_JOURNAL` and optionally `WMTM_REPLAY_ORIG_TREE`.

## Known quirks (kept for behaviour identity; fix after the switch)

- Engine state cached in a process does not see automated fast-path writes
  to the state file; a later real turn in the same process overwrites them
  (cycle can step back). Harmless in Iter (one process per transform call),
  matters for long-lived hosts (CLI service, other bots).
- State file writes are not atomic and not locked across processes.
- `close()` does not save (see the docstring).
- `embed_index.py` default cache path is `<repo>/memory/...`; `goalchainer_bridge`
  hardcodes the GoalChainer path (`WMTMConfig.goalchainer_src` covers `decide()` only).
