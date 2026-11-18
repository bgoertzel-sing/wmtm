# g12_coref_theme

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `coref_theme`. Premise predicate(s) looked for: `Coref`, `Theme`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "Mira tuned the old guitar."
- s2: "She then sold it."

Raw reply records (all fields, incl. usage and raw_text): g12_coref_theme.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g12_coref_theme.s01",
 "instances": [
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Mira",
   "span": "Mira"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "guitar",
   "definite": true,
   "props": [
    "old"
   ],
   "span": "the old guitar"
  },
  {
   "t": "activity",
   "id": "v1",
   "verb": "tune",
   "actor": "@n1",
   "patient": "@x1",
   "tense": "past",
   "span": "Mira tuned the old guitar"
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
(: s1_n1_name (Name mira "Mira") (STV 1.0 0.99))
(: s1_x1_member (Member sk_guitar_1__mh_g12_coref_theme guitar) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_guitar_1__mh_g12_coref_theme guitar__member_old) (STV 1.0 0.99))
(: s1_x1_implication (Implication (Member sk_guitar_1__mh_g12_coref_theme guitar__member_old) (Member sk_guitar_1__mh_g12_coref_theme old)) (STV 0.9 0.7))
(: s1_v1_member (Member sk_tune_1__mh_g12_coref_theme tune) (STV 1.0 0.99))
(: s1_v1_agent (Agent sk_tune_1__mh_g12_coref_theme mira) (STV 1.0 0.99))
(: s1_v1_patient (Patient sk_tune_1__mh_g12_coref_theme sk_guitar_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s1_v1_past (Past sk_tune_1__mh_g12_coref_theme) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "g12_coref_theme.s02",
 "instances": [
  {
   "t": "mention",
   "id": "m1",
   "word": "she",
   "span": "She"
  },
  {
   "t": "mention",
   "id": "m2",
   "word": "it",
   "span": "it"
  },
  {
   "t": "coref",
   "id": "c1",
   "mention": "@m1",
   "antecedent": "@s1.n1",
   "certainty": "certain",
   "span": "She"
  },
  {
   "t": "coref",
   "id": "c2",
   "mention": "@m2",
   "antecedent": "@s1.x1",
   "certainty": "certain",
   "span": "it"
  },
  {
   "t": "transfer",
   "id": "e1",
   "verb": "sell",
   "giver": "@m1",
   "object": "@m2",
   "tense": "past",
   "span": "She then sold it"
  },
  {
   "t": "time-relation",
   "id": "r1",
   "event": "@e1",
   "reference": "@s1.v1",
   "head": "After",
   "word": "then",
   "span": "then"
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "Earlier sentences as context",
   "text": "The section says the TEXT refers to the CONTEXT only through coreference, yet 'then' must order the TEXT's event after an event of the CONTEXT; it is unclear whether a time-relation may name a CONTEXT predication (here @s1.v1) as its reference."
  }
 ]
}
~~~

- unmapped codes: none
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `malformed`, findings: instance x3
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

  - inspect instance: instance 2 (coref): antecedent references unknown instance @s1.n1
  - inspect instance: instance 3 (coref): antecedent references unknown instance @s1.x1
  - inspect instance: instance 5 (time-relation): reference references unknown instance @s1.v1

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s2_m1_member (Member sk_she_1__mh_g12_coref_theme female) (STV 1.0 0.99))
(: s2_c1_coref (Coref sk_she_1__mh_g12_coref_theme mira) (STV 0.99 0.9))
(: s2_c2_coref (Coref sk_it_1__mh_g12_coref_theme sk_guitar_1__mh_g12_coref_theme) (STV 0.99 0.9))
(: s2_e1_member (Member sk_sell_1__mh_g12_coref_theme sell) (STV 1.0 0.99))
(: s2_e1_agent (Agent sk_sell_1__mh_g12_coref_theme sk_she_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s2_e1_theme (Theme sk_sell_1__mh_g12_coref_theme sk_it_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s2_e1_past (Past sk_sell_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s2_r1_before (Before sk_tune_1__mh_g12_coref_theme sk_sell_1__mh_g12_coref_theme) (STV 1.0 0.99))
~~~

**r1 summary.** Premise predicate(s): Coref top x2, Theme top x1. Rule `coref_theme` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g12_coref_theme.s01",
 "instances": [
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Mira",
   "span": "Mira"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "guitar",
   "definite": true,
   "props": [
    "old"
   ],
   "span": "the old guitar"
  },
  {
   "t": "activity",
   "id": "v1",
   "verb": "tune",
   "actor": "@n1",
   "patient": "@x1",
   "tense": "past",
   "span": "Mira tuned the old guitar"
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
(: s1_n1_name (Name mira "Mira") (STV 1.0 0.99))
(: s1_x1_member (Member sk_guitar_1__mh_g12_coref_theme guitar) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_guitar_1__mh_g12_coref_theme guitar__member_old) (STV 1.0 0.99))
(: s1_x1_implication (Implication (Member sk_guitar_1__mh_g12_coref_theme guitar__member_old) (Member sk_guitar_1__mh_g12_coref_theme old)) (STV 0.9 0.7))
(: s1_v1_member (Member sk_tune_1__mh_g12_coref_theme tune) (STV 1.0 0.99))
(: s1_v1_agent (Agent sk_tune_1__mh_g12_coref_theme mira) (STV 1.0 0.99))
(: s1_v1_patient (Patient sk_tune_1__mh_g12_coref_theme sk_guitar_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s1_v1_past (Past sk_tune_1__mh_g12_coref_theme) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "g12_coref_theme.s02",
 "instances": [
  {
   "t": "mention",
   "id": "m1",
   "word": "she",
   "span": "She"
  },
  {
   "t": "mention",
   "id": "m2",
   "word": "it",
   "span": "it"
  },
  {
   "t": "transfer",
   "id": "e1",
   "verb": "sell",
   "giver": "@m1",
   "object": "@m2",
   "tense": "past",
   "span": "She then sold it"
  },
  {
   "t": "time-relation",
   "id": "r1",
   "event": "@e1",
   "reference": "@s1.v1",
   "head": "After",
   "word": "then",
   "span": "then"
  },
  {
   "t": "coref",
   "id": "c1",
   "mention": "@m1",
   "antecedent": "@s1.n1",
   "certainty": "certain",
   "span": [
    "Mira",
    "She"
   ]
  },
  {
   "t": "coref",
   "id": "c2",
   "mention": "@m2",
   "antecedent": "@s1.x1",
   "certainty": "certain",
   "span": [
    "the old guitar",
    "it"
   ]
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "Earlier sentences as context",
   "text": "The section says the TEXT refers to the CONTEXT only through coreference, yet a sentence-initial or medial 'then' orders the TEXT's event after a CONTEXT event via the time-relation template; it is unclear whether a time-relation may name a qualified CONTEXT event (s1.v1) as its reference."
  }
 ]
}
~~~

- unmapped codes: none
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `malformed`, findings: instance x3
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

  - inspect instance: instance 3 (time-relation): reference references unknown instance @s1.v1
  - inspect instance: instance 4 (coref): antecedent references unknown instance @s1.n1
  - inspect instance: instance 5 (coref): antecedent references unknown instance @s1.x1

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s2_m1_member (Member sk_she_1__mh_g12_coref_theme female) (STV 1.0 0.99))
(: s2_e1_member (Member sk_sell_1__mh_g12_coref_theme sell) (STV 1.0 0.99))
(: s2_e1_agent (Agent sk_sell_1__mh_g12_coref_theme sk_she_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s2_e1_theme (Theme sk_sell_1__mh_g12_coref_theme sk_it_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s2_e1_past (Past sk_sell_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s2_r1_before (Before sk_tune_1__mh_g12_coref_theme sk_sell_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s2_c1_coref (Coref sk_she_1__mh_g12_coref_theme mira) (STV 0.99 0.9))
(: s2_c2_coref (Coref sk_it_1__mh_g12_coref_theme sk_guitar_1__mh_g12_coref_theme) (STV 0.99 0.9))
~~~

**r2 summary.** Premise predicate(s): Coref top x2, Theme top x1. Rule `coref_theme` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g12_coref_theme.s01",
 "instances": [
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Mira",
   "span": "Mira"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "guitar",
   "definite": true,
   "props": [
    "old"
   ],
   "span": "the old guitar"
  },
  {
   "t": "activity",
   "id": "v1",
   "verb": "tune",
   "actor": "@n1",
   "patient": "@x1",
   "tense": "past",
   "span": "Mira tuned the old guitar"
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
(: s1_n1_name (Name mira "Mira") (STV 1.0 0.99))
(: s1_x1_member (Member sk_guitar_1__mh_g12_coref_theme guitar) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_guitar_1__mh_g12_coref_theme guitar__member_old) (STV 1.0 0.99))
(: s1_x1_implication (Implication (Member sk_guitar_1__mh_g12_coref_theme guitar__member_old) (Member sk_guitar_1__mh_g12_coref_theme old)) (STV 0.9 0.7))
(: s1_v1_member (Member sk_tune_1__mh_g12_coref_theme tune) (STV 1.0 0.99))
(: s1_v1_agent (Agent sk_tune_1__mh_g12_coref_theme mira) (STV 1.0 0.99))
(: s1_v1_patient (Patient sk_tune_1__mh_g12_coref_theme sk_guitar_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s1_v1_past (Past sk_tune_1__mh_g12_coref_theme) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "g12_coref_theme.s02",
 "instances": [
  {
   "t": "mention",
   "id": "m1",
   "word": "she",
   "span": "She"
  },
  {
   "t": "mention",
   "id": "m2",
   "word": "it",
   "span": "it"
  },
  {
   "t": "transfer",
   "id": "e1",
   "verb": "sell",
   "giver": "@m1",
   "object": "@m2",
   "tense": "past",
   "span": "She then sold it"
  },
  {
   "t": "time-relation",
   "id": "r1",
   "event": "@e1",
   "reference": "@s1.v1",
   "head": "After",
   "word": "then",
   "span": "then"
  },
  {
   "t": "coref",
   "id": "c1",
   "mention": "@m1",
   "antecedent": "@s1.n1",
   "certainty": "certain",
   "span": [
    "Mira",
    "She"
   ]
  },
  {
   "t": "coref",
   "id": "c2",
   "mention": "@m2",
   "antecedent": "@s1.x1",
   "certainty": "certain",
   "span": [
    "the old guitar",
    "it"
   ]
  }
 ],
 "unmapped": [],
 "issues": []
}
~~~

- unmapped codes: none
- issues codes: none
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `malformed`, findings: instance x3
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

  - inspect instance: instance 3 (time-relation): reference references unknown instance @s1.v1
  - inspect instance: instance 4 (coref): antecedent references unknown instance @s1.n1
  - inspect instance: instance 5 (coref): antecedent references unknown instance @s1.x1

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s2_m1_member (Member sk_she_1__mh_g12_coref_theme female) (STV 1.0 0.99))
(: s2_e1_member (Member sk_sell_1__mh_g12_coref_theme sell) (STV 1.0 0.99))
(: s2_e1_agent (Agent sk_sell_1__mh_g12_coref_theme sk_she_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s2_e1_theme (Theme sk_sell_1__mh_g12_coref_theme sk_it_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s2_e1_past (Past sk_sell_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s2_r1_before (Before sk_tune_1__mh_g12_coref_theme sk_sell_1__mh_g12_coref_theme) (STV 1.0 0.99))
(: s2_c1_coref (Coref sk_she_1__mh_g12_coref_theme mira) (STV 0.99 0.9))
(: s2_c2_coref (Coref sk_it_1__mh_g12_coref_theme sk_guitar_1__mh_g12_coref_theme) (STV 0.99 0.9))
~~~

**r3 summary.** Premise predicate(s): Coref top x2, Theme top x1. Rule `coref_theme` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

