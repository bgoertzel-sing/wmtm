# Background reasoner, shadow, semantic-parse feed and goal engine (v0.7.0-rc1)

Two optional background features run next to the normal WMTM cycle. Both are **off by default** and, unless
`reasoner` is `pettachainer` (see below), neither can change what WMTM admits or shows: they run in detached,
niced worker processes, the cycle never waits for them, and every error is swallowed on the cycle side.

- **PeTTaChainer shadow** (Track G, `pc_shadow`): each cycle the top-K active items are handed to a worker that
  builds a small PLN knowledge base from the cached semantic parses only (v0.4: no regex fallback; unparsed items
  add no facts, counted in `unparsed_items`), applies the parse-quality gate, asks PeTTaChainer ranked chain goals
  (rc2, Track N: see "Goal ranking") with a hard per-query timeout, and appends one JSON line to `pc_shadow/shadow.jsonl` plus `pc_shadow/admit.json`
  (the admissible results, see below). v0.4 removed the Python-PLN comparison from the shadow; v0.5 (Track L) removed the Python PLN engine entirely. A Grace canary and a negative control run
  through the same path on every run; if they fail the record is `canary_fail` and no goal result is trusted.
- **Semantic-parse feed** (Track H, `semparse_feed`): each cycle the top-K items are queued by content hash; a
  worker parses them with the semantic-parsing-hitl prompt through the bot's existing OpenAI-compatible gateway,
  load-checks every atom in PeTTaChainer and caches the accepted atoms (`semparse_cache/cache.jsonl`). The same
  content is never parsed twice. At most `parse_cap_per_hour` (default 20) parse attempts run per rolling hour.
  v0.5 (Track M): the worker prepends an instruction block (`wmtm/semparse_preamble.py`, flag `semparse_preamble`,
  default on) to the pinned prompt; the pin is still checked against the unedited file. The cache key stays the
  content hash, so entries parsed with an earlier prompt are reused, not re-parsed; `worker_runs.jsonl` records
  `preamble`, `file_sha256`, `prompt_sha256`, and each parse attempt records `prompt_sha` (16 hex) in
  `parse_log.jsonl` / `cache.jsonl` (absent on pre-v0.5 entries). To re-parse under the new prompt, delete the
  matching `cache.jsonl` lines (costs one LLM call each, within the hourly cap).
  rc2 (Track O): optional CONTEXT coreference parsing, **off by default** (`semparse_context`, see below).
  rc4 (Track Q): optional speaker linking, **off by default** (`speaker_link`, see below).
- **Goal engine** (v0.6, GoalChainer phase 1, `goalchainer`, **off by default**, log only): runs inside the shadow
  worker after its canary; see "Goal engine" below.

Both hooks run on every WMTM cycle *and* (since v0.3.0-rc2) on automated turns: the automated fast path
(`WMTM.context_for` with no real user message) feeds them the top-K items from the state JSON without loading the
engine (`hooks_on_automated`, default true). Steady-state cost on that path is a few ms (flags read, busy/rate-limit
checks; the parse feed skips the enqueue when the top-K contents are unchanged). Shadow launches are rate-limited to
one per `shadow_min_interval_s` (default 300 s) on both paths, so autonomous ticks cannot spawn back-to-back runs.

## Reasoner switch (v0.5)

`reasoner` = `pettachainer` (default) or `off`. Unset = `WMTMConfig.reasoner` (itself `pettachainer`). Any other
value, including `python` (the Python PLN engine was removed in v0.5), means **off**: nothing is admitted on any path
(`reasoner_info.skipped` = `reasoner_off`; the flags-file key is listed under `_source.invalid`). Re-read every cycle,
so it flips without a restart. Orchestrators without a state dir (scratch orchestrators such as `decide()`) always
run with the reasoner off.

With `pettachainer`:
- There is no Python PLN engine (removed in v0.5) and no fallback.
- On every turn (rc2; rc1: only inside `WMTMOrchestrator.cycle()`) WMTM reads `<shadow_dir>/admit.json`, which
  the latest shadow worker run wrote. It admits from it only when all of these hold: the file is fresh
  (`reasoner_max_age_s`, measured from the run's spec timestamp), the run status is `ok` and the canary passed
  (negative control not proved). Otherwise it admits nothing that cycle (`CycleResult.reasoner_skipped`,
  `reasoner_info.skipped` = `no_admit_file` / `bad_admit_file` / `stale` / `run_<status>` / `already_consumed` /
  `no_candidates`).
- rc2: admission does not depend on the full cycle. User turns admit inside `cycle()`, or on their own when the cycle
  is skipped for `cycle_budget` (path `budget-skipped`). Automated turns admit on the fast path straight into the
  state snapshot (`reasoner_admit_on_automated`, default true; the engine modules are imported only when a new run
  has candidates). Each run (`run` = `<spec_ts>/<ts>`) is admitted at most once: once it yields gated candidates its
  id is stored as `pc_admit.consumed_run` in the state file and later turns skip it.
- rc2: conclusions already in WMTM (same text) or in the forgetting log are dropped before the caps
  (`dropped.known`), so a run that re-proves admitted conclusions still admits its new ones.
- rc2: every attempt (reasoner = pettachainer) appends one record (numbers and ids only) to
  `<shadow_dir>/admit_log.jsonl` (rotated to `.1` above `admit_log_max_bytes`): `ts`, `path`
  (`user` / `budget-skipped` / `automated`), `run`, `age_s`, `status`, `results`, `candidates`, `admitted`,
  `skipped`, `dropped`, and `timing` (user turns: `store_s`, `journal_s`, `recall_s`, `relevance_s`,
  `derives_cleanup_s`, `elapsed_before_cycle_s`, `cycle_s` or `admit_s` + `tick_s`, `total_s`, `cycle_budget`;
  automated: `admit_s`).
- Per result it needs a proof that used a derivation rule (`inh_trans`, `imp_trans`, `mem_inh`), so proofs straight
  from asserted facts are dropped. It also needs confidence >= 0.05 and (rc2) strength >= `reasoner_min_strength`
  (0.5; below it the conclusion means "probably not": `reasoner_negation` `skip` drops it, `unlikely` admits it
  as `unlikely: <text>`), at least one supporting item still active, and
  it applies the per-fact cap (`gate_max_per_fact`) and `reasoner_max_admit`.
- Admitted items: `source_type="derived"`, id `derived-pc_deduction-<cycle>-<content md5[:8]>` (rc1: `-<i>`), `derived_from` = the supporting
  item ids, initial STI = strength x confidence, and `provenance` = `{reasoner, goal, stv, proof, run_ts, query_s}`
  (kept in the state file). The usual novelty and forgotten-item checks apply.
- The shadow worker is launched on cycles even when `pc_shadow` is false. The automated fast path launches it only
  when `pc_shadow` is true.
- **Journal writeback:** derived items normally become writeback candidates (`derived_promotion` to the journal) once
  they reach age >= 15 and utility >= 1.5. PeTTaChainer-admitted items are excluded unless
  `reasoner_writeback` is true (default **false**: working memory only).

| key | env | default | meaning |
|---|---|---|---|
| `reasoner` | `WMTM_REASONER` | (`pettachainer`) | `pettachainer` or `off` (anything else = off) |
| `reasoner_max_age_s` | `WMTM_REASONER_MAX_AGE` | 900 | ignore `admit.json` older than this |
| `reasoner_max_admit` | `WMTM_REASONER_MAX_ADMIT` | 5 | admitted conclusions per cycle |
| `reasoner_min_strength` | `WMTM_REASONER_MIN_STRENGTH` | 0.5 | rc2: strength is a probability; below this a conclusion is negative |
| `reasoner_negation` | `WMTM_REASONER_NEGATION` | skip | rc2: negative conclusions `skip` (dropped, `dropped.negative`) or `unlikely` (admitted as `unlikely: ...`) |
| `reasoner_writeback` | `WMTM_REASONER_WRITEBACK` | false | allow journal writeback of PeTTaChainer-admitted items |
| `reasoner_admit_on_automated` | `WMTM_REASONER_ADMIT_ON_AUTOMATED` | true | rc2: also admit on automated turns |
| `admit_log_max_bytes` | `WMTM_ADMIT_LOG_MAX_BYTES` | 1000000 | rc2: rotate `admit_log.jsonl` above this size |
| `gate_on` | `WMTM_GATE` | true | parse-quality gate on shadow KB facts (`wmtm/parse_gate.py`) |
| `gate_min_conf` | `WMTM_GATE_MIN_CONF` | 0.3 | reject parsed facts below this confidence |
| `gate_broad_terms` / `gate_placeholder_terms` | `WMTM_GATE_BROAD_TERMS` / `WMTM_GATE_PLACEHOLDERS` | built-in lists | broad categories; pronoun-like subjects (always rejected) |
| `gate_hedged_quantifiers` / `gate_negative_quantifiers` | `WMTM_GATE_HEDGED` / `WMTM_GATE_NEGATIVE` | built-in lists | quantifier words (negative = rejected) |
| `gate_broad_action` / `gate_hedged_action` | `WMTM_GATE_BROAD_ACTION` / `WMTM_GATE_HEDGED_ACTION` | reject / reject | `reject`, `discount` or `keep` |
| `gate_identifier_action` | `WMTM_GATE_IDENTIFIER_ACTION` | reject | v0.5: Member/Inheritance with an identifier (hash, hex id, pid, uuid) as category, or an identifier subject typed as `gate_identifier_bad_categories`: `reject`, `discount` or `keep` |
| `gate_identifier_bad_categories` | `WMTM_GATE_IDENTIFIER_BAD` | branch, dir, path, file, repo, ... | kinds an identifier subject may not be typed as (also `*_<kind>`) |
| `gate_discount` | `WMTM_GATE_DISCOUNT` | 0.5 | strength factor for `discount` |
| `gate_max_per_fact` | `WMTM_GATE_MAX_PER_FACT` | 3 | admitted conclusions per KB fact per cycle (0 = no cap) |
| `gate_review_min` | `WMTM_GATE_REVIEW_MIN` | 3 | log facts behind >= N proved conclusions to `pc_shadow/parse_review.jsonl` |

## Goal ranking (rc2, Track N)

The shadow builds a pool of goals derivable by Inheritance/Implies transitivity and Member+Inheritance chains of up
to `shadow_max_hops` derivation steps (not already asserted, no `sk_*` placeholders unless `shadow_skolem_goals`),
scores each as `w_req`*overlap with the current request + `w_depth`*(hops-1) + `w_info`*category informativeness
(0 when the category echoes the subject name) + `w_sti`*max source STI, and asks the best `shadow_max_goals`.
Request terms: entities parsed from the current `source_type=user` items plus their 1-hop KB neighbours, and the
items' text tokens (an unparsed request still anchors by name). `shadow.jsonl` records `goal_rank`
(`pool`, `user_items`, `req_entities`, `req_tokens`, `hops` histogram) and each entry of `queries` its
`hops`, `score` and `overlap`.

## Context block (rc3, Track P)

On a real user turn: recall admits the best journal clusters, the relevance stimulus scores resident items, and
both mark matching items as recalled now (`recalled_at` / `recalled_cycle` in the state). Stale cleanup then spares
them (`cleanup_protect_recent`); rc2 evicted them in the same turn because a recalled note's journal age is >= 48 h
with utility 0. The block ranks items by `w_rel`*relevance + `w_sti`*STI/max STI. Relevance = the recall /
stimulus score for recalled items, IDF-weighted overlap with the request terms for others (derived conclusions),
normalised by the best score; the `context_min_request_items` best matches come first and, once a request is
known, other items scoring below `context_min_score` are left out. Items share
`context_total_chars` (at most `context_item_chars` each); a long item shows its opening plus the window with the
most request-term weight. Lines carry `rel=` when relevant. `context_rel` (scores, request terms, normaliser) is
persisted in the state, so automated turns rank the same way and score conclusions admitted after the request.
The request itself is a `source_type=user` item: the shadow's request-overlap goal ranking reads it
(`goal_rank.user_items` > 0).

## Context parsing (rc2, Track O, off by default)

`semparse_context=true` routes the feed to `<semparse_dir>/ctx1` (separate queue, cache, hourly cap and worker
pid). Each queued note is parsed with CONTEXT = atoms of up to `context_max_notes` related earlier notes (shared
terms, then recency), long notes per passage; re-emitted context atoms are dropped and context `sk_*` witnesses keep
their scope. Entries record `cache_version=ctx1` and `context_ids`. The shadow then prefers ctx1 entries over the
base cache. Cost: every note is parsed again in ctx1 (one call per passage), within `parse_cap_per_hour`. The base
cache is never rewritten; with the flag off nothing reads or creates `ctx1`.

## Speaker linking (rc4, Track Q, off by default)

`speaker_link=true` routes the feed to `<semparse_dir>/spk1` (separate queue, cache, hourly cap and worker pid).
Before parsing, each note's text is rewritten (`wmtm/semparse_speaker.py`): mapped usernames -> the canonical name,
"the user"/"the requester" -> the resolved speaker, "I"/"me"/"my" -> `speaker_self` (bot notes) or the speaker
(request items, `first_person="speaker"`), prefixed `Speaker: <Name>.` when resolved. Resolution order:
request metadata (`source:user_id` / `source:sender_username`), Telegram metadata in the text (`text:meta`), a
request phrase naming one mapped person (`text:request`); else unresolved. The request item gets its metadata from
`context_for(source=)` or, when omitted, the Iter request binding (see `wmtm/request_source.py`); a private chat's
chat id is the sender, a group chat names no sender (text routes only). Entries record `cache_version=spk1`,
`speaker`, `speaker_source`; `worker_runs.jsonl` records `speaker_stats`. The shadow prefers spk1 entries. Old
caches are kept and not backfilled; with the flag off nothing reads or creates `spk1`. Ids and names belong in the
deployed flags file only.

## Goal engine (v0.6, GoalChainer phase 1, off by default, log only)

v0.7: the core (need regulation, deontic legitimacy, ranking) is GoalChainer v2, run as a separate process in its
own environment (`goal_engine` `v2`, default; `native` = the v0.6 core below, rollback switch for one release).
Extraction, addressees, timing, gates and every output file stay as described here; proposal records gain
`engine`, `decision`, `action_id`, `v2` (review id, fingerprint, rank, proof, steps, plan); hold / escalate /
blocked decisions go to `runs.jsonl` (`v2`) only. Runtime, flags, licensing: `docs/GOALS_V2.md`.

`goalchainer=true` makes the PeTTaChainer shadow worker (so `pc_shadow` must be on too) run `wmtm.goals.run_shadow`
after its own run: needs (uncertainty, competence) from the snapshot's raw items + cached parser queries, candidate
actions (ClarifyQuestion, FlagUncertainty, LookUp, SummarizeStatus, RemindPending, SelfTask), legitimacy veto,
scoring. Gates: the shadow canary (else `shadow_canary_fail`), the goal canary (made-up person, known answer; else
`canary_fail`), a structural check per proposal; wall-clock cap `goal_budget_s` (SIGALRM; `budget_exceeded`).
Output, and nothing else: `<runtime_dir>/goalchainer/proposals.jsonl` (`id`, `action`, `need`, `text`, `why`,
`score`, `urge`, `cons`, `legit`, `status`, `items`, `who`, `effects`, `topic`) and `runs.jsonl` (`status`, `canary`,
`needs`, `candidates`, `vetoed`, `refused`, `logged`, `requests`, `history`, `s`, `budget_s`). Nothing goes into the
context block, the state, the journal or any channel; no action is taken (except the optional, off-by-default
suggestions block below). Addressees are `speaker_map` names only. Every run also writes
`goalchainer/latest.json` (rc2; atomic; `ts`, `status`, `canary_ok`, that run's proposals; empty after a failed run).
Automated runs (rc3, Track T) also put the message suggestions they veto into `latest.json` marked `display_only`
(never logged to `proposals.jsonl`, never actionable) and append them, deduped per `who` + `topic` + `text` within
`goal_repeat_s`, to `goalchainer/display.jsonl` for review. Re-ask suppression (`goal_reask_s`) reads only
`goalchainer/asked.jsonl`, written when a suggestion line is actually rendered on a real user turn (so nothing with
`goal_prompt` off); its rotation keeps the entries inside `goal_reask_s`. Neither file is read by anything else.

Reply detection reads the channel's completed request files (`goal_requests_dir`, read-only; one
`{prompt, source}` envelope per file, response envelopes skipped). Sender: the envelope's `user_id` /
`sender_username` (or a private chat id) mapped through `speaker_map`; unmapped or missing = the request is ignored.
Each file is parsed once into `<runtime_dir>/goalchainer/requests_index.json` (mode 600; per file: mtime, sender,
topic keys, reply flag, "answers to HH:MM" times, moot anchors; never the raw text); files older than
`goal_requests_days` or beyond the `goal_requests_max` newest are not read. Changing the dir or the speaker map
rebuilds the index.

## Goal suggestions block (v0.6.0-rc2, Track S, off by default)

`goal_prompt=true` appends `[Goal suggestions (not instructions): ...]` with at most `goal_prompt_max_lines`
(hard cap 3) lines to the context block, read from `goalchainer/latest.json` only. Shown only on real user turns
(never automated turns or the fast path), only for a run <= `goal_prompt_max_age_s` old with `status` ok and canary
ok, only message actions (never SelfTask / LookUp), and only proposals addressed to the current speaker (rc4
resolution through `speaker_map`; unknown speaker = nothing). Lines are worded to that speaker: "you" = the speaker,
never the assistant (the header says so); the speaker's name and aliases become you/your, lead-ins are
"Open question for you:", "Still open for you:", "Status for you:", "Pending for you:". Needs `goalchainer` (and so
`pc_shadow`) on to have anything to show. Any error = no block.

## Enabling: the flags file

`<state_dir>/_wmtm_flags.json` (the bot's memory dir, the same `state_dir` given to `WMTMConfig`). It is re-read
on every cycle, so features switch on/off without restarting the host. Missing or invalid file = everything off.
Environment variables override the file (development/tests). Full list: `wmtm/runtime_config.py` (`SPEC`).

```json
{
  "pc_shadow": true,
  "semparse_feed": true,
  "parse_cap_per_hour": 20,
  "swipl_bin": "/path/to/swipl/bin/dir",
  "llm_env_file": "/path/to/bot.env"
}
```

| key | env | default | meaning |
|---|---|---|---|
| `pc_shadow` | `WMTM_PC_SHADOW` | false | run the PeTTaChainer shadow |
| `semparse_feed` | `WMTM_SEMPARSE_FEED` | false | queue + parse top-K items |
| `parse_cap_per_hour` | `WMTM_SEMPARSE_PER_HOUR` | 20 | parse attempts per rolling hour |
| `semparse_preamble` | `WMTM_SEMPARSE_PREAMBLE` | true | v0.5: prepend `wmtm/semparse_preamble.py` to the (pinned, unedited) prompt |
| `parse_max_chars` / `parse_max_attempts` | `WMTM_SEMPARSE_MAX_CHARS` / `..._MAX_ATTEMPTS` | 1500 / 2 | skip longer items; retries on gateway errors |
| `shadow_k` / `shadow_max_goals` | `WMTM_PC_SHADOW_K` / `..._MAX_GOALS` | 200 / 60 | items per snapshot; chain goals per run |
| `shadow_timeout_s` / `shadow_budget_s` / `shadow_steps` | `WMTM_PC_SHADOW_TIMEOUT` / `_BUDGET` / `_STEPS` | 2 / 20 / 30 | per-query SIGKILL timeout; query budget per run; chainer steps |
| `shadow_min_interval_s` | `WMTM_PC_SHADOW_MIN_INTERVAL` | 300 | at most one shadow launch per N s (stamp `pc_shadow/last_launch`); 0 = no limit |
| `hooks_on_automated` | `WMTM_HOOKS_ON_AUTOMATED` | true | also run the hooks on automated (fast-path) turns |
| `shadow_full_kb` | `WMTM_PC_SHADOW_FULL_KB` | false | load all cached atoms, not just binary facts |
| `shadow_goal_rank` | `WMTM_PC_SHADOW_GOAL_RANK` | true | rc2: ranked goal pool (false = rc1 2-step goals) |
| `shadow_max_hops` / `shadow_min_hops` | `WMTM_PC_SHADOW_MAX_HOPS` / `..._MIN_HOPS` | 3 / 1 | rc2: longest chain in the pool; only ask goals needing >= N derivation steps |
| `shadow_goal_weights` | `WMTM_PC_SHADOW_GOAL_WEIGHTS` | `2,1,1,0.5` | rc2: `w_req,w_depth,w_info,w_sti` |
| `semparse_context` | `WMTM_SEMPARSE_CONTEXT` | false | rc2: CONTEXT coreference parsing into `<semparse_dir>/ctx1` (more LLM calls; see below) |
| `context_max_notes` / `context_max_atoms` / `context_max_chars` / `context_passage_chars` | `WMTM_CONTEXT_*` | 3 / 40 / 4000 / 600 | rc2: context selection and passage size |
| `shadow_skolem_goals` | `WMTM_PC_SHADOW_SKOLEM_GOALS` | false | also ask goals about parser-invented `sk_*` placeholder entities (their facts are always kept) |
| `runtime_dir` | `WMTM_RUNTIME_DIR` | `<state_dir>/_wmtm_shadow` | worker data (`pc_shadow/`, `semparse_cache/`) |
| `petta_dir` | `WMTM_PC_PETTA` | `<vendor>/petta-v1.0.6` | PeTTa checkout (has `python/`) |
| `pettachainer_dir` | `WMTM_PC_VENDOR` | `<vendor>/pettachainer-36b3fe6-dedup` | dir containing `pettachainer/` |
| `semparse_prompt` | `SEMPARSE_PROMPT` | `<vendor>/semparse-hitl-3ec15bd1/prompt.txt` | must match `semparse_prompt_sha256` |
| `swipl_bin` | `WMTM_SWIPL_BIN` | (PATH) | prepended to the workers' PATH |
| `llm_env_file` | `WMTM_LLM_ENV_FILE` | (none) | env file with `BASE_URL`, `LLM_MODEL`, `AI_API_KEY`; read by the parse worker, never copied |
| `worker_mem_mb` | `WMTM_WORKER_MEM_MB` | 3072 | RLIMIT_AS for each worker (and its PeTTa child) |
| `worker_nice` | `WMTM_WORKER_NICE` | 19 | plus `ionice -c 3` when available |
| `worker_sched_idle` | `WMTM_WORKER_SCHED_IDLE` | true | SCHED_IDLE for workers and their children: launched via `chrt -i 0` when available and set again by the worker itself on every thread at startup |
| `worker_prio_refresh_s` | `WMTM_WORKER_PRIO_REFRESH` | 1 (rc3; was 5) | the worker re-asserts nice + SCHED_IDLE on itself and its children every N s (scheduler daemons such as system76-scheduler reset them, e.g. to nice 12 / SCHED_OTHER); 0 = startup only |
| `cleanup_protect_recent` | `WMTM_CLEANUP_PROTECT_RECENT` | true | rc3: stale cleanup (user path and fast path) spares items recalled for / matching a real request within `cleanup_grace_turns` cycles or `cleanup_grace_s` s (operational noise is still evicted); false = rc2 |
| `cleanup_grace_turns` / `cleanup_grace_s` | `WMTM_CLEANUP_GRACE_TURNS` / `..._S` | 10 / 1800 | rc3: grace window (either one keeps an item) |
| `context_rank` | `WMTM_CONTEXT_RANK` | true | rc3: block ranked by request relevance + STI, longer request-focused item text (see "Context block"); false = rc2 block (top 15 by attention, 200 chars) |
| `context_rank_weights` | `WMTM_CONTEXT_RANK_WEIGHTS` | `0.7,0.3` | rc3: `w_rel,w_sti` (both normalised to 0-1) |
| `context_item_chars` / `context_total_chars` / `context_max_items` | `WMTM_CONTEXT_ITEM_CHARS` / `..._TOTAL_CHARS` / `..._MAX_ITEMS` | 600 / 6000 / 15 | rc3: per-item cap, item-text budget of the whole block (shared equally, floor 250), item count |
| `context_min_request_items` | `WMTM_CONTEXT_MIN_REQUEST_ITEMS` | 5 | rc3: the N best-matching items are always shown first |
| `context_min_score` | `WMTM_CONTEXT_MIN_SCORE` | 0.2 | rc3: once a request is known, other items scoring below this are not shown (their budget goes to the rest) |
| `request_item` / `request_item_chars` | `WMTM_REQUEST_ITEM` / `..._CHARS` | true / 600 | rc3: store the current request as one `source_type=user` item (never shown, never written back; replaced by the next request) |
| `speaker_link` | `WMTM_SPEAKER_LINK` | false | rc4: speaker-linked parsing into `<semparse_dir>/spk1` (see "Speaker linking") |
| `speaker_map` / `speaker_self` | `WMTM_SPEAKER_MAP` (JSON) / `WMTM_SPEAKER_SELF` | `{}` / `""` | rc4: Telegram user id or username -> canonical name; the bot's own name |
| `goalchainer` | `WMTM_GOALCHAINER` | false | v0.6: goal engine in the shadow worker, log only (see "Goal engine") |
| `goal_requests_dir` | `WMTM_GOAL_REQUESTS_DIR` | `""` (no history) | v0.6: channel's completed request files for reply detection (read-only; relative = against `state_dir`) |
| `goal_requests_days` / `goal_requests_max` | `WMTM_GOAL_REQUESTS_DAYS` / `..._MAX` | 14 / 500 | v0.6: request-history window and file cap |
| `goal_budget_s` | `WMTM_GOAL_BUDGET_S` | 90 | v0.6: wall-clock cap per goal run (v0.7: 10 -> 90 for v2) |
| `goal_engine` | `WMTM_GOAL_ENGINE` | `v2` | v0.7: `v2` (GoalChainer v2 core, separate process) or `native` (v0.6 core; rollback) |
| `goal_v2_python` / `goal_v2_release` | `WMTM_GOAL_V2_PYTHON` / `..._RELEASE` | `""` / `""` | v0.7: v2 environment interpreter (absolute, deploy-time); release tag recorded per run |
| `goal_v2_timeout_s` / `goal_v2_mem_mb` / `goal_v2_inferences` | `WMTM_GOAL_V2_TIMEOUT_S` / `..._MEM_MB` / `..._INFERENCES` | 60 / 1536 / 5e7 | v0.7: runner hard kill, address-space cap, v2 inference budget per request |
| `goal_weights` / `goal_targets` / `goal_scale` / `goal_age_cap_d` | `WMTM_GOAL_*` | `1,1` / `0.8,0.8` / 1 / 7 | v0.6: need weights and targets (uncertainty, competence); load at level 0.5; age cap (days) |
| `goal_max_proposals` / `goal_min_score` | `WMTM_GOAL_MAX_PROPOSALS` / `..._MIN_SCORE` | 5 / 0.05 | v0.6: proposals logged per run; score floor |
| `goal_repeat_s` / `goal_reask_s` / `goal_remind_after_s` | `WMTM_GOAL_REPEAT_S` / `..._REASK_S` / `..._REMIND_AFTER_S` | 21600 / 259200 / 86400 | v0.6: same proposal not re-logged; same person+topic not re-proposed; remind only after no reply |
| `goal_prompt` | `WMTM_GOAL_PROMPT` | false | rc2: goal suggestions block on real user turns (see "Goal suggestions block") |
| `goal_prompt_max_age_s` / `goal_prompt_max_lines` | `WMTM_GOAL_PROMPT_MAX_AGE_S` / `..._MAX_LINES` | 900 / 3 | rc2: freshness of `latest.json`; lines (hard cap 3) |
| `goalchainer_src` | `WMTM_GOALCHAINER_SRC` | `""` | v0.6: OmegaClaw-GoalChainer `src/` for its deontic resolver (else a local identical one) |
| `jsonl_max_bytes` / `cache_max_bytes` | `WMTM_JSONL_MAX_BYTES` / `WMTM_SEMPARSE_CACHE_MAX_BYTES` | 10 MB / 20 MB | logs rotate to `.1`; the parse cache is compacted (newest entries kept) |

Relative paths: vendor paths resolve against `<vendor>` = the directory holding the package's distribution dir
(`<bot>/vendor/` for `<bot>/vendor/wmtm-<tag>/wmtm`); data dirs resolve against `state_dir`. Put machine-specific
paths (swipl, the env file) only in the deployed flags file.

## Runtime layout (vendored deployment)

```
<bot>/vendor/wmtm-v0.7.0-rc1/          git archive of this repo (wmtm/ incl. wmtm/workers/), VERSION, MANIFEST.sha256
<bot>/vendor/petta-v1.0.6/             scripts/vendor_runtime.sh
<bot>/vendor/pettachainer-36b3fe6-dedup/
<bot>/vendor/semparse-hitl-3ec15bd1/   local only, self-ignoring (.gitignore '*'); upstream has no licence
<bot>/memory/_wmtm_flags.json          flags (deploy-time, machine-specific)
<runtimes>/goalchainer-v2-<tag>/       v0.7: GoalChainer v2 environment, OUTSIDE the bot tree (docs/GOALS_V2.md)
<bot>/memory/_wmtm_shadow/{pc_shadow,semparse_cache,goalchainer}/   worker data (real memory text: stays in memory/)
```

Workers start as `python -m wmtm.workers.pc_shadow` / `python -m wmtm.workers.semparse_feed` from the
distribution dir with `PYTHONPATH` set to it, so nothing depends on a development checkout. One worker of each kind
at a time (pidfile); a worker older than 15 min (shadow) / 3 h (parse) is presumed hung and killed by the next launch.

The parse worker refuses to spend anything unless the prompt matches its pinned sha256 and a no-LLM load canary
passes through PeTTaChainer.

## Monitoring

- Both workers record their actual CPU priority: `prio` (`nice`, `policy` after startup) and `prio_end`
  (`end` = what it was at the end of the run, `resets` = how often it had drifted and was re-asserted, `checks`).
- `pc_shadow/shadow.jsonl`: `status` (`ok`/`canary_fail`/`warm_fail`), `source` (`cycle`/`automated`), `canary.ok`, `neg.ok`, `goals_n`,
  `pc_proved`, `timeouts`, `skipped_budget`, `semparse_items`, `unparsed_items`, `facts`, `gate`, `total_s`
  (v0.4: the Python comparison fields are gone). Per query: `goal`, `ok`, `stv`, `proof`, `s`, `timeout`.
- `pc_shadow/admit.json`: the latest run's admissible results (`status`, `canary_ok`, `spec_ts`, `results[]` with
  `goal`, `stv`, `proof`, `sources`, `facts`). It is written for failed runs too, with no results.
  `pc_shadow/parse_review.jsonl`: facts the gate acted on.
- `goalchainer/runs.jsonl`: one line per goal run (`status` ok / canary_fail / shadow_canary_fail / budget_exceeded /
  error / hook_error, v0.7: v2_timeout / v2_crash / v2_error / v2_bad_output / v2_unconfigured / v2_review_error;
  `engine`, `canary.ok`, `logged`, `requests` stats, `s`; v0.7 `v2`: `status`, `s`, `runner_s`, `maxrss_mb`,
  `versions`, `release`, `decisions` (disposition counts), `reviews`, `display_decisions`); `goalchainer/proposals.jsonl`: logged proposals;
  `goalchainer/latest.json` (rc2): the last run's time, status, canary and proposals (what the suggestions block reads).
  `goalchainer/display.jsonl` (rc3): display-only suggestions of automated runs (review log, deduped 6 h);
  `goalchainer/asked.jsonl` (rc3): suggestion lines actually shown on user turns (empty/absent with `goal_prompt` off).
- `semparse_cache/parse_log.jsonl`: one line per parse attempt (status, secs, tokens); `worker_runs.jsonl`: one
  line per worker run (status, load canary, model, counts); `rejects.jsonl`: rejected atoms with reasons.
