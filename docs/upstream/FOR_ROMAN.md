# For Roman: rules nobody has yet

Pins: parser `24e37182`, seeded rules file `seeded_rules.pettachainer-master.metta` (sha256 `9c58f2e0…`), PeTTaChainer `b6aacc68`. None of the predicates proposed below (`Supersedes`, `Contradicts`, `SameDay`, `PartsOf`, `ReviewOf`, `DirectiveFor`, `Distributive`, `Disjoint`, `EvidenceAgainst`, `ValidUntil`) appears in that rules file.

This is a list of conclusions a reader would draw from the input, which no current rule can derive. In each case the premises are parsed and a rule is missing, either in PeTTaChainer or in the seeded rule set. It covers 34 conclusions, grouped by the kind of rule that is missing. All examples are made up. Rule shapes are written in the style of the seeded rule file: `(: id (Implication premises conclusion) (CTV …))`, with `Compute` for arithmetic.

## Summary

| # | Kind of missing rule | Reader-pass id | Cases | Firm / uncertain* |
|---|----------------------|----------------|-------|-------------------|
| 1 | Clock-time order (`Hour`/`Time` → `Before`) | `hour_order` | 7 | 6 / 1 |
| 2 | Superseded means no longer current | `supersedes_not_current` | 6 | 6 / 0 |
| 3 | Sums of counts or amounts | `sum_of_parts` | 5 | 3 / 2 |
| 4 | Contradicted means no longer holds | `contradicts_not` | 4 | 3 / 1 |
| 5 | A directive about a class applies to its members | `directive_inherit` | 3 | 1 / 2 |
| 6 | A passed review closes its task | `passed_closes` | 2 | 1 / 1 |
| 7 | A group property distributes to its members | `group_distribute` | 2 | 0 / 2 |
| 8 | Exclusive location (here means not there) | `exclusive_location` | 1 | 0 / 1 |
| 9 | Evidence against gives `Not` | `evidence_to_not` | 1 | 0 / 1 |
| 10 | A stated implication used as a rule | `note_adjective_impl` | 1 | 1 / 0 |
| 11 | Probably not a rule gap (see notes) | `negation_parse + none_needed_asserted` | 2 | 2 / 0 |
| | **Total** | | **34** | **23 / 11** |

\* "Firm" means a human reader would draw the conclusion without hesitation. "Uncertain" means a reader might hedge. So we'd want firm conclusions to come out strong, and uncertain ones weaker.

## Kinds, with invented examples

**1. Clock-time order (7).**
*Shape:* `(Implication (And (Hour $a $h1) (Hour $b $h2) (SameDay $a $b) (Compute < ($h1 $h2) -> true)) (Before $a $b))`. Times should be in minutes of the day so that minutes compare correctly. The `SameDay` guard (or a shared date) matters, because without it 09:00 on Tuesday would come "before" 17:00 on Monday. One of the 7 cases uses a full `Time` stamp rather than `Hour`. It needs the same rule over timestamps.
*Example:* `(Hour soundcheck 900)` (15:00), `(Hour doors 1080)` (18:00), `(SameDay soundcheck doors)`.
*Expected:* `(Before soundcheck doors)`.
*TV:* crisp, since it is arithmetic on firm premises. Same as `days_before_day`: `(CTV (STV 1.0 0.99) …)`.

**2. Superseded means no longer current (6).**
*Shape:* `(Implication (Supersedes $new $old) (Not (Current $old)))`. In 1 of the 6 cases, the text gives an end time rather than a successor. That variant is `(And (ValidUntil $old $t) (Now $n) (Compute < ($t $n) -> true)) → (Not (Current $old))`.
*Example:* "Plan B replaces Plan A." → `(Supersedes plan_b plan_a)`.
*Expected:* `(Not (Current plan_a))`.
*TV:* follows the `Supersedes` fact. A firm statement should give a strong `Not (Current …)`.

**3. Sums of counts or amounts (5).** In 3 cases the reader expects a total, and in 2 a difference that needs a total first (`MoreBy`).
*Shape (fixed arity):* `(Implication (And (PartsOf $w ($p $q)) (Measure $p $d $x $u) (Measure $q $d $y $u) (Compute + ($x $y) -> $s)) (Measure $w $d $s $u))`. A general version would need a fold over a list of parts. The open question is how the rule knows the list of parts is complete, since without that a total is only a lower bound.
*Example:* `(PartsOf tickets (presale door))`, `(Measure presale count 140 ticket)`, `(Measure door count 60 ticket)`.
*Expected:* `(Measure tickets count 200 ticket)`. Then `measure_moreby` can compare that total with another measure.
*TV:* firm if all parts are firm and the list is closed. If the list may be incomplete, the TV should be weaker, or the result should be `MeasureAtLeast`. We don't know the right behaviour yet.

**4. Contradicted means no longer holds (4).**
*Shape:* `(Implication (Contradicts $e $c) (Not (Holds $c)))`.
*Example:* "The new test result contradicts the claim that the cable is faulty." → `(Contradicts test_result_2 claim_cable_faulty)`.
*Expected:* `(Not (Holds claim_cable_faulty))`.
*TV:* not known. It should probably depend on how reliable `$e` is compared with the original claim, rather than being crisp. For 3 of the 4 cases a reader is firm.

**5. A directive about a class applies to its members (3).**
*Shape:* `(Implication (And (Directive (Forall $x (Member $x $k) $act)) (Member $t $k)) (Directive $act[$t]))`. A plain-atom version: `(And (DirectiveFor $k $p) (Member $t $k)) → (DirectiveFor $t $p)`. One of the 3 cases is a prohibition ("never X"), so the rule must also carry a `Not` through.
*Example:* "Every rehearsal starts with a line check." and "Friday's session is a rehearsal." → `(DirectiveFor rehearsal line_check_first)`, `(Member friday_session rehearsal)`.
*Expected:* `(DirectiveFor friday_session line_check_first)`.
*TV:* deduction. It should be firm when both premises are firm.

**6. A passed review closes its task (2).**
*Shape:* `(Implication (And (ReviewOf $r $t) (Member $r passed)) (Member $t closed))`.
*Example:* "The stage plan review passed." → `(ReviewOf review_7 stage_plan)`, `(Member review_7 passed)`.
*Expected:* `(Member stage_plan closed)`.
*TV:* a domain default. It is firm in 1 case and uncertain in the other.

**7. A group property distributes to its members (2).**
*Shape:* `(Implication (And (Member $g $p) (MemberOf $x $g) (Distributive $p)) (Member $x $p))`. The `Distributive` guard is needed because "the band is large" does not mean each player is large.
*Example:* `(Member horn_section late)`, `(MemberOf tobin horn_section)`, `(Distributive late)`.
*Expected:* `(Member tobin late)`.
*TV:* both of our cases are uncertain, so the rule should give a weaker strength than its premises.

**8. Exclusive location (1).**
*Shape:* `(Implication (And (LocatedIn $x $a) (Disjoint $a $b)) (Not (LocatedIn $x $b)))`.
*Example:* `(LocatedIn van depot)`, `(Disjoint depot venue)`. *Expected:* `(Not (LocatedIn van venue))`.
*TV:* only as strong as the `Disjoint` fact. Our case is uncertain.

**9. Evidence against gives `Not` (1).**
*Shape:* `(Implication (EvidenceAgainst $e (Member $x $k)) (Not (Member $x $k)))`.
*Example:* "The log shows the fan was never on." → `(EvidenceAgainst log_3 (Member fan running))`.
*Expected:* `(Not (Member fan running))`.
*TV:* uncertain, and it should be weaker than the evidence.

**10. A stated implication used as a rule (1).** The text itself states a general rule ("anything X is Y"), and the parser loads it as an `Implication` atom. Nothing then uses that atom as a rule.
*Example:* "Anything acoustic is quiet." gives `(Implication (Member $x acoustic) (Member $x quiet))`. With `(Member lute acoustic)`, the expected conclusion is `(Member lute quiet)`.
*Ask:* can the chainer use KB-loaded `Implication` atoms as rules, with the TV taken from the atom?

**11. Probably not a rule gap (2).** These are counted in the 34 because the reader pass put them there, but they may belong elsewhere.
- *Count asserted directly (1):* the reader's conclusion is a `Cardinality` that the text states outright, so no rule should be needed. The miss is in matching or querying.
- *Negated role fact (1):* the reader expected `(Not (Patient e x))`. The negation was parsed, but in a form no query reaches. This is likely a parser or normaliser item, not a rule item.
