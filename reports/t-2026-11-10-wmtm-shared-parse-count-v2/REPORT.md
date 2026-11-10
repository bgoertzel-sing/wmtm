# t-2026-11-10-wmtm-shared-parse-count-v2: fixed parse-call shares, counted across all logs

Supersedes: t-2026-11-10-wmtm-shared-parse-count

## Summary
andy asked for the 20-per-hour parse budget to be real, with fixed shares: live gets 10 calls per rolling hour and all hive tasks together get 10. Each share has to be counted across every log that belongs to it, and measure_parse has to log its calls too. This is done in the new `wmtm/parse_budget.py`. Every gateway call now reserves one row in its share's ledger before anything is sent, and the reservation is atomic (under a file lock). The task share counts a host-wide task ledger plus every registered task log together, so no task counts only its own log. The live share counts live's base, ctx1 and spk1 logs together. Tasks only read live's files. A task cache or log inside the live dir is refused. When a share is full, the feed worker stops with status `share_full` and measure_parse waits (or stops, with `--on-share-full stop`). Both shares are config values (`parse_share_live_per_hour`, `parse_share_tasks_per_hour`, default 10).

Tests: 16 new, each with a control. The full suite passes: 840 passed, 21 skipped (base 27c1a41: 824 passed, 21 skipped). 0 real parse calls: only synthetic logs, fake LLMs and a local fake gateway. **Open, needs a deploy decision:** live still runs vendored rc2 (4d2ab315), so the live share takes effect only after the new code is deployed with `"parse_role": "live"` in live's flags. Any caller that is not live defaults to the task share. I made no live flag changes and no restarts.

## Refs
- Base: wmtm main 27c1a41aaaeb. Code: branch hive/t-2026-11-10-wmtm-shared-parse-count-v2 (staged, not pushed).
- Pins recorded: PeTTaChainer b6aacc68, PeTTa 3681b9b, Man Hin 533c2274. This change runs no engine or parser, and no A/B or Mesto scoring applies (no reasoning change).
- The v1 branch had no commits, so there was no earlier work to carry over.

## What changed
- `wmtm/parse_budget.py` (new): `ParseBudget(role)` with `reserve`/`acquire` (wait, bounded by `parse_share_max_wait_s`, or `ShareFull`), `used`, `status`, and `host_status`. A log row with `call_ids` is joined to the ledger, so each call counts once. A row without them (rc2 live, older tools) counts as one call. A `mocked` row counts as none.
- Provider gate: `semparse_provider.upstream_llm`/`gateway_llm` and the legacy `semparse_adapter.gateway_llm` acquire before every request. With no budget given, they use the default share, so there is no uncounted path in the repo.
- `parse_cache`: `budget()` = min(own cap, share remaining). All three loops stop on a full share without recording an attempt (the item stays queued). Rows carry `call_ids`. The feed worker passes the cache's share and records `share`/`share_stop`. The llm-canary row carries `call_ids`.
- `tools/measure_parse.py`: always uses the task share, writes `<out>/parse_log.jsonl` (one counted, registered row per call: ids and numbers only), and gets `--on-share-full wait|stop` and `--max-wait-s`. `--per-hour` now defaults to the task share.
- `runtime_config`: `parse_role`, both shares, `parse_share_max_wait_s`, `parse_live_dir`, `parse_budget_dir` (README table and docs/RUNTIME.md updated). conftest gives every test its own budget dir.

## Acceptance evidence
1. Two task callers never exceed the task share. `test_two_task_callers_never_exceed_task_share`: A takes 10, B gets 0 with `share_full`. `..._interleaved_and_concurrent`: two threads with a slow fake send exactly 10. Control `test_control_per_cache_counting_lets_two_tasks_reach_20`: own-log counting gives 20.
2. Live's calls don't use the task share. `test_live_calls_do_not_use_task_share`: 15 live rc2 rows give live 0 remaining and tasks 10, and live file hashes are unchanged. Control `test_control_v1_pool_rule_would_starve_tasks`: the v1 rule leaves 5. `test_live_share_counts_across_subcaches`: 3+3+3 rows give 1 left, and the 27c1a41 own-log rule would give 17.
3. measure_parse writes a counted row per call. `test_main_writes_a_counted_row_per_call`: 3 gateway calls give 3 log rows and 3 ledger rows with the same ids, used = 3, and still 3 with the ledger removed. `test_main_stops_when_task_share_is_full`: nothing is sent.
- Mutation checks (`mutation.log`, `mutate.py`): with the change undone the tests fail. M1 (own log only), M2 (live counted in tasks), M3 (no measure_parse row), M4 (provider ungated). M0 (unmutated) passes.
- Suite: `WMTM_SEMPARSE_HITL=<1f1a7a6f clone> python3 -m pytest -q tests` gives 840 passed, 21 skipped (`full_suite.log`). Without HITL: 820 passed, 41 skipped. The f44d7b74 checkout fails 2 provider-patch tests at base too (environmental, because that checkout already has the providers), so the 1f1a7a6f pin was used. Python 3.10.12, pytest 9.1.1, pop-os.

## Limits
- The live share takes effect only after the deploy described above. Until then rc2 live caps each sub-cache at 20/h on its own.
- `parse_budget_dir` is host-wide (`~/.wmtm/parse_budget`). Tasks in sandboxes with a different HOME or host need it set to a shared path.
- A caller that bypasses wmtm's providers (its own HTTP client) is not counted. All in-repo paths are gated.
- Counting is per gateway call, so a ctx1 note with several passages uses several calls. The feed's hard stop on 429 is not added here (measure_parse already has one).
