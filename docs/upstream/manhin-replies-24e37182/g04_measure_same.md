# g04_measure_same

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `measure_same`. Premise predicate(s) looked for: `Measure`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "Both amplifiers weigh 12 kilograms."

Raw reply records (all fields, incl. usage and raw_text): g04_measure_same.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g04_measure_same.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "amplifier",
   "count": 2,
   "definite": true,
   "span": "Both amplifiers"
  },
  {
   "t": "measure",
   "id": "m1",
   "bearer": "@g1",
   "head": "Measure",
   "dimension": "weight",
   "magnitude": 12,
   "unit": "kilogram",
   "tense": "present",
   "span": "Both amplifiers weigh 12 kilograms"
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "measure",
   "text": "The measure template says a plural bearer is measured as a whole with no distribution, but with 'both' the natural reading is that each amplifier weighs 12 kilograms; the instructions give no way to choose the distributive reading for a measure, so the group is measured as a whole here."
  }
 ]
}
~~~

- unmapped codes: none
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s1_g1_groupof (GroupOf sk_group_1__mh_g04_measure_same amplifier) (STV 1.0 0.99))
(: s1_g1_cardinality (Cardinality sk_group_1__mh_g04_measure_same 2) (STV 1.0 0.99))
(: s1_m1_measure (Measure sk_group_1__mh_g04_measure_same weight 12 kilogram) (STV 1.0 0.99))
~~~

**r1 summary.** Premise predicate(s): Measure top x1. Rule `measure_same` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g04_measure_same.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "amplifier",
   "definite": true,
   "count": 2,
   "span": "Both amplifiers"
  },
  {
   "t": "measure",
   "id": "m1",
   "bearer": "@g1",
   "head": "Measure",
   "dimension": "weight",
   "magnitude": 12,
   "unit": "kilogram",
   "tense": "present",
   "span": "Both amplifiers weigh 12 kilograms"
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "measure",
   "text": "The measure template says a plural bearer measures the whole with no distribution, but 'both' here most naturally means each amplifier weighs 12 kilograms; the instructions give no way to distribute a measure over the members, so the parse follows the whole-group reading."
  }
 ]
}
~~~

- unmapped codes: none
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s1_g1_groupof (GroupOf sk_group_1__mh_g04_measure_same amplifier) (STV 1.0 0.99))
(: s1_g1_cardinality (Cardinality sk_group_1__mh_g04_measure_same 2) (STV 1.0 0.99))
(: s1_m1_measure (Measure sk_group_1__mh_g04_measure_same weight 12 kilogram) (STV 1.0 0.99))
~~~

**r2 summary.** Premise predicate(s): Measure top x1. Rule `measure_same` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g04_measure_same.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "amplifier",
   "definite": true,
   "count": 2,
   "span": "Both amplifiers"
  },
  {
   "t": "measure",
   "id": "m1",
   "bearer": "@g1",
   "head": "Measure",
   "dimension": "weight",
   "magnitude": 12,
   "unit": "kilogram",
   "tense": "present",
   "span": "Both amplifiers weigh 12 kilograms"
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "measure",
   "text": "The measure template says a plural bearer measures the whole with no distribution, but 'both' strongly favours the reading that each amplifier weighs 12 kilograms, and no instruction says whether a distribution may name a measure instance to give that reading."
  }
 ]
}
~~~

- unmapped codes: none
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s1_g1_groupof (GroupOf sk_group_1__mh_g04_measure_same amplifier) (STV 1.0 0.99))
(: s1_g1_cardinality (Cardinality sk_group_1__mh_g04_measure_same 2) (STV 1.0 0.99))
(: s1_m1_measure (Measure sk_group_1__mh_g04_measure_same weight 12 kilogram) (STV 1.0 0.99))
~~~

**r3 summary.** Premise predicate(s): Measure top x1. Rule `measure_same` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

