# g10_located_in_part

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `located_in_part`. Premise predicate(s) looked for: `LocatedIn`, `PartOf`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "The spare strings are in the east wing, which is part of the venue."

Raw reply records (all fields, incl. usage and raw_text): g10_located_in_part.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g10_located_in_part.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "string",
   "definite": true,
   "props": [
    "spare"
   ],
   "span": "The spare strings"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "wing",
   "definite": true,
   "props": [
    "east"
   ],
   "span": "the east wing"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "venue",
   "definite": true,
   "span": "the venue"
  },
  {
   "t": "locative",
   "id": "l1",
   "thing": "@g1",
   "place": "@x1",
   "head": "LocatedIn",
   "preposition": "in",
   "tense": "present",
   "span": "The spare strings are in the east wing"
  },
  {
   "t": "part-whole",
   "id": "w1",
   "part": "@x1",
   "whole": "@x2",
   "word": "part of",
   "tense": "present",
   "span": "the east wing, which is part of the venue"
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
(: s1_g1_groupof (GroupOf sk_group_1__mh_g10_located_in_part string) (STV 1.0 0.99))
(: s1_g1_groupof_2 (GroupOf sk_group_1__mh_g10_located_in_part string__member_spare) (STV 1.0 0.99))
(: s1_x1_member (Member sk_wing_1__mh_g10_located_in_part wing) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_wing_1__mh_g10_located_in_part wing__member_east) (STV 1.0 0.99))
(: s1_x1_implication (Implication (Member sk_wing_1__mh_g10_located_in_part wing__member_east) (Member sk_wing_1__mh_g10_located_in_part east)) (STV 0.9 0.7))
(: s1_x2_member (Member sk_venue_1__mh_g10_located_in_part venue) (STV 1.0 0.99))
(: s1_l1_locatedin (LocatedIn sk_group_1__mh_g10_located_in_part sk_wing_1__mh_g10_located_in_part) (STV 1.0 0.99))
(: s1_w1_partof (PartOf sk_wing_1__mh_g10_located_in_part sk_venue_1__mh_g10_located_in_part) (STV 1.0 0.99))
~~~

**r1 summary.** Premise predicate(s): LocatedIn top x1, PartOf top x1. Rule `located_in_part` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g10_located_in_part.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "string",
   "definite": true,
   "props": [
    "spare"
   ],
   "span": "The spare strings"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "wing",
   "definite": true,
   "props": [
    "east"
   ],
   "span": "the east wing"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "venue",
   "definite": true,
   "span": "the venue"
  },
  {
   "t": "locative",
   "id": "l1",
   "thing": "@g1",
   "place": "@x1",
   "head": "LocatedIn",
   "preposition": "in",
   "tense": "present",
   "span": "The spare strings are in the east wing"
  },
  {
   "t": "part-whole",
   "id": "w1",
   "part": "@x1",
   "whole": "@x2",
   "word": "part of",
   "tense": "present",
   "span": "the east wing, which is part of the venue"
  },
  {
   "t": "distribution",
   "id": "d1",
   "group": "@g1",
   "over": [
    "@l1"
   ],
   "span": "The spare strings are in the east wing"
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
(: s1_g1_groupof (GroupOf sk_group_1__mh_g10_located_in_part string) (STV 1.0 0.99))
(: s1_g1_groupof_2 (GroupOf sk_group_1__mh_g10_located_in_part string__member_spare) (STV 1.0 0.99))
(: s1_x1_member (Member sk_wing_1__mh_g10_located_in_part wing) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_wing_1__mh_g10_located_in_part wing__member_east) (STV 1.0 0.99))
(: s1_x1_implication (Implication (Member sk_wing_1__mh_g10_located_in_part wing__member_east) (Member sk_wing_1__mh_g10_located_in_part east)) (STV 0.9 0.7))
(: s1_x2_member (Member sk_venue_1__mh_g10_located_in_part venue) (STV 1.0 0.99))
(: s1_l1_locatedin (LocatedIn sk_group_1__mh_g10_located_in_part sk_wing_1__mh_g10_located_in_part) (STV 1.0 0.99))
(: s1_w1_partof (PartOf sk_wing_1__mh_g10_located_in_part sk_venue_1__mh_g10_located_in_part) (STV 1.0 0.99))
(: s1_d1_implication (Implication (PartOf $x sk_group_1__mh_g10_located_in_part) (LocatedIn $x sk_wing_1__mh_g10_located_in_part)) (STV 1.0 0.9))
~~~

**r2 summary.** Premise predicate(s): LocatedIn in Implication x1, LocatedIn top x1, PartOf in Implication x1, PartOf top x1. Rule `located_in_part` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g10_located_in_part.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "string",
   "definite": true,
   "props": [
    "spare"
   ],
   "span": "The spare strings"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "wing",
   "definite": true,
   "props": [
    "east"
   ],
   "span": "the east wing"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "venue",
   "definite": true,
   "span": "the venue"
  },
  {
   "t": "locative",
   "id": "l1",
   "thing": "@g1",
   "place": "@x1",
   "head": "LocatedIn",
   "preposition": "in",
   "tense": "present",
   "span": "The spare strings are in the east wing"
  },
  {
   "t": "part-whole",
   "id": "w1",
   "part": "@x1",
   "whole": "@x2",
   "word": "part of",
   "tense": "present",
   "span": "which is part of the venue"
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
(: s1_g1_groupof (GroupOf sk_group_1__mh_g10_located_in_part string) (STV 1.0 0.99))
(: s1_g1_groupof_2 (GroupOf sk_group_1__mh_g10_located_in_part string__member_spare) (STV 1.0 0.99))
(: s1_x1_member (Member sk_wing_1__mh_g10_located_in_part wing) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_wing_1__mh_g10_located_in_part wing__member_east) (STV 1.0 0.99))
(: s1_x1_implication (Implication (Member sk_wing_1__mh_g10_located_in_part wing__member_east) (Member sk_wing_1__mh_g10_located_in_part east)) (STV 0.9 0.7))
(: s1_x2_member (Member sk_venue_1__mh_g10_located_in_part venue) (STV 1.0 0.99))
(: s1_l1_locatedin (LocatedIn sk_group_1__mh_g10_located_in_part sk_wing_1__mh_g10_located_in_part) (STV 1.0 0.99))
(: s1_w1_partof (PartOf sk_wing_1__mh_g10_located_in_part sk_venue_1__mh_g10_located_in_part) (STV 1.0 0.99))
~~~

**r3 summary.** Premise predicate(s): LocatedIn top x1, PartOf top x1. Rule `located_in_part` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

