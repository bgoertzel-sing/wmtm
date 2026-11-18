# g08_subset_is_part

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `subset_is_part`. Premise predicate(s) looked for: `SubsetOf`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "The brass players are a subset of the Norland band."

Raw reply records (all fields, incl. usage and raw_text): g08_subset_is_part.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g08_subset_is_part.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "player",
   "definite": true,
   "mods": [
    "brass"
   ],
   "span": "The brass players"
  },
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Norland",
   "span": "Norland"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "band",
   "definite": true,
   "mods": [
    "@n1"
   ],
   "span": "the Norland band"
  },
  {
   "t": "part-whole",
   "id": "w1",
   "part": "@g1",
   "whole": "@x1",
   "word": "subset of",
   "tense": "present",
   "span": "The brass players are a subset of the Norland band"
  },
  {
   "t": "distribution",
   "id": "d1",
   "group": "@g1",
   "over": [
    "@w1"
   ],
   "span": "The brass players are a subset of the Norland band"
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "part-whole",
   "text": "A subset of a collective noun (a subset of the band) is not among the listed forms; it is read here as a plural part of a whole, with a distribution so that each member is a part, but the instructions do not say whether a subset relation between a group and a collective whole should instead be a portion or a part-whole without a distribution."
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
(: s1_g1_groupof (GroupOf sk_group_1__mh_g08_subset_is_part player) (STV 1.0 0.99))
(: s1_g1_groupof_2 (GroupOf sk_group_1__mh_g08_subset_is_part player__mod_brass) (STV 1.0 0.99))
(: s1_n1_name (Name norland "Norland") (STV 1.0 0.99))
(: s1_x1_member (Member sk_band_1__mh_g08_subset_is_part band) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_band_1__mh_g08_subset_is_part band__mod_norland) (STV 1.0 0.99))
(: s1_w1_partof (PartOf sk_group_1__mh_g08_subset_is_part sk_band_1__mh_g08_subset_is_part) (STV 1.0 0.99))
(: s1_d1_implication (Implication (PartOf $x sk_group_1__mh_g08_subset_is_part) (PartOf $x sk_band_1__mh_g08_subset_is_part)) (STV 1.0 0.9))
~~~

**r1 summary.** Premise predicate(s): none. Rule `subset_is_part` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g08_subset_is_part.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "player",
   "definite": true,
   "mods": [
    "brass"
   ],
   "span": "The brass players"
  },
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Norland",
   "span": "Norland"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "band",
   "definite": true,
   "mods": [
    "@n1"
   ],
   "span": "the Norland band"
  },
  {
   "t": "part-whole",
   "id": "w1",
   "part": "@g1",
   "whole": "@x1",
   "word": "a subset of",
   "tense": "present",
   "span": "The brass players are a subset of the Norland band"
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
(: s1_g1_groupof (GroupOf sk_group_1__mh_g08_subset_is_part player) (STV 1.0 0.99))
(: s1_g1_groupof_2 (GroupOf sk_group_1__mh_g08_subset_is_part player__mod_brass) (STV 1.0 0.99))
(: s1_n1_name (Name norland "Norland") (STV 1.0 0.99))
(: s1_x1_member (Member sk_band_1__mh_g08_subset_is_part band) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_band_1__mh_g08_subset_is_part band__mod_norland) (STV 1.0 0.99))
(: s1_w1_partof (PartOf sk_group_1__mh_g08_subset_is_part sk_band_1__mh_g08_subset_is_part) (STV 1.0 0.99))
~~~

**r2 summary.** Premise predicate(s): none. Rule `subset_is_part` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g08_subset_is_part.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "player",
   "mods": [
    "brass"
   ],
   "definite": true,
   "span": "The brass players"
  },
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Norland",
   "span": "Norland"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "band",
   "definite": true,
   "mods": [
    "@n1"
   ],
   "span": "the Norland band"
  },
  {
   "t": "part-whole",
   "id": "w1",
   "part": "@g1",
   "whole": "@x1",
   "word": "a subset of",
   "tense": "present",
   "span": "The brass players are a subset of the Norland band"
  },
  {
   "t": "distribution",
   "id": "d1",
   "group": "@g1",
   "over": [
    "@w1"
   ],
   "span": "The brass players are a subset of the Norland band"
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "part-whole",
   "text": "The forms list 'part of' and 'member of' but not 'a subset of'; it was read as part-whole with the group as the part. The rule that adds a distribution for a plural part does not say whether 'subset', which holds of the group as a whole, should still distribute to each member."
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
(: s1_g1_groupof (GroupOf sk_group_1__mh_g08_subset_is_part player) (STV 1.0 0.99))
(: s1_g1_groupof_2 (GroupOf sk_group_1__mh_g08_subset_is_part player__mod_brass) (STV 1.0 0.99))
(: s1_n1_name (Name norland "Norland") (STV 1.0 0.99))
(: s1_x1_member (Member sk_band_1__mh_g08_subset_is_part band) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_band_1__mh_g08_subset_is_part band__mod_norland) (STV 1.0 0.99))
(: s1_w1_partof (PartOf sk_group_1__mh_g08_subset_is_part sk_band_1__mh_g08_subset_is_part) (STV 1.0 0.99))
(: s1_d1_implication (Implication (PartOf $x sk_group_1__mh_g08_subset_is_part) (PartOf $x sk_band_1__mh_g08_subset_is_part)) (STV 1.0 0.9))
~~~

**r3 summary.** Premise predicate(s): none. Rule `subset_is_part` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

