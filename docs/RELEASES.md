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

## v0.6.0-rc3 (2026-10-21)
GoalChainer fixes (Track T) plus two review/hygiene additions on top of v0.6.0-rc2. No new flags; `goal_prompt`
still off by default; with it off the block, state, journal and API behave exactly as rc2. All rc2 flags-file keys
are still valid.
- Track T fix 1: an automated goal run still vetoes message actions (never acted on, never in `proposals.jsonl`),
  but recomputes them on the same items with every other norm applied and puts them in `latest.json` marked
  `display_only: true` (fields now include `topic`, `display_only`). Their freshness is that run's `ts`.
  `runs.jsonl` records `display_only` (count) for automated runs.
- Track T fix 2: re-ask suppression (`goal_reask_s`) counts a proposal as asked only when a line was actually
  rendered on a real user turn: `goal_prompt.render(record=True)` (the live `format_context` path only) appends
  `{ts, shown_at, id, who, topic, action, display_only}` per shown line to `goalchainer/asked.jsonl`. Logging a
  proposal no longer counts; with `goal_prompt` off nothing is ever asked and the file is not created.
- rc3 (a): display-only suggestions are also appended to `goalchainer/display.jsonl` (same record as
  `proposals.jsonl` + `display_only: true`, `run_id`, `ts`, `source`) for review / rating before phase 2. An
  identical suggestion (same `who` + `topic` + `text`) is not re-logged within `goal_repeat_s` (6 h). Size-rotated
  (`jsonl_max_bytes`, `.1`). Read by nothing except that dedupe (never by re-ask or anything actionable).
  `runs.jsonl` records `display_logged`.
- rc3 (b): `asked.jsonl` is size-rotated (`jsonl_max_bytes`): the file moves to `.1` and the entries still within
  `goal_reask_s` are written back, so the re-ask window survives rotation.
- Tests: `tests/test_goals_track_t.py`, `tests/test_goals_rc3.py`.

## v0.6.0-rc2 (2026-10-20)
GoalChainer phase b, step 1 (Track S) on top of v0.6.0-rc1: an optional, read-only "Goal suggestions (not
instructions)" block on the user path. **Off by default** (`goal_prompt`); with the flag off the block, state,
journal and API behave exactly as rc1. All rc1 flags-file keys are still valid.
- The engine now also writes `<runtime_dir>/goalchainer/latest.json` after every goal run (atomic; `ts`, `run_id`,
  `status`, `canary_ok`, and that run's proposals incl. repeats; a failed run writes an empty list so older
  suggestions never survive it). Written whenever `goalchainer` is on, also with `goal_prompt` off.
- `wmtm/goal_prompt.py` (never imports the goal engine) renders at most `goal_prompt_max_lines` (hard cap 3) lines
  when: `goal_prompt` is on; the turn is a real user turn (`format_context(..., request=user_msg)`; automated turns
  and the automated fast path never get it); the run is fresh (`goal_prompt_max_age_s`, 900 s), `status` ok and
  canary ok; the proposal is a message action (ClarifyQuestion, FlagUncertainty, SummarizeStatus, RemindPending;
  never SelfTask / LookUp) addressed to the current speaker (resolved like rc4: the request item's source metadata
  via `speaker_map`; unknown speaker = no block). Any error = no block.
- Wording convention: lines are worded *to the current speaker* so the bot can relay them; the header says
  `"you" = the speaker, not the assistant`. The speaker's canonical name and its `speaker_map` aliases become
  you / your (case-insensitive, whole word, possessive 's -> your, is/was/has/does -> are/were/have/do), command verbs
  ("Ask X", "Remind X about") are dropped, redundant item markers ("Still pending:", "Open question for you:") are
  removed, and each line starts with "Open question for you:", "Still open for you:", "Status for you:" or
  "Pending for you:". Example (made-up names): engine "Remind quill about: Still pending: quill's choice on the gear
  order" -> "Pending for you: your choice on the gear order".
- Tests: `tests/test_goals_track_s.py`.

## v0.6.0-rc1 (2026-10-20)
GoalChainer phase 1 on top of v0.5.0-rc4 (tracks R, R2, R2.1): a homeostatic goal engine that **only logs**
proposals. **Off by default** (`goalchainer`); flags-file keys of rc4 are all still valid; API, adapters, state and
block unchanged. Design: `docs/GOALCHAINER_DESIGN.md`.
- Needs (`wmtm/goals/needs.py`): uncertainty (open questions, blocked-on, parser queries cached by the semantic
  parser) and competence (pending / waiting-on items, the bot's undelivered promises) estimated from the WMTM active
  set; level from the count, age and salience of open signals; urge `u = w * phi(target - level)`. A signal closes
  when a later note resolves it, reports it moot / answered, or the addressee replied on the topic (request history,
  below). "The user" resolves to the person whose request came last; the bot's own to-dos become self-tasks.
- Actions (`wmtm/goals/actions.py`): ClarifyQuestion, FlagUncertainty, LookUp (factual gaps only, read-only),
  SummarizeStatus (<= 3 whole-sentence items), RemindPending (only after `goal_remind_after_s` without a reply),
  SelfTask (log only). Messages go to a person resolved through `speaker_map` only (never "user", nobody, or the
  bot). One proposal per (person, topic) across Ask/Flag/Remind/LookUp; no re-proposal to the same person on the
  same topic within `goal_reask_s` unless the topic gained new content (history = logged proposals).
- Legitimacy (`wmtm/goals/legitimacy.py`) is a veto only: live changes, pushes, memories in git and writes are
  forbidden; in autonomous (automated) turns every message/write action is vetoed. GoalChainer's deontic resolver is
  used when `goalchainer_src` points at its `src/`, else an identical local one. A repeat inside `goal_repeat_s` is
  discounted and not re-logged. score = urge * geometric mean(considerations) * discouragements.
- Log only: the engine runs inside the PeTTaChainer shadow worker (detached, niced, SCHED_IDLE) after the shadow
  canary, gated by its own known-answer goal canary and a structural check per proposal, under `goal_budget_s`
  (SIGALRM). Output: `<runtime_dir>/goalchainer/proposals.jsonl` + `runs.jsonl` only. Nothing reaches the context
  block, the state, the journal or any channel; every exception is caught and recorded in `runs.jsonl`
  (`status` error / budget_exceeded / hook_error).
- Request history (new in rc1, for the "addressee replied" check): `goal_requests_dir` (flags file; relative =
  against `state_dir`) = the channel's completed request files, read-only. Sender = `speaker_map` lookup of the
  envelope's `user_id` / `sender_username` (or a private chat's chat id), never guessed from the text; the request
  text excludes the quoted group-context / document / authority blocks. Indexed once per file in
  `<runtime_dir>/goalchainer/requests_index.json` (mode 600; topic-key digests only, no raw text); bounded by
  `goal_requests_days` (14) and `goal_requests_max` (500). Group requests written before the transport added the
  sender cannot close anything.
- Parser queries are now kept in the semparse cache entries (`queries`, <= 20 x 300 chars) for the uncertainty
  need; raw items handed to the shadow worker carry `origin_ts`.
- Offline replay: `scripts/goals_replay.py` (copies of a journal / cache / request history only; output gitignored).
- Tests: `tests/test_goals_track_r.py`, `tests/test_goals_track_r2.py`, `tests/test_goals_v060.py` (log-only:
  nothing in the block, state or journal with `goalchainer` on; request index; budget/errors; names from
  `speaker_map` only).

## v0.5.0-rc4 (2026-10-20)
Track Q on top of v0.5.0-rc3: speaker linking for the semantic parser, **off by default** (`speaker_link`).
Flags-file keys of rc3 are all still valid; adapters unchanged (`WMTM.context_for` gained an optional `source=`).
- Problem: in parsed notes "the user", "the requester" and "I" become fresh per-note `sk_*` witnesses, so facts about
  one person never accumulate across notes. Names are rigid in the parser, so the text handed to the parser names
  the speaker (`wmtm/semparse_speaker.py`); the prompt file is never edited.
- Flags (flags file only, never in code): `speaker_link` (bool, false), `speaker_map` (object: Telegram user id or
  username -> canonical lower-case name), `speaker_self` (the bot's own name: "I"/"my"/the bot name -> it).
- Speaker resolution, most to least reliable (`speaker_source`): `source:<key>` = request metadata stored with the
  queued item; `text:meta` = Telegram metadata quoted in the text, one person only; `text:request` = a request
  phrase naming exactly one mapped person; otherwise unresolved (no guessing). A known but unmapped sender
  (`source_unmapped`) is never resolved from the text.
- Request metadata (rc4 wiring): the rc3 `source_type=user` request item carries `source_meta` (normalised by
  `wmtm/request_source.py`: a private chat's `chat_id` is the sender's user id; a group `chat_id` names no person;
  sender fields of a richer envelope pass through) and `first_person="speaker"` (I/me/my in a request = the
  requester, never the bot). Source: `context_for(..., source=)`, else (with `speaker_link` on) the Iter request
  binding (`ITER_REQUEST_IDS` / `ITER_OUTER_CHANNEL_ROOT/processing/<id>.json`, read only; ignored when its prompt
  does not contain the start of the user message). Both feed paths (cycle hook and automated fast path) hand the
  metadata to the parse queue.
- Limitation: Telegram group requests carry no sender id in the channel envelope (`source` = chat_id, message_id,
  update_id), so group requests fall back to the text routes. Minimal fix (outside this package): the transport adds
  the sender (`user_id`, `sender_username`) to `source`; `normalise` already passes those through.
- Cache: speaker-linked parses live in `<semparse_dir>/spk1` (`cache_version=spk1`, `speaker`, `speaker_source` per
  entry, keyed by the original content hash); base and ctx1 caches are never rewritten and old notes are not
  backfilled. The shadow prefers spk1 over ctx1 over base when `speaker_link` is on. `worker_runs.jsonl` records
  `speaker_link` and `speaker_stats` (resolved count, counts per `speaker_source`).
- State addition (ignored by rc3): `source_meta` on the request item.
- Capacity overflow (store full, same-turn admissions) evicts the request item last: rc3 could drop it in the
  same turn when PeTTaChainer admissions filled the store, so neither the feed nor the shadow saw the request.
- Tests: `tests/test_semparse_speaker.py`, `tests/test_request_source.py`.

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
