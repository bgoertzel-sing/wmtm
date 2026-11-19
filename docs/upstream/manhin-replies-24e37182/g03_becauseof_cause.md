# g03_becauseof_cause

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `becauseof_cause`. Premise predicate(s) looked for: `BecauseOf`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "The show was moved because of the storm."

Raw reply records (all fields, incl. usage and raw_text): g03_becauseof_cause.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g03_becauseof_cause.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "show",
   "definite": true,
   "span": "The show"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "storm",
   "definite": true,
   "span": "the storm"
  },
  {
   "t": "motion",
   "id": "m1",
   "verb": "move",
   "moved": "@x1",
   "tense": "past",
   "span": "The show was moved"
  },
  {
   "t": "oblique",
   "id": "a1",
   "event": "@m1",
   "head": "BecauseOf",
   "object": "@x2",
   "span": "because of the storm"
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "motion",
   "text": "Moving an event to another time (rescheduling) is neither a change of place nor clearly a change of state, so no template plainly fits; it was parsed as an agentless motion with the show as the moved thing."
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
(: s1_x1_member (Member sk_show_1__mh_g03_becauseof_cause show) (STV 1.0 0.99))
(: s1_x2_member (Member sk_storm_1__mh_g03_becauseof_cause storm) (STV 1.0 0.99))
(: s1_m1_member (Member sk_move_1__mh_g03_becauseof_cause move) (STV 1.0 0.99))
(: s1_m1_theme (Theme sk_move_1__mh_g03_becauseof_cause sk_show_1__mh_g03_becauseof_cause) (STV 1.0 0.99))
(: s1_m1_past (Past sk_move_1__mh_g03_becauseof_cause) (STV 1.0 0.99))
(: s1_a1_becauseof (BecauseOf sk_move_1__mh_g03_becauseof_cause sk_storm_1__mh_g03_becauseof_cause) (STV 1.0 0.99))
~~~

**r1 summary.** Premise predicate(s): BecauseOf top x1. Rule `becauseof_cause` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g03_becauseof_cause.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "show",
   "definite": true,
   "span": "The show"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "storm",
   "definite": true,
   "span": "the storm"
  },
  {
   "t": "motion",
   "id": "m1",
   "verb": "move",
   "moved": "@x1",
   "tense": "past",
   "span": "The show was moved"
  },
  {
   "t": "oblique",
   "id": "a1",
   "event": "@m1",
   "head": "BecauseOf",
   "object": "@x2",
   "span": "because of the storm"
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "motion",
   "text": "Move with an event noun as its object (a show moved, i.e. rescheduled or relocated) is not clearly a change of place; the motion template lists move without saying whether rescheduling an event belongs there."
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
(: s1_x1_member (Member sk_show_1__mh_g03_becauseof_cause show) (STV 1.0 0.99))
(: s1_x2_member (Member sk_storm_1__mh_g03_becauseof_cause storm) (STV 1.0 0.99))
(: s1_m1_member (Member sk_move_1__mh_g03_becauseof_cause move) (STV 1.0 0.99))
(: s1_m1_theme (Theme sk_move_1__mh_g03_becauseof_cause sk_show_1__mh_g03_becauseof_cause) (STV 1.0 0.99))
(: s1_m1_past (Past sk_move_1__mh_g03_becauseof_cause) (STV 1.0 0.99))
(: s1_a1_becauseof (BecauseOf sk_move_1__mh_g03_becauseof_cause sk_storm_1__mh_g03_becauseof_cause) (STV 1.0 0.99))
~~~

**r2 summary.** Premise predicate(s): BecauseOf top x1. Rule `becauseof_cause` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g03_becauseof_cause.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "show",
   "definite": true,
   "span": "The show"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "storm",
   "definite": true,
   "span": "the storm"
  },
  {
   "t": "motion",
   "id": "m1",
   "verb": "move",
   "moved": "@x1",
   "tense": "past",
   "span": "The show was moved"
  },
  {
   "t": "oblique",
   "id": "a1",
   "event": "@m1",
   "head": "BecauseOf",
   "object": "@x2",
   "span": "because of the storm"
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "motion",
   "text": "Move with an event noun as the thing moved (a show moved) may mean rescheduled rather than a change of place; no template or boundary says which reading or template applies, so the literal motion reading was used."
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
(: s1_x1_member (Member sk_show_1__mh_g03_becauseof_cause show) (STV 1.0 0.99))
(: s1_x2_member (Member sk_storm_1__mh_g03_becauseof_cause storm) (STV 1.0 0.99))
(: s1_m1_member (Member sk_move_1__mh_g03_becauseof_cause move) (STV 1.0 0.99))
(: s1_m1_theme (Theme sk_move_1__mh_g03_becauseof_cause sk_show_1__mh_g03_becauseof_cause) (STV 1.0 0.99))
(: s1_m1_past (Past sk_move_1__mh_g03_becauseof_cause) (STV 1.0 0.99))
(: s1_a1_becauseof (BecauseOf sk_move_1__mh_g03_becauseof_cause sk_storm_1__mh_g03_becauseof_cause) (STV 1.0 0.99))
~~~

**r3 summary.** Premise predicate(s): BecauseOf top x1. Rule `becauseof_cause` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

