# For Man Hin: premises the parser did not produce, and one label bug

This is a list of facts that the rules in your seeded rules file need but the parser did not output. It covers 33 conclusions. The rule existed in each case, but the premise it needs was not in the parse, so the rule never fired. Then there is one bug: two different statements came out under the same label.

Pins: parser `24e37182`, seeded rules file `seeded_rules.pettachainer-master.metta` (sha256 `9c58f2e0…`). The rule ids below are from that file. All examples are made up. None of them comes from the notes we tested.

## Summary

| # | Rule id | Premise the rule needs | Cases |
|---|---------|------------------------|-------|
| 1 | `month_class` | `(Month $t $m)` | 13 |
| 2 | `rank_orders` | `(Ordinal $a $m $s $c)` for two items | 5 |
| 3 | `becauseof_cause` | `(BecauseOf $e $x)` | 4 |
| 4 | `measure_same` | `(Measure $x $d $a $u)` for two items, same amount | 2 |
| 5 | `measure_moreby` | `(Measure $x $d $a $u)` for two items | 2 |
| 6 | `unit_measure` | `(Measure $x $d $n $u)` in a convertible unit | 1 |
| 7 | `unit_atmost` | `(MeasureAtMost $x $d $n $u)` | 1 |
| 8 | `subset_is_part` | `(SubsetOf $s $g)` | 1 |
| 9 | `located_trans` | `(LocatedIn $x $y)` for both links | 1 |
| 10 | `located_in_part` | `(LocatedIn $x $p)` | 1 |
| 11 | `days_before_day` | `(BeforeBy $t $a $n day)` | 1 |
| 12 | `coref_theme` | `(Coref $m $a)` was loaded; rule still did not fire | 1 |
| | **Total** | | **33** |

In 32 of the 33 cases the premise was simply absent from the parse. The one exception is case 12, where the premise was present.

## Groups, with invented examples

**1. `month_class` (13).** Rule: `(Month $t $m) → (Member $t $m)`. A date that names a month should produce a `Month` fact. In these cases the date was parsed (or skipped) without one.
*Example:* "The Calderwick rehearsal is on 14 March."
*Expected:* `(Month calderwick_rehearsal march)`, from which the rule gives `(Member calderwick_rehearsal march)`.

**2. `rank_orders` (5).** Rule: two `(Ordinal $a $m $s $c)` facts on the same scale `$s` and class `$c`, with `$m < $n`, give `(More $s $a $b)`. Words like "first", "second" and "third", and ranked lists, did not produce `Ordinal` facts.
*Example:* "In the setlist, Lantern Song is first and Low Tide is third."
*Expected:* `(Ordinal lantern_song 1 setlist_position song)` and `(Ordinal low_tide 3 setlist_position song)`. Note that the rule needs `$s != $c`, so the scale and the class must be different symbols.

**3. `becauseof_cause` (4).** Rule: `(BecauseOf $e $x) → (Because $e $x)`. Causal phrases ("because of", "due to", "since …") produced no `BecauseOf` fact.
*Example:* "The show was moved because of the storm."
*Expected:* `(BecauseOf move_show storm)`.

**4. `measure_same` (2).** Rule: two `(Measure $x $d $a $u)` facts with the same dimension, amount and unit give `(SameDegree $d $x $y)`. The amounts were in the text but no `Measure` fact was produced.
*Example:* "Both amplifiers weigh 12 kilograms."
*Expected:* `(Measure amp_a weight 12 kilogram)` and `(Measure amp_b weight 12 kilogram)`.

**5. `measure_moreby` (2).** Rule: two `Measure` facts in the same dimension and unit give `(MoreBy $d $x $y $g $u)`. As in group 4, the `Measure` facts were missing.
*Example:* "The main hall seats 300 people and the side room seats 120."
*Expected:* `(Measure main_hall capacity 300 person)` and `(Measure side_room capacity 120 person)`, from which the rule gives a difference of 180.

**6. `unit_measure` (1).** Rule: `(Measure $x $d $n $u)` plus `(UnitFactor $u $c $f)` gives the same measure in unit `$c`. The `Measure` fact was missing.
*Example:* "The cable is 300 centimetres long."
*Expected:* `(Measure cable length 300 centimetre)`. With the seeded `(UnitFactor centimetre metre 0.01)` the rule gives `(Measure cable length 3.0 metre)`. The unit has to be the full unit symbol used in the seeded `UnitFactor` facts (`centimetre`, `gram`, …), not an abbreviation such as `cm`.

**7. `unit_atmost` (1).** Rule: like group 6, but for upper bounds. A phrase like "at most" or "no more than" did not produce `MeasureAtMost`.
*Example:* "Each case can hold at most 500 grams of picks."
*Expected:* `(MeasureAtMost case_each weight 500 gram)`. With the seeded `(UnitFactor gram kilogram 0.001)` the rule gives `(MeasureAtMost case_each weight 0.5 kilogram)`.

**8. `subset_is_part` (1).** Rule: `(SubsetOf $s $g) → (PartOf $s $g)`. A "some of the …" or "a subset of …" phrase produced no `SubsetOf`.
*Example:* "The brass players are a subset of the Norland band."
*Expected:* `(SubsetOf brass_players norland_band)`.

**9. `located_trans` (1).** Rule: `(LocatedIn $x $y)` and `(LocatedIn $y $z)` give `(LocatedIn $x $z)`. One of the two links was not produced.
*Example:* "The mixer is in the booth. The booth is in the main hall."
*Expected:* `(LocatedIn mixer booth)` and `(LocatedIn booth main_hall)`.

**10. `located_in_part` (1).** Rule: `(LocatedIn $x $p)` and `(PartOf $p $w)` give `(LocatedIn $x $w)`. The `LocatedIn` fact was missing.
*Example:* "The spare strings are in the east wing, which is part of the venue."
*Expected:* `(LocatedIn spare_strings east_wing)` and `(PartOf east_wing venue)`.

**11. `days_before_day` (1).** Rule: `(BeforeBy $t $a $n day)` and `(Day $a $d)` give `(Day $t $d-$n)`. The phrase "N days before X" did not produce `BeforeBy`.
*Example:* "The sound check is two days before the concert. The concert is on day 10."
*Expected:* `(BeforeBy sound_check concert 2 day)` and `(Day concert 10)`, from which the rule gives `(Day sound_check 8)`.

**12. `coref_theme` (1).** Rule: `(Coref $m $a)` and `(Theme $e $m)` give `(Theme $e $a)`. Here the `Coref` fact *was* in the KB, but the conclusion still was not derived. The most likely cause is that the `Theme` role was attached to a different term than the mention `$m` that `Coref` links. We have not confirmed this.
*Example:* "Mira tuned the old guitar. She then sold it."
*Expected:* `(Coref it_2 old_guitar)` and `(Theme sell_1 it_2)`. Both must use the same mention symbol `it_2`.

## Bug: one label, two different statements

**What we saw.** In one note's lowering, two atoms had the same label but different statements. Both were directives of the form `(Directive (And …))` with truth value `(STV 1.0 0.99)`. One had four conjuncts (`Member`, `Patient`, `Beneficiary`, `Location`). The other had the same four plus two more `Member` conjuncts. It happened once, in one note, in our main run (about 1,400 labelled statements). No other label in that run had more than one statement. This is a single case and we have not reproduced it on other input.

**Why it matters.** The label is the proof name. With two statements under one name, a proof that cites the label is ambiguous, and anything keyed by label (dedup, retraction, or a later update) may keep one statement and silently drop the other.

**Synthetic reproduction (invented text):**

> "Please set up the speakers in the hall for Mira. Please set up the speakers in the hall for Mira, the big ones and the black ones."

What we'd expect is two distinct labels, for example `dir_setup_1` and `dir_setup_2`:
```
(: dir_setup_1 (Directive (And (Member s1 set_up) (Patient s1 speakers) (Beneficiary s1 mira) (Location s1 hall))) (STV 1.0 0.99))
(: dir_setup_2 (Directive (And (Member s2 set_up) (Patient s2 speakers) (Beneficiary s2 mira) (Location s2 hall) (Member speakers big) (Member speakers black))) (STV 1.0 0.99))
```
What the bug looks like is the same label on both lines. A check that would catch it: after lowering, no label appears with two different statements.
