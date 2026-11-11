## Summary
andy asked for the design's recall_relevance_floor (0.1) and a 0.5 direct weight for PromotesFrom (the same as EvidenceFor), with tests, and then a live-path replay of the same 20 notes from frozen parses: A = 265062e (base), B = this branch (26e7769). Both changes are in, and each test has a negative control. The floor/weight tests pass (10/10), and so does the full suite (1146 passed, 41 skipped, 6 xfailed). The replay ran 12 arms, each 40/40 turns with 0 errors and 0 parse calls.

Result: A and B give the same per-turn rows in every arm. The count rule HOLDS in all arms. Mesto §11 W1/W2/W3 are 0 in every arm. noseed p3: 6 correct, 0 wrong, 1 unclear, 1 not judged, in both A and B. The graph-only path was never reached, so this replay does not show whether graph-only candidates filling the budget hurts. With the seed journal, keyword matches fill the whole 15-item budget on every user turn (300 candidates and 72 admitted per arm, 0 graph-only). Without the seed, the journal has no EvidenceFor/PromotesFrom edges and recall finds 0 candidates. Still open for andy: testing graph-only admission needs a harness where keyword recall leaves room in the budget (for example a smaller seed, or a query with few keyword hits). I did not pick a fix, per the order.

Supersedes: t-2026-11-10-wmtm-graph-recall

# t-2026-11-10-wmtm-graph-recall-floor-replay

## Pins
A 265062eb, B 26e77694 (branch hive/t-2026-11-10-wmtm-graph-recall-floor-replay, on b9c9d51). PeTTaChainer b6aacc68 (~/scratch/ppv/pc, HEAD exact). PeTTa p1-engine/petta-3681b9b (tree sha ea8227004b29b3bc, 637 files, the same directory for every arm). Man Hin 533c2274 is present in scratch/upstream-latest/sph but not exercised (0 parse calls). Caches (frozen, read-only): p3 = nov5_1f1a7a6f (sha 839129a6f0b23639), 533 = ppv_r1_533c2274 (a839f2972a888b3b), f44 = nov9_f44d7b74 (b96748ca2aad51bb). Seed journal: the live journal snapshot e0b6f1d93714038a with the 20 note blocks removed, giving 77c7f485c02be6bc (40522 EvidenceFor, 148 PromotesFrom). It is not in the repo.

## Item 1: code
- wmtm/recall_bridge.py: recall(floor=...) drops candidates with score <= floor. api.py passes runtime flag recall_relevance_floor (WMTM_RECALL_RELEVANCE_FLOOR, default 0.1, design s8.2). Direct callers keep 0.0.
- A direct PromotesFrom link (either direction) gets +0.5 in spreading activation, the same as a direct EvidenceFor link.
- tests/test_recall_floor_weight.py: 10/10 pass, with a negative control for each change. Full suite: 1146 passed, 41 skipped, 6 xfailed in 11.45s. The gap suite (tests/test_design_s12_gapcheck.py) is part of it.

## Item 2-3: replay, per turn A vs B
Harness: tools/turn_loop.py and tools/run_arms.sh (from v3). Each note gives 1 user turn plus 1 automated tick, with GoalChainer v2 on and a sandbox state dir per arm. Recall is logged per call (ids, scores and planned STI only). graph_only = keyword-only score (graph=False) == 0. A's _score_cluster is keyword-gated, so in A graph_only is always 0 by construction. Recall scoring uses a fixed clock (time=1794350000) in every arm (see Deviations). Planned STI = max(score*10, 1).

### full arms (seed journal + 20 notes)

| turn | A cands | A admitted | A graph-only | A kw STI min-max | B cands | B admitted | B graph-only | B kw STI min-max |
|---|---|---|---|---|---|---|---|---|
| 0 | 15 | 15 | 0 | 59.2-112.2 | 15 | 15 | 0 | 59.2-112.2 |
| 1 | 15 | 15 | 0 | 53.8-59.2 | 15 | 15 | 0 | 53.8-59.2 |
| 2 | 15 | 15 | 0 | 50.0-53.8 | 15 | 15 | 0 | 50.0-53.8 |
| 3 | 15 | 11 | 0 | 45.0-49.5 | 15 | 11 | 0 | 45.0-49.5 |
| 4 | 15 | 1 | 0 | 43.1-43.1 | 15 | 1 | 0 | 43.1-43.1 |
| 5 | 15 | 2 | 0 | 44.1-53.8 | 15 | 2 | 0 | 44.1-53.8 |
| 6 | 15 | 1 | 0 | 43.0-43.0 | 15 | 1 | 0 | 43.0-43.0 |
| 7 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 8 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 9 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 10 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 11 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 12 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 13 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 14 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 15 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 16 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 17 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 18 | 15 | 1 | 0 | 44.1-44.1 | 15 | 1 | 0 | 44.1-44.1 |
| 19 | 15 | 0 | 0 | - | 15 | 0 | 0 | - |

Same per-turn rows in all six full arms (A and B, caches p3/533/f44): True

### noseed arms (20 notes only)

| turn | A cands | A admitted | A graph-only | A kw STI min-max | B cands | B admitted | B graph-only | B kw STI min-max |
|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 1 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 2 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 3 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 4 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 5 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 6 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 7 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 8 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 9 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 10 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 11 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 12 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 13 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 14 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 15 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 16 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 17 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 18 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |
| 19 | 0 | 0 | 0 | - | 0 | 0 | 0 | - |

Same per-turn rows in all six noseed arms (A and B, caches p3/533/f44): True


Totals per seeded arm (A and B the same): 20 user turns, 300 candidates, 72 admitted, 0 graph-only candidates, 0 graph-only admitted. Unseeded arms: 0 candidates. Evictions are 6 in each seeded arm and 7 in each unseeded arm, the same in A and B.

## Count rule and Mesto §11 per arm
Offline pc_shadow spec, judged by v3 tools/judge.py with the F3 v3 W1-W4 rules (DEVIATION_1 nwdef join kept) and the W4 table. No new hand verdicts. Per arm the judged spec is the non-empty spec with the most goals, and among those the latest (results/pairs.txt).

| arm | atoms | goals | proved | C/W/U/unjudged | W1/W2/W3 | count rule |
|---|---|---|---|---|---|---|
| full p3 A / B | 46 / 46 | 1 / 1 | 1 / 1 | 0/0/0/1 both | 0/0/0 | HOLDS |
| full 533 A / B | 27 / 27 | 0 / 0 | 0 | 0/0/0/0 | 0/0/0 | HOLDS |
| full f44 A / B | 25 / 25 | 0 / 0 | 0 | 0/0/0/0 | 0/0/0 | HOLDS |
| noseed p3 A / B | 291 / 291 | 8 / 8 | 8 / 8 | 6/0/1/1 both | 0/0/0 | HOLDS |
| noseed 533 A / B | 160 / 160 | 0 / 0 | 0 | 0/0/0/0 | 0/0/0 | HOLDS |
| noseed f44 A / B | 198 / 198 | 0 / 0 | 0 | 0/0/0/0 | 0/0/0 | HOLDS |

In the seeded arms the KB is near-empty. Keyword recall admits 15 seed clusters per user turn, the store reaches 60 items, and the 20 parsed notes get crowded out (1 of 20 resident at turn 10). So the seeded arms test recall admission, and the unseeded arms test the count rule and §11. 533 and f44 give 0 goals in A and B alike: this is the parser drift found in v3, not this branch.

## Does filling the budget hurt?
This replay cannot say. Review 1 finding 1 (direct EvidenceFor neighbours at 0.56-2.06 filling the budget) did not happen here. Every admitted item had a keyword score above 0, and the candidate lists of A and B were the same on every turn. The floor and the PromotesFrom weight therefore changed nothing on these 20 notes. No fix proposed (andy's decision).

## Deviations
- Fixed clock: the first run admitted different ids in A and B on p3 turns 9-10. The cause was wall-clock recency (B ran about 8 min later; T185901Z scored 4.4120 vs 4.4112). All arms were rerun with the fixed clock. The wall-clock runs are kept in /tmp/gfr/loop_wallclock as evidence (NOTES.txt 16:33-16:50).
- Some pc_shadow specs were saved as raw_items. tools/rebuild_raw.py rebuilds them, and the atom/goal counts match shadow.jsonl.
- pilotseed v1 was invalid (the seed copy never ran) and was rerun as pilotseed2 (NOTES.txt).
- v3 deviations carry over (one pin set, the journal mirror of mark_recalled).

Evidence: results/, tools/, NOTES.txt, SHA256SUMS.txt. No note text is in the repo.
