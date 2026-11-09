# Pins (t-2026-11-09-wmtm-live-path-replay-v3), recorded 2026-11-09 13:21 PDT
Supersedes: t-2026-11-09-wmtm-live-path-replay-v2
- Branch hive/t-2026-11-09-wmtm-live-path-replay-v3 off 4f79bfc (v2 head; on 56bc717 flat-inheritance-v2, on 35dd978). Hive base 965ea636.
- Arm A code: vendor wmtm-v0.7.0-rc2 (commit 4d2ab315, _wmtm_pin.py), live flags copied with sandbox paths.
- Arm B code: this branch (wmtm-module working tree at 4f79bfc).
- Turn loop (all arms): PeTTa p1-engine 3681b9b, PeTTaChainer /tmp/lpr/pc @ f873824 (contains b6aacc68), GoalChainer v2 release pymetta-native.2.
- Offline v2 A/B (runs_offline/full_A, full_B): A used vendor PeTTa v1.0.6 + PeTTaChainer 36b3fe6-dedup, B used 3681b9b + f873824 (pins differed; goal pool built in Python before the engine, so goals_n is unaffected).
- Parses (raw caches off-repo, sha256 in CACHE_SHA256.txt):
  - A: live spk1 copy, prompt-mode 3ec15bd1 (sent sha 2fcbcc54), cache sha 92bea773.
  - B533: catalog 533c2274 (prompt 1585e873), Nov 9.
  - Bf44: catalog f44d7b74 (prompt 645bff3f), fresh re-parse Nov 9.
  - Bp3: /tmp/p3_out/ab/B2 cache, catalog 1f1a7a6f (prompt e4c4a76c), Nov 5 (stand-in for the deleted F3 v3 f44d7b74 cache).
- Notes: same 20 ids, raw_spec.json sha256 0a339405e8f2450ed97b83abaa243e9c342ad58de76fce59c9a3fd89c8432aa5 (pop-os only).
