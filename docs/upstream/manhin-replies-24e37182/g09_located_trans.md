# g09_located_trans

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `located_trans`. Premise predicate(s) looked for: `LocatedIn`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "The mixer is in the booth."
- s2: "The booth is in the main hall."

Raw reply records (all fields, incl. usage and raw_text): g09_located_trans.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g09_located_trans.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "mixer",
   "definite": true,
   "span": "The mixer"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "booth",
   "definite": true,
   "span": "the booth"
  },
  {
   "t": "locative",
   "id": "l1",
   "thing": "@x1",
   "place": "@x2",
   "head": "LocatedIn",
   "preposition": "in",
   "tense": "present",
   "span": "The mixer is in the booth"
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
(: s1_x1_member (Member sk_mixer_1__mh_g09_located_trans mixer) (STV 1.0 0.99))
(: s1_x2_member (Member sk_booth_1__mh_g09_located_trans booth) (STV 1.0 0.99))
(: s1_l1_locatedin (LocatedIn sk_mixer_1__mh_g09_located_trans sk_booth_1__mh_g09_located_trans) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "g09_located_trans.s02",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "booth",
   "definite": true,
   "span": "The booth"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "hall",
   "definite": true,
   "props": [
    "main"
   ],
   "span": "the main hall"
  },
  {
   "t": "locative",
   "id": "l1",
   "thing": "@x1",
   "place": "@x2",
   "head": "LocatedIn",
   "preposition": "in",
   "tense": "present",
   "span": "The booth is in the main hall"
  },
  {
   "t": "coref",
   "id": "c1",
   "mention": "@x1",
   "antecedent": "@s1.x2",
   "certainty": "certain",
   "span": [
    "the booth",
    "The booth"
   ]
  }
 ],
 "unmapped": [],
 "issues": []
}
~~~

- unmapped codes: none
- issues codes: none
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `malformed`, findings: instance x1
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

  - inspect instance: instance 3 (coref): antecedent references unknown instance @s1.x2

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s2_x1_member (Member sk_booth_2__mh_g09_located_trans booth) (STV 1.0 0.99))
(: s2_x2_member (Member sk_hall_1__mh_g09_located_trans hall) (STV 1.0 0.99))
(: s2_x2_member_2 (Member sk_hall_1__mh_g09_located_trans hall__member_main) (STV 1.0 0.99))
(: s2_x2_implication (Implication (Member sk_hall_1__mh_g09_located_trans hall__member_main) (Member sk_hall_1__mh_g09_located_trans main)) (STV 0.9 0.7))
(: s2_l1_locatedin (LocatedIn sk_booth_2__mh_g09_located_trans sk_hall_1__mh_g09_located_trans) (STV 1.0 0.99))
(: s2_c1_coref (Coref sk_booth_2__mh_g09_located_trans sk_booth_1__mh_g09_located_trans) (STV 0.99 0.9))
~~~

**r1 summary.** Premise predicate(s): LocatedIn top x2. Rule `located_trans` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g09_located_trans.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "mixer",
   "definite": true,
   "span": "The mixer"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "booth",
   "definite": true,
   "span": "the booth"
  },
  {
   "t": "locative",
   "id": "l1",
   "thing": "@x1",
   "place": "@x2",
   "head": "LocatedIn",
   "preposition": "in",
   "tense": "present",
   "span": "The mixer is in the booth"
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
(: s1_x1_member (Member sk_mixer_1__mh_g09_located_trans mixer) (STV 1.0 0.99))
(: s1_x2_member (Member sk_booth_1__mh_g09_located_trans booth) (STV 1.0 0.99))
(: s1_l1_locatedin (LocatedIn sk_mixer_1__mh_g09_located_trans sk_booth_1__mh_g09_located_trans) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "g09_located_trans.s02",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "booth",
   "definite": true,
   "span": "The booth"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "hall",
   "definite": true,
   "props": [
    "main"
   ],
   "span": "the main hall"
  },
  {
   "t": "locative",
   "id": "l1",
   "thing": "@x1",
   "place": "@x2",
   "head": "LocatedIn",
   "preposition": "in",
   "tense": "present",
   "span": "The booth is in the main hall"
  },
  {
   "t": "coref",
   "id": "c1",
   "mention": "@x1",
   "antecedent": "@s1.x2",
   "certainty": "certain",
   "span": [
    "the booth",
    "The booth"
   ]
  }
 ],
 "unmapped": [],
 "issues": []
}
~~~

- unmapped codes: none
- issues codes: none
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `malformed`, findings: instance x1
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

  - inspect instance: instance 3 (coref): antecedent references unknown instance @s1.x2

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s2_x1_member (Member sk_booth_2__mh_g09_located_trans booth) (STV 1.0 0.99))
(: s2_x2_member (Member sk_hall_1__mh_g09_located_trans hall) (STV 1.0 0.99))
(: s2_x2_member_2 (Member sk_hall_1__mh_g09_located_trans hall__member_main) (STV 1.0 0.99))
(: s2_x2_implication (Implication (Member sk_hall_1__mh_g09_located_trans hall__member_main) (Member sk_hall_1__mh_g09_located_trans main)) (STV 0.9 0.7))
(: s2_l1_locatedin (LocatedIn sk_booth_2__mh_g09_located_trans sk_hall_1__mh_g09_located_trans) (STV 1.0 0.99))
(: s2_c1_coref (Coref sk_booth_2__mh_g09_located_trans sk_booth_1__mh_g09_located_trans) (STV 0.99 0.9))
~~~

**r2 summary.** Premise predicate(s): LocatedIn top x2. Rule `located_trans` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g09_located_trans.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "mixer",
   "definite": true,
   "span": "The mixer"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "booth",
   "definite": true,
   "span": "the booth"
  },
  {
   "t": "locative",
   "id": "l1",
   "thing": "@x1",
   "place": "@x2",
   "head": "LocatedIn",
   "preposition": "in",
   "tense": "present",
   "span": "The mixer is in the booth"
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
(: s1_x1_member (Member sk_mixer_1__mh_g09_located_trans mixer) (STV 1.0 0.99))
(: s1_x2_member (Member sk_booth_1__mh_g09_located_trans booth) (STV 1.0 0.99))
(: s1_l1_locatedin (LocatedIn sk_mixer_1__mh_g09_located_trans sk_booth_1__mh_g09_located_trans) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "g09_located_trans.s02",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "booth",
   "definite": true,
   "span": "The booth"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "hall",
   "definite": true,
   "props": [
    "main"
   ],
   "span": "the main hall"
  },
  {
   "t": "locative",
   "id": "l1",
   "thing": "@x1",
   "place": "@x2",
   "head": "LocatedIn",
   "preposition": "in",
   "tense": "present",
   "span": "The booth is in the main hall"
  },
  {
   "t": "coref",
   "id": "c1",
   "mention": "@x1",
   "antecedent": "@s1.x2",
   "certainty": "certain",
   "span": [
    "the booth",
    "The booth"
   ]
  }
 ],
 "unmapped": [],
 "issues": []
}
~~~

- unmapped codes: none
- issues codes: none
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `malformed`, findings: instance x1
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

  - inspect instance: instance 3 (coref): antecedent references unknown instance @s1.x2

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s2_x1_member (Member sk_booth_2__mh_g09_located_trans booth) (STV 1.0 0.99))
(: s2_x2_member (Member sk_hall_1__mh_g09_located_trans hall) (STV 1.0 0.99))
(: s2_x2_member_2 (Member sk_hall_1__mh_g09_located_trans hall__member_main) (STV 1.0 0.99))
(: s2_x2_implication (Implication (Member sk_hall_1__mh_g09_located_trans hall__member_main) (Member sk_hall_1__mh_g09_located_trans main)) (STV 0.9 0.7))
(: s2_l1_locatedin (LocatedIn sk_booth_2__mh_g09_located_trans sk_hall_1__mh_g09_located_trans) (STV 1.0 0.99))
(: s2_c1_coref (Coref sk_booth_2__mh_g09_located_trans sk_booth_1__mh_g09_located_trans) (STV 0.99 0.9))
~~~

**r3 summary.** Premise predicate(s): LocatedIn top x2. Rule `located_trans` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

