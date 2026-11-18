# g05_measure_moreby

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `measure_moreby`. Premise predicate(s) looked for: `Measure`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "The main hall seats 300 people and the side room seats 120."

Raw reply records (all fields, incl. usage and raw_text): g05_measure_moreby.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g05_measure_moreby.s01",
 "instances": [],
 "unmapped": [
  {
   "span": "The main hall seats 300 people",
   "code": "G00",
   "construction": "A capacity verb (seats) with a counted noun phrase states how many people the hall can hold, not that any people were seated, and no template states a capacity."
  },
  {
   "span": "the side room seats 120",
   "code": "G00",
   "construction": "A capacity verb (seats) with a bare number states how many the room can hold, and no template states a capacity."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "measure",
   "text": "The measure template covers verbs such as weighs and costs but names no capacity dimension, while stative-relation's boundary says 'holds forty litres' has no template yet, so it is unclear whether capacity verbs (seats, holds) with a number are measures or unmapped."
  }
 ]
}
~~~

- unmapped codes: G00, G00
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
~~~

**r1 summary.** Premise predicate(s): none. Rule `measure_moreby` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g05_measure_moreby.s01",
 "instances": [],
 "unmapped": [
  {
   "span": "The main hall seats 300 people",
   "code": "G00",
   "construction": "A capacity verb (seats) with a count of people, stating how many a place can hold; no template covers capacity."
  },
  {
   "span": "the side room seats 120",
   "code": "G00",
   "construction": "A capacity verb (seats) with a bare number and the unit left out, stating how many a place can hold; no template covers capacity."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "measure",
   "text": "A capacity verb with a count (seats 300 people, holds forty litres) is not clearly covered. The measure template takes measure verbs with a unit such as weighs and costs, and gives no capacity dimension. Its boundary sends counts of things to a group. The stative-relation boundary sends 'holds forty litres' to unmapped G00."
  }
 ]
}
~~~

- unmapped codes: G00, G00
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
~~~

**r2 summary.** Premise predicate(s): none. Rule `measure_moreby` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g05_measure_moreby.s01",
 "instances": [],
 "unmapped": [
  {
   "span": "The main hall seats 300 people",
   "code": "G00",
   "construction": "A capacity verb (seats) with a counted noun phrase stating how many people a place can hold, not a count of actual people present."
  },
  {
   "span": "the side room seats 120",
   "code": "G00",
   "construction": "A capacity verb (seats) with a bare number stating how many a place can hold, its unit left understood from the first clause."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "measure",
   "text": "The measure template covers capacity-like verbs (weighs, costs) through the noun the verb gives, but the stative-relation boundary sends 'holds forty litres' to unmapped, and neither says whether a capacity verb like 'seats N people' is a measure (and with what dimension and unit) or unmapped."
  }
 ]
}
~~~

- unmapped codes: G00, G00
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
~~~

**r3 summary.** Premise predicate(s): none. Rule `measure_moreby` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

