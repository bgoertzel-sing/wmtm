# t-2026-11-10-wmtm-design-gap-check — working notes (not the result)

> Superseded by REPORT.md (2026-11-10 02:40 UTC). The environment section below is the state BEFORE the user-space install; the candidate gaps were tested there (GAP-1..8).

Saved 2026-11-10 ~02:30 UTC from the transcript of the first working session
(agent:main:cron:e6797f7a…), because that session was cut off before it wrote anything to disk.
Code under test: projects/wmtm/repos/wmtm-27c1a41 (source tarball; no .git directory).

## Environment (observed 2026-11-10 02:22 UTC)
- git: not installed. So the branch hive/<task> cannot be pushed, and hive-task result will be refused.
- swipl: not on PATH. gcc/cc: not installed. python3 = 3.11; import janus_swi -> ModuleNotFoundError.
- The janus.so that ships with the local swipl 9.3.36 is built for cpython-3.10, and there is no python3.10 binary on the host.
  Without a compiler there is no way to build janus_swi for 3.11, so the real PeTTa/PeTTaChainer engine can't be driven from Python here.
- Baseline suite (env-gapcheck/baseline_suite.log): 803 passed, 11 failed, 31 skipped.
  - 4 failures: janus_swi missing.
  - 7 failures: exit 3 / warm_fail, meaning the chainer can't start (test_f1_s11_subunit x2, test_name_resolve, test_p4_rule_goals, test_pc_admit, test_pc_shadow x2).
  - Inferred, not confirmed: all 11 are environmental.
  - Skips: WMTM_TEST_GC2_PYTHON unset (4), WMTM_SEMPARSE_HITL checkout missing (~19), git/tag v0.1.0 missing (8), PETTA_PARSER/SWIPL unset (1).

## Candidate gaps (Hypothesis until a test confirms each one)
- G-recall-spread: recall_bridge._score_cluster returns 0.0 when there's no keyword overlap, and it does so before spreading activation runs.
  So a cluster that is reachable only through EvidenceFor from an active cluster is never recalled. That undercuts the design's associative recall.
- G-promotes-from: PromotesFrom is parsed (recall_bridge.py:34, :99) and the docstring at :392 says it is followed. Whether recall actually traverses it still needs checking.
- G-lti-recall: LTI boosts don't appear to feed into the recall score.
- G-derived-penalty (s7.1): with a derived penalty of /1.5, a derived item with STI slightly above a recalled item's should be evicted first (0.32 vs 0.4 composite).
  The previous session expected the current code to evict the recalled item instead. Not yet tested.
- G-promotion-default: derived items used across many cycles are not written back with default flags. With the flag on, it may pass.
- G-triviality: no filter found yet that separates trivial restatements from non-trivial derived conclusions in admission or eviction. The grep was not finished.

## Planned acceptance suite
tests/test_design_s12_gapcheck.py: one test per design requirement. Known gaps are marked xfail(strict=True, reason="GAP-n ...").
Tests that need the engine skip with "not run: environment". The memory-lifecycle tests use a recorded admit fixture, so they cover store, forget and promote only, not inference correctness.
- s12.2: full-cycle test, no re-admission after eviction, promotion, recalled-item enrichment (T4).
- s12.3: 100-cycle synthetic simulation at capacity about 20.
- s12.4: capacity invariant, forgetting-log completeness, snapshot round-trip, supersede chains.
- Mesto's examples: coverage map of the 11 points.

Still to do: the component table, the derived-belief usefulness analysis, the ranked gap list, and the report.
