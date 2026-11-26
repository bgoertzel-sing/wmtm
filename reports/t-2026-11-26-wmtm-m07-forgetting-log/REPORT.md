# t-2026-11-26-wmtm-m07-forgetting-log: forgetting-log cap that does not end forgotten status (M-07)

## Summary

The order asked that a forgotten conclusion be re-admitted only through should_re_admit's STI test, however long ago it was forgotten, while the forgetting log stays bounded. Done. When a derivation is pruned from the 500-record window, its content and derivation keys go into a fixed-size Bloom filter (2^18 bits = 32 KiB, k=7). A Bloom filter has no false negatives, so a pruned derivation still counts as forgotten and can come back only through the STI test. A false positive only sends a never-forgotten derivation through the same test. Prunes are O(1) (deque + refcounts), from_dict applies the cap, there is a new runtime_config key forgetting_log_max (default 500), and ForgetRecord has final_confidence (optional, read from provenance stv).

Tests: the 10 new tests fail on main (10/10) and pass on the change. The full suite gives 1641 passed, 70 skipped, 5 xfailed, and test_s12_2_multicycle_forgetting_log_prevents_rederivation still passes. I replayed a frozen copy of the live state on pop-os (500 records, cycle 20584). Loading and saving it is byte-identical to main, and with cap 100 the window is identical to main's. The only difference is the gap: main still treats 14 of the 79 derivations as forgotten, and the change treats all 79 as forgotten. No live change, nothing pushed. Still open: the §7.3 recency and similar-confidence rule (see the end of this report).

## Base / refs
- Base: wmtm main 915bc8caeb32186a093e3227f3c1ec2db38c8210 (origin/main at start)
- Branch: hive/t-2026-11-26-wmtm-m07-forgetting-log
- Evidence: /srv/hive-evidence/t-2026-11-26-wmtm-m07-forgetting-log/ (SHA256SUMS; the frozen state input is kept mode 600 outside the repo because it contains note text)

## Why a Bloom filter (the smallest mechanism)
- A plain set of pruned hashes grows without bound, which the order calls useless. Raising the cap only moves the gap.
- A Bloom filter has fixed memory and no false negatives, which is exactly the property needed: once forgotten, always forgotten. Its error goes only in the safe direction (an extra STI test).
- Only derivations (records with derived_from) enter the filter, because only they reach the reasoner admission test. Recalled and user items keep their old window-only behaviour, unchanged. Live, 83 of the 500 window records are derivations and the window spans about 381 cycles, so roughly 0.22 derivations are pruned per cycle. The false-positive rate stays below 1% up to about 13.7k pruned derivations, which is about 60k cycles. pruned_fp_rate() reports the current rate.
- The filter is saved zlib + base64 under forgetting_log["pruned"] and only appears after the first derivation prune, so small logs save exactly as before.

## Changes (file:area)
- wmtm/forgetting_log.py: _PrunedKeys (Bloom filter); deque + Counter refcounts, so _prune_one is O(1); is_forgotten / is_forgotten_key also consult the filter; should_re_admit(..., derived_from=) uses the same key; ForgetRecord.final_confidence; from_dict(d, max_records=None) applies the cap (argument, else the saved cap, else 500) and routes the excess through the filter; to_dict adds "pruned" and final_confidence only when present.
- wmtm/orchestrator.py: _is_skipworthy now goes through should_re_admit(content, forget_log_override_threshold, initial_sti, derived_from), which is the same rule as before (skip if forgotten and STI < 500.0), now in one place. restore_state passes the cap from runtime_config forgetting_log_max (_forget_log_cap).
- wmtm/pc_admit.py: admit_on_snapshot's known() previously built its own set from the window records, which bypassed the filter. It now uses ForgettingLog.from_dict(...).is_forgotten.
- wmtm/runtime_config.py + README.md: forgetting_log_max (WMTM_FORGETTING_LOG_MAX, int, 500). The README flags table stays in sync with SPEC.
- tests/test_m07_forgetting_log_cap.py: 10 tests.

## Tests (acceptance 1)
- New tests on main 915bc8c: 10 failed (new_tests_on_main.out). On the change: 10 passed (new_tests_on_change.out).
- Covered: synthetic replay with cap 3 and 5 records (pruned d0 and d1 still forgotten; other sources = new derivation); round trip saving 5 records and loading with cap 2 (window d3, d4; all 5 forgotten; cap and filter persist); saved cap applied without an argument; a pruned derivation re-derived with low STI is refused (_is_skipworthy True, should_re_admit False); with high STI it is admitted; refcounts; recalled prunes do not fill the filter; an old saved log loads and saves byte-identically; final_confidence from stv; config default 500.
- Full suite: 1641 passed, 70 skipped, 5 xfailed (suite.out), including test_s12_2_multicycle_forgetting_log_prevents_rederivation.

## Live-shaped replay (acceptance 2 and 3)
Input: a frozen copy of the live protocosmo2 _wmtm_state.json taken 14:55 (cycle 20584, 500/500 records, 83 with sources). Script m07_replay.py was run with PYTHONPATH set to main and then to the change (replay.out).
- A, load as-is: to_dict == the saved dict on both (old saved log loads without error, nothing added); 83 derivation keys forgotten on both.
- B, sequential replay with cap 100: the window item-id sequence hash is identical (19113c126441); 73 recalled hashes in the window on both. Forgotten derivations: main 14/79, change 79/79. That difference is the gap and nothing else. FP rate 5.7e-18.

## Stop-lines kept
M-07 only. No live change, nothing pushed, no note text in the repo (tests use synthetic strings; hashes and ids only).

## Follow-up: §7.3 recency and similar confidence (not done)
The rule "forgotten recently with similar confidence -> skip or lower STI" would need:
(1) the candidate's confidence at the admission test (InferenceCandidate.confidence / stv, available);
(2) final_confidence at eviction, which this change now records in the window;
(3) for pruned keys, an approximate eviction time and confidence. A Bloom filter stores neither, so it would need generational filters (one per N cycles, oldest dropped = the "recently" horizon) or a small count-min table of confidence buckets;
(4) a decision on the outcome (skip versus a lower starting STI) and on the thresholds.
