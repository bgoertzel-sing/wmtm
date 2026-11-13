# t-2026-11-13-wmtm-spread-seed-sweep: E alone, E + fallback, or E + top x% on every turn?

## Summary

Asked: which spread-seed setting should graph recall use by default? The agreed plan (spread from this turn's keyword matches, E; on turns that match nothing, fall back to the top 50% most active residents) had never been run as one rule, and Ben reads the design as additive (always this turn's matches plus the top x% most active). I added the setting as two flags (default unchanged) and replayed the spread-seeds probe on its exact inputs in five arms: E alone, E + top 50% / 25% only on no-match turns, and E + top 10% / 25% on every turn.

Answer: **the plan as written (E + 50% fallback) is the worst of the five on this replay. It brings churn back (57 evictions, 27 useful items evicted; E has 0) and shows fewer useful items than E alone (63 vs 73).** On the 16 no-match turns it admits 129 graph items, of which 11 are on-topic useful. Those new items then replace the 15 residents the context block would otherwise show, so useful shown on those turns falls from 21 to 11. Best overall here is **E + top 10% on every turn** (Ben's reading at 10%): 0 evictions, precision of admitted 0.49 (E 0.52), the most useful shown (77) and the best revisit coverage (19/47), with first-visit coverage the same as E (36/70). **E + 25% fallback** is the other zero-churn option: best first-visit coverage (42/70) and precision of shown (0.40), but noisier admissions (0.43, 26% off-topic). Ranking: P10 > F25 > E > P25 > F50. Arm 1 reproduces the probe's E row exactly (byte-identical per-turn log, modulo write-back note ids). No default changed: andy picks. Limits: one synthetic journal, one seed, 40 turns; this ranks settings, it does not fix the best x. Status: done, waiting for review. Code staged in the hive queue repo on branch hive/t-2026-11-13-wmtm-spread-seed-sweep (base af934da), not pushed.

## Change (wmtm/, 4 files + README; defaults = today)

- runtime_config.SPEC: `recall_spread_fallback_pct` (env `WMTM_RECALL_SPREAD_FALLBACK_PCT`) and `recall_spread_add_pct` (env `WMTM_RECALL_SPREAD_ADD_PCT`), float, default **0** (off). Two flags rather than one mode flag, so both readings can be set and compared independently. README flags-table rows added.
- Both act **only with `recall_spread_seeds=turn`** (E). With all (today's default) or focus they are ignored, so setting them alone changes nothing (tested).
- context.recall_spread_pct(cfg, key): float in [0, 100]; absent, invalid, NaN or <= 0 gives 0; > 100 gives 100.
- RecallBridge.top_sti_ids(residents, pct): the top ceil(n * pct / 100) residents by attention.sti (at least 1 when n > 0), ties in get_active_set order. pct 50 gives exactly the focus (D) set (seeded test).
- RecallBridge.spread_seed_ids("turn", ..., fallback_pct, add_pct): E's seeds (clusters matching the query by keyword + the request item) plus top_sti_ids(residents, x), where x = add_pct on every turn, or fallback_pct when **no cluster matches the query by keyword** (E's keyword seed set is empty). If both are set, a no-match turn uses the larger. Residents are still never candidates; floor, weights, starting STI and budget unchanged.
- api.context_for: passes fallback_pct / add_pct only when mode is turn and the value is > 0. With both at 0 it makes exactly the probe's E call (tested with a spy), which is why arm 1 can reproduce byte for byte.

## Tests (tests/test_recall_spread_sweep.py, 60 tests)

- Config: SPEC defaults 0; parsing (int, string, spaces, 0, negative, junk, None, NaN, > 100); env read.
- top_sti_ids rounding (5 residents: 10% -> 1, 25% -> 2, 50% -> 3, 100% -> 5; 60 residents: 6 / 15 / 30); pct 50 = focus on 10 seeded stores.
- **Default unchanged**: turn with both pcts 0 = plain turn (seeds and recall); pcts ignored under all and focus; API on 4 seeded 10-turn scripts with no-match turns: flags unset = pct flags set without turn, and turn + pcts 0 = plain turn (same admissions and context blocks); the API spy shows the old call when mode is unset and the probe's E call when pcts are 0.
- **Fallback only on no-match turns**: on a matching query the seeds and recall equal plain E; on a no-match query the seeds are the top x% (= focus at 50) and their links are recalled, where plain E recalls nothing (negative control). Seeded property (10 seeds x 6 worlds x 2 queries): fallback = plain E on matching turns, = E + add x% on no-match turns, and differs from plain E somewhere. API: on scripts where every query matches, E + fallback 50 equals plain E exactly; with no-match turns it admits something else (negative control).
- **Additive on every turn**: seeds = E's + top x% on matching and no-match queries (hand-built and 10 seeded properties); linked items of the added residents are recalled, which plain E and E + fallback do not do on a matching turn (negative control). Both flags set: larger pct on a no-match turn.
- Full suite (results/suite.txt): **1309 passed, 41 skipped, 6 xfailed** = the probe's 1249 / 41 / 6 plus the 60 new tests (env-gapcheck venv, Python 3.10.22, engine variables unset as before; real-engine tests not rerun, untouched code).

## Replay: identical inputs

- gen_journal.py, probe_turns.py, check_rerun.py, analyse3.py, data/turns.json and data/labels.json are byte-identical copies of the probe's (SHA256SUMS.txt; same hashes as the probe's SHA256SUMS). The journal is regenerated with seed 20261111: sha256 5e93b344...71bd0, the probe's hash. analyse3.py asserts every arm's journal and turn hashes are equal.
- Fixed clock, WMTMConfig(reasoner="off", use_pln=False), capacity 60, recall_budget 10 (default), floor 0.1. 0 parse/pc_shadow calls (violations=0 in every arm), 0 errors. Nothing ran on pop-os.
- Arms (results/arms.txt, set by tools/run5.sh; the code and everything else are the same for E..P25):
  - **A** = probe-A worktree 265062e, keyword only: reference for "hubs lost", as in the probe.
  - **E** (arm 1) = WMTM_RECALL_SPREAD_SEEDS=turn.
  - **F50** (arm 2, the plan) = turn + WMTM_RECALL_SPREAD_FALLBACK_PCT=50.
  - **F25** (arm 3) = turn + FALLBACK_PCT=25.
  - **P10** (arm 4, Ben's reading) = turn + WMTM_RECALL_SPREAD_ADD_PCT=10.
  - **P25** (arm 5) = turn + ADD_PCT=25.
- **Arm 1 reproduction** (results/rerun_check.txt): check_rerun.py against the probe's committed run gives identical_modulo_writeback_ids **true for E** and for A. Every E number below equals the probe's E row (admitted 119, precision 0.52, 0 evictions, max store 51, budget binds 6, useful shown 73, first visit 36/70, revisit 14/47, hubs lost 9).
- Definitions are the probe's (tools/table5.py follows table4.py). "Turns with the store at capacity" = turns ending with 60 residents; on the probe's C and D runs this gives the probe's 23 and 15. **No-match turn** = no journal cluster matches the query by keyword (the condition under which the fallback fires); it depends only on query and journal, so it is the same for every arm: 16 turns, Q3 x10, R3 x5 and one Q2 (turn 16). All Q1, R2 and the other 9 Q2 turns match.

## Results (whole run, 40 turns; results/table5.md, table5.json)

| | A | E | F50 | F25 | P10 | P25 |
|---|---|---|---|---|---|---|
| admitted (new, recalled) | 32 | 119 | 248 | 177 | 141 | 205 |
| of which graph-only | 0 | 83 | 212 | 141 | 104 | 169 |
| on-topic useful admitted | 18 | 62 | 75 | 76 | 69 | 73 |
| precision of admitted (on-topic) | 0.56 | 0.52 | 0.30 | 0.43 | 0.49 | 0.36 |
| graph-only admissions from another topic | n/a | 11 of 83 (13%) | 100 of 212 (47%) | 36 of 141 (26%) | 16 of 104 (15%) | 64 of 169 (38%) |
| evictions (capacity) | 0 | 0 | 57 | 0 | 0 | 31 |
| useful evicted (hubs) | 0 (0) | 0 (0) | 27 (1) | 0 (0) | 0 (0) | 13 (2) |
| first turn with an eviction | None | None | 20 | None | None | 20 |
| turns with the store at capacity (max store) | 0 (max 26) | 0 (max 51) | 2 (max 60) | 0 (max 51) | 0 (max 53) | 1 (max 60) |
| turns the budget (10) binds | 0 | 6 | 16 | 7 | 6 | 9 |
| useful shown (on-topic) | 50 | 73 | 63 | 74 | 77 | 67 |
| items shown / precision of shown | 261 / 0.19 | 323 / 0.23 | 214 / 0.29 | 186 / 0.40 | 323 / 0.24 | 240 / 0.28 |
| first-visit coverage (hubs + linked) | 17/70 (17+0) | 36/70 (17+19) | 40/70 (17+23) | 42/70 (17+25) | 36/70 (17+19) | 36/70 (17+19) |
| revisit coverage | 9/47 | 14/47 | 15/47 | 17/47 | 19/47 | 15/47 |
| hubs lost vs A (turns) | - | 9 (8) | 18 (11) | 15 (9) | 10 (8) | 14 (9) |
| of which evicted in-turn | - | 0 | 0 | 0 | 0 | 0 |
| resident seeds added (turns) | - | - | 344 (16) | 146 (16) | 155 (39) | 411 (39) |

By turn kind, per arm: admitted / graph-only admitted / on-topic useful admitted / evictions / useful evicted / on-topic useful shown

| kind (turns) | A | E | F50 | F25 | P10 | P25 |
|---|---|---|---|---|---|---|
| Q1 (10) | 21 / 0 / 13 / 0 / 0 / 15 | 69 / 46 / 39 / 0 / 0 / 27 | 67 / 46 / 37 / 16 / 8 / 27 | 67 / 46 / 37 / 0 / 0 / 27 | 69 / 46 / 39 / 0 / 0 / 27 | 74 / 53 / 36 / 13 / 5 / 26 |
| Q2 (10) | 7 / 0 / 2 / 0 / 0 / 10 | 26 / 20 / 9 / 0 / 0 / 13 | 36 / 30 / 9 / 1 / 0 / 14 | 29 / 23 / 8 / 0 / 0 / 13 | 40 / 34 / 11 / 0 / 0 / 13 | 43 / 37 / 12 / 8 / 6 / 14 |
| Q3/R3 (15) | 0 / 0 / 0 / 0 / 0 / 18 | 0 / 0 / 0 / 0 / 0 / 21 | 119 / 119 / 10 / 26 / 13 / 10 | 55 / 55 / 14 / 0 / 0 / 22 | 6 / 6 / 5 / 0 / 0 / 25 | 48 / 48 / 8 / 4 / 1 / 18 |
| R2 (5) | 4 / 0 / 3 / 0 / 0 / 7 | 24 / 17 / 14 / 0 / 0 / 12 | 26 / 17 / 19 / 14 / 6 / 12 | 26 / 17 / 17 / 0 / 0 / 12 | 26 / 18 / 14 / 0 / 0 / 12 | 40 / 31 / 17 / 6 / 1 / 9 |
| match (24) | 32 / 0 / 18 / 0 / 0 / 32 | 119 / 83 / 62 / 0 / 0 / 52 | 119 / 83 / 64 / 31 / 14 / 52 | 119 / 83 / 62 / 0 / 0 / 52 | 135 / 98 / 64 / 0 / 0 / 52 | 157 / 121 / 65 / 27 / 12 / 49 |
| no-match (16) | 0 / 0 / 0 / 0 / 0 / 18 | 0 / 0 / 0 / 0 / 0 / 21 | 129 / 129 / 11 / 26 / 13 / 11 | 58 / 58 / 14 / 0 / 0 / 22 | 6 / 6 / 5 / 0 / 0 / 25 | 48 / 48 / 8 / 4 / 1 / 18 |
(Rows "match"/"no-match" split all 40 turns by whether the query matches any cluster. "Resident seeds added" = sum over turns of ceil(n·x/100), n = residents when recall ran.)

What the fallback does on the no-match turns (Q3/R3 + turn 16):
- **E**: admits nothing; the context block shows the 15 top residents, 21 useful on-topic sightings over 16 turns.
- **F50**: admits 129 graph-only items (10 on most of these turns, the budget), 11 of them on-topic useful. They fill the store (first eviction turn 20, 57 evictions over the run, 26 of them on no-match turns) and the block on those turns shows only 4-10 items, mostly the new ones: useful shown 21 -> 11. The other 31 evictions fall on later matching turns, which find the store full.
- **F25**: half the seeds, 58 admissions on no-match turns (14 useful), 0 evictions, useful shown 22 (= E). Its overall gain is first-visit coverage (42/70 vs 36) and fewer, cleaner items shown (186 / 0.40).
- **P10**: adds 1-6 resident seeds on every turn. On no-match turns it admits only 6 items (5 useful); on matching turns it adds 16 admissions over E (15 graph-only). 0 evictions. Its gain is revisit coverage (19/47 vs 14) and useful shown (77 vs 73); first-visit coverage is unchanged (36/70).
- **P25**: 411 seeds added, 205 admitted, churn back (31 evictions, 13 useful, store full at turn 21), off-topic 38%.
- On matching turns, the fallback arms recall what E recalls (same admitted counts: 119 / 83 / 62); F50's 31 evictions there come from the store the no-match turns filled.

Mechanism note (**observed** in the per-turn table, mechanism **inferred**, not traced in the block code): on a turn where recall admits nothing, the context block shows 15 residents; on a turn where recall admits items, it shows about as many items as it admitted (here 1-10). So a fallback that admits a few off-topic items on a no-match turn can show fewer useful items than admitting none.

## Ranking (no default changed; andy picks)

1. **P10, E + top 10% every turn.** No churn, precision 0.49 (E 0.52), off-topic graph admissions 15% (E 13%), highest useful shown (77) and revisit coverage (19/47). Costs: 22 more admissions than E, first visit no better than E, hubs lost 10 vs 9.
2. **F25, E + top 25% only on no-match turns.** No churn, best first-visit coverage (42/70) and best precision of shown (0.40), useful admitted 76. Costs: precision of admitted 0.43, 26% off-topic graph admissions, hubs lost 15, shows fewer items in total (186).
3. **E alone.** Cleanest admissions (0.52, 13% off-topic), no churn, but no graph recall on no-match turns.
4. **P25, E + top 25% every turn.** Churn returns (31 evictions, 13 useful evicted), precision 0.36, no coverage gain over E except revisit 15/47.
5. **F50, E + top 50% on no-match turns (the plan).** Most churn (57 evictions, 27 useful evicted, 1 hub), precision 0.30, 47% off-topic graph admissions, useful shown 63 (below E's 73), hubs lost 18.

Trade-off in short: on this replay, adding resident seeds helps only while the added share stays small. At 50% (the plan) or at 25% on every turn the churn E removed comes back. 10% on every turn and 25% as a fallback are both churn-free. P10 buys revisit coverage and useful items shown; F25 buys first-visit coverage at the price of noisier admissions. P10 ranks first because it is closest to E in precision and wins on items shown. A reviewer who values first-visit reach of linked items more would swap 1 and 2.

## Limits

- One synthetic journal (seed 20261111, 372 clusters, 3-turn topic blocks), 40 turns, capacity 60, budget 10. This ranks the five settings on that replay; it does not fix a best x, and the boundary between "churn-free" and "churn" (somewhere between 10-25% additive and 25-50% fallback here) depends on store size, link density and run length.
- No-match turns here are all the topic-free follow-ups (Q3/R3) plus one Q2. How often real Telegram requests match no cluster is not measured.
- "Top x% most active" is read as top ceil(n·x/100) residents by STI (as focus/D), at least 1 seed. Other readings (by attention.total, a fixed count, floor rounding) were not tested. With few residents, 10% still adds 1 seed per turn.
- When both flags are set, a no-match turn uses the larger pct. That combination was not run.
- Seeds added from residents get the same treatment as E's keyword seeds (no self spread term; residents are never candidates either way).
- Reasoner and PLN off, as in the probe; real-engine tests not rerun.
- The context-block shrink on turns with recalls is inferred from per-turn counts, not traced in code.

## Refs

- Code: branch **hive/t-2026-11-13-wmtm-spread-seed-sweep** in the hive queue repo (/hive/protocosmo/.hive/queue/wmtm), base **af934da** (head of hive/t-2026-11-11-wmtm-spread-seeds-probe, as the order says). Not pushed. Like its base it is not on main a99c271.
- Files: wmtm/runtime_config.py, wmtm/context.py, wmtm/recall_bridge.py, wmtm/api.py, README.md, tests/test_recall_spread_sweep.py; reports/t-2026-11-13-wmtm-spread-seed-sweep/: REPORT.md, SHA256SUMS.txt, tools/ (gen_journal.py, probe_turns.py, check_rerun.py, analyse3.py: probe copies; run5.sh: exact commands; table5.py), data/ (turns.json, labels.json; journal.metta gitignored, regenerated by run5.sh), results/ (A, E, F50, F25, P10, P25: turns.jsonl + stdout.txt; arms.txt, rerun_check.txt, summary.json, turn_table.md, analyse_stdout.txt, table5.json, table5.md, table5_stdout.txt, suite.txt).
- Rerun all arms: `sh reports/t-2026-11-13-wmtm-spread-seed-sweep/tools/run5.sh /hive/protocosmo/workspace/projects/wmtm/repos <worktree of this branch>` (first folder holds probe-A at 265062e). One arm, from the report folder after `. env-gapcheck/env.sh` and `python3 tools/gen_journal.py --out data`: e.g. arm 2 = `env WMTM_RECALL_SPREAD_SEEDS=turn WMTM_RECALL_SPREAD_FALLBACK_PCT=50 python tools/probe_turns.py --code <worktree> --state <fresh dir> --data data --out results/F50` (arm 1: drop the pct variable; arms 3-5: FALLBACK_PCT=25, ADD_PCT=10, ADD_PCT=25).
