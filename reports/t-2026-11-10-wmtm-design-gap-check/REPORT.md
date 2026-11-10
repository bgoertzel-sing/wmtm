# t-2026-11-10-wmtm-design-gap-check: how far wmtm main is from Ben's design

## Summary
andy asked how far wmtm main (27c1a41) is from working as Ben's Sep 5 design doc describes, using the design's own §12 tests and Mesto's worked examples as the definition of "working". **Short answer:** the bookkeeping is mostly there. That covers the bounded store, decay, the forgetting log (keyed on the derivation, as Mesto asked), one eviction rule for every path, superseded clusters never recalled, and derived items that carry their sources back into the active set. All of it passes design-derived tests, including a full cycle on the real reasoner (PeTTaChainer b6aacc68 on PeTTa 3681b9b). The learning parts are missing. (1) A useful derived belief never reaches long-term memory with default flags, because `reasoner_writeback` is off. (2) Nothing tells a trivial restatement ("an X_Y is a Y") from a useful conclusion: an item counts as "used" just by being shown in the context. (3) The engine runs only deduction-style chaining. No induction, abduction or analogy is asked or proved. (4) Recall ignores the graph unless keywords already match, so the design's "key insight" does not work.

The new acceptance suite (`tests/test_design_s12_gapcheck.py`, `tests/test_design_s12_engine.py`) has 18 passing tests plus 8 known gaps marked strict xfail. A strict xfail turns red as soon as its gap is fixed. The environment problem is solved: the full upstream suite now shows **0 failures** (previously 11 environmental failures). Two things need a decision from Ben or andy: whether promotion should be on (live or by default), and whether induction and abduction are still in scope, now that the Oct 16 note marks §3.4 as historical. Nothing in production code was changed.

**Revision 2 (after review 1):** every ranked gap now has impact, size and owner (§5). 9 of the 11 are ours alone. Inference breadth (GAP-9) needs Roman's PeTTaChainer rules as well as our goal generation, and contradiction handling (GAP-6) may. None needs Man Hin, though Mesto's §2 example, still untested, probably does. The engine record now holds both rounds, plus the PeTTaChainer and PeTTa directories and content hashes, which match fresh codeload tarballs of b6aacc68 and 3681b9b.

## Pins and environment
- wmtm: github.com/bgoertzel-sing/wmtm **27c1a41aaaeb5335a747f8d279391f749ccf0345** (git clone; branch `hive/t-2026-11-10-wmtm-design-gap-check`). Main's own pin is PeTTaChainer bdae8d7e (runtime_config.py:171). As ordered, every engine run here overrides it with b6aacc68 via `WMTM_PC_VENDOR`.
- PeTTaChainer **b6aacc686675c2c3fd5758adbd2ee245e3e7a5a5** (rTreutlein/PeTTaChainer master HEAD per `git ls-remote`, 2026-11-10). PeTTa **3681b9baa28d005dfbad21ad9b5d46b243b1e323** (branch pr/compact-datatypes). I checked both vendored trees with `diff -rq` against fresh codeload tarballs of the full SHAs: identical.
- The environment is entirely in user space (no sudo, no container change). git 2.56.0 and Python 3.10.22 come from the conda-forge toolchain env (`~/toolchain/env`, micromamba 2.0.5). SWI-Prolog 9.2.9 comes from conda-forge (`~/opt/swipl929`, the same binary used for the Roman reruns). `janus_swi` 1.5.3 was built by pip against that swipl, inside a py3.10 venv (`projects/wmtm/env-gapcheck/venv310`), and `janus_swi.query_once('X is 1+2')` returns `{X: 3}`. pytest is 9.2.0. Settings are in `ENV.md` (env.sh). No new micromamba env was needed: the existing conda-forge envs already supplied git, swipl and python 3.10.
- Note: the old notes said "local swipl 9.3.36". That swipl was not used. The engine ran on 9.2.9.

## Baseline rerun (the 11 environmental failures)
Command: `. env.sh && python -m pytest -q -rfs tests` at 27c1a41, before the new tests were added. Log: `baseline_rerun.log`.
- Before (no janus or swipl): 803 passed, 11 failed, 31 skipped.
- **Now: 819 passed, 0 failed, 26 skipped (395.7 s).** All 11 failures are gone: the 4 "janus_swi missing" and the 7 warm_fail/exit 3 (test_f1_s11_subunit x2, test_name_resolve real-engine, test_p4_rule_goals, test_pc_admit, test_pc_shadow x2). Five tests that skipped before now run (the PC integration skips).
- The 26 remaining skips are all external inputs, not part of this order: WMTM_SEMPARSE_HITL checkout (18), WMTM_TEST_GC2_PYTHON (4), real-data replay WMTM_REPLAY_DATA (3), PETTA_PARSER/SWIPL for the codec test (1).
- With the new tests included (`full_suite.log`): **837 passed, 26 skipped, 8 xfailed, 0 failed, 0 xpassed** (468.7 s, exit 0). That is 819 upstream tests + 18 new passes, with the 8 strict xfails being the GAP tests.
- Rev 2, engine present (`full_suite_r2.log`, 2026-11-10 03:05-03:13 UTC): **837 passed, 26 skipped, 8 xfailed, 0 failed** (492.6 s, exit 0). One earlier rev-2 run (`full_suite_r2a_warmfail.log`, 02:57 UTC) had 1 failure: test_engine_s12_2 stopped at round 1 with `warm_fail`. Its worker record shows `warm_s` 93.9 s against 25-29 s in the other runs. The worker runs at nice 19 / idle priority, and host load was around 4-9 on 4 cores at the time (other tenants). *Inferred:* CPU starvation, not a code fault. The same test passed alone (`engine_run.log`) and in the full rerun. This is a real flakiness risk for engine tests on a loaded host.

## 1. Component table
"Live" means the flags file of the live bot. It is **not reachable** from this container, so I did not check it. Per the order, `reasoner_writeback` was absent from the live file on Oct 28. Per reports/t-2026-11-09-wmtm-live-path-replay-v3/PINS.md (quoted in the deploy-split report), live runs vendor rc2 4d2ab315, not main. "Seen working" uses this task's tests plus existing reports. No live evidence was gathered here.

| Part | Implemented (27c1a41) | Tested | Live flag / default | Seen working |
|---|---|---|---|---|
| §3.1 bounded store: capacity, admit, evict | store.py:17-39 (capacity validation), :43-87 admit (overflow evicts lowest STI, :132-144; the request item goes last); forgetting.py:61-67 policy over-capacity by lowest utility | test_wmtm_store.py; test_wmtm_simulation.py; new test_s12_4_capacity_never_exceeded_random_ops | none (capacity a constructor arg; design 200) | yes: 600 random ops, never over capacity; 100-cycle sim pinned at 20/20 |
| §3.2 items: recalled vs derived, derived_from, utility | item.py:16-46 (source_type recalled/derived/asserted/user, derived_from, utility, provenance) | test_wmtm_item.py; new test_s12_2_full_cycle…; engine test | — | yes: the engine conclusion "cat is a animal" admitted with derived_from [s1, s0] and PC provenance (engine_s12.json) |
| §3.3/§8 recall: relevance | recall_bridge.py:201-227 recall, :229-302 IDF overlap + substring + bigrams + evidence count + recency; api.py:253 top_k=15 | test_wmtm_recall_bridge.py, test_recall_bridge.py, test_wmtm_recall.py | — | yes (keyword path) |
| LTI boost | **not implemented**: LTMCluster (recall_bridge.py:59-70) has no LTI; no ECAN-driven sampling (§8.1c). AttentionValue.lti exists but is only consulted inside WMTM (attention.py:71) | none | — | no (GAP-10) |
| spreading activation over EvidenceFor / PromotesFrom / Supersedes | recall_bridge.py:386-473: EvidenceFor in both directions, depth 2, decay 0.3 (design 0.7); **PromotesFrom parsed (:34, :99) but not traversed** (:431-445); the spread is added only after a cluster already has keyword score > 0 (:263) | test_wmtm_recall_bridge.py; new test_s8_1_…evidence_for (pass), test_s3_3_… (xfail GAP-1), test_s8_1_…promotes_from (xfail GAP-2) | — | partly: it reorders keyword hits; it never recalls a keyword-less neighbour |
| superseded never recalled | recall_bridge.py:77-86, :127-160 (superseded clusters dropped at parse) | test_wmtm_recall_bridge.py; new test_s12_4_recall_never_admits_superseded | — | yes |
| recall budget | api.py:253 (top_k=15 per user turn, plus topic dedupe); design §8.3: 10 | indirectly via test_api.py | — | yes (value differs from design) |
| §3.4/§9 inference (PeTTaChainer) | pc_shadow.py (worker snapshot, goal pool), workers/pc_shadow; pc_admit.py:146-222 load_candidates (gate, min strength, caps, sources = live store ids), orchestrator.py:186-227 admission | test_pc_shadow.py, test_pc_admit*.py, test_f3v2_native_chain.py, test_p4_rule_goals.py; new test_design_s12_engine.py | `reasoner` (runtime_config.py:44, "" = pettachainer); `pc_shadow` default False | **deduction only.** The single proof on the synthetic KB is `conditional-implication (by sp1 (by sp0 …))` for (Inheritance cat animal). The Implies chain rain→wet→slippery is not proved (engine-native goals only, F3 v2). No induction, abduction, analogy or evidence-aggregation goal is generated. Derived beliefs do carry derived_from and do enter the active set (engine test) |
| §3.5 utility: used/missed recorded, changes survival | utility.py:27-33 (utility_score = use×2 + inferred_from×1.5 − miss×0.3); uses recorded when an item is **shown** in the context (api.py:337-339, F17) or its words overlap the response (context.py:316-331); _reinforce +2 STI on use (orchestrator.py:320-325) | test_wmtm_utility.py; new full-cycle and simulation tests | — | partly: in the sim, used items survive (8/8 useful notes resident at the end; background notes live 3.3 cycles). But "use" is mostly "was displayed", so it cannot separate useful from trivial (GAP-5) |
| §3.6/§7 forgetting: STI decay | attention.py:35-39 (STI ×0.90/tick; design 2%/tick); store.py:115-128 floor 0.01; forgetting.py:42-49 (0.05, derived 0.10) | test_wmtm_attention.py; new test_s7_1a… | — | yes |
| age limit | forgetting.py:51-58 (max_age 50, derived 20, min_utility 0.5); + wall-clock stale :70-89 and context.cleanup_stale_items | test_f1_s9_one_rule.py, test_wmtm_forgetting*.py | cleanup_* flags (runtime_config.py) | yes |
| capacity pressure, composite score, derived penalty | **not as designed**: store overflow is STI-only (store.py:132-144); policy overflow is utility-only (forgetting.py:61-67); no composite STI·0.4+util·0.4+LTI·0.2, no 1.5× derived penalty | new test_s7_1c… (xfail GAP-3) | — | no. In the 100-cycle sim all 487 evictions came from capacity overflow; the forget phase evicted 0 |
| contradiction resolution §7.1d | **not implemented** (no contradiction handling anywhere) | new test_s7_1d… (xfail GAP-6) | — | no |
| derived-item penalty | only stricter thresholds (derived STI 0.10, max_age 20: forgetting.py:91-101) | new test_s7_1_derived_items_forgotten_no_later_than_recalled | — | yes, in that form |
| forgetting log | forgetting_log.py:42-131 (derivation key = conclusion + sorted sources, F1 §4; FIFO cap 500); every path records it (orchestrator.py:167-170, :424-449) | test_wmtm_forgetting_log.py, test_f1_s4_forgetting.py, test_f1_s9_*; new §12.4 tests | `forget_one_rule` default True | yes, including on the engine path: the re-proved conclusion was dropped as "known" |
| §4 full cycle | orchestrator.py:349-421 (recall → reasoner → shadow launch → GoalChainer → forget → writeback) | test_wmtm_orchestrator.py, test_wmtm_integration.py; new full-cycle and engine tests | — | yes |
| §6.3/§10 promotion of durable derived beliefs, writeback | writeback.py:27-44 (DerivedBelief cluster with DerivedFrom), :106-114 (age ≥ 15, util ≥ 1.5); orchestrator.py:341-343 **drops PeTTaChainer items unless reasoner_writeback**; recalled enrichment :116-124 | test_wmtm_writeback.py; new promotion tests (default xfail GAP-4; flag-on pass) | `reasoner_writeback` default **False** (runtime_config.py:109); absent from the live file on Oct 28 (per order) | **On main with default flags: promotion never happens** for reasoner conclusions, which since Track L are the only derived beliefs. With the flag on it works: exactly one DerivedBelief cluster with both DerivedFrom links. Live: no (flag absent; live is rc2). Only `asserted` (mem.derive) items can be promoted by default |
| §6.3 WMTMDerivedForgotten note in LTM | **not implemented**; the log persists only inside the WMTM snapshot (orchestrator.py:96-121) | new test_s6_3… (xfail GAP-8) | — | no |

## 2. §12 tests (synthetic data)
All in `tests/test_design_s12_gapcheck.py` (memory lifecycle, using synthetic InferenceCandidate, the object PeTTaChainer admission produces) and `tests/test_design_s12_engine.py` (real worker). Result: `16 passed, 8 xfailed` and `2 passed (80 s)`.

**§12.2 integration**
- Full cycle recall → infer → use → decay → forget: **pass** (test_s12_2_full_cycle…). On the engine: **pass** (test_engine_s12_2_full_cycle_and_no_rederivation). PeTTaChainer proves cat→animal, which is admitted with sources [s1, s0], decays unused, and is forgotten. The next engine run proves it again, and admission drops it as known.
- Forgetting log prevents re-derivation over cycles: **pass**. Over 80 cycles the same never-used conclusion was admitted once.
- Promotion of a durable derived belief to LTM: **fails with default flags (GAP-4)**, **passes with reasoner_writeback=1**.
- Writeback of recalled-item enrichment: **passes** in the code's form (an EnrichmentNote after 30 cycles of use). It **fails** the design's form, new EvidenceFor links (GAP-7).

**§12.3 simulation** (100 cycles, capacity 20; 8 useful notes used whenever active, 52 background notes never used; 2 synthetic conclusions offered per cycle; `sim_s12_3.json`)
- Occupancy: mean 19.8, max 20, min over the last 50 cycles 20. No endless growth and no collapse, but it is always full.
- Evictions: 4.87 per cycle, all from capacity overflow. The forget phase (decay, age and utility triggers) evicted 0 items in 100 cycles.
- Inferences admitted: 1.74 per cycle (of 2 offered; the rest were duplicates or forgotten derivations). Forgetting log at the end: 487 records.
- Survival: all 8 useful notes were resident at the end and never evicted. Background notes lived 3.3 cycles on average (n=304). Derived items resident at steady state: about 1.
- Reading: stable and selective, but selection comes from STI reinforcement on use, not from the design's utility composite. In this regime the age, utility and composite rules never act.

**§12.4 properties**: capacity never exceeded (600 random ops, all source types) **pass**; every evicted derived item is forgotten or promoted **pass**; the forgetting log blocks identical re-derivation and survives a snapshot round trip **pass**; recall never admits superseded clusters **pass**.

**Engine record (revision 2).** `engine_s12.json` now holds `engine`, `round1`, `between_rounds` and `round2` (rerun 2026-11-10 02:56 UTC, `engine_run.log`: 2 passed in 74 s, exit 0):
- `engine.pettachainer_dir` = env-gapcheck/pettachainer-b6aacc68, `pettachainer_tree_sha256` = 26636ebf…7c0; `engine.petta_dir` = env-gapcheck/petta-3681b9b, `petta_tree_sha256` = f438eb3d…8a0. These are the trees the worker is given: pc_shadow.py:33 and :50 put `cfg["pettachainer_dir"]` and `petta_dir/python` first on sys.path. `round*.rec.petta` confirms the PeTTa module path.
- Checked against upstream: `python tree_sha256.py --tgz env-gapcheck/pettachainer-b6aacc68.tgz env-gapcheck/petta-3681b9b.tgz` extracts the codeload tarballs (top dirs `PeTTaChainer-b6aacc686675c2c3fd5758adbd2ee245e3e7a5a5`, `PeTTa-3681b9baa28d005dfbad21ad9b5d46b243b1e323`) and gives the same two hashes. The tarballs' sha256 are 9a391bc6…bb16 and 200d53b7…535e. The same function is in the test and in `tree_sha256.py` (byte caches and .git excluded). `stated_pins` are the SHAs from the environment variables; the hashes are the check.
- round 1: canary ok, `(Inheritance cat animal)` proved by `conditional-implication (by sp1 (by sp0 …))`, STV (1.0, 0.871); admitted 1 ("cat is a animal", derived_from [s1, s0]).
- between rounds: that item was forgotten with `in_forget_log: true`.
- round 2: canary ok, negative control not proved, the same goal re-proved with the same proof; admission `dropped.known = 1`, `candidates = 0`, `admitted = 0`, `skipped = no_candidates`.

## 3. Useful vs trivial derived beliefs
t-2026-11-10-wmtm-score-49-goals found 39 of 41 correct conclusions to be one-hop "an X_Y is a Y" restatements. **Nothing in main tells them apart from useful ones:**
- Admission: parse_gate rejects broad, placeholder and hedged terms (thing, entity, trivial, …: runtime_config.py:117) and caps conclusions at 3 per fact (gate_max_per_fact). Neither checks whether the conclusion only restates a compound name of its own source. Initial STI is 1 + 4×request relevance (pc_admit.py:127-144), so a restatement that repeats the request's words starts *higher*.
- Utility: a use is credited when the item is shown in the context block (api.py:337-339) or shares words with the response (context.py:316-331). A displayed restatement earns the same credit as a non-trivial conclusion.
- Eviction: STI-only overflow and threshold rules, with no novelty or informativeness term. The design's "novelty bonus" (§3.4) only means "not an exact duplicate" (orchestrator.py:207-210).
- Test: test_s3_5_trivial_restatement_ranked_below_nontrivial_conclusion is an xfail (GAP-5). After 3 cycles both items have identical attention and utility.

## 4. Mesto's worked examples (review of 6 Nov)
Status from the full suite at 27c1a41 with the engine present (0 failures):

| § | Example | main | Tests |
|---|---|---|---|
| 1 | a named individual is one entity | passes the cross-note case on the engine; the "a note says two Rexes differ" undercut is not tested | test_name_resolve.py (incl. test_real_engine_resolved_cross_note_fact_derives) |
| 2 | a fact stated in other words still reaches the reasoner ("vet is a doctor" through a calibrated link) | **no test found; not shown on main** | — |
| 3 | a conclusion keeps its truth value and reasons | passes | test_pc_shadow.py::test_derived_enters_kb_with_engine_tv_and_sources, ::test_derived_dropped_when_a_source_is_withdrawn |
| 4 | forgetting frees space but never forbids a conclusion | passes | test_f1_s4_forgetting.py (9 tests); new test_mesto_4… |
| 5 | notes not dropped or merged for sharing words | passes | test_f2_context_goals.py::test_s5_* (4) |
| 6 | every derivation kept, support recomputed | partly: withdrawal drops or keeps correctly; "one product per derivation" labels (m1·m2·n1 + m1·m2·n7) are not tested | test_pc_shadow.py::test_decision2_* |
| 7 | evidence kept apart from attention in the context block | passes | test_f2_context_goals.py::test_s7_* (3) |
| 8 | a goal closes on evidence for its condition | partly, by test name only: goal closure on evidence is tested (::test_satisfied_by_task_id, ::test_satisfied_by_closing_sentence_terms, ::test_multi_item_goal_needs_every_item_closed, ::test_closing_a_prerequisite_does_not_satisfy_the_follow_up, ::test_closure_of_a_different_object_does_not_satisfy). Mesto's merge-report example itself has no test | test_goal_lifecycle.py (mapped by name; Mesto's review text is not in this container, so his example was not re-derived) |
| 9 | one rule for every admit/evict/forget path | passes | test_f1_s9_one_rule.py, test_f1_s9_replay.py; new test_mesto_9… |
| 10 | GoalChainer reads WMTM's evidence; ties stay ties | passes, except the real-v2 test, which skips (WMTM_TEST_GC2_PYTHON unset) | test_f2_context_goals.py::test_s10_*, test_decision4_* |
| 11 | engine change judged on the merged tree | passes now that the engine runs (2 tests were environmental failures before) | test_f1_s11_subunit.py |

## 5. Ranked gaps (impact, size, owner)
Ranked by how much each keeps main from "working as designed". **Size** is an estimate from reading the cited code, not a measurement: XS = a flag or a few lines (under an hour plus tests); S = one module plus tests (about a day); M = several modules, or a behaviour change that moves existing tests (2 to 5 days); L = needs a design decision or upstream engine work (more than a week). **Owner**: *ours* = wmtm code in this repository; *Roman* = PeTTaChainer (rTreutlein/PeTTaChainer) rules or engine; *Man Hin* = the semantic parser (semparse, pinned in semparse_catalog). No ranked gap depends on Man Hin; one optional fix route and one untested item do (marked).

| # | Gap | Impact | Size | Owner | Depends on / notes |
|---|---|---|---|---|---|
| 1 | **GAP-4 promotion off** (§6.3, §7.2, §13.3). With defaults no reasoner conclusion reaches LTM; since Track L these are the only derived beliefs, so the WMTM adds nothing to the archive | High | **XS** code: the `reasoner_writeback` default (runtime_config.py:109), or the live flags file. The flag-on path already passes its test. Plus a live rollout check | **ours** | *Decision for Ben or andy.* Should follow GAP-5: promoting today's mostly trivial conclusions puts noise into LTM (§14 risk) |
| 2 | **GAP-5 no useful/trivial signal** (§3.5, §13.3). Utility credits display, not use | High | **M** overall. (a) **S**: an admission-side triviality filter in pc_admit.load_candidates (pc_admit.py:146-222) rejecting a conclusion that only restates a compound name of its own source ("an X_Y is a Y"). (b) **M**: credit use from what the response relied on, not from display (api.py:337-339, context.py:316-331); this moves existing utility tests | **ours** | Optional route for (a): Man Hin's parser could stop emitting the X_Y→Y facts that produce these restatements (*Inferred* from t-2026-11-10-wmtm-score-49-goals; not checked against the parser). Not required |
| 3 | **GAP-9 inference breadth** (§3.4, §9.1). Only deduction-style chaining over Inheritance and Member×Inheritance runs | High if in scope | **L** | **Roman + ours** | Roman: PeTTaChainer rules for induction, abduction, analogy and revision/aggregation, and native chaining over Implies. F3 v2 dropped Implies from TRANSITIVE (pc_shadow.py:22) *because* the engine has no native Implies chaining, so rain→wet→slippery is never asked (engine_s12.json.kinds.json: goals_n = 1). Ours: `pc_shadow.build_goals` (pc_shadow.py:204-229) generates only 2-step transitive and Member joins, so new goal shapes are needed even once the rules exist. *Scope decision for Ben* first: the Oct 16 note marks §3.4 historical |
| 4 | **GAP-1 graph recall** (§3.3 "key insight", §13.5). Spreading activation only reorders keyword hits | High | **S**: in recall_bridge.py, stop the early `return 0.0` (:262-263) from excluding clusters reachable by spreading from the active set (:386-473). xfail test_s3_3… is the acceptance test | **ours** | Changes recall ranking, so recall tests and the recall budget (api.py:253) need re-checking |
| 5 | **GAP-3 eviction scoring** (§7.1c). STI-only overflow, no composite, no 1.5× derived penalty; in the simulation overflow does all the forgetting | Medium-high | **M**: one composite score used by store._evict_lowest_sti (store.py:132-144) and the policy overflow (forgetting.py:61-67); touches the F1 §9 one-rule tests | **ours** | The LTI term stays a no-op until GAP-10 |
| 6 | **GAP-10 LTI** (§3.3 step 2, §8.1c). No LTI on LTM clusters, no LTI-driven recall | Medium | **M**: an LTI field in the LTM cluster parse (recall_bridge.py:59-70), updated on recall/use and written back, plus a recall term | **ours** | Needs an addition to the LTM note format that recall_bridge parses; any other writer of that format must agree. No test yet (nothing to test against) |
| 7 | **GAP-2 PromotesFrom not traversed** (§8.1b) | Low-medium | **XS**: add the already-parsed PromotesFrom edges (recall_bridge.py:34, :99) to `_collect_activation_neighbors` (:437-450) | **ours** | Only matters after GAP-1, since spreading adds no new clusters today |
| 8 | **GAP-7 enrichment as links** (§4 step 6). Writeback copies a note instead of adding EvidenceFor links | Low-medium | **S**: writeback.py `_select_recalled` / `format_enrichment_metta` (:116-124) | **ours** | — |
| 9 | **GAP-6 contradiction resolution** missing (§7.1d) | Medium | **L**: needs a design (what counts as a contradiction, which side survives). pc_admit already sees negative-polarity proofs (pc_admit.py:195, :206) and drops them | **ours**, possibly **Roman** | If detection should come from engine negation/revision proofs, it depends on what PeTTaChainer can prove |
| 10 | **GAP-8 WMTMDerivedForgotten not in LTM** (§6.3). The log lives only in the snapshot, FIFO 500 | Low | **S**: write forgetting-log records through writeback | **ours** | — |
| 11 | **GAP-11 observability**: CycleResult.evicted omits capacity-overflow evictions | Low | **XS**: orchestrator.py:409 sets `result.evicted = len(self.forget_phase())`; add the evictions drained at :168-170 | **ours** | — |

Untested, not ranked (no evidence either way on main):
- **Mesto §2** (a fact stated in other words reaches the reasoner through a calibrated link): no test found. Size unknown until a test exists. Owner **Man Hin + ours** (*Inferred*): whether "vet is a doctor" reaches the KB depends first on what the parser emits, then on our feed into pc_shadow.
- **Mesto §6 labels** ("one product per derivation", m1·m2·n1 + m1·m2·n7): owner **ours** (pc_shadow decision-2 support code); the test is S once Mesto's worked numbers are at hand.

Parameter deviations, not gaps: STI decay 10%/tick (design 2%), spreading decay 0.3 (0.7), recall budget 15 (10), thresholds rescaled (STI 0.05 vs 5.0).

By owner: 9 of 11 gaps are ours alone; GAP-9 needs Roman; GAP-6 may need Roman. No ranked gap needs Man Hin.

## 6. Acceptance suite
- `tests/test_design_s12_gapcheck.py`: 24 tests. 16 pass. 8 are strict xfail with the reason "GAP-n …" (GAP-1, 2, 3, 4, 5, 6, 7, 8). An XPASS turns the suite red, so whoever closes a gap must remove its marker.
- `tests/test_design_s12_engine.py`: 2 engine tests. They skip with "not run: environment" when the vendored runtime is absent. Set `WMTM_PC_PETTA`, `WMTM_PC_VENDOR`, `WMTM_SWIPL_BIN`.
- No production code was changed. GAP-9, 10 and 11 have no test: 9 is a scope question, 10 has no input to test (no LTI field), and 11 is an observation.

## Limits
- Engine tests use the test semparse fake (as test_pc_shadow does), not the LLM parser. Parse quality is outside this check.
- The live flags file and live state were not reachable. Every "live" statement comes from the order or the deploy-split report.
- The simulation is one synthetic regime with one seed (123). Other mixes (more derived offers, smaller recalls) may let the age and utility rules act.
- Mesto §1, 6 and 8 are mapped from test names and docstrings, not re-derived from his worked numbers.
- In §12.2 the "durable" belief's use is simulated with `record_use`, the same call api.py makes when an item is shown.

## Commands
```
. projects/wmtm/env-gapcheck/env.sh
cd projects/wmtm/repos/wmtm-git          # 27c1a41 + this branch
python -m pytest -q -rfs tests                                    # baseline (before new tests): 819 passed, 26 skipped
WMTM_GAPCHECK_SIM_OUT=…/sim_s12_3.json python -m pytest -q tests/test_design_s12_gapcheck.py   # 16 passed, 8 xfailed
WMTM_GAPCHECK_ENGINE_OUT=…/engine_s12.json python -m pytest -q tests/test_design_s12_engine.py # 2 passed in 80 s
WMTM_GAPCHECK_PC_SHA=b6aacc68… WMTM_GAPCHECK_PETTA_SHA=3681b9ba… WMTM_GAPCHECK_ENGINE_OUT=…/engine_s12.json python -m pytest -q tests/test_design_s12_engine.py   # rev 2: 2 passed in 74 s
python reports/t-2026-11-10-wmtm-design-gap-check/tree_sha256.py --tgz env-gapcheck/pettachainer-b6aacc68.tgz env-gapcheck/petta-3681b9b.tgz
```
Artifacts (in reports/t-2026-11-10-wmtm-design-gap-check/ on the branch): REPORT.md, ENV.md, baseline_rerun.log, full_suite.log, full_suite_r2.log, full_suite_r2a_warmfail.log, sim_s12_3.json, engine_s12.json, engine_s12.json.kinds.json, engine_run.log, tree_sha256.py, NOTES.md.

## Revision history
- **Rev 2 (2026-11-10, after review 1 by reviewer.claude, failed).** (1) Acceptance 4: §5 is now a table with impact, size (XS/S/M/L, defined) and owner (ours / Roman / Man Hin) for all 11 gaps, plus owners for the two untested Mesto items. (2) Engine evidence: tests/test_design_s12_engine.py now writes round 2, the between-rounds forgetting state, and the engine directories with content hashes; the hashes match the codeload tarballs. Test-only change. (3) Mesto §8 now mapped by name to test_goal_lifecycle.py; §1 undercut, §2 and §6 labels are still untested (Mesto's review text is not in this container), as before. (4) Fixes: test_f1_s4_forgetting.py has 9 tests, not 7; the utility formula is at utility.py:27-33. Review findings 3 and 4 (thin Mesto coverage; §12.3/§12.4 on synthetic candidates) are limits already stated and are unchanged.
- Rev 1: f1c6ee0, 8b24c4a.
