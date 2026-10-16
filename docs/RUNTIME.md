# Background reasoner shadow and semantic-parse feed (v0.3)

Two optional background features run next to the normal WMTM cycle. Both are **off by default** and neither can
change what WMTM admits or shows: they run in detached, niced worker processes, the cycle never waits for them,
and every error is swallowed on the cycle side.

- **PeTTaChainer shadow** (Track G, `pc_shadow`): each cycle the top-K active items are handed to a worker that
  builds a small PLN knowledge base (cached semantic parses where available, else the regex PLN mapping), asks
  PeTTaChainer 2-step chain goals with a hard per-query timeout, compares with what the Python PLN derived from the
  same facts, and appends one JSON line to `pc_shadow/shadow.jsonl`. A Grace canary and a negative control run
  through the same path on every run; if they fail the record is `canary_fail` and no goal result is trusted.
- **Semantic-parse feed** (Track H, `semparse_feed`): each cycle the top-K items are queued by content hash; a
  worker parses them with the semantic-parsing-hitl prompt through the bot's existing OpenAI-compatible gateway,
  load-checks every atom in PeTTaChainer and caches the accepted atoms (`semparse_cache/cache.jsonl`). The same
  content is never parsed twice. At most `parse_cap_per_hour` (default 20) parse attempts run per rolling hour.

Both hooks run on every WMTM cycle *and* (since v0.3.0-rc2) on automated turns: the automated fast path
(`WMTM.context_for` with no real user message) feeds them the top-K items from the state JSON without loading the
engine (`hooks_on_automated`, default true). Steady-state cost on that path is a few ms (flags read, busy/rate-limit
checks; the parse feed skips the enqueue when the top-K contents are unchanged). Shadow launches are rate-limited to
one per `shadow_min_interval_s` (default 300 s) on both paths, so autonomous ticks cannot spawn back-to-back runs.

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
| `parse_max_chars` / `parse_max_attempts` | `WMTM_SEMPARSE_MAX_CHARS` / `..._MAX_ATTEMPTS` | 1500 / 2 | skip longer items; retries on gateway errors |
| `shadow_k` / `shadow_max_goals` | `WMTM_PC_SHADOW_K` / `..._MAX_GOALS` | 200 / 60 | items per snapshot; chain goals per run |
| `shadow_timeout_s` / `shadow_budget_s` / `shadow_steps` | `WMTM_PC_SHADOW_TIMEOUT` / `_BUDGET` / `_STEPS` | 2 / 20 / 30 | per-query SIGKILL timeout; query budget per run; chainer steps |
| `shadow_min_interval_s` | `WMTM_PC_SHADOW_MIN_INTERVAL` | 300 | at most one shadow launch per N s (stamp `pc_shadow/last_launch`); 0 = no limit |
| `hooks_on_automated` | `WMTM_HOOKS_ON_AUTOMATED` | true | also run the hooks on automated (fast-path) turns |
| `shadow_full_kb` | `WMTM_PC_SHADOW_FULL_KB` | false | load all cached atoms, not just binary facts |
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
| `worker_prio_refresh_s` | `WMTM_WORKER_PRIO_REFRESH` | 5 | the worker re-asserts nice + SCHED_IDLE on itself and its children every N s (scheduler daemons such as system76-scheduler reset them, e.g. to nice 12 / SCHED_OTHER); 0 = startup only |
| `jsonl_max_bytes` / `cache_max_bytes` | `WMTM_JSONL_MAX_BYTES` / `WMTM_SEMPARSE_CACHE_MAX_BYTES` | 10 MB / 20 MB | logs rotate to `.1`; the parse cache is compacted (newest entries kept) |

Relative paths: vendor paths resolve against `<vendor>` = the directory holding the package's distribution dir
(`<bot>/vendor/` for `<bot>/vendor/wmtm-<tag>/wmtm`); data dirs resolve against `state_dir`. Put machine-specific
paths (swipl, the env file) only in the deployed flags file.

## Runtime layout (vendored deployment)

```
<bot>/vendor/wmtm-v0.3.0-rc2/          git archive of this repo (wmtm/ incl. wmtm/workers/), VERSION, MANIFEST.sha256
<bot>/vendor/petta-v1.0.6/             scripts/vendor_runtime.sh
<bot>/vendor/pettachainer-36b3fe6-dedup/
<bot>/vendor/semparse-hitl-3ec15bd1/   local only, self-ignoring (.gitignore '*'); upstream has no licence
<bot>/memory/_wmtm_flags.json          flags (deploy-time, machine-specific)
<bot>/memory/_wmtm_shadow/{pc_shadow,semparse_cache}/   worker data (real memory text: stays in memory/)
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
  `pc_proved`, `timeouts`, `skipped_budget`, `agree_both`, `pc_only`, `py_only_asked`, `tv_diff_mean`, `total_s`.
- `semparse_cache/parse_log.jsonl`: one line per parse attempt (status, secs, tokens); `worker_runs.jsonl`: one
  line per worker run (status, load canary, model, counts); `rejects.jsonl`: rejected atoms with reasons.
