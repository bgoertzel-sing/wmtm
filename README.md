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
metadata). v0.6.0-rc1 adds the GoalChainer phase-1 goal engine (`goalchainer`, default off): needs, candidate
actions and a legitimacy veto computed in the shadow worker; proposals are only logged to
`<runtime_dir>/goalchainer/proposals.jsonl`, never shown or acted on; reply detection reads the channel's completed
request files (`goal_requests_dir`). See `docs/RELEASES.md`. v0.7.0-rc1 moves the goal engine's core (need
regulation, deontic legitimacy, ranking) to MesTTo's GoalChainer v2, run as a separate process from its own,
separately installed environment (GPL-3.0 code is never vendored or imported); `goal_engine: native` rolls back to
the v0.6 core. See `docs/GOALS_V2.md`. v0.7.0-rc2 (Track V) fixes the WMTM goal layers: closure from older and
sender-less replies and from later journal notes, a 7-day item age cap, (person, topic cluster) dedupe, alias /
bundle / fragment text fixes and a live-flag contradiction check (`docs/RUNTIME.md`).

## Runtime flags reference

Every flag the code reads is defined in `wmtm/runtime_config.SPEC` (107 keys, listed below in SPEC order).
`runtime_config.resolve()` is the only reader of the flags file (via `read_flags_file()`), and it is
re-run every cycle, so changes take effect without a restart.

Precedence (later wins): SPEC default < `<state_dir>/_wmtm_flags.json` < environment variable (set and
non-empty). A missing, unreadable or non-object flags file counts as absent. Keys starting with `_`
(e.g. `_changed`) are ignored; any other key not in SPEC is reported in `cfg["_source"]["unknown_keys"]`
and otherwise ignored. A value that cannot be converted to the flag's type is skipped and reported in
`cfg["_source"]["invalid"]` (by key for a bad file value, by env var name for a bad env value). The value from the
previous layer stays: a bad file value keeps the default, and a bad env value keeps the file value if there is a valid one, otherwise the default. `reasoner` values other than `pettachainer`/`off`
are invalid and become `off`. Data-dir defaults: `runtime_dir` = `<state_dir>/_wmtm_shadow`,
`shadow_dir` = `<runtime_dir>/pc_shadow`, `semparse_dir` = `<runtime_dir>/semparse_cache`;
`python` defaults to the running interpreter.

Not flags: `goal_requests` and `goal_notes` are filled in internally by the goal engine
(`wmtm/goals/engine.py`); `state_dir` and `_source` are added by `resolve()`.
"Read at" shows up to two read sites.

| key | env var | type | default | notes (from `runtime_config.SPEC`) | read at |
|---|---|---|---|---|---|
| `pc_shadow` | `WMTM_PC_SHADOW` | bool | `false` | When true, every cycle launches the detached PeTTaChainer shadow worker (`pc_shadow.maybe_launch`), and so does every automated turn if `hooks_on_automated` is set. `reasoner = pettachainer` forces the launch even when this is false. | `wmtm/orchestrator.py:390` `wmtm/context.py:473` |
| `semparse_feed` | `WMTM_SEMPARSE_FEED` | bool | `false` | When true, every cycle queues the top `shadow_k` active items for semantic parsing and may start the parse worker (`parse_cache.maybe_feed`). | `wmtm/orchestrator.py:396` `wmtm/parse_cache.py:332` |
| `reasoner` | `WMTM_REASONER` | str | `''` | pettachainer\|off; "" = API default (pettachainer); anything else = off | `wmtm/runtime_config.py:269` `wmtm/runtime_config.py:270` |
| `reasoner_max_age_s` | `WMTM_REASONER_MAX_AGE` | float | `900.0` | A shadow-worker result older than this many seconds is skipped as `stale` and none of its conclusions are admitted. 0 or empty falls back to 900. | `wmtm/pc_admit.py:137` |
| `reasoner_max_admit` | `WMTM_REASONER_MAX_ADMIT` | int | `5` | The most PeTTaChainer conclusions admitted from one worker result, after the per-fact cap. 0 falls back to 5. | `wmtm/pc_admit.py:182` |
| `reasoner_min_strength` | `WMTM_REASONER_MIN_STRENGTH` | float | `0.5` | Track O: derived strength is a probability; below reasoner_min_strength it means "probably not" | `wmtm/pc_admit.py:43` |
| `reasoner_negation` | `WMTM_REASONER_NEGATION` | str | `'skip'` | skip \| unlikely ("unlikely: &lt;text&gt;") | `wmtm/pc_admit.py:51` |
| `semparse_context` | `WMTM_SEMPARSE_CONTEXT` | bool | `false` | Track O: CONTEXT coreference (off by default; results go to &lt;semparse_dir&gt;/ctx1, the old cache is kept) | `wmtm/parse_cache.py:339` `wmtm/parse_cache.py:492` |
| `context_max_notes` | `WMTM_CONTEXT_MAX_NOTES` | int | `3` | Context parse (`semparse_context`): the most earlier notes passed as context for one item (`select_context`). | `wmtm/parse_cache.py:414` `wmtm/parse_cache.py:508` |
| `context_max_atoms` | `WMTM_CONTEXT_MAX_ATOMS` | int | `40` | Context parse: the most atoms from earlier notes passed as context. | `wmtm/parse_cache.py:415` `wmtm/parse_cache.py:509` |
| `context_max_chars` | `WMTM_CONTEXT_MAX_CHARS` | int | `4000` | Context parse: the most characters of context atoms passed. | `wmtm/parse_cache.py:416` `wmtm/parse_cache.py:510` |
| `context_passage_chars` | `WMTM_CONTEXT_PASSAGE_CHARS` | int | `600` | Context parse: the item text is split into passages of at most this many characters, and each passage is parsed separately. | `wmtm/parse_cache.py:422` `wmtm/parse_cache.py:512` |
| `speaker_link` | `WMTM_SPEAKER_LINK` | bool | `false` | Track Q: speaker linking. When true, new parses resolve who is speaking (via `speaker_map` / `speaker_self`) and go to &lt;semparse_dir&gt;/spk1; old caches are kept, no backfill. Can be set in the flags file or with `WMTM_SPEAKER_LINK` (normal precedence). | `wmtm/parse_cache.py:335` `wmtm/workers/semparse_feed.py:100` |
| `speaker_map` | `WMTM_SPEAKER_MAP` | dict | `{}` | Object mapping a Telegram user id or username to a canonical lower-case name. Used by speaker linking (`speaker_link`) and by the goal engine (who is a person, who a request came from). If it changes, the request index is rebuilt. | `wmtm/goals/requests.py:66` `wmtm/goals/requests.py:78` |
| `speaker_self` | `WMTM_SPEAKER_SELF` | str | `''` | The bot's own canonical name. With speaker linking, I/me/my in notes become this name, and the goal engine uses it as its own name. | `wmtm/goals/requests.py:66` `wmtm/goals/requests.py:78` |
| `goalchainer` | `WMTM_GOALCHAINER` | bool | `false` | Track R: GoalChainer phase 1 (log only; wmtm/goals).  Runs inside the PeTTaChainer shadow worker, after its canary; writes &lt;runtime_dir&gt;/goalchainer/proposals.jsonl only.  Nothing reaches the prompt, no action is taken. | `wmtm/workers/pc_shadow.py:185` `wmtm/goals/engine.py:437` |
| `goalchainer_src` | `WMTM_GOALCHAINER_SRC` | str | `''` | Directory appended to `sys.path` before importing `goal_chainer.deontic` for norm resolution. Empty: nothing is added, but the import is still attempted from the existing `sys.path`. Only if the import fails is the built-in local resolver used (result cached per value). Relative path resolves against the vendor root. | `wmtm/goals/legitimacy.py:41` |
| `goal_weights` | `WMTM_GOAL_WEIGHTS` | str | `'1,1'` | w_unc, w_comp | `wmtm/goals/engine.py:49` |
| `goal_targets` | `WMTM_GOAL_TARGETS` | str | `'0.8,0.8'` | target level per need (1 = nothing open) | `wmtm/goals/engine.py:50` |
| `goal_scale` | `WMTM_GOAL_SCALE` | float | `1.0` | load at which level = 0.5 | `wmtm/goals/engine.py:51` |
| `goal_age_cap_d` | `WMTM_GOAL_AGE_CAP_D` | float | `7.0` | Goal engine: the age in days at which the age weight of a need signal or candidate action stops growing. | `wmtm/goals/engine.py:52` |
| `goal_max_proposals` | `WMTM_GOAL_MAX_PROPOSALS` | int | `5` | per run | `wmtm/goals/engine.py:52` |
| `goal_min_score` | `WMTM_GOAL_MIN_SCORE` | float | `0.05` | Goal engine: a candidate scoring below this gets status `weak` instead of `proposed`. | `wmtm/goals/engine.py:53` |
| `goal_repeat_s` | `WMTM_GOAL_REPEAT_S` | float | `21600.0` | same proposal not re-logged within 6 h | `wmtm/goals/engine.py:53` |
| `goal_remind_after_s` | `WMTM_GOAL_REMIND_AFTER_S` | float | `86400.0` | RemindPending only after 1 d w/o reply | `wmtm/goals/engine.py:56` |
| `goal_reask_s` | `WMTM_GOAL_REASK_S` | float | `259200.0` | same person+topic not re-proposed within 3 d | `wmtm/goals/engine.py:57` `wmtm/goal_prompt.py:218` |
| `goal_budget_s` | `WMTM_GOAL_BUDGET_S` | float | `90.0` | wall-clock cap per goal run (SIGALRM; v0.7: 10 -&gt; 90 for v2) | `wmtm/goals/engine.py:447` |
| `goal_engine` | `WMTM_GOAL_ENGINE` | str | `'v2'` | v0.7: GoalChainer v2 core (wmtm/goals/v2.py), run as a separate process in its own environment (deploy-time path in the flags file; GPL-3.0 code is never imported into WMTM's process).  goal_engine "native" = the v0.6 scoring core (rollback switch, kept for one release).  Without goal_v2_python a v2 run logs v2_unconfigured. v2 \| native | `wmtm/goals/engine.py:30` |
| `goal_v2_python` | `WMTM_GOAL_V2_PYTHON` | str | `''` | Absolute path of the interpreter (`<v2 env>/bin/python`) that runs the GoalChainer v2 runner as a separate process. Empty or missing file: v2 runs fail with `v2_unconfigured`. Usually set in the deploy-time flags file; the env var works too. | `wmtm/goals/v2.py:227` |
| `goal_v2_runner` | `WMTM_GOAL_V2_RUNNER` | str | `''` | dev/test override of wmtm/goals/v2_runner.py | `wmtm/goals/v2.py:228` |
| `goal_v2_release` | `WMTM_GOAL_V2_RELEASE` | str | `''` | release tag of the runtime (recorded per run) | `wmtm/goals/engine.py:36` |
| `goal_v2_timeout_s` | `WMTM_GOAL_V2_TIMEOUT_S` | float | `60.0` | hard kill of the runner process group | `wmtm/goals/v2.py:231` |
| `goal_v2_mem_mb` | `WMTM_GOAL_V2_MEM_MB` | int | `1536` | runner address-space cap | `wmtm/goals/v2.py:239` |
| `goal_v2_inferences` | `WMTM_GOAL_V2_INFERENCES` | int | `50000000` | v2 inference budget per request | `wmtm/goals/v2.py:237` |
| `goal_prompt` | `WMTM_GOAL_PROMPT` | bool | `false` | Track S (phase b): "Goal suggestions (not instructions)" block on the user path, from goalchainer/latest.json. | `wmtm/goal_prompt.py:159` `wmtm/goal_prompt.py:232` |
| `goal_prompt_max_age_s` | `WMTM_GOAL_PROMPT_MAX_AGE_S` | float | `900.0` | only runs &lt;= 15 min old | `wmtm/goal_prompt.py:176` |
| `goal_prompt_max_lines` | `WMTM_GOAL_PROMPT_MAX_LINES` | int | `3` | hard cap 3 in wmtm/goal_prompt.py | `wmtm/goal_prompt.py:238` |
| `goal_requests_dir` | `WMTM_GOAL_REQUESTS_DIR` | str | `''` | v0.6: request history for the "addressee replied" check: the channel's completed request files (read-only; deploy-time path in the flags file, relative = against state_dir; "" = no history).  Indexed in &lt;runtime_dir&gt;/goalchainer/requests_index.json (digests only, no raw text); see wmtm/goals/requests.py. Relative path resolves against the state_dir. | `wmtm/goals/requests.py:105` `wmtm/goals/engine.py:586` |
| `goal_requests_days` | `WMTM_GOAL_REQUESTS_DAYS` | float | `14.0` | Goal engine: the minimum look-back in days for request/reply files. It widens to the age of the oldest open item + 1 day, capped at `goal_history_max_days`. | `wmtm/goals/requests.py:92` `wmtm/goals/requests.py:113` |
| `goal_requests_max` | `WMTM_GOAL_REQUESTS_MAX` | int | `500` | Goal engine: the most request files read (newest first). | `wmtm/goals/requests.py:115` |
| `goal_history_max_days` | `WMTM_GOAL_HISTORY_MAX_DAYS` | float | `45.0` | v0.7.0rc2 (Track V): closure, age cap and paraphrase dedupe (see docs/RUNTIME.md "Goal engine"). The request window grows with the age of the oldest active item (goal_requests_days is the minimum), up to goal_history_max_days; the journal closure index (digests only) covers the same span. | `wmtm/goals/requests.py:93` `wmtm/goals/requests.py:114` |
| `goal_close_unattributed` | `WMTM_GOAL_CLOSE_UNATTRIBUTED` | bool | `true` | sender-less group replies may close | `wmtm/goals/requests.py:159` `wmtm/goals/engine.py:63` |
| `goal_journal_closure` | `WMTM_GOAL_JOURNAL_CLOSURE` | bool | `true` | later journal notes may close items | `wmtm/goals/engine.py:590` `wmtm/goals/notes.py:81` |
| `goal_journal_path` | `WMTM_GOAL_JOURNAL_PATH` | str | `''` | Journal file the goal engine reads notes from (for journal closure). "" = &lt;state_dir&gt;/_journal/journal.metta. Relative path resolves against the state_dir. | `wmtm/goals/notes.py:36` |
| `goal_max_item_age_days` | `WMTM_GOAL_MAX_ITEM_AGE_DAYS` | float | `7.0` | no message about older items | `wmtm/goals/engine.py:60` |
| `goal_topic_overlap` | `WMTM_GOAL_TOPIC_OVERLAP` | float | `0.4` | topic-cluster term overlap threshold | `wmtm/goals/engine.py:59` `wmtm/goals/engine.py:470` |
| `reasoner_writeback` | `WMTM_REASONER_WRITEBACK` | bool | `false` | v0.4: write PeTTaChainer-admitted conclusions back to the long-term journal (derived_promotion)?  Off = they live in working memory only.  Python-PLN / tool-derived items are not affected. | `wmtm/orchestrator.py:340` |
| `reasoner_admit_on_automated` | `WMTM_REASONER_ADMIT_ON_AUTOMATED` | bool | `true` | v0.4 rc2: also admit PeTTaChainer conclusions on automated (fast-path) turns | `wmtm/context.py:514` |
| `admit_log_max_bytes` | `WMTM_ADMIT_LOG_MAX_BYTES` | int | `1000000` | &lt;shadow_dir&gt;/admit_log.jsonl (+ .1) | `wmtm/pc_admit.py:243` |
| `gate_on` | `WMTM_GATE` | bool | `true` | Track J parse-quality gate (wmtm/parse_gate.py); applies to PeTTaChainer conclusions only | `wmtm/parse_gate.py:62` |
| `gate_min_conf` | `WMTM_GATE_MIN_CONF` | float | `0.3` | Parse gate (when `gate_on`): a fact whose parse confidence is below this is rejected. | `wmtm/parse_gate.py:62` |
| `gate_broad_terms` | `WMTM_GATE_BROAD_TERMS` | str | `'thing,things,entity,entities,object,objects,something,anything,everything,stuff,item,items,concept,trivial,important,relevant,useful,ok,fine,good,bad'` | Parse gate: comma-separated broad or evaluative categories. An Inheritance/Member fact into one of these gets `gate_broad_action`. | `wmtm/parse_gate.py:63` |
| `gate_placeholder_terms` | `WMTM_GATE_PLACEHOLDERS` | str | `'it,this,that,they,them,thing,something,someone,somebody,x,y,z'` | Parse gate: comma-separated pronoun-like words. A fact whose subject is one of these, or an `sk_*` placeholder, is rejected. | `wmtm/parse_gate.py:63` |
| `gate_hedged_quantifiers` | `WMTM_GATE_HEDGED` | str | `'mostly,most,some,often,usually,sometimes,many,few,several,rarely,partly,generally,typically,maybe,probably'` | Parse gate: comma-separated quantifiers that are not universal (e.g. mostly, some). A fact carrying one gets `gate_hedged_action`. | `wmtm/parse_gate.py:64` |
| `gate_negative_quantifiers` | `WMTM_GATE_NEGATIVE` | str | `'no,none,nothing,never,not,nobody,neither'` | Parse gate: comma-separated negative quantifiers (e.g. no, none). A fact carrying one is rejected. | `wmtm/parse_gate.py:64` |
| `gate_broad_action` | `WMTM_GATE_BROAD_ACTION` | str | `'reject'` | reject \| discount \| keep | `wmtm/parse_gate.py:65` |
| `gate_hedged_action` | `WMTM_GATE_HEDGED_ACTION` | str | `'reject'` | reject \| discount \| keep | `wmtm/parse_gate.py:65` |
| `gate_discount` | `WMTM_GATE_DISCOUNT` | float | `0.5` | strength factor for discount | `wmtm/parse_gate.py:67` |
| `gate_identifier_action` | `WMTM_GATE_IDENTIFIER_ACTION` | str | `'reject'` | reject \| discount \| keep (Track M) | `wmtm/parse_gate.py:66` |
| `gate_identifier_bad_categories` | `WMTM_GATE_IDENTIFIER_BAD` | str | `'branch,dir,directory,folder,path,file,repo,repository,worktree,tree,remote,fork'` | an id subject may not be typed as these (also *_&lt;term&gt;) | `wmtm/parse_gate.py:66` |
| `gate_max_per_fact` | `WMTM_GATE_MAX_PER_FACT` | int | `3` | admitted conclusions per KB fact per cycle; 0 = no cap | `wmtm/parse_gate.py:68` |
| `gate_review_min` | `WMTM_GATE_REVIEW_MIN` | int | `3` | log facts behind &gt;= N proved conclusions | `wmtm/parse_gate.py:68` |
| `parse_cap_per_hour` | `WMTM_SEMPARSE_PER_HOUR` | int | `20` | The most parse attempts in any rolling hour (cost cap). Negative values are clamped to 0, which stops parsing. | `wmtm/runtime_config.py:268` `wmtm/parse_cache.py:49` |
| `semparse_preamble` | `WMTM_SEMPARSE_PREAMBLE` | bool | `true` | Track M: prepend semparse_preamble.PREAMBLE to the (pinned, unedited) prompt | `wmtm/workers/semparse_feed.py:84` `wmtm/workers/semparse_feed.py:95` |
| `parse_max_chars` | `WMTM_SEMPARSE_MAX_CHARS` | int | `1500` | Items longer than this are skipped, not truncated, by the parse queue. | `wmtm/parse_cache.py:50` |
| `parse_max_attempts` | `WMTM_SEMPARSE_MAX_ATTEMPTS` | int | `2` | Attempts per item before it is cached as failed. Only `llm_error` is retried. | `wmtm/parse_cache.py:51` |
| `shadow_k` | `WMTM_PC_SHADOW_K` | int | `200` | How many top active-set items go to the shadow worker and to the parse feed. | `wmtm/parse_cache.py:341` `wmtm/parse_cache.py:371` |
| `shadow_max_goals` | `WMTM_PC_SHADOW_MAX_GOALS` | int | `60` | The most goals the shadow worker queries in one run. | `wmtm/pc_shadow.py:249` |
| `shadow_full_kb` | `WMTM_PC_SHADOW_FULL_KB` | bool | `false` | True: each item's whole parsed KB goes into PeTTa. False: only the binary facts the goals are built from, which is much faster. | `wmtm/pc_shadow.py:273` |
| `shadow_skolem_goals` | `WMTM_PC_SHADOW_SKOLEM_GOALS` | bool | `false` | True keeps goals about parser placeholder entities (`sk_*`). By default they are dropped. | `wmtm/pc_shadow.py:249` |
| `shadow_goal_rank` | `WMTM_PC_SHADOW_GOAL_RANK` | bool | `true` | Track N: Design A ranked goal pool (off = Track M 2-step goals) | `wmtm/pc_shadow.py:282` |
| `shadow_max_hops` | `WMTM_PC_SHADOW_MAX_HOPS` | int | `3` | Track N: longest chain in the pool (derivation steps) | `wmtm/pc_shadow.py:291` |
| `shadow_min_hops` | `WMTM_PC_SHADOW_MIN_HOPS` | int | `1` | Track N: only ask goals needing &gt;= N steps | `wmtm/pc_shadow.py:292` |
| `shadow_goal_weights` | `WMTM_PC_SHADOW_GOAL_WEIGHTS` | str | `'2,1,1,0.5'` | Track N: w_req,w_depth,w_info,w_sti | `wmtm/pc_shadow.py:293` |
| `shadow_timeout_s` | `WMTM_PC_SHADOW_TIMEOUT` | float | `2.0` | Shadow worker: timeout in seconds for each PeTTa query, including the canary and negative-control queries. The worker's `--timeout` option overrides it. | `wmtm/workers/pc_shadow.py:34` |
| `shadow_budget_s` | `WMTM_PC_SHADOW_BUDGET` | float | `20.0` | Shadow worker: total seconds for all goal queries in one run. Goals still waiting when it runs out are skipped. | `wmtm/workers/pc_shadow.py:35` |
| `shadow_steps` | `WMTM_PC_SHADOW_STEPS` | int | `30` | Shadow worker: PeTTa step limit for each query. | `wmtm/workers/pc_shadow.py:33` |
| `shadow_min_interval_s` | `WMTM_PC_SHADOW_MIN_INTERVAL` | float | `300.0` | The fewest seconds between two shadow-worker launches. 0 means no limit. | `wmtm/pc_shadow.py:341` |
| `cleanup_protect_recent` | `WMTM_CLEANUP_PROTECT_RECENT` | bool | `true` | Track P: recall/context plumbing (wmtm/context.py).  Each switch off = the rc2 behaviour. stale cleanup spares fresh recalls | `wmtm/context.py:676` |
| `cleanup_grace_turns` | `WMTM_CLEANUP_GRACE_TURNS` | int | `10` | ... recalled/relevant within N cycles | `wmtm/context.py:678` |
| `cleanup_grace_s` | `WMTM_CLEANUP_GRACE_S` | float | `1800.0` | ... or within N seconds | `wmtm/context.py:679` |
| `context_rank` | `WMTM_CONTEXT_RANK` | bool | `true` | block ranked by request relevance + STI | `wmtm/context.py:575` `wmtm/context.py:940` |
| `context_rank_weights` | `WMTM_CONTEXT_RANK_WEIGHTS` | str | `'0.7,0.3'` | w_rel, w_sti (both normalised 0-1) | `wmtm/context.py:699` |
| `context_item_chars` | `WMTM_CONTEXT_ITEM_CHARS` | int | `600` | per item cap (rc2: 200); share = total/items | `wmtm/context.py:904` |
| `context_total_chars` | `WMTM_CONTEXT_TOTAL_CHARS` | int | `6000` | all item texts together (rc2: &lt;= 3000) | `wmtm/context.py:902` |
| `context_max_items` | `WMTM_CONTEXT_MAX_ITEMS` | int | `15` | The most ranked items shown in the context block (at least 1). | `wmtm/context.py:901` |
| `context_min_request_items` | `WMTM_CONTEXT_MIN_REQUEST_ITEMS` | int | `5` | best-matching items always shown | `wmtm/context.py:845` |
| `context_min_score` | `WMTM_CONTEXT_MIN_SCORE` | float | `0.2` | with a known request: hide weaker filler | `wmtm/context.py:850` |
| `request_item` | `WMTM_REQUEST_ITEM` | bool | `true` | admit the request as a source_type=user item | `wmtm/context.py:955` |
| `request_item_chars` | `WMTM_REQUEST_ITEM_CHARS` | int | `600` | When the user message is admitted as a request item, whitespace is collapsed and the text is cut to this many characters (at least 20). | `wmtm/context.py:958` |
| `hooks_on_automated` | `WMTM_HOOKS_ON_AUTOMATED` | bool | `true` | When true, automated (fast-path) turns also run the shadow and parse-feed hooks. `pc_shadow` or `semparse_feed` must still be on. | `wmtm/context.py:473` |
| `runtime_dir` | `WMTM_RUNTIME_DIR` | str | `''` | Root directory for WMTM runtime data (goal engine output, shadow and parse-cache dirs by default). Empty: `<state_dir>/_wmtm_shadow` (`.local-data` in the repo if there is no state_dir). Relative path resolves against the state_dir. | `wmtm/runtime_config.py:263` `wmtm/runtime_config.py:264` |
| `shadow_dir` | `WMTM_PC_SHADOW_DIR` | str | `''` | Directory of the PeTTaChainer shadow worker's files and the admission log (`admit_log.jsonl`). Empty: `<runtime_dir>/pc_shadow`. Relative path resolves against the state_dir. | `wmtm/runtime_config.py:265` `wmtm/pc_admit.py:120` |
| `semparse_dir` | `WMTM_SEMPARSE_DIR` | str | `''` | Directory of the semantic-parse cache, queue and parse log (Track O/Q caches live in its `ctx1` / `spk1` subdirs). Empty: `<runtime_dir>/semparse_cache`. Relative path resolves against the state_dir. | `wmtm/runtime_config.py:266` `wmtm/parse_cache.py:48` |
| `petta_dir` | `WMTM_PC_PETTA` | str | `'petta-v1.0.6'` | PeTTa installation the workers use: its `python/` dir goes on `sys.path` and `PETTA_PATH` is set to it in the worker environment. Relative path resolves against the vendor root. | `wmtm/runtime_config.py:458` `wmtm/runtime_config.py:459` |
| `pettachainer_dir` | `WMTM_PC_VENDOR` | str | `'pettachainer-36b3fe6-dedup'` | PeTTaChainer checkout the parse and shadow workers put on `sys.path` to load the reasoner. Relative path resolves against the vendor root. | `wmtm/workers/semparse_feed.py:31` `wmtm/workers/pc_shadow.py:32` |
| `semparse_prompt` | `SEMPARSE_PROMPT` | str | `'semparse-hitl-3ec15bd1/prompt.txt'` | Prompt file the semantic parser sends to the LLM (its sha256 is checked against `semparse_prompt_sha256`). Relative path resolves against the vendor root. | `wmtm/workers/semparse_feed.py:32` |
| `semparse_prompt_sha256` | `WMTM_SEMPARSE_PROMPT_SHA256` | str | `'2ed18b934e28afac75b1d6c7c47b7b7413ed778c4c2916441274fb42933d9d1e'` | If set, the parse worker refuses to run (status `prompt_mismatch`) when the sha256 of the prompt file differs. Empty means no check. | `wmtm/workers/semparse_feed.py:62` |
| `swipl_bin` | `WMTM_SWIPL_BIN` | str | `''` | Directory prepended to the workers' `PATH` so they find `swipl` (for PeTTa). Empty: `PATH` unchanged. Relative path resolves against the vendor root. | `wmtm/runtime_config.py:456` `wmtm/runtime_config.py:457` |
| `llm_env_file` | `WMTM_LLM_ENV_FILE` | str | `''` | Env file (`BASE_URL`, `LLM_MODEL`, `AI_API_KEY`) the parse worker's LLM gateway reads; variables already in the process environment take precedence. Empty: only the process environment is used. Relative path resolves against the vendor root. | `wmtm/workers/semparse_feed.py:79` |
| `python` | `WMTM_WORKER_PYTHON` | str | `''` | The interpreter that runs the detached workers. Empty means the running interpreter. | `wmtm/runtime_config.py:267` `wmtm/runtime_config.py:466` |
| `worker_nice` | `WMTM_WORKER_NICE` | int | `19` | The nice level workers start at. It is re-asserted while a worker runs if the level drops below it. | `wmtm/runtime_config.py:369` `wmtm/runtime_config.py:467` |
| `worker_sched_idle` | `WMTM_WORKER_SCHED_IDLE` | bool | `true` | True: workers run under SCHED_IDLE (`chrt -i 0`) and re-assert it while they run. | `wmtm/runtime_config.py:375` `wmtm/runtime_config.py:468` |
| `worker_prio_refresh_s` | `WMTM_WORKER_PRIO_REFRESH` | float | `1.0` | Track P: 1 s (was 5 s; the host scheduler resets it) | `wmtm/runtime_config.py:401` `wmtm/runtime_config.py:408` |
| `worker_mem_mb` | `WMTM_WORKER_MEM_MB` | int | `3072` | Address-space cap (RLIMIT_AS) in MB for worker processes and their children, e.g. PeTTa. 0 means no cap. | `wmtm/workers/semparse_feed.py:33` `wmtm/workers/pc_shadow.py:36` |
| `jsonl_max_bytes` | `WMTM_JSONL_MAX_BYTES` | int | `10000000` | JSONL logs (parse log, `worker_runs.jsonl`, ...) are rotated to `.1` when larger than this. 0 means no rotation. | `wmtm/parse_cache.py:52` `wmtm/workers/semparse_feed.py:47` |
| `cache_max_bytes` | `WMTM_SEMPARSE_CACHE_MAX_BYTES` | int | `20000000` | `cache.jsonl` is compacted when larger than this: the newest entry per hash is kept, then the oldest entries are dropped. 0 means no cap. | `wmtm/parse_cache.py:53` |

### Live flags file audit (2026-10-28)

Compared the deployed `_wmtm_flags.json` (16 keys, sha256 `a684dfc8…3027`, mtime 2026-10-23) with SPEC (107 keys). Only key names are listed; values are not reproduced here.

- **In the live file but not read by code (1):** `_changed` (a free-text change note; `resolve()` only reads SPEC keys, and `_changed` occurs nowhere else in `wmtm/`).
- **In the live file and read (15):** `pc_shadow`, `semparse_feed`, `reasoner`, `reasoner_max_age_s`, `speaker_link`, `speaker_map`, `speaker_self`, `goalchainer`, `goal_engine`, `goal_v2_python`, `goal_v2_release`, `goal_requests_dir`, `parse_cap_per_hour`, `swipl_bin`, `llm_env_file`.
- **Read by code but absent from the live file (92), so they run on the SPEC default unless a `WMTM_*` env var is set:** `reasoner_max_admit`, `reasoner_min_strength`, `reasoner_negation`, `semparse_context`, `context_max_notes`, `context_max_atoms`, `context_max_chars`, `context_passage_chars`, `goalchainer_src`, `goal_weights`, `goal_targets`, `goal_scale`, `goal_age_cap_d`, `goal_max_proposals`, `goal_min_score`, `goal_repeat_s`, `goal_remind_after_s`, `goal_reask_s`, `goal_budget_s`, `goal_v2_runner`, `goal_v2_timeout_s`, `goal_v2_mem_mb`, `goal_v2_inferences`, `goal_prompt`, `goal_prompt_max_age_s`, `goal_prompt_max_lines`, `goal_requests_days`, `goal_requests_max`, `goal_history_max_days`, `goal_close_unattributed`, `goal_journal_closure`, `goal_journal_path`, `goal_max_item_age_days`, `goal_topic_overlap`, `reasoner_writeback`, `reasoner_admit_on_automated`, `admit_log_max_bytes`, `gate_on`, `gate_min_conf`, `gate_broad_terms`, `gate_placeholder_terms`, `gate_hedged_quantifiers`, `gate_negative_quantifiers`, `gate_broad_action`, `gate_hedged_action`, `gate_discount`, `gate_identifier_action`, `gate_identifier_bad_categories`, `gate_max_per_fact`, `gate_review_min`, `semparse_preamble`, `parse_max_chars`, `parse_max_attempts`, `shadow_k`, `shadow_max_goals`, `shadow_full_kb`, `shadow_skolem_goals`, `shadow_goal_rank`, `shadow_max_hops`, `shadow_min_hops`, `shadow_goal_weights`, `shadow_timeout_s`, `shadow_budget_s`, `shadow_steps`, `shadow_min_interval_s`, `cleanup_protect_recent`, `cleanup_grace_turns`, `cleanup_grace_s`, `context_rank`, `context_rank_weights`, `context_item_chars`, `context_total_chars`, `context_max_items`, `context_min_request_items`, `context_min_score`, `request_item`, `request_item_chars`, `hooks_on_automated`, `runtime_dir`, `shadow_dir`, `semparse_dir`, `petta_dir`, `pettachainer_dir`, `semparse_prompt`, `semparse_prompt_sha256`, `python`, `worker_nice`, `worker_sched_idle`, `worker_prio_refresh_s`, `worker_mem_mb`, `jsonl_max_bytes`, `cache_max_bytes`.

To redo the audit against another flags file: `python3 -c "import json,sys,wmtm.runtime_config as rc; l=json.load(open(sys.argv[1])); s=set(rc.SPEC); print('unread', sorted(set(l)-s)); print('absent', sorted(s-set(l)))" path/to/_wmtm_flags.json`

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
