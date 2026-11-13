# t-2026-11-13-wmtm-spread-seed-default: P10 as the default; does P10 still lead on a second journal?

## Summary

**Flag first: on the second journal (seed 20261113) P10 does not lead. Plain E (this turn's matches only) comes out ahead, and P10 is second.** As the order says, I made the change anyway: graph recall now defaults to this turn's matches plus the top 10% most active residents on every turn (arm P10). andy may want to revert. On the new journal E shows more useful items (87 vs 82), keeps more revisits (15/51 vs 12/51), loses fewer hubs (12 vs 18), admits more cleanly (0.50 vs 0.47) and is the same on churn (0 evictions for both). P10 still beats E on first-visit coverage (46/72 vs 42/72) and precision of what is shown (0.29 vs 0.26), and it is the best of the four arms that add resident seeds. Ranking on seed 20261113: **E > P10 > P25 > F25 > F50**. On the sweep's seed it was P10 > F25 > E > P25 > F50. Over the two journals together, E and P10 are close (useful shown 160 vs 159, revisit 29 vs 31, first visit 78 vs 82, hubs lost 21 vs 28). So the evidence does not separate them. What both seeds agree on is that the original plan (F50, top 50% only on no-match turns) is last, with churn back (57 and 62 evictions).

The default is P10 everywhere it is read: the runtime_config SPEC (`recall_spread_seeds` turn, `recall_spread_add_pct` 10), the context.py readers (absent or invalid values give the SPEC default), the API call and the README flags table. The old settings can still be chosen: `WMTM_RECALL_SPREAD_SEEDS=all` (the behaviour before the flag), `focus`, `WMTM_RECALL_SPREAD_ADD_PCT=0` (plain E), and FALLBACK_PCT with ADD_PCT=0. Tests cover each of these. Under the new default, seed 20261111 reproduces the sweep's P10 run byte for byte, apart from the write-back note ids. The default also equals explicit P10 on seed 20261113. Full suite: 1329 passed, 41 skipped, 6 xfailed. Synthetic data only, and no deployment: changing the live flag is andy's call. Code is staged in the hive queue repo on branch hive/t-2026-11-13-wmtm-spread-seed-default. It is not pushed and is waiting for review.

## Base

- Started from **hive/t-2026-11-13-wmtm-spread-seed-sweep @ 572982e** (passed review), as the order says. The hive recorded base a99c271 (= main). As with the sweep and its base, this branch is not on main: merge-base(a99c271, 572982e) = b9c9d51.
- Worktree: projects/wmtm/repos/default. Branch: hive/t-2026-11-13-wmtm-spread-seed-default (queue repo /hive/protocosmo/.hive/queue/wmtm).
- Environment: the env-gapcheck venv (Python 3.10.22), with git from /hive/protocosmo/opt/swipl929/bin (not on the default PATH). Nothing ran on pop-os. No parse calls: probe_turns.py refuses them, and violations=0 in all 14 runs. No live flags or restarts.

## Change (default flip; 4 code files + README + tests)

- **wmtm/runtime_config.py** SPEC: `recall_spread_seeds` default **turn** (was all); `recall_spread_add_pct` default **10.0** (was 0); `recall_spread_fallback_pct` stays 0. Comments are updated.
- **wmtm/context.py**: `recall_spread_seeds(cfg)`: absent, None or invalid now give the SPEC default (turn), not a hard-coded "all". `recall_spread_pct(cfg, key)`: absent or invalid (non-number, None, NaN) give the SPEC default for that key (add 10, fallback 0); `<= 0` is still off, `> 100` is still 100. This matches `resolve()`, which already keeps the SPEC default for an unparsable env value. Without it, a junk env value would give 10 through resolve() but 0 through a raw cfg.
- **wmtm/api.py**: comment only. The call path was already correct: under the new default it passes `spread_seeds="turn", request_id, add_pct=10.0` (spy test).
- **wmtm/recall_bridge.py**: docstrings only. The *method argument* defaults of `RecallBridge.recall` (spread_seeds "all", pcts 0) are **kept** for direct callers, the same convention as `floor=0.0` there. The flag default lives in SPEC and api.py passes it. The only production caller of `rb.recall` is api.context_for (grep), so every live turn gets P10. Test `test_bridge_default_matches_flag_default` checks that what the readers return reaches the bridge as P10.
- **README.md** flags table: rows `recall_spread_seeds` (`turn`), `recall_spread_add_pct` (`10`) and `recall_spread_fallback_pct` (`0`, "for the fallback rule alone set ADD_PCT=0 too"), with the history of the change. test_readme_flags_sync passes, and a new test checks the three default cells.

### How to get the old behaviour back (for andy)

| setting | env |
|---|---|
| before the spread-seed flags (all residents seed) | `WMTM_RECALL_SPREAD_SEEDS=all` |
| arm E (this turn's matches only) | `WMTM_RECALL_SPREAD_ADD_PCT=0` |
| the original plan F50 | `WMTM_RECALL_SPREAD_ADD_PCT=0 WMTM_RECALL_SPREAD_FALLBACK_PCT=50` |
| reverting the code default | the two SPEC defaults in runtime_config.py (+ README cells, test_recall_spread_default.py) |

## Tests

- New **tests/test_recall_spread_default.py** (15 tests): SPEC defaults; the readers give turn / 10 / 0 for `{}`, None and a resolved empty state dir; README default cells; **API with no flags = explicit P10** (admissions and context blocks, 4 seeded 10-turn scripts with no-match turns). Negative control: the default differs from all and from E on those scripts. **Spy on the API's recall call per mode**: default → turn+add 10; all → the old call with no seed kwargs; focus → focus; turn+ADD 0 → the probe's E call; ADD 0 alone → E; turn+ADD 0+FALLBACK 50 → fallback only; ADD 25 → add 25; invalid mode → default. all and E set in the flags file run exactly as the same setting from env, and differ from each other (3 seeds).
- Updated: test_recall_spread_seeds.py (default is turn; invalid = default; "unset = all" is now "unset = turn + add 10"; the spy checks all → old call and unset → turn + 10) and test_recall_spread_sweep.py (SPEC defaults; invalid add_pct = 10, invalid fallback_pct = 0 (5 new cases); the old-mode API equalities now set all / ADD 0 explicitly). No test was weakened. Each one that compared with "unset" now compares with the explicit old setting.
- **Full suite** (results/suite.txt): **1329 passed, 41 skipped, 6 xfailed**, EXIT 0 (the sweep's 1309 + 20 new). The baseline on the unchanged worktree was 1309/41/6. Before the test updates, exactly 18 tests failed, all of them checks of the old default.

## Replays

Tools: gen_journal.py, probe_turns.py, check_rerun.py, analyse3.py and table5.py are byte-identical copies of the sweep's (SHA256SUMS.txt; same hashes as the sweep's SHA256SUMS). tools/run_arms.sh = the sweep's run5.sh, except that, because the defaults moved, every sweep arm now sets all three seed-rule variables **explicitly**, and arm **D** sets none (= the new code default). tools/check_rerun_wb.py = check_rerun.py, also normalising the `-2` suffix journal.append adds to a write-back note id when two notes fall in the same wall-clock second (see below). Fixed clock, WMTMConfig(reasoner="off", use_pln=False), capacity 60, recall_budget 10, floor 0.1, 40 turns. A = probe-A worktree 265062e (keyword-only reference for "hubs lost").

### Second seed: 20261113

- `python3 tools/gen_journal.py --out data-s20261113 --seed 20261113`: same generator and settings, with turns and labels built by the same code from the seed. Journal sha256 **0fb3fded...cfa7c** (seed 20261111: 5e93b344...71bd0), turns 9b60f6d9... (vs b4390070...), labels 34b0e894... (vs 0e2a35d9...): a fresh journal, not a reuse. 362 clusters (vs 372), 17 hubs, 72 first-visit targets (vs 70), 51 revisit targets (vs 47).
- No-match turns (no cluster matches the query by keyword): 17 = Q3 x10, R3 x5, Q2 (turn 19), R2 (turn 36). Seed 1 had 16.

Results (results-s20261113/table5.md; D = no variables = the new default):

| | A | E | F50 | F25 | P10 | P25 | D |
|---|---|---|---|---|---|---|---|
| admitted (new, recalled) | 35 | 122 | 241 | 186 | 141 | 187 | 141 |
| of which graph-only | 0 | 85 | 203 | 148 | 106 | 151 | 106 |
| on-topic useful admitted | 22 | 61 | 83 | 75 | 66 | 76 | 66 |
| precision of admitted (on-topic) | 0.63 | **0.50** | 0.34 | 0.40 | 0.47 | 0.41 | 0.47 |
| graph-only admissions from another topic | n/a | 0 of 85 (0%) | 62 of 203 (31%) | 26 of 148 (18%) | 6 of 106 (6%) | 28 of 151 (19%) | 6 of 106 (6%) |
| evictions (capacity) | 0 | 0 | 62 | 0 | 0 | 0 | 0 |
| useful evicted (hubs) | 0 (0) | 0 (0) | 29 (3) | 0 (0) | 0 (0) | 0 (0) | 0 (0) |
| first turn with an eviction | None | None | 21 | None | None | None | None |
| turns with the store at capacity (max store) | 0 (max 24) | 0 (max 45) | 4 (max 60) | 0 (max 50) | 0 (max 49) | 0 (max 57) | 0 (max 49) |
| turns the budget (10) binds | 0 | 7 | 15 | 7 | 7 | 10 | 7 |
| useful shown (on-topic) | 58 | **87** | 76 | 76 | 82 | 80 | 82 |
| items shown / precision of shown | 269 / 0.22 | 340 / 0.26 | 222 / 0.34 | 193 / **0.39** | 280 / 0.29 | 253 / 0.32 | 280 / 0.29 |
| first-visit coverage (hubs + linked) | 17/72 | 42/72 | **53/72** | 47/72 | 46/72 | 46/72 | 46/72 |
| revisit coverage | 10/51 | **15/51** | **15/51** | 13/51 | 12/51 | **15/51** | 12/51 |
| hubs lost vs A (turns) | - | **12 (8)** | 27 (14) | 24 (12) | 18 (10) | 22 (10) | 18 (10) |
| of which evicted in-turn | - | 0 | 0 | 0 | 0 | 0 | 0 |
| resident seeds added (turns) | - | - | 377 (17) | 164 (17) | 153 (39) | 391 (39) | (= P10) |

By turn kind (admitted / graph-only / on-topic useful admitted / evictions / useful evicted / on-topic useful shown):

| kind (turns) | E | F50 | F25 | P10 | P25 |
|---|---|---|---|---|---|
| match (23) | 122 / 85 / 61 / 0 / 0 / 54 | 122 / 84 / 60 / 29 / 14 / 53 | 123 / 85 / 63 / 0 / 0 / 55 | 126 / 91 / 62 / 0 / 0 / 54 | 150 / 114 / 67 / 0 / 0 / 58 |
| no-match (17) | 0 / 0 / 0 / 0 / 0 / 33 | 119 / 119 / 23 / 33 / 15 / 23 | 63 / 63 / 12 / 0 / 0 / 21 | 15 / 15 / 4 / 0 / 0 / 28 | 37 / 37 / 9 / 0 / 0 / 22 |

(Full per-kind split for Q1/Q2/Q3-R3/R2 in results-s20261113/table5.md.)

**Ranking on seed 20261113** (the sweep's criteria in its order: churn, then precision of admitted and off-topic share, then useful shown and coverage):

1. **E.** No churn, the cleanest admissions (0.50, 0% off-topic), the most useful shown (87), revisit 15/51 (tied best), fewest hubs lost (12). Weakest first-visit coverage among the non-A arms (42/72).
2. **P10.** No churn, 0.47 and 6% off-topic (cleanest of the arms that add seeds), useful shown 82, first visit 46/72. Lowest revisit coverage of the five (12/51), hubs lost 18. On no-match turns it admits 15 items (4 useful) and useful shown there drops from E's 33 to 28: the same block-shrink effect the sweep saw for F50, small here.
3. **P25.** No churn on this journal (31 evictions on seed 1), 0.41 / 19% off-topic, useful shown 80, revisit 15/51, hubs lost 22.
4. **F25.** No churn, 0.40 / 18%, useful shown 76, best precision of shown (0.39), first visit 47/72, hubs lost 24.
5. **F50 (the plan).** Churn again: 62 evictions, 29 useful evicted (3 hubs), 0.34 / 31% off-topic, hubs lost 27. Best first-visit coverage (53/72), as on seed 1 (40/70, second there).

**P10 does not lead on seed 20261113; E does.** P10's two wins on seed 1 were useful shown (77 vs E 73) and revisit coverage (19/47 vs 14/47). Both reverse here (82 vs 87, 12/51 vs 15/51).

### Both seeds side by side

| | E s1 / s2 | P10 s1 / s2 | F25 s1 / s2 | P25 s1 / s2 | F50 s1 / s2 |
|---|---|---|---|---|---|
| evictions | 0 / 0 | 0 / 0 | 0 / 0 | 31 / 0 | 57 / 62 |
| precision of admitted | 0.52 / 0.50 | 0.49 / 0.47 | 0.43 / 0.40 | 0.36 / 0.41 | 0.30 / 0.34 |
| off-topic graph-only | 13% / 0% | 15% / 6% | 26% / 18% | 38% / 19% | 47% / 31% |
| useful shown | 73 / 87 (160) | 77 / 82 (159) | 74 / 76 (150) | 67 / 80 (147) | 63 / 76 (139) |
| first-visit coverage | 36/70 / 42/72 (78) | 36/70 / 46/72 (82) | 42/70 / 47/72 (89) | 36/70 / 46/72 (82) | 40/70 / 53/72 (93) |
| revisit coverage | 14/47 / 15/51 (29) | 19/47 / 12/51 (31) | 17/47 / 13/51 (30) | 15/47 / 15/51 (30) | 15/47 / 15/51 (30) |
| hubs lost vs A | 9 / 12 (21) | 10 / 18 (28) | 15 / 24 (39) | 14 / 22 (36) | 18 / 27 (45) |
| rank | 3 / 1 | 1 / 2 | 2 / 4 | 4 / 3 | 5 / 5 |

What holds across both journals (**observed** on 2 seeds; anything more general is **inferred**): F50 is last both times and the only arm with churn on both. E and P10 are both churn-free and the two cleanest. Between E and P10 the lead flips with the journal, and the two-seed totals are within a few items of each other. P10 is the best of the four "add resident seeds" settings on both seeds. P25's churn on seed 1 did not recur on seed 2 (max store 57 vs 60), so the churn boundary depends on the journal.

### Seed 20261111 under the new default (acceptance 3)

- `tools/run_arms.sh ... 20261111 s20261111 "A E F50 F25 P10 P25 D"` regenerates the journal with sha256 5e93b344...71bd0, and turns and labels with the sweep's hashes (b4390070..., 0e2a35d9...).
- **D (no variables, the new default) vs the sweep's committed P10 run: identical modulo write-back note ids** (check_rerun.py true; results-check.txt). D's table column equals the sweep's P10 row in every cell: admitted 141, graph-only 104, useful admitted 69, precision 0.49, off-topic 16 of 104 (15%), 0 evictions, max store 53, budget binds 6, useful shown 77, shown 323 / 0.24, first visit 36/70, revisit 19/47, hubs lost 10 (8) (results-s20261111/table5.md).
- Every other arm rerun on this branch with explicit variables also reproduces its sweep run (A, E, F50, F25, P10, P25 all true), so the default flip changed nothing except what an unset flag means.
- Seed 20261113: D = P10 as well (check_rerun_wb.py true). Negative controls: D differs from E, F50, F25 and P25 there.
- Note on the write-back ids: on seed 20261113, D's run happened to write two journal write-back notes in the same wall-clock second, so journal.append named the second `ep-note-...Z-2`. check_rerun.py normalises `ep-note-<stamp>` but not the suffix, so it reports false for D vs P10 there. The only differences are those two note ids, in the "scored" lists of turns 30-39, all with score 0 (checked entry by entry). check_rerun_wb.py normalises the suffix and reports true. With either checker, all the seed 20261111 comparisons are true.

## Limits

- Two synthetic journals from one generator, 40 turns each, capacity 60, budget 10. Two seeds show that the E-vs-P10 order is not stable. They do not show which one is better in general: that needs more seeds or real traffic. All differences between E and P10 here are a few items per 40 turns.
- Rankings use the sweep's criteria and order (churn, then admission cleanliness, then shown/coverage). Weighting first-visit coverage higher would favour P10 on seed 2 (46 vs 42) and F25/F50 on both.
- The no-match share (16-17 of 40 turns, mostly topic-free follow-ups) is set by the generator. How often real requests match no cluster is not measured.
- Reasoner and PLN off, as in the probe and the sweep; real-engine tests not rerun (engine variables unset as before).
- Code default only. Nothing deployed, no live flag changed.

## Refs

- Code: branch **hive/t-2026-11-13-wmtm-spread-seed-default** in the hive queue repo (/hive/protocosmo/.hive/queue/wmtm), base **572982e** (head of hive/t-2026-11-13-wmtm-spread-seed-sweep). Hive base a99c271 (main). Not pushed.
- Files: wmtm/runtime_config.py, wmtm/context.py, wmtm/api.py, wmtm/recall_bridge.py, README.md, tests/test_recall_spread_default.py (new), tests/test_recall_spread_seeds.py, tests/test_recall_spread_sweep.py. Report folder reports/t-2026-11-13-wmtm-spread-seed-default/: REPORT.md, SHA256SUMS.txt, tools/ (sweep copies + run_arms.sh + check_rerun_wb.py), data-s20261111/ and data-s20261113/ (turns.json, labels.json; journal.metta gitignored and regenerated), results-s20261111/ and results-s20261113/ (per arm turns.jsonl + stdout.txt; arms.txt, gen_journal_stdout.txt, summary.json, turn_table.md, analyse_stdout.txt, table5.json, table5.md, table5_stdout.txt), results-check.txt, results/suite.txt.
- Rerun: `sh reports/t-2026-11-13-wmtm-spread-seed-default/tools/run_arms.sh /hive/protocosmo/workspace/projects/wmtm/repos <worktree> 20261113 s20261113 "A E F50 F25 P10 P25 D"` (and 20261111 s20261111). Then, from the report folder: `python3 tools/analyse3.py --data data-<tag> --arm A=results-<tag>/A/turns.jsonl ... --arm D=results-<tag>/D/turns.jsonl --out results-<tag>` and `python3 tools/table5.py --code <worktree> --data data-<tag> --results results-<tag>`; the checks are listed in results-check.txt.
