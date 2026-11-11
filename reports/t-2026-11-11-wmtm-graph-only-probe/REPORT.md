# t-2026-11-11-wmtm-graph-only-probe: does graph-only recall filling the budget hurt?

## Summary

Asked: on synthetic data that leaves room in the 15-slot recall budget, does graph-only recall (B, the floor-replay code 26e7769: floor 0.1, direct PromotesFrom 0.5) crowd out useful items or hurt recall, compared with keyword-only recall (A, its base 265062e)?

Answer: **it hurts admission precision and churns working memory, but it does not displace keyword hits, and what reaches the context block gets slightly better.** Over 40 identical turns B admitted 471 items against A's 32. 438 of B's were graph-only, and only 14% of B's admissions were useful for the turn's topic (A: 56%). B's recall cut was full on 26 of 40 turns. 75% of B's graph-only admissions (329/438) were items of an earlier topic, reached by spreading from items still resident from that topic. They filled the 60-item store by turn 14 and caused 365 of 383 capacity evictions, 186 of them planted-useful items (46 keyword hubs among them). Keyword hits were not crowded out of recall: the one keyword hit cut by the top-15 limit was an off-topic substring match. At the context level B showed 60 on-topic useful items against A's 50 (precision 0.21 against 0.19). B reached 37 of the 70 planted useful items during their topic's turns against A's 17. A can never show linked items, which carry no keyword. The cost: on 12 keyword-free follow-up or revisit turns, B's fresh graph-only batch pushed 19 sightings of the topic's hubs out of view. Choosing a fix (a cap on graph-only, a lower starting STI, or neither) is andy's decision. This report doesn't pick one.

Status: done, waiting for review. Staged in the hive queue repo on branch hive/t-2026-11-11-wmtm-graph-only-probe (code ref below), base ref 7bc0072 (head of hive/t-2026-11-10-wmtm-graph-recall-floor-replay). Not pushed to GitHub, as the order asks.

## Question and setup

- **A** = 265062e (keyword-only recall; the base of the floor-replay branch). **B** = 26e7769 (the floor-replay code: graph-only candidates, recall_relevance_floor 0.1, direct PromotesFrom weight 0.5). Both were checked out as detached worktrees from the hive queue clone of github.com/bgoertzel-sing/wmtm. The branch head 7bc0072 adds only report files on top of 26e7769 (git diff 26e7769 7bc0072 -- wmtm is empty).
- **Journal** (data/journal.metta, sha256 5e93b344…71bd0; generator tools/gen_journal.py, seed 20261111, deterministic: two generations compare equal byte for byte). It has 372 clusters: 10 topics; 17 keyword hubs (useful); 11 keyword distractors (noise); 33 useful and 36 noise depth-1 neighbours over EvidenceFor/PromotesFrom; 20 useful and 55 noise depth-2 neighbours over EvidenceFor; 200 unlinked background clusters. Topics 4 and 8 each have one heavy fan-out hub (3 useful + 10 noise depth-1 neighbours). Linked items carry no query keyword (asserted by the generator), so they can only arrive through the graph.
- **Turn script** (data/turns.json, the same file for both arms): per topic Q1 (two keywords), Q2 (the third keyword), Q3 (keyword-free follow-up); then revisits R2/R3 for topics 0, 2, 4, 6, 8. That makes 40 turns. Keyword hits per query (not yet resident): 0 to 4, histogram {0: 21, 1: 11, 2: 4, 3: 3, 4: 1} (results/leak_check.txt). So keyword hits never fill the budget.
- **Path**: the live API turn WMTM.observe() + WMTM.context_for(q): recall(top_k=15[, floor]), then store.admit(initial_sti = max(10·score, 1)), relevance stimulus, request item, stale cleanup, orchestrator cycle, context block. Config: WMTMConfig(reasoner="off", use_pln=False), capacity 60. The pc_shadow / parse_cache launchers are replaced by recorders that refuse (0 calls in both arms). There were no PeTTa/PeTTaChainer runs, no parse calls, no notes, and nothing ran on pop-os. Clock: time.time fixed at 1794350000 + 60 s per turn in both arms.
- **Logging** (results/{A,B}/turns.jsonl). Every cluster scored inside recall() is logged, including zero scores and those below the cut, with: score, keyword-only score, spread term, source (keyword / graph-only / zero), candidate rank, and cut reason (top_k / floor / zero / none). Every admit is logged with its initial STI and STI after; every eviction with its STI and the admit that caused it; plus the store before and after each turn, the context block, and the item ids it shows. labels.json is read only by tools/analyse.py and tools/leak_check.py, never by the harness.

## Results (results/summary.json; per-turn A/B table results/turn_table.md)

| whole run (40 turns) | A | B |
|---|---|---|
| admitted (new, recalled) | 32 | 471 |
| of which graph-only | 0 | 438 |
| useful for the turn's topic / noise | 18 / 14 | 67 / 404 |
| **precision of admitted (on-topic)** | **0.56** | **0.14** |
| precision of admitted (planted useful, any topic) | 0.63 | 0.49 |
| precision of graph-only admitted (on-topic) | n/a | 0.11 |
| turns with the 15-slot recall cut full | 0 | 26 |
| candidates cut by top_k / by floor | 0 / 0 | 751 / 583 |
| keyword candidates cut by top_k | 0 | 1 (an off-topic substring hit, score 0.65, rank 34, turn 19) |
| store evictions (capacity) / caused by a graph-only admit | 0 / 0 | 383 / 365 |
| planted-useful items evicted (hubs among them) | 0 | 186 (46) |
| context block: items shown, on-topic useful / noise | 261: 50 / 211 | 286: 60 / 226 |
| **precision of shown (on-topic)** | **0.19** | **0.21** |
| distinct planted-useful items shown during their topic's first visit | 17 / 70 (all hubs) | 37 / 70 (17 hubs + 20 linked) |
| same, during the revisit turns (topics 0, 2, 4, 6, 8) | 9 / 47 | 15 / 47 |
| STI on admit: keyword min / max / mean | 6.5 / 183.9 / 91.0 | 6.5 / 183.9 / 93.9 |
| STI on admit: graph-only min / max / mean | n/a | 7.28 / 78.8 / 9.33 |

By turn kind (shown on-topic useful / noise): Q1 A 15/8, B 15/29; Q2 A 10/20, B 17/39; Q3+R3 A 18/180, B 19/142; R2 A 7/3, B 9/16.

**What graph-only admission displaced:**
1. **From the recall cut: nothing useful.** Keyword scores (min 0.65, median 9.2, max 18.4) sit above graph-only scores (349 of 438 admitted graph-only items score 0.73, which is (0.5 direct + 0.06 spread) × 1.3 recency; max 7.88). The one keyword candidate cut was a planted hub of another topic, matched only by substring. Graph-only candidates displace each other: all 38 on-topic useful candidates cut by top_k were graph-only.
2. **From the store: a lot.** Graph-only items enter at STI 7.28. Capacity eviction removes the lowest STI, and each turn's 15 fresh graph-only items evict the decayed items of earlier turns: 95 useful depth-1 items, 45 useful depth-2 items, 46 hubs, and 197 noise or distractor items. A never reaches capacity (store ≤ 26 items).
3. **From the context block: a little, offset by gains.** Turn by turn against A, B dropped 19 on-topic useful sightings (all hubs) on 12 turns, all of them keyword-free follow-ups (Q3/R3) or revisits. It added 29 on-topic useful sightings (linked items A cannot recall). On keyword turns (Q1/Q2/R2) B showed every on-topic keyword hit A showed.

**Where the noise comes from:** of B's 438 graph-only admissions, 48 were on-topic useful, 61 on-topic planted noise, 165 another topic's useful items, and 164 another topic's noise. Every resident item seeds the spread, so after a topic switch the active set keeps pulling in the previous topics' neighbourhoods. The floor (0.1) removes the candidates reached only through the spread term, with no direct link to a resident item (a depth-2 spread is 0.018 × 1.3): 583 cuts, 534 of them depth-2 items. A depth-2 item is therefore recalled only after its depth-1 parent is resident (then it has a direct link, 0.5).

**Label leak check** (results/leak_check.txt): every linked text has 6 filler words for both labels. Ids are random hex. The median graph-only score is 0.728 for both useful and noise. The mean differs (0.66 against 0.48) because noise is weighted toward depth 2 (55 of 75 depth-2 items), which is graph position, not label.

**Reproducibility:** results/rerun_check.txt. A second run of each arm is identical, except for the ids of A's 5 journal write-back notes (ep-note-<wall-clock UTC>; journal.append does not use time.time). Those always score 0. B writes none, because its items churn out before write-back.

## Conclusion

On this journal, graph-only filling **hurts** the precision of what is admitted (0.56 → 0.14) and the stability of working memory (383 evictions, 186 of them useful). It does **not** crowd keyword hits out of recall. It **slightly helps** what the context shows (50 → 60 useful sightings, 0.19 → 0.21 precision, coverage of planted useful items 17 → 37 of 70), at the cost of hiding the topic's hubs on keyword-free follow-up turns. The main noise source is not noisy links next to the current topic. It is spreading from items resident from earlier topics. Which mechanism to change, if any, is andy's decision. Both options he named would act on finding 2: a cap on graph-only admissions per turn would bound the number of evictions, and a lower starting STI would change which items those evictions remove.

## Limits

- Synthetic only. The useful/noise ratio of the links (about 1:1 at depth 1, 1:2.75 at depth 2), the 3-turn topic blocks and the capacity of 60 drive the magnitudes. A journal with denser links or longer topic blocks would shift them.
- Reasoner off and PLN off, so derived items never compete for capacity or context slots. The order lets inference be skipped. The shadow worker, GoalChainer and parse feed were not exercised.
- The labels define "useful" as planted useful and on the turn's topic. That is a proxy for what an LLM would use, not a measurement of answer quality.
- One seed. The run is deterministic (fixed clock), so a second seed would test the journal's design, not the code. It was not run.
- No automated ticks between user turns (the fast path works on the state file, which the in-process orchestrator would overwrite).

## Files (reports/t-2026-11-11-wmtm-graph-only-probe/)

tools/gen_journal.py, tools/probe_turns.py, tools/analyse.py, tools/leak_check.py, tools/check_rerun.py, tools/run.sh; data/journal.metta, data/turns.json, data/labels.json; results/A/, results/B/ (turns.jsonl, stdout.txt), results/summary.json, results/turn_table.md, results/leak_check.txt, results/rerun_check.txt, SHA256SUMS.txt. No code under wmtm/ is changed.
