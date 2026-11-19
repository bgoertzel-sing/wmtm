# t-2026-11-17-wmtm-impl-premise-proving: note-implication premise goals, lowering stopgaps, C4, C7/C8

> **Superseded by t-2026-11-17-wmtm-impl-premise-proving-v2:** the two lowering stopgaps (`shadow_lowering_stopgaps`) described below were removed (code, tests, docs and tools); `shadow_note_impl_premise` is kept, off by default, and its literal() check now reads only the implication's own note. This report is kept as history.

## Summary
andy asked for three things. The first was a flag that asks a note implication's conclusion for entities from the same note even when the premise is not stated literally, leaving PeTTaChainer to prove the premise. The second was two lowering stopgaps behind a separate flag: "everything is a thing", and narrowed-class membership. The third was a C4 rerun with a larger budget and finishing C7/C8. Both flags are built, off by default, and tested. With them off, the 20-note spec is byte-identical to 9a8f693. **On the 20 real notes neither flag adds a single proof.** The premise flag builds 36 same-note goals and 0 are proved, even at 10x the step budget. The stopgaps add 221 atoms and change nothing. The count rule holds in every arm (non-restatement and admitted 36/1/0 C/W/U, as with flags off). The reader pass stays at 8 of 75.

On the invented cases the stopgaps do help. C5 ("not liquid") is proved with both flags on. C4 is proved at 300 steps with the thing stopgap, and the proof bridges the two toy skolems through coref_member (the earlier reason is corrected below). C7 (the converse near miss) correctly does not fire. **C8 shows a risk:** with the narrow stopgap on, a hand-asked probe about an instance in one note is proved through another note's rule, because both notes share the narrowed-class definition. The goal builder itself never binds across notes (0 cross-note candidates), but this proof path does cross notes. **Recommendation:** don't keep the stopgaps. They don't help on real notes, and the narrow stopgap opens a cross-note path. Keep shadow_note_impl_premise off until the lowering fix (Man Hin) gives PartOf/On/Of premises something to match. Open for andy: whether to keep the premise flag in the code at all.

## Base and code
- Base: wmtm main 9a8f693 (PRs 45-47 merged). Branch hive/t-2026-11-17-wmtm-impl-premise-proving, commit 732d860 (code, tests, README) plus the report commit. Not pushed.
- `shadow_note_impl_premise` (bool, default false), `master_loader.note_impl_premise_goals`. This applies to a note-stated Implication/BiImplication (label in atom_src) whose premise does not match loaded facts literally; literal premises are left to `note_impl_goals`. Candidates are the entity arguments (first argument of Member/Name, second of Agent/Patient/Theme/Bearer) of statements whose label carries **the implication's own note suffix**, so no other note's entities are ever considered. Only conclusions with exactly one free variable are built (others are counted). Conclusions already stated are skipped. Goals are tagged `nimplp:<label>`.
- **Cap** (`shadow_note_impl_cands`, default 8): per implication direction, candidates are scored by how many of the premise's constant symbols (classes, predicates, other than And/Member/Agent/Patient/Theme/Bearer/Inheritance/thing) appear in that entity's own-note statements. Score 0 is excluded. The highest scores are kept, ties go by first appearance, and the rest are counted as `capped` (0 on the 20 notes and on the invented cases).
- `shadow_lowering_stopgaps` (str, default "" = off; `thing`, `narrow` or both), `master_loader.lowering_stopgaps`, appended after the notes. (a) thing: `(: stopgap_thing__C (Inheritance C thing) (STV 1.0 0.99))` for every class C of a ground note Member. (b) narrow: for a narrowed class K with `kind__` (Inheritance K noun) and `by_` (NarrowBy K (Is a)), `(Implication (And (Member $x noun) (Member $x a)...) (Member $x K))` at STV 1.0/0.99.
- Tests: tests/test_impl_premise_proving.py has 8 tests on synthetic atoms (same-note goal, never across notes, literal left to the one-step builder, score-0 and cap, stated conclusion and multi-variable conclusion skipped, seeded rules ignored, stopgap thing/narrow and the which selector, flags off by default). The README flags table is updated. Full suite: 1609 passed, 70 skipped, 5 xfailed.
- Flags off unchanged: specs built with this branch and with 9a8f693, both flags off, compare byte-identical (`base` = all note-impl flags off, and `off` = shadow_note_impl_goals on); cmp is in the evidence.

## Step 2: shadow_note_impl_premise on the 20 real notes (cached parses, 0 calls, parsed.jsonl md5 unchanged)
Arms: base = no note-impl flags. off = shadow_note_impl_goals on (the one-step builder; reference for "flags off" in this task). ip = off + premise flag. sg = off + stopgaps thing,narrow. ipsg = both. ipsg_s300 = ipsg at 300 steps. All arms: status ok, canary ok.

| arm | goals | proved | timeouts | premise goals built / proved | new proved vs base C/W/U | admitted C/W/U | trivial refused | reader rows of 75 |
|---|---|---|---|---|---|---|---|---|
| base | 105 | 105 | 0 | - | - | 22/1/0 | 82 | 8 |
| off | 119 | 119 | 0 | - | 14/0/0 (the 14 one-step nimpl restatements, nig-v2 verdicts) | 36/1/0 | 82 | 8 |
| ip | 155 | 119 | 0 | 36 / **0** | 14/0/0 | 36/1/0 | 82 | 8 |
| sg | 119 | 119 | 0 | - | 14/0/0 | 36/1/0 | 82 | 8 |
| ipsg | 155 | 119 | 0 | 36 / **0** | 14/0/0 | 36/1/0 | 82 | 8 |
| ipsg_s300 | 155 | 119 | 5 | 36 / **0** | 14/0/0 | 36/1/0 | 82 | 8 |

- Builder stats (ip): 41 note implications. Premise literal 15 (left to note_impl_goals), not literal 26. 39 candidates, 3 conclusions already stated, 36 goals over 14 implications, 3 with multi-variable conclusions skipped, 0 capped, **0 cross-note**.
- **No new conclusion was proved, so there is nothing new to judge.** The 105 shared goals: 0 status changes and 0 strength changes in every arm, and 0 timeouts among them at 300 steps.
- Why 0: 31 of the 36 goals come from implications whose only premise is `(PartOf $x <skolem>)`. The other 5 have `(Member $x c)` with `(On $x sk)` or `(Of $x sk)`. Instantiated for the candidate, the premise atom is absent for all 36, and no seeded rule concludes On/Of. Only 2 rules conclude PartOf, and they don't reach these entities. The gap is in what the notes are lowered to, not in the step budget.

## Count rule (C/W/U/unjudged; vs live A 2C/2W | vs flags off = base)
| arm | all | non-restatement | admitted |
|---|---|---|---|
| base | 97/4/4/0 (fails, as before / -) | 22/1/0/0 (holds) | 22/1/0/0 (holds) |
| off, ip, sg, ipsg, ipsg_s300 | 111/4/4/0 (fails, as before / holds) | 36/1/0/0 (holds / holds) | 36/1/0/0 (holds / holds) |

The ip, sg and ipsg lines equal the off line exactly. Neither new flag changes any count.

## Step 3: stopgaps on the 20 real notes, alone (sg) and with step 1 (ipsg)
187 thing atoms and 34 narrow implications are added. 0 proofs use a stopgap atom in either arm, at 30 or at 300 steps, and no goal is added or changed (tables above). On real notes no note-stated Inheritance has a narrowed class as its subject (there is 1 note-stated Inheritance in all, about an ordinary class), and 18 Member facts already state a narrowed class directly, so the "anything ..." shape the stopgaps target is nearly absent. **Verdict: they don't help on real notes.**

## Invented cases (variable-test notes; arms as above, steps 30 unless stated)
| case | goal built by premise flag | off | ip | sg | ipsg |
|---|---|---|---|---|---|
| C1 anything acoustic is quiet | none (lowered as Inheritance, no Implication) | - | - | - | - |
| C2 every bird that sings is happy | literal, one-step builder | proved 1.0/0.892 | same | same | same |
| C3 if someone plays the drum, they are loud | none (conclusion about the constant sk_they_1, no variable) | - | - | - | - |
| C4 red and round is a ball | (Member sk_toy_1 ball), (Member sk_toy_2 ball) | not built | not proved | (probe) | not proved at 30 |
| C5 frozen is not liquid | (Not (Member sk_pond_1 liquid)) | not built | not proved | - | **proved 1.0/0.894** (stopgap_thing) |
| C7 converse near miss: is the banjo acoustic? (probe) | none | not proved | not proved | not proved | not proved (correct) |
| C8 viol (other note) quiet? (probe) | none (cross-note, never built) | not proved | not proved | **proved 0.9/0.7** | **proved 0.9/0.7** |

## Step 4: C4
Step budget 30 (as before) and 100: not proved in any arm. **300 steps** (WMTM_PC_SHADOW_STEPS=300, per-goal timeout 2 s): both toy goals are **proved at 0.896/0.676 with the thing stopgap (sg and ipsg)**, and not proved without it (off, ip). The proof is `s1_r1_implication` over the conjunction of stopgap_thing (thing), red and round, where the conjunct on the other skolem is reached `by coref_member` over `Coref sk_toy_2 sk_toy_1` (and coref_sym).
**Corrected C4 reason** (it replaces "still not proved in diag: the two premises sit on two skolems" in the variable test's report): coref_member does bridge Member across the toy skolems. C4 needed both the missing thing premise and a larger step budget. With the thing stopgap at 300 steps, it is proved.

## Step 5: C7 and C8
Parsed within the task share: 2 calls (share 3/10 used before, 0 429s; drive_c78.py = the variable test's driver with TASK changed and MAX_CALLS 4; pinned hitl 24e37182, prompt 257425b2). C7: the banjo is never proved acoustic (the converse near miss holds in all arms). C8: the goal builder builds nothing (it is cross-note, by design). With the stopgaps, the hand-asked probe is proved through C7's `s1_k1_inheritance` (Inheritance thing__member_acoustic quiet), `stopgap_narrow__thing__member_acoustic` and `stopgap_thing__viol`. The narrowed class is a shared definition (kind__/by_ are loaded once for both notes), so **the narrow stopgap carries a rule from one note to another note's instance.** That is the cross-note behaviour the order rules out for goals. It only shows up through a probe here, but in live use any goal about the viol could take that path.

## Limits
- One parse per sentence (temperature 0); parse variance was not measured.
- 5 per-goal 2 s timeouts at 300 steps (all on premise goals). A longer per-goal timeout was not tried.
- The 20-note judgments reuse earlier verdicts (b01..b105 from trivial-filter-coref, n01..n14 from nig-v2). No new conclusion needed a verdict.

## Evidence
/srv/hive-evidence/t-2026-11-17-wmtm-impl-premise-proving/: {base,off,ip,sg,ipsg,ipsg_s300}/{spec,build,shadow,admit,run}, base_9a8f693/ and off_9a8f693/ (flags-off specs from the base commit), inv/ (6 invented notes plus the C4 step-budget runs c4_s{100,300}_*), inv8/ (with C7/C8), c78/ (driver log, calls, parsed), tools/{build_spec_ipp.py,run_ipp.sh,recompute_ipp.py,drive_c78.py}, recompute_ipp.json (counts only; private mode-700 temp dir), parsed.md5_{before,after}, pytest_full.log, SHA256SUMS.
