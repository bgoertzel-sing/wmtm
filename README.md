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
- Design notes: `docs/`; release/tag mapping: `docs/RELEASES.md`.
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
`use_goalchainer`, `reasoner` (`"pettachainer"` default, or `"off"`; v0.5 removed `"python"`), `capacity` (60),
time budgets.

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

## Background reasoner shadow and parse feed (v0.3)

Optional, off by default, enabled per bot through `<state_dir>/_wmtm_flags.json` (re-read every cycle; no
restart): a PeTTaChainer shadow that runs PeTTaChainer on the top-K items (since Track L the only reasoner; the
Python PLN engine was removed), and a
semantic-parse feed that parses items through the bot's LLM gateway (default cap 20 parses/hour). Both run in
detached, niced, memory-capped workers (`python -m wmtm.workers.*`) and never affect the cycle. See
`docs/RUNTIME.md`; `scripts/vendor_runtime.sh` builds the PeTTa v1.0.6 / PeTTaChainer 36b3fe6 (+ dedup patch)
runtime, `scripts/fetch_semparse_hitl.sh` fetches the semantic-parsing prompt (not redistributed: no licence).

v0.5.0-rc2 adds ranked shadow goals (chains up to 3 steps, anchored on the current request; `shadow_goal_rank`,
default on), treats derived strength as a probability (`reasoner_min_strength` 0.5, `reasoner_negation`
skip|unlikely, default skip) and an optional CONTEXT coreference parse path (`semparse_context`, default off).
v0.5.0-rc3 fixes the recall/context plumbing: freshly recalled notes survive stale cleanup, the context block is
ranked by relevance to the current request (longer, request-focused item text under a character budget), and the
request is stored as a `source_type=user` item so request-anchored goal ranking works. v0.5.0-rc4 adds optional
speaker linking for the semantic parser (`speaker_link`, default off; the request item carries its request
metadata). See `docs/RELEASES.md`.

## Replay equivalence

`tests/test_replay_equivalence.py` runs the original 83ea611 glue
(`tests/fixtures/iter_83ea611/`, code copies) and the adapter + `wmtm.api` in
scratch Iter-shaped trees (frozen clock, `PYTHONHASHSEED=0`) over consecutive
turns (DMs, group context, attachments, autonomous/check-in prompts,
injections, derives, multi-day gaps, writeback) and requires byte-identical
messages, stderr, state file, pending file and journal appends after every
step. It includes a known-answer canary (journal-only codeword must reach the
prompt, survive one fast-path tick with exactly one 0.9 decay, and a derived
note must be admitted). By default it runs on the synthetic fixtures in
`tests/fixtures/synthetic/` (regenerate with
`python3 tests/fixtures/synthetic/make_fixtures.py`).

## No real memories in this repo

This repository contains no real bot memories: no WMTM state, journal/LTM
notes, conversation excerpts, chat or message ids, or reports about specific
conversations. All test data is synthetic (invented people, topics, notes and
ids). `.gitignore` excludes the usual memory paths (`memory/`, `_journal/`,
`*_wmtm_state*.json`, `journal*.metta`, `.replay-data/`); do not force-add them.

To replay against real data locally, copy a bot's memory directory (read-only)
to a scratch directory OUTSIDE the repo and point `WMTM_REPLAY_DATA` at it:

```sh
mkdir -p /tmp/wmtm-replay/_journal
cp <bot>/memory/_wmtm_state.json /tmp/wmtm-replay/
cp <bot>/memory/_journal/journal.metta /tmp/wmtm-replay/_journal/
WMTM_REPLAY_DATA=/tmp/wmtm-replay python3 -m pytest tests/test_replay_equivalence.py
```

Without `WMTM_REPLAY_DATA` the real-data cases are skipped with a message;
the test refuses a directory inside the repo. Optionally set
`WMTM_REPLAY_ORIG_TREE` to a full snapshot of the original Iter tree.

## Known quirks (kept for behaviour identity; fix after the switch)

- Engine state cached in a process does not see automated fast-path writes
  to the state file; a later real turn in the same process overwrites them
  (cycle can step back). Harmless in Iter (one process per transform call),
  matters for long-lived hosts (CLI service, other bots).
- State file writes are not atomic and not locked across processes.
- `close()` does not save (see the docstring).
- `embed_index.py` default cache path is `<repo>/memory/...`; `goalchainer_bridge`
  hardcodes the GoalChainer path (`WMTMConfig.goalchainer_src` covers `decide()` only).
