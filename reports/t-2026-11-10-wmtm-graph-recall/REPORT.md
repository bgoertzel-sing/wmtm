# t-2026-11-10-wmtm-graph-recall: recall follows the memory graph (GAP-1, GAP-2)

## Summary

andy asked for recall to work the way the design's "key insight" says (§3.3, §8.1b, §13.5): a cluster linked to something already in working memory should be recalled even when it shares no keyword with the request, and spreading activation should follow PromotesFrom links as well as EvidenceFor. Both now work. The early return that dropped every cluster with no keyword match is gone from the recall path. In its place, a cluster with no keyword match is scored on its graph links to the active items, using the existing weights. Unlinked clusters still score 0. PromotesFrom is followed in both directions, at depth 1 only. The GAP-1 and GAP-2 strict xfails are removed and pass, and so do 312 new tests on synthetic clusters, among them a 300-case property test showing recall never goes over its top_k budget and never returns a superseded or active cluster. Full suite: 1151 passed, 26 skipped, 6 xfailed (base: 837 passed, 26 skipped, 8 xfailed). The two xfails that left are GAP-1 and GAP-2; the other six gaps are untouched.

One thing needs a decision before merge. On the §12.3-style simulation, recall used to return 3.7 candidates per step on average. It now fills its budget: 14.9 of 15, and 11.1 of those come only through the graph. Most of those are weak depth-2 neighbours, scoring about 0.02, where a single keyword match scores 1.5 or more. They rank below every keyword match, so they only fill free slots, but on the live path each one is admitted with STI 1.0. The design has a recall_relevance_floor of 0.1 (§11) that wmtm does not implement. A floor of 0.1 would keep direct EvidenceFor neighbours (0.56) and drop depth-2 neighbours (0.018), but it would also drop direct PromotesFrom neighbours (0.06) unless they get the same 0.5 direct-link weight as EvidenceFor. That trade-off is a choice for Ben or andy, and I left it out of this change. The recall step is slower (median): 0.20 → 0.33 ms on the simulation and 46 → 61 ms on a synthetic 7,900-cluster journal. I did not run the live A/B replay; see Limits.

## Base and pins

- Repository: wmtm, branch hive/t-2026-11-10-wmtm-graph-recall, started from hive/t-2026-11-10-wmtm-design-gap-check at **265062eb3d9b0900d2b1ea991521f52351a394b2** (not yet on main; main is 27c1a41aaaeb). The work is one commit on top of 265062e.
- PeTTaChainer **b6aacc686675c2c3fd5758adbd2ee245e3e7a5a5** and PeTTa **3681b9baa28d005dfbad21ad9b5d46b243b1e323**: the engine tests in the suite (test_design_s12_engine, test_pc_*) ran on these trees through env.sh (WMTM_PC_VENDOR, WMTM_PC_PETTA). They are the trees the gap check verified against codeload tarballs.
- Man Hin's parser (leungmanhin/semantic-parsing-hitl) **533c2274**: recorded, but not exercised. The change does not touch parsing, and no parse calls were made.
- Upstream-first: no change to Roman's or Man Hin's code. The only production file changed is wmtm/recall_bridge.py. No live flags changed, nothing restarted, no note text anywhere.

## What changed (wmtm/recall_bridge.py)

1. **GAP-1.** _score_cluster gets a keyword argument graph (default False). recall() passes graph=True. When layers 1-2 (IDF term overlap, substring) score 0 and graph is True, the score is the layer-5 spread (_spreading_activation_for) alone. That covers the direct EvidenceFor link to an active item (+0.5 each, existing weight) and the depth-2 spread map (×0.2, decay 0.3, existing). The loop-noise factor and recency factor then apply as before. If the spread is 0 too, the score is 0, so an unlinked cluster is never a candidate. Layers 3-4 (bigrams, evidence-support bonus) belong to a keyword match and are skipped here. Bigrams are 0 anyway without a shared term. The support bonus is skipped so that a graph-only cluster ranks on graph evidence alone and cannot climb above keyword matches by support count. Keyword-matched clusters are scored exactly as before.
2. **Resident stimulus keeps its keyword gate.** context.relevance_stimulus scores residents with _score_cluster's default (graph=False), so that path is unchanged. Every resident is an activation seed itself, so opening the gate there would boost all residents on every turn. That would be a different change, outside this order.
3. **GAP-2.** A reverse PromotesFrom index (_promotes_from_targets). _activation_hop now knows its hop. _collect_activation_neighbors follows PromotesFrom in both directions (forward targets and reverse sources, like EvidenceFor) only from hop 0, i.e. to depth 1 (§8.1b). A node reached through PromotesFrom still follows EvidenceFor on the next hop: the PromotesFrom edge is at depth 1 and the EvidenceFor edge at depth 2, which is within §8.1b's "EvidenceFor depth 1-2". A PromotesFrom edge at depth 2 is not followed, whether it comes after a PromotesFrom hop or after an EvidenceFor hop. Supersedes is still not an edge.
4. **Kept.** Superseded clusters are dropped by parse_journal and never become candidates or graph nodes. top_k is unchanged. All weights are unchanged: 0.5 direct, 0.2 spread, recall decay 0.3, depth 2. _tokenize, _STOPWORDS and layers 1-2 are untouched, so keyword matching did not widen.

Diff: wmtm/recall_bridge.py +62/-24 (mostly docstrings plus the restructured layer 3-5 block). tests/test_design_s12_gapcheck.py: the two xfail markers removed (-4). New file: tests/test_graph_recall.py.

## Acceptance

| # | Criterion | Evidence |
|---|---|---|
| 1 | GAP-1 and GAP-2 strict xfails now pass, markers removed | test_s3_3_spreading_activation_recalls_linked_cluster_without_keywords, test_s8_1_spreading_activation_follows_promotes_from pass. xfailed 8 → 6 (full_suite.log) |
| 1 | every other test passes, including superseded and budget | test_s12_4_recall_never_admits_superseded, test_recall_top_k_limit (×2 files) pass. full_suite.log EXIT=0 |
| 2 | linked cluster, no keyword overlap, recalled | test_linked_cluster_without_keyword_overlap_is_recalled (EvidenceFor both directions). Disjointness asserted with the bridge's own tokenizer |
| 2 | unlinked cluster not recalled (negative control) | test_unlinked_cluster_without_keyword_overlap_is_not_recalled (a linked control in the same journal is recalled). test_graph_only_recall_needs_an_active_item |
| 2 | PromotesFrom reached at depth 1, not depth 2 | test_promotes_from_neighbour_reached_at_depth_1_not_depth_2 (also PF after an EF hop: not followed; EF after a PF hop: followed), test_promotes_from_followed_forward_from_the_promoted_item, test_promotes_from_depth_0_reaches_nothing, test_promotes_from_neighbour_recalled_without_keywords_but_not_at_depth_2 |
| 2 | superseded never recalled even when linked | test_superseded_never_recalled_even_when_linked (EF and PF links, both directions, one superseded cluster also the best keyword match) |
| 3 | budget never exceeded (property) | test_recall_budget_and_filters_property, 300 seeds. Random journals of 1-60 clusters with random EF/PF links and superseded sets, random active sets, queries and top_k 0-25. Checks: ≤ top_k, distinct, no active or superseded cluster, scores > 0 and sorted, every graph-only candidate is reachable under an independent restatement of §8.1b, and the result is the top_k prefix of the unbounded ranking |
| 3 | recall-step time on §12.3 simulation, before and after | below, bench_summary.json |
| 4 | full suite passes | 1151 passed, 26 skipped, 6 xfailed, EXIT=0 (full_suite.log). Base on 265062e: 837 passed, 26 skipped, 8 xfailed (baseline_suite.log) |

The new tests detect the gap: on the base tree, 9 of the 12 new non-property tests fail. Every test that expects graph recall or PromotesFrom fails, while the superseded and depth-0 tests and the 300 property cases pass (failing_on_base.log).

Extra guard tests: test_keyword_match_outranks_graph_only_neighbour (graph-only candidates fill free slots and do not displace keyword matches), test_graph_only_score_uses_existing_spread_weights (direct EF neighbour = 0.5 + 0.2×0.3 exactly), test_resident_relevance_stimulus_keeps_keyword_gate.

## Recall-step time and recall volume (bench_recall_step.py)

Interleaved, 5 runs each on the same host (loadavg about 4.7-5.3; other tenants), perf_counter around each recall() call. Synthetic data.

- **A: the §12.3 simulation** (100 cycles, capacity 20, seed 123, 8 useful + 52 background notes, 3 + 4 named per task). The fixed recall list is replaced by RecallBridge.recall(top_k=15) over a 60-cluster synthetic journal with one EvidenceFor link per note and a PromotesFrom link on every fifth note.
- **B: scale.** 7,900 synthetic clusters, 1-2 EF and on average 0.2 PF links each, 40 active items, 30 queries, top_k 15.

| | before (265062e) | after |
|---|---|---|
| A recall step, mean of 5 run means | 0.208 ms (0.198-0.220) | 0.361 ms (0.332-0.388) |
| A recall step, median of run medians | 0.195 ms | 0.335 ms |
| A candidates per step, mean / max (budget 15) | 3.69 / 7 | 14.92 / 15 |
| A graph-only candidates per step, mean / max | 0 / 0 | 11.13 / 14 |
| A occupancy max (capacity 20), useful notes resident at end (of 8) | 20, 6 | 20, 6 |
| B recall step, mean of run means | 47.5 ms (46.3-48.4) | 63.9 ms (60.3-66.5) |
| B candidates max / graph-only mean | 15 / 0 | 15 / 0 |

Reading: the budget is never exceeded (max 15 = top_k in both parts, and the property test). In B, keyword matches always fill the 15 slots, so graph-only candidates never appear and recall output is the same kind as before. In A, where few clusters match, graph-only candidates fill the free slots. The extra time is _spreading_activation_for running for every cluster without a keyword match (the spread map itself is computed once per active set, as before). That cost is about +14 ms on 7,900 clusters. Computing the spread lookup once per recall() call would remove most of it. I left that out to keep the diff to what the order asked.

## Scoring rules

- A/B count rule: **not run** on the live path here. W1 counts come from inference over what recall admits, and this change can admit extra graph-only items when keyword matches leave budget free, so a live-path replay is the right check before merge. The in-repo replay and equivalence tests pass: test_replay_equivalence, test_f1_s9_replay, tests/replay. The identical-class-level-fact and DEVIATION_1 rules are unaffected: no inference or admission code changed.
- Mesto §11: the suite's Mesto tests pass (test_mesto_4..., test_mesto_9...). Recall is not one of the points those tests cover.

## Decisions taken (and alternatives)

- PromotesFrom "depth 1" = PromotesFrom edges only from the seeds, both directions. Alternative: allow PromotesFrom anywhere within one PromotesFrom edge of a path. Rejected because it would follow PromotesFrom at depth 2 after an EvidenceFor hop.
- Graph-only clusters skip the evidence-support bonus. Alternative: keep it, which lets support count (up to +2.0) push a graph-only cluster above keyword matches.
- relevance_stimulus left keyword-gated (see above).
- No relevance floor, no new weight for direct PromotesFrom links. Both are open for decision (Summary).

## Limits

- No live A/B replay (above). All timing numbers come from synthetic journals on a shared host.
- Graph-only candidates are weak by construction: direct EF about 0.56, direct PF 0.06, depth-2 0.018, before recency factors. Whether to admit the weak ones is the floor decision.
- api.py admits every candidate with STI max(score×10, 1), so a graph-only item enters at STI 1.0. Whether such items earn their place over time was not measured beyond the simulation's useful-resident count (6 of 8, before and after).

## Files (reports/t-2026-11-10-wmtm-graph-recall/)

REPORT.md; baseline_suite.log (265062e); full_suite.log (this branch); failing_on_base.log (the new tests on the base tree); bench_recall_step.py, bench.log, bench_before_run1-5.json, bench_after_run1-5.json, bench_summary.py, bench_summary.json.

## Commands

    . projects/wmtm/env-gapcheck/env.sh        # git 2.56.0, python 3.10.22 venv, swipl 9.2.9, pytest 9.2.0 (gap-check ENV.md)
    python -m pytest -q -rfs tests                                         # baseline_suite.log / full_suite.log
    python -m pytest -q tests/test_graph_recall.py                         # on a git-archive of 265062e -> failing_on_base.log
    PYTHONPATH=<tree> python reports/t-2026-11-10-wmtm-graph-recall/bench_recall_step.py <label> <out.json>
    python reports/t-2026-11-10-wmtm-graph-recall/bench_summary.py
