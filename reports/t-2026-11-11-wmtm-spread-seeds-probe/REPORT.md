# t-2026-11-11-wmtm-spread-seeds-probe: which spreading seeds stop the flooding?

## Summary

Asked: recall-budget-10 showed that the budget only slows the flooding, because 76% of graph-only admissions come from spreading out of residents of earlier topics. Add one flag for where spreading starts (default unchanged), then run the probe on identical inputs with budget 10 in four arms: A = keyword only (reference), C = all residents seed (today), D = the attention focus (top half of residents by STI), E = this turn only (this turn's keyword-matched items + the request item).

Answer: **E removes the churn on this probe, and it costs no useful reach compared with today (C); it increases it. D reduces the churn but does not remove it.** E had 0 evictions in 40 turns (C 243, D 158). E's store never filled (max 51 of 60), and the budget bound on only 6 turns (C 29). E's admitted items are almost as clean as keyword-only: precision 0.52 (A 0.56, C 0.15, D 0.26). Only 13% of E's graph-only admissions belong to another topic (C 76%, D 54%). Useful reach, E against C: on-topic useful shown 73 against 50, first-visit coverage 36 against 33 of 70 (linked items 19 against 16), revisit coverage 14 against 10 of 47. No hub was evicted. D reaches the most linked items: first visit 43/70 (26 linked), revisit 16/47, useful admitted 74. But D still evicts 64 useful items (9 of them hubs), and its store sits at capacity from turn 24 on. E has a cost of its own: on turns whose query matches nothing by keyword (the Q3/R3 turns, the topic-free follow-up "consequence then, what follows next"), E has no seeds, so graph recall admits nothing there, as in A. D and C keep spreading from residents on those turns. Today's default is unchanged: with the flag unset, this branch reproduces recall-budget-10's C run exactly. The full suite passes (1249 passed, 41 skipped, 6 xfailed). As the order says, no option is picked and no default changed: andy decides. One open point for that: the design's §8.1b says "Already-active WMTM items spread activation", which reads like C. E's seeds are mostly not yet resident. Status: done, waiting for review. The code is staged in the hive queue repo on branch hive/t-2026-11-11-wmtm-spread-seeds-probe (base 207c382), not pushed.

## Design reading (what each value means)

- §3.3 (line 99): recall should "Boost items connected to currently-active WMTM items (spreading activation via EvidenceFor edges)". §8.1b (line 312): "Spreading Activation: Already-active WMTM items spread activation through the LTM graph".
- §3.1 (line 72): get_active_set returns "items sorted by STI descending (the "attention focus")". §9.2 (line 359): inference runs "only ... on items in top-50% STI (the attention focus)".
- So "currently-active" can be read three ways. **C** = all residents (§8.1b, today's code). **D** = the §9.2 attention focus, applied to recall's seeds as well. **E** = this turn's request, which the order defines. §3.1 calls the whole sorted set "the attention focus", while §9.2 gives the top 50%. D uses §9.2's reading because the order names it.

## Change (wmtm/, 5 files; flag default = today)

- runtime_config.SPEC: `recall_spread_seeds` (env `WMTM_RECALL_SPREAD_SEEDS`), str, default **all**, values all | focus | turn (case and spaces ignored). Any other value means all. README flags-table row added.
- context.recall_spread_seeds(cfg) validates the value. context.request_item_id(user_msg, cfg) returns the id admit_request_item gives this turn's request item. admit_request_item now uses the same helper (same id, same text).
- RecallBridge.recall(..., spread_seeds="all", request_id=None) and RecallBridge.spread_seed_ids(mode, query_terms, store, request_id):
  - **all**: every resident, the same set object as before. The default path is the old code path.
  - **focus**: ceil(n/2) of the n residents by attention.sti. Ties keep get_active_set order. The ranking is by STI, not get_active_set's attention.total (a test covers this).
  - **turn**: every cluster, resident or not, that matches this turn's query by keyword (layers 1-2 of _score_cluster score > 0; RecallBridge._keyword_matches, tested equal to that condition), plus the request item id. The request item is not a journal cluster. It has no EvidenceFor or PromotesFrom edges, so it spreads nothing in the LTM graph (tested). Its id is passed so that this holds if that changes.
  - The seeds replace the residents only in layer 5: the 0.5 direct-link weights and the depth-2 spread. **Residents are still never candidates.** Nothing else changes: the floor 0.1, the weights, the starting STI and the recall budget 10.
  - Under focus/turn, a cluster that is itself a seed gets no spread term (exclude_seed_self). That term would only be its own hop-0 activation, +0.2, never a link. It matters only for E, where keyword hits are seeds and candidates at once. Under all, the resident relevance stimulus keeps scoring residents against all residents, as before.
- api.context_for: with the flag unset or all, it makes the old call `rb.recall(user_msg, store, top_k=..., floor=...)` with no new arguments (tested with a spy). Otherwise it passes spread_seeds and request_id. The relevance stimulus (context.relevance_stimulus) and request_relevance are not changed. They score residents for STI and ranking and admit nothing.

## Tests (tests/test_recall_spread_seeds.py, 67 tests)

- Config: SPEC default all, env and flag read, invalid value gives all.
- **C / all**: on a hand-built store (residents H 90, X 80, L 5, L2 4 with LTI 1000, R 3 matching "zephyr"), every resident's linked cluster is recalled, and a cluster linked only to a non-resident keyword hit is not. Negative control: focus drops the link to low-STI L2.
- **D / focus**: the seeds are {H, X, L} (3 of 5 by STI). L2 has the highest attention.total but is excluded. Clusters linked to L2 and R are not recalled, keyword hits are unaffected, and rounding is checked (1 resident gives 1 seed, 4 give 2). Negative control: all recalls them.
- **E / turn**: the seeds are {K (fresh keyword hit), R (resident keyword hit), request id}. A cluster linked to K or R is recalled; clusters linked only to non-matching residents are not. Negative control: all gives the opposite. A seed gets no self-boost: K's score is the same as under all, and without the exclusion it would be 0.2 × 1.3 higher. The request id changes nothing.
- **Seeded property tests** (10 seeds × focus/turn): on random 70-cluster graphs and 16-resident stores, every graph-only candidate is within reach of the mode's seeds (a direct link or the depth-2 spread). The focus seeds are exactly the top ceil(n/2) by STI, and residents are never candidates. Negative control (10 × 2, three worlds each): under all, graph-only candidates outside those seeds' reach exist, so the property is not vacuous.
- **Default unchanged (acceptance 1)**: 6 seeded 10-turn scripts through WMTM.observe + context_for under a fixed clock. Flag unset gives exactly the same admissions and context blocks as all. Negative control: on the same scripts, focus or turn admits something else (6/6). API wiring: an env value reaches recall with the request item's id, and the unset flag makes the old call.
- **Against 207c382** (the test file in a copy of the recall-budget-10 worktree, results/tests_on_207c382.txt): 61 fail, 6 pass. The 6 are the unset-equals-all API tests, which hold trivially on code that has no flag.
- **Full suite** (results/suite.txt): **1249 passed, 41 skipped, 6 xfailed** in 28.6 s. That is recall-budget-10's 1182 / 41 / 6 plus the 67 new tests. It ran in the env-gapcheck venv (Python 3.10.22) with the vendored-engine variables unset, as in the previous tasks. The real-engine tests were not rerun: this change touches neither the reasoner nor PeTTaChainer.

## Probe: identical inputs

- The journal generator, harness, rerun checker, analysis, turns.json and labels.json are byte-identical copies of recall-budget-10's (= the probe's): gen_journal.py d5c01df0…, probe_turns.py 3b445581…, check_rerun.py 9f132e79…, analyse3.py de5708d3…, turns.json b4390070…, labels.json 0e2a35d9… (SHA256SUMS.txt). The journal was regenerated with seed 20261111: sha256 5e93b344…71bd0, the probe's hash. Each arm's turns.jsonl meta records the journal and turn hashes, and analyse3.py asserts they are equal.
- Fixed clock (1794350000 + 60 s/turn), WMTMConfig(reasoner="off", use_pln=False), capacity 60, recall_budget 10 (default, not touched), floor 0.1. Recorders refuse pc_shadow and parse_cache calls: 0 calls in every arm. There were 0 parse calls and 0 errors. Nothing ran on pop-os.
- Arms: A = worktree probe-A at 265062e (clean). C, D, E = this branch's worktree with WMTM_RECALL_SPREAD_SEEDS unset, focus and turn (tools/run4.sh).
- **Reproduction**: tools/check_rerun.py against the committed recall-budget-10 run gives identical_modulo_writeback_ids true for A and for C with the flag unset (results/rerun_check.txt). Every C number below equals recall-budget-10's C.
- results/table4.json comes from tools/table4.py, which reads summary.json (analyse3.py, unchanged) and adds "hubs lost". A hub lost is an on-topic useful hub that A showed on a turn and the arm did not. "Evicted in-turn" means it was resident at turn start in that arm and evicted by that turn's admissions. Every probe turn is a keyword query.

## Results (whole run, 40 turns)

| | A keyword only | C all residents (today) | D attention focus | E this turn only |
|---|---|---|---|---|
| admitted (new, recalled) | 32 | 339 | 290 | **119** |
| of which graph-only | 0 | 304 | 252 | 83 |
| on-topic useful admitted | 18 | 50 | **74** | 62 |
| **precision of admitted (on-topic)** | 0.56 | 0.15 | 0.26 | **0.52** |
| graph-only admissions from another topic | n/a | 231 of 304 (76%) | 137 of 252 (54%) | **11 of 83 (13%)** |
| **evictions (capacity)** | 0 | 243 | 158 | **0** |
| caused by a graph-only admit | 0 | 224 | 146 | 0 |
| **useful evicted** (hubs among them) | 0 | 111 (35) | 64 (9) | **0** |
| first turn with an eviction | none | 14 | 17 | none |
| turns with the store at capacity (60) | 0 (max 26) | 23 | 15 | 0 (max 51) |
| turns the budget (10) binds | 0 (cut 15) | 29 | 19 | 6 |
| **useful shown (on-topic)** | 50 | 50 | 67 | **73** |
| items shown / precision of shown | 261 / 0.19 | 241 / 0.21 | 237 / **0.28** | 323 / 0.23 |
| **first-visit coverage** (hubs + linked) | 17/70 (17+0) | 33/70 (17+16) | **43/70 (17+26)** | 36/70 (17+19) |
| **revisit coverage** | 9/47 | 10/47 | **16/47** | 14/47 |
| **hubs lost vs A** (turns) | – | 19 (13) | 18 (11) | **9 (8)** |
| of which evicted in-turn | – | 4 (turns 27, 32, 36) | 0 | 0 |
| useful sightings gained vs A | – | 19 | 35 | 32 |
| keyword hits cut by the budget | 0 | 1 | 2 | 2 |

Keyword hits cut by the budget: all were off-topic substring hits (topic-9 hubs on turn 19, a topic-6 turn, score 0.65). No on-topic keyword hit was cut in any arm. Hubs lost without in-turn eviction (all of D's and E's; Q3/R3 turns) were displaced from the 15-item context block by other items. They were not evicted.

Per turn (results/turn_table.md, per_turn in summary.json):
- C: from turn 13, 10 in and (from turn 18) 10 out every turn, as in recall-budget-10.
- D: the store fills at turn 24 and from turn 25 churns 3-10 items a turn (10 on most turns).
- E admits in bursts on keyword-hit turns (7, 6, 10, 10, 10, …) and 0 on the Q3/R3 turns. Its store stays between 8 and 51 because stale cleanup and decay remove items faster than E admits them.

By turn kind, admitted / on-topic useful shown:
- Q1: C 70/14, D 63/15, E 69/27 (A 21/15).
- Q2: C 86/16, D 70/19, E 26/13 (A 7/10).
- Q3+R3: C 133/14, D 110/26, E 0/21 (A 0/18).
- R2: C 50/6, D 47/7, E 24/12 (A 4/7).

## Answer

- **E (this turn only) removes the churn** on this probe: 0 evictions against 243, the store never reaches capacity, and the budget binds on 6 turns instead of 29. It also removes most of the noise source the probe found: only 13% of its graph-only admissions belong to another topic, against 76%. Its admitted precision (0.52) is close to keyword-only (0.56).
  - **Cost in useful reach against today (C): none on any reported measure.** Useful shown 50 → 73, first-visit coverage 33 → 36 (linked 16 → 19), revisit 10 → 14, useful admitted 50 → 62, hubs lost 19 → 9 with none evicted.
  - **Cost against D:** fewer linked items reached (first visit 36 vs 43, linked 19 vs 26; revisit 14 vs 16; useful admitted 62 vs 74). On turns whose query matches nothing by keyword (Q3/R3: "consequence then, what follows next"), E has no seeds and admits nothing from the graph, as A. That is where D gets its extra reach (Q3+R3 useful shown: D 26, E 21, A 18, C 14).
- **D (attention focus) reduces the churn but does not remove it.** It has 35% fewer evictions than C (158 against 243), 64 useful evicted (9 hubs) and a store at capacity from turn 24, churning up to 10 a turn. Precision is 0.26. D is the best arm for useful reach (first visit 43/70, revisit 16/47, useful admitted 74, precision of shown 0.28). It still pays for that reach with evictions and 54% off-topic graph admissions.
- **C** is unchanged (= recall-budget-10).

## Limits

- Synthetic only: one seed, the probe's journal (3-turn topic blocks, its link ratios, capacity 60), 40 turns. E never reaching capacity is a result for this journal and run length. A longer run, denser keyword matches or a different capacity could make E fill the store too. That was not tested.
- E's reach depends on keyword hits. On a turn with no keyword hit, E does no graph recall at all. The probe's Q3/R3 turns are such turns (0 positive candidates in A and E). They are the follow-up questions that spreading from residents is meant to serve, but whether real Telegram requests often match nothing is not measured here.
- The request item seeds nothing: it is not a journal cluster and has no edges. In E the seeds are in practice this turn's keyword hits.
- Under E, a keyword-hit seed gets no self spread term (+0.2 × recency). Without the exclusion, every keyword hit would get a uniform bonus that comes from no link. This is a choice the order does not cover, and it is flagged here.
- The harness's per-candidate "spread" log field calls _spreading_activation_for without exclude_seed_self. In E it therefore shows +0.2 for keyword-hit seeds. Recall's scores and every table number are unaffected, and analyse3.py does not read that field.
- The flag applies to recall's candidate scoring only. The resident relevance stimulus and the context ranking still use all residents.
- Reasoner and PLN are off, as in the probe. The real-engine tests were not rerun (untouched code).
- The arm's mode is set by run4.sh through the environment and is not written in turns.jsonl meta. D and E differ from C in every summary number, and C reproduces the unset run exactly.

## Refs

- Code: branch hive/t-2026-11-11-wmtm-spread-seeds-probe in the hive queue repo (/hive/protocosmo/.hive/queue/wmtm), base **207c382** (head of hive/t-2026-11-11-wmtm-recall-budget-10, as the order says). Not pushed. Like its base, it is not on main a99c271 (main lacks the graph-recall floor-replay chain).
- Files: wmtm/runtime_config.py, wmtm/context.py, wmtm/recall_bridge.py, wmtm/api.py, README.md, tests/test_recall_spread_seeds.py. reports/t-2026-11-11-wmtm-spread-seeds-probe/: REPORT.md, SHA256SUMS.txt, tools/ (gen_journal.py, probe_turns.py, check_rerun.py, analyse3.py: copies; table4.py; run4.sh: exact commands), data/ (turns.json, labels.json; journal.metta is gitignored and is regenerated by run4.sh), results/ (A, C, D, E turns.jsonl + stdout.txt; summary.json, turn_table.md, analyse_stdout.txt, table4.json, rerun_check.txt, suite.txt, tests_on_207c382.txt).
- Reproduce: `sh tools/run4.sh /hive/protocosmo/workspace/projects/wmtm/repos <worktree of this branch>` (the first folder holds probe-A at 265062e), then `python3 tools/table4.py --data data --results results`.
