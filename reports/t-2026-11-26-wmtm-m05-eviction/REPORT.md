# t-2026-11-26-wmtm-m05-eviction: composite eviction score with the derived penalty (M-05), flag off

## Summary

The order asked for capacity eviction to rank items by the design's composite score (STI*0.4 + utility*0.4 + LTI*0.2, with derived items divided by 1.5), through one code path, behind a flag that is off by default. Flag-off behaviour had to stay exactly as it is today. That is done, on base wmtm main 915bc8c. With `composite_eviction` on, admit overflow and the forgetting policy now pick their victim with the same function. The §7.1b age review is also on with the flag: at max_age an item is kept and its age reset if its utility is above min_utility, and evicted otherwise. The strict GAP-3 xfail test now passes with the flag on. The 9 new tests pass. The full suite gives 1639 passed and 1 failed. The failure is `test_feed_watch::test_running_young_worker_is_ok`, a timing flake that also fails in 2 of 6 runs on unmodified 915bc8c.

Flag-off identity was not checked against a pop-os frozen run. The block answer (cos, 2026-11-26) took that check out of this task's acceptance. In its place I ran a local flag-off differential: 200 seeded admit/forget sequences, base 915bc8c against the branch. Eviction traces and forget logs are byte-identical (sha256 in §3). I also added `tools/m05_replay.py`, which takes a frozen-run path and the flag value and writes the eviction order plus the STI/utility/LTI of every evicted and surviving item. It writes ids and sha256 content hashes only, never note text. **The pop-os replay on a frozen run is still pending.** It is a follow-up for a pop-os worker after this task closes, using that script.

The STI-vs-utility ranges in §4 come from the synthetic fixture and from that fixture replayed through the tool. The normalisation in §4 is a proposal, marked *to be confirmed on a frozen run*. It is not decided. `test_feed_watch::test_running_young_worker_is_ok` is a pre-existing flake and not part of this change: it fails 2 of 6 runs on unmodified 915bc8c.

Code: see the result header (impl c88abb2; branch hive/t-2026-11-26-wmtm-m05-eviction), base 915bc8caeb32186a093e3227f3c1ec2db38c8210. Local only, not pushed.

## 1. Change

- `wmtm/eviction.py` (new) adds `eviction_cfg(cfg)`, which returns None when the flag is off. It also adds `composite_score(item, cfg)` (§7.1c, docs/wmtm_design_doc.txt l.270-274; §10 derived_eviction_penalty 1.5) and `lowest()`.
- `wmtm/store.py`: `eviction_cfg` attribute (default None, not serialized); `composite_victim()` is the one ranking used by both capacity paths. rc4 still applies: the user request item goes last. `_evict_lowest_sti` uses it only when `eviction_cfg` is set.
- `wmtm/forgetting.py`: `_evict_over_capacity` uses `store.composite_victim()` when the flag is on. `_evict_aged_low_utility` applies the §7.1b keep/reset/evict rule when the flag is on. With the flag off, both run unchanged.
- The orchestrator, api, context (fast path) and pc_admit call `orch._sync_eviction_cfg(cfg)`, which passes the resolved runtime config to the store before admissions that can overflow capacity, and in `forget_phase`.
- `wmtm/runtime_config.py` gets 4 SPEC keys, each with a matching README row: `composite_eviction` (false), `eviction_weights` ("0.4,0.4,0.2"), `derived_eviction_penalty` (1.5) and `eviction_min_utility` (2.0). Malformed values fall back to the design defaults.

## 2. Tests

- `tests/test_m05_composite_eviction.py` (9 tests, all pass):
  - the flag is off by default;
  - the §12.1 composite unit test, including config overrides and the fallbacks;
  - a capacity-3 replay with a recalled low-STI/high-utility item, a derived item with the same values and a recalled high-STI/low-utility item: admitting a 4th evicts the derived one, which reaches forget_log via drain_pending_evicted, and the §12.4 invariant holds at every step;
  - the same replay with the flag off, which evicts the lowest STI as before;
  - both capacity paths pick the same victim;
  - rc4 still holds with the flag on;
  - the §7.1b age review with the flag on and off;
  - the orchestrator syncs the flag from the env.
- `tests/test_design_s12_gapcheck.py::test_s7_1c_...composite_penalty`: I removed the strict xfail marker. The test now sets the flag on and passes.
- Full suite: 1639 passed, 71 skipped, 4 xfailed, 1 failed. The failure is the feed_watch timing flake, which also fails 2 of 6 runs on base 915bc8c.

## 3. Flag-off identity

`tools/flagoff_replay.py` runs 200 seeds with random capacity 2-8 and 10-60 ops (admit with random type/STI/utility/LTI/age, or forget_phase), with every WMTM_* env var cleared. Each step records the active ids, the drained evictions and the forget_log ids. Base (915bc8c) and branch (c88abb2) outputs are byte-identical: sha256 36301445096dbff4d6ff3db6969b1bbfdc30e9519aa3d520ae2121f8ea07e380 for both. The script is kept at `reports/t-2026-11-26-wmtm-m05-eviction/tools/flagoff_replay.py`.

`tools/m05_replay.py <frozen-run path> <0|1> [--capacity N] [--cycles K] [--out FILE]` takes a snapshot JSON (snapshot_state() output) or a directory of them. For each snapshot it restores the state, can lower the capacity, runs forget_phase K times with the flag set as given, and writes one JSON line: the eviction order, then id, content_sha256, source_type, STI, utility, LTI and age for every evicted and every surviving item. It is covered by `tests/test_m05_replay_tool.py` (3 tests): no note text in the output, deterministic, the flag is honoured, and directory input works.

**Pending (not part of this task's acceptance): the pop-os replay on a frozen run.** For a pop-os worker: run `tools/m05_replay.py <run> 0` on 915bc8c and on this branch, compare byte for byte, and put SHA256SUMS under /srv/hive-evidence/<task>/.

## 4. STI-vs-utility scale: to be confirmed on a frozen run

Synthetic state (tests/fixtures/synthetic/wmtm_state.json, n=20, as stored):

| | min | median | p90 | max |
|---|---|---|---|---|
| STI | 0.153 | 6.484 | 39.317 | 44.775 |
| utility | 0.0 | 9.4 | 25.4 | 31.4 |
| LTI | 0.0 | 0.46 | 1.775 | 2.154 |

Replayed state (the same fixture through `tools/m05_replay.py`, capacity 12, one forget_phase, which applies decay and the utility tick; n=20):

| | min | median | p90 | max |
|---|---|---|---|---|
| STI | 0.138 | 7.736 | 37.286 | 42.197 |
| utility | 0.0 | 11.4 | 27.4 | 33.4 |
| LTI | 0.0 | 0.597 | 2.073 | 2.525 |

In the replay, flag off and flag on agree on the first 6 of 8 victims. For the last 2, flag off evicts two recalled items with high STI and utility 9.4. Flag on instead evicts two recalled items with lower STI (6.13 and 4.61) and higher utility (11.4 and 14.9).

Share of the summed weighted composite (synthetic): STI 0.56, utility 0.42, LTI 0.01. In practice the LTI weight of 0.2 contributes almost nothing. Utility grows by +1.0 per use (item.py) and has no bound, so over long runs it will outweigh STI. In this fixture the first 5 victims are the same under STI, utility, composite and max-normalised composite.
Proposed normalisation, **to be confirmed on a frozen run** (not decided): (a) max-normalise each term over the eviction pool; (b) a fixed squash such as u/(1+u) for utility and sti/sti_cap for STI; (c) rank-normalise each term within the pool. (a) and (c) keep the design's weights meaningful whatever the scale.
