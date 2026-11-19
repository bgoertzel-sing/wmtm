# g06_unit_measure

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `unit_measure`. Premise predicate(s) looked for: `Measure`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "The cable is 300 centimetres long."

Raw reply records (all fields, incl. usage and raw_text): g06_unit_measure.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g06_unit_measure.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "cable",
   "definite": true,
   "span": "The cable"
  },
  {
   "t": "measure",
   "id": "m1",
   "bearer": "@x1",
   "head": "Measure",
   "dimension": "long",
   "magnitude": 300,
   "unit": "centimetre",
   "tense": "present",
   "span": "The cable is 300 centimetres long"
  }
 ],
 "unmapped": [],
 "issues": []
}
~~~

- unmapped codes: none
- issues codes: none
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s1_x1_member (Member sk_cable_1__mh_g06_unit_measure cable) (STV 1.0 0.99))
(: s1_m1_measure (Measure sk_cable_1__mh_g06_unit_measure long 300 centimetre) (STV 1.0 0.99))
~~~

**r1 summary.** Premise predicate(s): Measure top x1. Rule `unit_measure` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g06_unit_measure.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "cable",
   "definite": true,
   "span": "The cable"
  },
  {
   "t": "measure",
   "id": "m1",
   "bearer": "@x1",
   "head": "Measure",
   "dimension": "long",
   "magnitude": 300,
   "unit": "centimetre",
   "tense": "present",
   "span": "The cable is 300 centimetres long"
  }
 ],
 "unmapped": [],
 "issues": []
}
~~~

- unmapped codes: none
- issues codes: none
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s1_x1_member (Member sk_cable_1__mh_g06_unit_measure cable) (STV 1.0 0.99))
(: s1_m1_measure (Measure sk_cable_1__mh_g06_unit_measure long 300 centimetre) (STV 1.0 0.99))
~~~

**r2 summary.** Premise predicate(s): Measure top x1. Rule `unit_measure` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g06_unit_measure.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "cable",
   "definite": true,
   "span": "The cable"
  },
  {
   "t": "measure",
   "id": "m1",
   "bearer": "@x1",
   "head": "Measure",
   "dimension": "long",
   "magnitude": 300,
   "unit": "centimetre",
   "tense": "present",
   "span": "The cable is 300 centimetres long"
  }
 ],
 "unmapped": [],
 "issues": []
}
~~~

- unmapped codes: none
- issues codes: none
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s1_x1_member (Member sk_cable_1__mh_g06_unit_measure cable) (STV 1.0 0.99))
(: s1_m1_measure (Measure sk_cable_1__mh_g06_unit_measure long 300 centimetre) (STV 1.0 0.99))
~~~

**r3 summary.** Premise predicate(s): Measure top x1. Rule `unit_measure` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

