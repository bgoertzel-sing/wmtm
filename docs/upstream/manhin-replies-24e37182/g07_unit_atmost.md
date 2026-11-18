# g07_unit_atmost

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `unit_atmost`. Premise predicate(s) looked for: `MeasureAtMost`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "Each case can hold at most 500 grams of picks."

Raw reply records (all fields, incl. usage and raw_text): g07_unit_atmost.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g07_unit_atmost.s01",
 "instances": [],
 "unmapped": [
  {
   "span": "Each case can hold at most 500 grams of picks",
   "code": "G00",
   "construction": "A capacity statement: a container verb with a bounded measured amount as its object, under a capability modal and over a quantified class, stating the most each case can contain."
  }
 ],
 "issues": []
}
~~~

- unmapped codes: G00
- issues codes: none
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
~~~

**r1 summary.** Premise predicate(s): none. Rule `unit_atmost` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g07_unit_atmost.s01",
 "instances": [],
 "unmapped": [
  {
   "span": "Each case can hold at most 500 grams of picks",
   "code": "G00",
   "construction": "A capacity statement: a container verb (can hold) whose object is an upper-bounded measured amount, saying how much each case is able to contain."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "measure",
   "text": "The measure template covers a bounded quantity of a substance (MeasureAtMost on a witness of the stuff), and the locative template covers holding a separate thing, but the stative-relation boundary sends 'holds forty litres' to unmapped; under 'can hold', the bound is the container's capacity rather than an amount actually held, and no instruction says how to combine the bound with the capability modal."
  }
 ]
}
~~~

- unmapped codes: G00
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
~~~

**r2 summary.** Premise predicate(s): none. Rule `unit_atmost` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g07_unit_atmost.s01",
 "instances": [],
 "unmapped": [
  {
   "span": "Each case can hold at most 500 grams of picks",
   "code": "G00",
   "construction": "A capacity statement: a quantified container subject with can hold and an upper-bounded measure of a substance, where the bound scopes over the modal (no case can hold more than 500 grams), so neither the measure nor the containment can be stated on its own."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "measure",
   "text": "The instructions cover a bounded measure (MeasureAtMost) and a capability modal (Can) separately, but not an upper bound that scopes over the modal (can hold at most N means it cannot hold more than N). Putting the bound inside Can would state a different and weaker claim. The stative-relation boundary also sends 'holds forty litres' to unmapped, so the whole clause is reported."
  }
 ]
}
~~~

- unmapped codes: G00
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
~~~

**r3 summary.** Premise predicate(s): none. Rule `unit_atmost` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

