# Releases and history rewrite

The history of `main` was rewritten so that it contains no real bot
memories (WMTM state, journal notes, conversation-derived reports or ids).
The `wmtm/` package code was not changed: every rewritten commit has the
same `wmtm/` tree as its original.


## Tags

| Tag | Commit | Content |
|-----|--------|---------|
| `v0.1.0` | `64297af` | = old `v0.1.0` (`225947c`) minus memory-derived docs; `wmtm/` tree `c7c1d30` |
| `v0.2.0-rc2` | tagged commit | = old `v0.2.0-rc1` (`a5cb1e5`) minus memory fixtures/docs, plus synthetic replay fixtures, `WMTM_REPLAY_DATA` opt-in, `.gitignore` guards, invented ids in comment examples; `wmtm/` tree `fab6bf5` |

`v0.2.0-rc1` is retired: its package code is identical to `v0.2.0-rc2` except for
comment/docstring examples (rc1 `wmtm/` tree `1e3dd64`, rc2 `fab6bf5`); tests/docs differ. Deployments pinned to
commit `a5cb1e5` (old rc1) keep working unchanged and can move to
`v0.2.0-rc2` at the next redeploy without a code change.

## Old -> new commits

Commits `b9fcc24` .. `5d4ca52` (the subtree-split package history and the
move into `wmtm/`) were already clean and are unchanged. Rewritten:

| Old | New | Subject |
|-----|-----|---------|
| `225947c` | `64297af` | Add packaging, WMTM tests and docs from snapshot 83ea611 |
| `bd32621` | `502a5b8` | Move generic turn logic and default journal into the package |
| `ea29059` | `8dd28e4` | Add wmtm.api (WMTM, WMTMConfig) and a minimal CLI stub |
| `64728f4` | `14b01d0` | Add reference Iter adapters (not installed anywhere) |
| `a5cb1e5` | `66cc921` | Add replay-equivalence test, known-answer canary and fixtures; 0.2.0rc1 |

What changed in the rewritten commits: memory-derived documents and the
real state/journal fixtures were removed, `PETTA_PIN.md` was reduced to its
technical content, three comments in the Iter glue copies were made
generic, and the replay test switched to synthetic fixtures (real data only
via `WMTM_REPLAY_DATA`, see README).

The pre-rewrite refs exist only in the original local clone
(`old-main-with-fixtures`, `old-v0.1.0`, `old-v0.2.0-rc1`) and must never be
pushed.

## v0.2.0-rc3 (2026-10-16)
- Stopgap: quantifier/negation pronouns (nothing, something, anything, everything, none, nobody, someone, anyone,
  everyone, noone) are now stopwords for the regex triple extractor. Before, "nothing has room" became the
  junk belief (nothing, has, room). The semantic-parsing reasoner will replace this extractor.
- Test: `tests/test_quantifier_stopwords.py`.

## v0.3.0-rc1 (2026-10-16)
- Tracks E-H (PeTTaChainer scaling/timeout studies, upstream repros, PeTTaChainer shadow, semantic-parse feed),
  rebased onto v0.2.0-rc3.
- Runtime flags file `<state_dir>/_wmtm_flags.json` (env still overrides; absent = off), read every cycle:
  the shadow and the parse feed switch on/off without a host restart. `wmtm/runtime_config.py`, `docs/RUNTIME.md`.
- Workers moved into the package (`python -m wmtm.workers.pc_shadow|semparse_feed`); all runtime paths come from
  the config with defaults relative to the vendored package; worker data defaults to `<state_dir>/_wmtm_shadow/`.
- Workers run SCHED_IDLE + nice 19 + ionice idle (a host scheduler daemon was seen rewriting plain nice values).
- Worker address-space cap (`worker_mem_mb`, default 3 GB); JSONL size caps (rotation to `.1`; the parse log keeps
  the rolling hour so the cost cap holds; the parse cache is compacted); hung-worker reaping; stale spec cleanup.
- Shadow goals about parser-invented `sk_*` placeholder entities are dropped by default (`shadow_skolem_goals`);
  their facts stay in the KB.
- Parse worker verifies the pinned prompt sha256 before any LLM call.
- `scripts/vendor_runtime.sh` replaces `scripts/pettachainer/pc_vendor36.sh`; `scripts/fetch_semparse_hitl.sh`
  takes a destination. No machine-specific paths in package code or tests.
- API unchanged (`WMTM`, `WMTMConfig`); existing Iter adapters work as-is.

## v0.3.0-rc2 (2026-10-16)
- The Track G/H hooks also run on automated turns. Before, they ran only inside `WMTMOrchestrator.cycle()`
  (real user turns), so on a mostly autonomous bot they almost never fired. `context.fast_path_automated` now calls
  `context.automated_hooks` after saving the state: same flags file, single-worker busy guard and parse cap, fed
  from the state snapshot's top-K item fields (the workers build the snapshot), no engine import. Flag
  `hooks_on_automated` (default true). Added fast-path latency (fresh process, 50 synthetic items, ~380 KB parse
  cache): about +0.4 ms with the hooks off, about +2 ms in steady state, about +14 ms when the top-K contents changed (one
  enqueue), about +11 ms when a worker is spawned.
- Shadow launches are rate-limited (`shadow_min_interval_s`, default 300 s; cycle and automated paths).
- Worker CPU priority: workers are launched via `chrt -i 0` when available, set nice + SCHED_IDLE on every thread
  themselves at startup, and re-assert it on themselves and their children every `worker_prio_refresh_s` (5 s).
  A host scheduler daemon (system76-scheduler) was seen resetting a live parse worker to SCHED_OTHER / nice 12.
  Output records carry the actual `prio` and `prio_end` (incl. `resets`).
- Fast-path imports trimmed (`subprocess`/`resource` imported where used; builtin sha256 instead of hashlib).
- Tests: `tests/test_automated_hooks.py`.

## v0.5.0-rc3 (2026-10-19)
Track P on top of v0.5.0-rc2: recall/context plumbing, so the memories recalled for a request reach the prompt.
Flags-file keys of rc2 are all still valid; API and adapters unchanged. Every change has its own switch (defaults
on); all off = rc2 behaviour.
- (a) `cleanup_protect_recent` (default true; `cleanup_grace_turns` 10, `cleanup_grace_s` 1800): stale cleanup
  (user path and automated fast path) spares items recalled for, or matching, a real request within the grace
  window (`recalled_at` / `recalled_cycle` on the item). rc2 evicted every freshly recalled journal note in the same
  turn, before the block was rendered (journal age >= 48 h, utility 0), so the block showed what earlier turns had
  kept, not the request's recall. Operational-noise eviction still applies.
- (b) `context_rank` (default true): the block is ranked by `w_rel`*relevance + `w_sti`*STI (`context_rank_weights`
  `0.7,0.3`). Relevance = recall / relevance-stimulus score (recalled items) or IDF-weighted request-term overlap
  (other items), normalised; the `context_min_request_items` (5) best matches come first; once a request is known,
  items scoring below `context_min_score` (0.2) are left out. Items share
  `context_total_chars` (6000; at most `context_item_chars` 600 each, floor 250); a long item shows its opening plus
  its most request-relevant window instead of the first 200 chars. Lines carry `rel=`. The relevance
  (`context_rel`: scores, request terms) is persisted in the state, so automated turns rank the same way and also
  score conclusions admitted after the request. F17 passive utility goes to the items actually shown.
- (c) `request_item` (default true): the current request is stored as one `source_type=user` item (replaced by
  the next request; never shown, never written back), so Track N's request-overlap goal ranking has request terms
  (`goal_rank.user_items` was always 0 on live). Derived conclusions that overlap the request get relevance and rank
  into the block through (b).
- (d) parse gate `identifier_category`: an identifier may follow any short alphabetic prefix (`ref_`, `tag_`,
  `build_`, ...; `[a-z]{1,8}[_-]`) when the hex run has both a digit and a letter; `ref` added to the known
  prefixes (which also allow all-digit runs). `ref_<hash>` typed as a branch is now rejected; dated names such as
  `release_20250307` are not identifiers.
- (e) `worker_prio_refresh_s` default 1 s (was 5 s): short worker runs ended at nice 12 because the host scheduler
  reset them before the first re-assert.
- State additions (ignored by rc2): `recalled_at` / `recalled_cycle` on items, `context_rel` in the snapshot,
  `source_type=user` items (rc2 would display them: remove them on a pin rollback).
- Replay equivalence runs with the Track P switches off (the original glue has none of them).
- Tests: `tests/test_track_p.py`.

## v0.5.0-rc2 (2026-10-19)
Tracks N and O on top of v0.5.0-rc1. Flags-file keys of rc1 are all still valid; API unchanged.
- Track N: ranked shadow goals (Design A, `docs/TRACK_M_GOALS.md`), on by default (`shadow_goal_rank`). The goal
  pool holds every goal derivable by chains of up to `shadow_max_hops` (3) derivation steps that is not already
  asserted; goals needing fewer than `shadow_min_hops` (1) steps are skipped. Score = `w_req`*request overlap +
  `w_depth`*(hops-1) + `w_info`*category informativeness + `w_sti`*source STI (`shadow_goal_weights`, default
  `2,1,1,0.5`); the best `shadow_max_goals` are asked. Request terms come from the current request items
  (`source_type=user`, now passed through to the shadow worker on both paths): their parsed entities plus 1-hop KB
  neighbours, and their text tokens. `shadow.jsonl` records `goal_rank` (pool size, request terms, hops histogram)
  and each query carries its `hops`, `score` and `overlap`. `shadow_goal_rank=false` restores the rc1 (Track M) 2-step goals.
- Track O (1): derived strength is a probability. A conclusion with strength below `reasoner_min_strength`
  (default 0.5; rc1 admitted from 0.1) means "probably not" and is never admitted as a weak positive.
  `reasoner_negation` = `skip` (default: dropped, counted in `dropped.negative`) or `unlikely` (admitted as
  `unlikely: <text>` when 1-strength >= `reasoner_min_strength`, STI from 1-strength). Admitted items carry
  `provenance.polarity`.
- Track O (2): CONTEXT coreference parsing (`wmtm/semparse_context.py`, `SemParseAdapter.parse_item_ctx`,
  `parse_cache.process_queue_ctx`). **Off by default** (flags key `semparse_context`, env `WMTM_SEMPARSE_CONTEXT`):
  it did not improve the replay results and multiplies parse cost (one LLM call per passage). When on, the feed
  queues into a separate cache version `<semparse_dir>/ctx1` (own queue, hourly cap, worker pid), each note is
  parsed with the atoms of up to `context_max_notes` related earlier notes as CONTEXT (long notes per
  `context_passage_chars` passage), and the shadow prefers ctx1 entries over the base cache. The base cache is never
  rewritten; switching it off again falls back to the base cache. With it off nothing reads or creates `ctx1`.
- Parse cache unchanged: content-hash key; existing entries are reused, not re-parsed.
- Tests: `tests/test_goal_rank.py`, `tests/test_semparse_context.py`, additions in `tests/test_pc_admit.py`.

## v0.5.0-rc1 (2026-10-18)
Tracks L and M on top of v0.4.0-rc2 (rc2 admission behaviour kept unchanged).
- Track L: the Python PLN engine is removed (`wmtm/inference.py`, `wmtm/pln.py`, `wmtm/pln_bridge.py` and their
  tests). PeTTaChainer is the only reasoner. The candidate type moved to `wmtm/candidate.py`. No code path
  (cycle, budget-skipped user turn, automated fast path, `wmtm.api`) imports a removed module.
- `reasoner` = `pettachainer` (default: `WMTMConfig.reasoner`, the orchestrator, `context.fast_path_automated`) |
  `off`. Any other value, including the removed `python`, means **off**: the reasoner phase admits nothing
  (`reasoner_info.skipped = reasoner_off`, flags-file value recorded as invalid), on every path.
  `WMTMConfig(reasoner="python")` raises `ValueError`.
- Orchestrators without a state dir (scratch orchestrators, e.g. `decide()`) force the reasoner off: they never
  launch or admit from the shadow worker.
- With the Python engine gone, the cycle no longer runs the basic inference / contradiction phases;
  `CycleResult.contradictions` / `resolutions` / `contradiction_evictions` are removed.
- Track M: parse-gate rule `identifier_category`: rejects Member/Inheritance whose category is an identifier (git
  hash, hex id, pid, uuid; optional `c_`/`id_`/`sha_`... prefix), or whose identifier subject is typed as
  branch/dir/path/file/repo/... (also `*_branch` etc.). Flags `gate_identifier_action` (reject|discount|keep,
  default reject) and `gate_identifier_bad_categories`.
- Track M: `wmtm/semparse_preamble.py`: an instruction block prepended to the pinned semparse prompt by
  `SemParseAdapter` (flag `semparse_preamble`, default on; the parse worker passes the flags-file value). The
  prompt file is not edited and the worker still checks its sha256 pin. The worker records `preamble`,
  `file_sha256` and `prompt_sha256` (what is actually sent) in `worker_runs.jsonl`; each parse attempt records
  `prompt_sha` (16 hex) in `parse_log.jsonl` and `cache.jsonl`.
- Parse cache: still keyed by content hash only. Entries parsed under the v0.4 prompt are **reused, not
  re-parsed** (no extra LLM cost on upgrade); only new content is parsed with the preamble.
- Design note for goal steering: `docs/TRACK_M_GOALS.md`.
- Flags-file keys of v0.4 are all still valid. API unchanged except the `reasoner` values above.

## v0.4.0-rc2 (2026-10-17)
- Bugfix: with `reasoner=pettachainer`, conclusions were admitted only inside `WMTMOrchestrator.cycle()`. On a
  busy host the user turn exceeded `cycle_budget` (15 s) before the cycle, and automated turns never admit, so a
  fresh, canary-passed `admit.json` was never admitted live. Admission (cheap: no PLN) now runs on every user turn,
  also when the cycle is skipped for budget, and on automated turns via the fast path (flag
  `reasoner_admit_on_automated`, default true). Same guards and caps; each run is admitted at most once
  (`pc_admit.consumed_run` in the state file).
- Conclusions already present or forgotten are dropped before the caps (`dropped.known`); rc1 let them fill
  `reasoner_max_admit`, so repeat runs admitted nothing new.
- `<shadow_dir>/admit_log.jsonl` (size-capped): path, run, counts, skip reason, per-phase timing of user turns.
- PeTTaChainer item ids are `derived-pc_deduction-<cycle>-<md5[:8]>` (no collisions outside the cycle).
- Fast-path latency: +0.1 ms median steady state; ~25 ms once per new run (engine import) in a fresh process.
- Tests: `tests/test_pc_admit_rc2.py`.

## v0.4.0-rc1 (2026-10-17)
- Tracks I-K. Reasoner switch `reasoner` = `python` (default, unchanged behaviour) | `pettachainer` in the flags
  file. With `pettachainer` the Python PLN phase is replaced by admitting PeTTaChainer conclusions from the shadow
  worker's `pc_shadow/admit.json`: only from fresh, canary-passed runs, only rule-derived proofs within the
  timeout and budget, with STV and proof-term provenance on each item. There is no Python fallback: a missing,
  stale or failed run means nothing is admitted that cycle (`wmtm/pc_admit.py`).
- Parse-quality gate for the shadow KB (`wmtm/parse_gate.py`, flags `gate_*`). It has per-fact sanity rules
  (placeholder subjects, low confidence, negative and hedged quantifiers, broad categories), a per-fact cap on
  admitted conclusions, and a review log.
- Shadow KB is built from cached semantic-parse atoms only. The regex fallback, the Python PLN comparison and
  `reasoner=both` were removed.
- `reasoner_writeback` (default false): PeTTaChainer-admitted conclusions are not written back to the long-term
  journal. They stay in working memory only.
- API unchanged. `WMTMConfig.reasoner` accepts `python` | `pettachainer`. Existing Iter adapters work as-is.
- Tests: `tests/test_pc_admit.py`, `tests/test_parse_gate.py`.
