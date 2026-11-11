# t-2026-11-11-wmtm-recall-budget-10: Ben's recall budget (10 new items per cycle), then the graph-only probe in three arms

## Summary

Asked: wmtm should follow the design's recall_budget (at most 10 new items per cycle, "prevents flooding WMTM with recalled items in a single cycle"), on every recall path. Then the graph-only probe should be rerun on identical inputs in three arms: A = keyword only (265062e), B = graph recall with a top-15 cut (26e7769), C = graph recall with budget 10 (this branch).

Answer: **the budget of 10 does not remove the flooding or the evictions the probe found. It slows them down by about a third, and the useful items reached drop with it.** Over the same 40 turns C admitted 339 new items (B 471, A 32) and caused 243 capacity evictions (B 383, A 0). 111 of those evictions were planted-useful items (B 186) and 35 were keyword hubs (B 46). The 60-item store still fills on turn 14, as in B. From turn 13 on, every C turn admits exactly 10 items and evicts exactly 10. The budget binds on 29 of 40 turns. The admitted items are no cleaner: precision is 0.15 against B's 0.14 (A 0.56). 76% of C's graph-only admissions (231 of 304) are still items of an earlier topic, reached by spreading from items still resident from that topic. The cost is in useful items reached. On-topic useful items shown fell from 60 to 50, which is A's number. Planted-useful items shown during their topic's first visit fell from 37 to 33 of 70 (linked items 20 → 16). Revisit coverage fell from 15 to 10 of 47. On-topic useful admissions fell from 67 to 50. On 3 keyword turns C also evicted 4 resident hubs during the turn itself, hubs that B still showed. Context precision is unchanged (0.21). What remains is the probe's main noise source: every resident item seeds the spread, so the candidate pool is far larger than any per-cycle cap. As the order asks, this report does not try another fix. Status: done, waiting for review. The code is staged in the hive queue repo on branch hive/t-2026-11-11-wmtm-recall-budget-10, not pushed. The base ref is da2d9f2 (head of hive/t-2026-11-11-wmtm-graph-only-probe, as the order says); the code ref is the tip of that branch. The tests pass: the full suite (1182 passed, 41 skipped, 6 xfailed) and 36 new tests, which fail on B's code.

## Design reading: per user turn, per automated tick, or both?

The design counts per **cycle**. s8.3: "Each cycle: admit at most N new items (default: 10)". s10: "recall_budget: 10  # max new items per cycle". s4: recall is step 1 of each reasoning cycle. In wmtm a cycle is one value of the orchestrator's cycle counter:

- A **user turn** is one cycle. api.context_for runs the recall before orch.cycle(), under the same counter value; cycle() then increments it. The budget-skipped branch increments it too.
- An **automated tick** (the fast path, context.fast_path_automated) is also a cycle (it increments the snapshot's cycle), but it has **no recall step**. It admits only PeTTaChainer conclusions (derived items, which fall under the inference budget, not this one). So the budget applies there, but nothing recalled is admitted (tested).

Implemented: one budget per cycle, shared by every path that admits recalled items in that cycle. That covers the user-turn recall (api.py, formerly top_k=15) and orchestrator.cycle(recall_fn=...) (orchestrator._recall_from_ltm, which until now admitted everything recall_fn returned). A grep for store.admit / source_type 'recalled' / .recall( found no other recall-to-store path in wmtm/. pc_shadow builds a worker-side raw store, not the live one. The forgetting log's should_re_admit has no caller.

## Change (wmtm/, 5 files, +87/-3)

- runtime_config.SPEC: recall_budget (env WMTM_RECALL_BUDGET), int, default **10**. A value of 0 or less means no budget: the old top-15 user-turn cut and an unlimited recall_fn. That switch exists for the negative controls and replays. README flags table row added (the flags-sync test checks it).
- context.recall_budget(cfg): returns an int > 0 or None. An invalid value gives 10. context.RECALL_TOP_K_UNBUDGETED = 15.
- orchestrator: _recall_used = [cycle, n]. recall_slots(budget) gives the slots left in this cycle. take_recall_slot(budget) counts one new recalled item, or refuses when the budget is spent. The counter is saved in the state snapshot while its cycle is current, so a restart in mid-cycle does not reset it. _recall_from_ltm admits at most the slots left. When recall_fn offers more new items than that, the highest-STI ones are kept (ties in recall_fn order). Re-admitting a resident item is not a new item and is not limited.
- api.context_for: the recall cut is this cycle's slots left (rb.recall(top_k=slots)). The admission loop also takes a slot per new item and stops when none is left. is_duplicate_topic skips do not take a slot. The request item (source_type user) and derived items are not recall and are not counted.

Nothing else is changed: the floor (0.1), the weights, the starting STI (max(10·score, 1)), capacity and the spreading are as in B.

## Tests (tests/test_recall_budget.py, 36 tests)

- Config: SPEC default 10, flag/env read, invalid value → 10, 0 / negative → no budget.
- **Property, user turns** (12 seeds): seeded random journals (70 clusters, two of 8 words each, so a 1-3 word query matches far more than 10, plus 60 random EvidenceFor/PromotesFrom links) and random 12-turn scripts through WMTM.observe + context_for. Budgets are drawn from {1, 3, 5, 10, 12}. Every admit is recorded with the live cycle counter. Checked: new recalled items per cycle ≤ budget, and the maximum equals the budget, so the budget binds and the test is not vacuous.
- **Negative control** (4 seeds): the same scripts with the budget off admit more than 10 in some cycle (up to 15).
- Default without a flag gives 10 per cycle. Budget 10 admits exactly the first 10 of what budget 15 admits (the best candidates are kept).
- **Property, cycle(recall_fn)** (10 seeds, 6 cycles each, 0-29 offered rows): new items = min(budget, offered), and they are exactly the top-budget by STI. Negative control: budget off admits all 25. Resident re-admission is not limited.
- Shared budget: 7 slots taken by the user path leave 3 for recall_fn in the same cycle, and the next cycle is fresh. A user turn followed by a recall_fn in the same cycle admits 10, none of them from recall_fn. A spent budget survives snapshot/restore within the cycle.
- Automated ticks: three fast-path ticks after a user turn add no item.
- **Against B's code** (the test file copied into a copy of the 26e7769 worktree): 34 of 36 fail. The property tests fail on their assertions ({0: 15, 1: 15, ...}, "15 <= 10", "18 <= 4"), the API tests on the missing functions. The 2 that pass are the automated-tick test and the recall_fn no-budget control, which hold on B too.

Full suite (results/suite.txt): **1182 passed, 41 skipped, 6 xfailed** in 33.9 s. That is the floor-replay baseline of 1146 passed, 41 skipped, 6 xfailed, plus the 36 new tests. It was run the same way as the floor-replay suite: env-gapcheck venv (Python 3.10.22), with the vendored-engine variables unset, so the real-reasoner tests skip. The real-reasoner tests were also run on this branch with PeTTaChainer b6aacc68 on PeTTa 3681b9b (env-gapcheck/env.sh): tests/test_design_s12_engine.py, 2 passed in 74.6 s (results/engine_tests.txt). A full-suite run with the engine variables set was OOM-killed once (exit 137; the container's cgroup limit is 8 GiB, shared with the other bots), while stray workers of an earlier interrupted run overlapped it. A clean single rerun with the engine variables set reached 63% with no failure (every engine test up to there passed). It had not finished when this report was posted, because the real-worker tests take about 40 s each on this host. Its result is not claimed here.

## Probe rerun: identical inputs

- The journal generator, harness, turn script, labels and rerun checker are the probe's files, byte for byte: tools/gen_journal.py d5c01df0…, tools/probe_turns.py 3b445581…, tools/check_rerun.py 9f132e79…, data/turns.json b4390070…, data/labels.json 0e2a35d9… (the same sha256 as in the probe's SHA256SUMS.txt). The journal was regenerated with seed 20261111: sha256 5e93b344…71bd0, the probe's hash. Each arm's turns.jsonl meta records the journal and turn hashes, and analyse3.py asserts they are equal across the arms.
- Arms: A = worktree at 265062e, B = worktree at 26e7769 (both clean, git status empty), C = this branch's worktree. The same fixed clock (1794350000 + 60 s/turn), WMTMConfig(reasoner="off", use_pln=False), capacity 60, and refusing recorders for pc_shadow/parse_cache: 0 calls in all three arms. There were no PeTTa runs in the probe, no parse calls, no notes, and nothing ran on pop-os.
- **A and B reproduce the probe**: tools/check_rerun.py on the probe's committed turns.jsonl against this rerun gives identical_modulo_writeback_ids true for both (results/rerun_check.txt). Every A and B number below equals the probe report's.
- Analysis: tools/analyse3.py is the probe's analyse.py generalised to N arms, with the same metrics and label rules. One definition is adapted: "recall cut full" means recall() returned top_k candidates (15 for A/B, 10 for C).

## Results (results/summary.json; per-turn A/B/C table results/turn_table.md)

| whole run (40 turns) | A | B | C |
|---|---|---|---|
| admitted (new, recalled) | 32 | 471 | **339** |
| of which graph-only | 0 | 438 | 304 |
| useful for the turn's topic / noise | 18 / 14 | 67 / 404 | 50 / 289 |
| **precision of admitted (on-topic)** | **0.56** | **0.14** | **0.15** |
| precision of admitted (planted useful, any topic) | 0.63 | 0.49 | 0.47 |
| precision of graph-only admitted (on-topic) | n/a | 0.11 | 0.10 |
| most new items admitted in one turn | 4 | 15 | 10 |
| turns with the recall cut full (15 slots A/B; 10 slots C) | 0 | 26 | 29 |
| candidates cut by top_k / by floor | 0 / 0 | 751 / 583 | 926 / 613 |
| on-topic useful candidates cut by top_k | 0 | 38 | 51 |
| keyword candidates cut by top_k | 0 | 1 (off-topic substring hit, score 0.65, turn 19) | 1 (the same one, rank 30) |
| store evictions (capacity) / caused by a graph-only admit | 0 / 0 | 383 / 365 | **243 / 224** |
| planted-useful items evicted (hubs among them) | 0 | 186 (46) | **111 (35)** |
| first turn with an eviction (store at 60) | none (max 26) | 14 | 14 |
| context block: items shown, on-topic useful / noise | 261: 50 / 211 | 286: 60 / 226 | 241: 50 / 191 |
| **precision of shown (on-topic)** | **0.19** | **0.21** | **0.21** |
| distinct planted-useful items shown during their topic's first visit | 17 / 70 (all hubs) | 37 / 70 (17 hubs + 20 linked) | **33 / 70 (17 hubs + 16 linked)** |
| same, during the revisit turns (topics 0, 2, 4, 6, 8) | 9 / 47 | 15 / 47 | 10 / 47 |
| STI on admit: keyword min / max / mean | 6.5 / 183.9 / 91.0 | 6.5 / 183.9 / 93.9 | 6.5 / 183.9 / 91.3 |
| STI on admit: graph-only min / max / mean | n/a | 7.28 / 78.8 / 9.33 | 7.28 / 65.8 / 9.76 |

By turn kind (shown on-topic useful / noise): Q1 A 15/8, B 15/29, C 14/30. Q2 A 10/20, B 17/39, C 16/38. Q3+R3 A 18/180, B 19/142, C 14/99. R2 A 7/3, B 9/16, C 6/24.

**Per turn** (results/turn_table.md): new admissions per turn, B: 3 5 10 3 4 4 3 7 7 5 11 1 6 then 15 on every turn from 13 on (16: 12). C: identical to B on turns 0-9 and 12, where the budget did not bind. On turn 10 C admitted 10 against B's 11, and on turn 11 2 against 1. From turn 13 on C admitted 10 every turn. Evictions per turn from turn 14: B 11, 15, 12, then 15 each turn; C 1, 6, 8, 8, then 10 each turn. In both arms the store sits at capacity and turns over a budget's worth of items each turn.

**What the budget changed:**
1. **Flooding: capped, not removed.** The cap binds on 29 turns. The pool of candidates above the floor is far larger than 10 on those turns: 926 candidates were cut by top_k. Precision of what enters is unchanged (0.14 → 0.15), because the top 10 by score are drawn from the same mix. 349 of B's 438 graph-only admissions score 0.73 ((0.5 direct + 0.06 spread) × 1.3 recency), so the score barely ranks them.
2. **Evictions: fewer, not gone.** 383 → 243 (−37%). Useful evicted 186 → 111, hubs 46 → 35. C's graph-only admissions still caused 224 of the 243.
3. **Noise source: the same.** C's 304 graph-only admissions: 30 on-topic useful, 43 on-topic noise, 109 another topic's useful items, 122 another topic's noise. So 76% are off-topic (B: 75%). The floor cut 613 candidates (B 583), mostly depth-2 items.
4. **Keyword hits: still never cut.** The one top_k cut is the same off-topic substring hit as in B. But the churn reaches resident hubs on keyword turns. On turn 27 (Q1, topic 9), turn 32 (R2, topic 2) and turn 36 (R2, topic 6, 2 hubs), C showed none of 4 on-topic hubs that B showed. All 4 were resident at the start of the turn in C, were not candidates (residents are never candidates), and were evicted by that turn's 10 admissions. Against A, C dropped 19 on-topic useful sightings (all hubs) on 13 turns (Q3 7, R3 3, R2 2, Q1 1) and added 19. B dropped 19 on 12 turns (Q3 7, R3 4, R2 1) and added 29.

**What it cost in useful items reached:** on-topic useful admitted 67 → 50. On-topic useful shown 60 → 50, back to A's level: C's gain over A in sightings (19) is offset by its losses (19). First-visit coverage 37 → 33 of 70: the linked items, which only graph recall reaches, fell 20 → 16. Revisit coverage 15 → 10 of 47 (A 9). Context precision held at 0.21 because C also showed fewer noise items (191 against 226; the block was shorter, 241 items against 286).

## Conclusion

The design's recall budget is now enforced on every path that admits recalled items, per WMTM cycle, with a default of 10. On the probe's journal it **does not remove the flooding or the evictions**. It lowers their rate from 15 to 10 per turn: 28% fewer admissions, 37% fewer evictions, 40% fewer useful items evicted. The store still fills on turn 14 and then churns 10 items per turn. The admitted mix is just as noisy (precision 0.15), because 76% of graph-only admissions still come from spreading out of residents of earlier topics. The budget limits how much of that spread enters per cycle, not which part. The cost is about a quarter of the useful items graph recall reached (useful admitted −25%, useful shown −17% to A's level, linked items covered 20 → 16, revisit coverage 15 → 10), plus 4 hub sightings lost on keyword turns. What remains is unchanged from the probe: spreading from all residents, the flat 0.73 score of direct-link candidates, and the starting STI of graph-only items (7.28) all stay. The order excludes acting on them here.

## Limits

- Synthetic only, one seed, the probe's journal (link ratios, 3-turn topic blocks, capacity 60). The magnitudes depend on it. A journal with sparser links, or a capacity of 200 (the design's wmtm_capacity), would let the budget bind less often.
- Reasoner and PLN off in the probe, so derived items do not compete. The engine tests in the suite run the real PeTTaChainer, but not on the probe's data.
- "Cycle" is the orchestrator's counter. If a user turn ran out of time before the cycle and the tick (the counter is not incremented then), the next turn shares its cycle and its budget. That is strict per the design ("give inference and forgetting time to work between recalls"), but it could starve a turn on a very busy host. The probe never hits it (fixed clock).
- No automated ticks between the probe's user turns (as in the probe). Automated ticks admit no recalled items (tested), so they would not change C's admissions.
- Base: this branch is on hive/t-2026-11-11-wmtm-graph-only-probe (da2d9f2), as the order says. That branch is on floor-replay 7bc0072 (code = 26e7769) and is not in main a99c271 (main lacks 26e7769). A merge to main needs the floor-replay branch first.

## Files

wmtm/runtime_config.py, wmtm/context.py, wmtm/orchestrator.py, wmtm/api.py, README.md, tests/test_recall_budget.py. reports/t-2026-11-11-wmtm-recall-budget-10/: REPORT.md; tools/ (gen_journal.py, probe_turns.py, check_rerun.py: copies of the probe's; analyse3.py; run3.sh: exact commands); data/ (turns.json, labels.json; journal.metta is gitignored, as in the probe, and is regenerated by run3.sh with sha256 5e93b344…71bd0 recorded in SHA256SUMS.txt and in each arm's turns.jsonl meta); results/A, B, C (turns.jsonl, stdout.txt); results/summary.json, turn_table.md, analyse_stdout.txt, rerun_check.txt, suite.txt, engine_tests.txt; SHA256SUMS.txt.

Reproduce: sh tools/run3.sh <folder with worktrees probe-A (265062e) and probe-B (26e7769)> <worktree of this branch>.
