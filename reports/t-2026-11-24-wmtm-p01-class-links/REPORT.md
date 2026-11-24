# t-2026-11-24-wmtm-p01-class-links: wmtm-side class-link pass (P-01, P-12, E-01, P-04)

## Summary
The task asked why the 77-84 class-to-class links per parse run produce no new conclusions, and whether a wmtm-side pass, off by default and using only what the parses state, can add links that PeTTaChainer chains into more correct conclusions.

**Why the existing links don't produce conclusions (counts, 5 frozen runs):**
- The links are almost all definitions the lowering writes itself: 76-83 of 77-84 per run are `kind__` links from a narrowed class to its base noun. Only 1 per run is anything else.
- Nothing consumes them. 0 of the 280 pinned rules (9c58f2e0) mention Inheritance, and goals_arm applies rules one step forward only.
- Applying them would add nothing anyway. Member(x,A) plus A→B gives Member(x,B), which is already stated in 40-47 cases per run and new in 0, because the lowering writes the base-class Member itself. No link chains into another link.
- Generic statements become variable Implications, not Inheritance. Their classes are almost never instantiated in the notes. Per run, the class a range quantifies over has no individual anywhere in 9-15 cases, one only in another note in 2-3 cases, and one in the same note in 0-1. A Member fact reaches a generic's antecedent class in the same note in 0-1 cases.
- Counts are in diag.json, diag_parse.json and diag_derivable.json.

**The pass:** wmtm/class_links.py, behind the flag `class_links` / `WMTM_CLASS_LINKS` (default False), has three rules:
- R1 generic is-a: a universal generic Member→Member over the same variable with strength ≥ 0.9.
- R2 narrowed subset (P-12): two narrowed classes of the same base noun, where one's restrictions are a strict subset of the other's.
- R3 member link.

Every derived atom carries the names of its source statements and its parse unit ids. An R2 link that can't be traced to a parse unit is not emitted. No world knowledge is used.

**Result:** the pass adds 10-18 narrowed-subset links per run (cc 77-84 → 87-100). It derives 0 generic is-a links and 0 new Member facts. Conclusions are unchanged on all 5 runs (goals on = off, 0 new), so the count rule, the wide rule and the reader score are identical with the flag on and off. There are no new W, and also no gain. The gain is 0, which is inside the run-to-run noise, so this is **not an improvement**. On these notes the bottleneck is not missing links. It is (a) generics over classes the notes never instantiate and (b) Inheritance with no consumer in the scorer.

**Open, needing a decision:** whether to pursue the real levers in other tasks:
- instantiating generic ranges, meaning a parser or lowering change so that note individuals are linked to the classes the generics quantify over;
- an Inheritance-aware scorer or chaining pass.

Recommendation: do not merge the flag as a gain. Keep it only if the P-12 links are wanted for PeTTaChainer queries.

## Per-run table (flag off = flag on on every metric except cc)
| run | narrow C/W/U | wide strict C/W | reader /75 | cc off → on | derived (R1/R2/R3) | goals off=on | new conclusions |
|---|---|---|---|---|---|---|---|
| A0 (pinned) | 22/1/0 | 5/0 | 8 | 79 → 97 | 0/18/0 | 652 = 652 | 0 |
| A1 a1frozen | 22/6/0 | 5/0 | 7 | 84 → 100 | 0/16/0 | 657 = 657 | 0 |
| r1 | 24/1/0 | 5/0 | 8 | 77 → 93 | 0/16/0 | 657 = 657 | 0 |
| r2 | 25/6/1 | 7/0 | 8 | 77 → 87 | 0/10/0 | 666 = 666 | 0 |
| r3 | 25/2/0 | 5/0 | 7 | 81 → 97 | 0/16/0 | 662 = 662 | 0 |
| range | C 22-25, W 1-6 | C 5-7, W 0 | 7-8 | +10 to +18 | R2 10-18 | identical | 0 |

The narrow, wide and reader figures are the archived Clerk A/B scores (FINDING2, plus review4 for pinned A0). They carry over unchanged because the regenerated goal sets are equal with the flag on and off (sorted comparison, recompute.out). With 0 new conclusions there was nothing to judge C/W/U.

## Acceptance
1. Diagnosis with counts: see above and diag*.json.
2. Flag off: atoms are byte-identical to the input on all 5 runs, and the goals regenerated with pins/goals_arm.py and rules 9c58f2e0 equal the archived goals on all 5. Flag on: derived_without_units = 0 on all 5.
3. Per-run table with ranges is above. Count rule holds (no new W). The gain (0) does not exceed the run-to-run range.
4. tests/test_class_links.py: 12 tests, covering each rule firing and must-not-fire cases (most/few/no, ground, different variable, event consequent, conditioned antecedent, across bases, equal or disjoint restrictions, untraceable, already stated, downward). Also the README flag-table sync. 35 passed together with test_parse_normalise.

## Details
- Base: wmtm 9a8f693 (hive base). wmtm main head at start was fd48815. Branch hive/t-2026-11-24-wmtm-p01-class-links in worktree projects/omegaclaw/p01/wmtm-wt. Not pushed.
- Pins: PINS.md from the Clerk A/B, which gives PeTTaChainer bdae8d7, PeTTa 3681b9b, templates sph-24e37182, rules 9c58f2e0, and goals_arm b868a3db.
- Parse runs: A0 = sentence_parse/parsed.jsonl (sha 33b9cb5e), A1 = a1frozen, r1-r3 = result3/a1varfull. All atoms were taken from the Clerk A/B retained load_arm output. No new parse calls were made and no live change was made.
- Files: wmtm/class_links.py, tools/class_links_apply.py, tests/test_class_links.py, the runtime_config.py flag and the README flag row.
- Evidence: /srv/hive-evidence/t-2026-11-24-wmtm-p01-class-links/. recompute.sh is counts-only and runs in a mktemp dir; its output is recompute.out. SHA256SUMS covers the evidence. Derived atoms and provenance (apply/, goals/) stay in /srv only.
