# Review 3 finding 4: does wmtm's shadow path hit PC3 / R1-R8? (P4 rev4)

Source list: LIST-roman.md (t-2026-11-05-upstream-latest-lists-v2, rerun on PeTTaChainer master bdae8d7e).
Measured on rev4/r3_ab/dmnw/spec_B_dmnw.json (B spec, 396 atoms: 264 facts, 132 Implication rules, 13 goals)
and rev4/r3_ab/*/shadow.jsonl (8 arms, steps 30, timeout 10 s). Counts were made by a script over the spec atoms.

| Item | What upstream breaks | Shape in wmtm B spec | Hit? | wmtm stopgap |
|---|---|---|---|---|
| PC3 / R1 | And-elimination from a stored (And ...) gives c ~ 0 | stored facts containing And: 0; goals containing And: 0 | No (not reachable from current specs) | None needed now. If semparse starts storing And facts, conjunct answers will be c~0. Watch item, not a stopgap |
| R2 | modus ponens with premise s<1, and CTV rule form, collapses c | 60 of 132 rules use CTV; nwdef proofs revise a fact from 0.7 to ~0.20 (rev4/PROOF_KINDS.md); facts with s<1: 0, but derived premises can have s<1 | **Yes** (the 0.2017 vs 0.1771 goal-B effect in PROOF_KINDS.md is this) | Already recorded: nwdef A/B in rev4/nwdef_ab. No code stopgap; left for upstream |
| R3 | rules that cannot fire / bare-variable conclusions remove valid derivations | 21 rules with a bare-variable conclusion | Shape present; **no effect measured**: arm nor3 (those rules removed) gives the same ok/timeout per goal as full2 on all 13 goals | None |
| R4 | runaway search on small KBs | 1 goal times out at 10 s in every arm: (Member sk_config_1__i_ep_note_20261028T185959Z effective) | Not established: the timeout is consistent with R4 but not shown to be it | Existing 10 s per-query timeout and 3072 MB mem cap bound it |
| R5 | join over conjuncts of a derived And returns nothing | goals with And: 0 | No | None |
| R6 | proof labels leak between instances in one process | inner child creates one PeTTaChainer per process (wmtm/workers/pc_shadow.py:52); semparse_feed's loader is a separate process (semparse_feed.py:85) | No | None |
| R7 | nested (Member x c) returned as (c x) | facts with a nested Member: 0 | No | None |
| R8 | TV pattern with Band raises a type error | no Band in wmtm/*.py or wmtm/workers/*.py | No | None |

Also for finding 4: the Equivalence drop in semparse lowering now has a `STOPGAP(upstream: PC-EQ1 ...)` marker
in wmtm/pc_shadow.py and a row in docs/STOPGAPS.md.
