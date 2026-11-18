# g01_month_class

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `month_class`. Premise predicate(s) looked for: `Month`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "The Calderwick rehearsal is on 14 March."

Raw reply records (all fields, incl. usage and raw_text): g01_month_class.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g01_month_class.s01",
 "instances": [
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Calderwick",
   "span": "Calderwick"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "rehearsal",
   "definite": true,
   "mods": [
    "@n1"
   ],
   "eventive": true,
   "span": "The Calderwick rehearsal"
  },
  {
   "t": "time",
   "id": "t1",
   "event": "@x1",
   "month": "march",
   "day": 14,
   "tense": "present",
   "span": "on 14 March"
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
(: s1_n1_name (Name calderwick "Calderwick") (STV 1.0 0.99))
(: s1_x1_member (Member sk_rehearsal_1__mh_g01_month_class rehearsal) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_rehearsal_1__mh_g01_month_class rehearsal__mod_calderwick) (STV 1.0 0.99))
(: s1_t1_time (Time sk_rehearsal_1__mh_g01_month_class sk_time_1__mh_g01_month_class) (STV 1.0 0.99))
(: s1_t1_month (Month sk_time_1__mh_g01_month_class march) (STV 1.0 0.99))
(: s1_t1_day (Day sk_time_1__mh_g01_month_class 14) (STV 1.0 0.99))
(: s1_t1_member (Member sk_time_1__mh_g01_month_class day) (STV 1.0 0.99))
~~~

**r1 summary.** Premise predicate(s): Month top x1. Rule `month_class` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g01_month_class.s01",
 "instances": [
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Calderwick",
   "span": "Calderwick"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "rehearsal",
   "definite": true,
   "eventive": true,
   "mods": [
    "@n1"
   ],
   "span": "The Calderwick rehearsal"
  },
  {
   "t": "time",
   "id": "t1",
   "event": "@x1",
   "day": 14,
   "month": "march",
   "tense": "present",
   "span": "on 14 March"
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
(: s1_n1_name (Name calderwick "Calderwick") (STV 1.0 0.99))
(: s1_x1_member (Member sk_rehearsal_1__mh_g01_month_class rehearsal) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_rehearsal_1__mh_g01_month_class rehearsal__mod_calderwick) (STV 1.0 0.99))
(: s1_t1_time (Time sk_rehearsal_1__mh_g01_month_class sk_time_1__mh_g01_month_class) (STV 1.0 0.99))
(: s1_t1_month (Month sk_time_1__mh_g01_month_class march) (STV 1.0 0.99))
(: s1_t1_day (Day sk_time_1__mh_g01_month_class 14) (STV 1.0 0.99))
(: s1_t1_member (Member sk_time_1__mh_g01_month_class day) (STV 1.0 0.99))
~~~

**r2 summary.** Premise predicate(s): Month top x1. Rule `month_class` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g01_month_class.s01",
 "instances": [
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Calderwick",
   "span": "Calderwick"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "rehearsal",
   "definite": true,
   "mods": [
    "@n1"
   ],
   "eventive": true,
   "span": "The Calderwick rehearsal"
  },
  {
   "t": "time",
   "id": "t1",
   "event": "@x1",
   "month": "march",
   "day": 14,
   "tense": "present",
   "span": "on 14 March"
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
(: s1_n1_name (Name calderwick "Calderwick") (STV 1.0 0.99))
(: s1_x1_member (Member sk_rehearsal_1__mh_g01_month_class rehearsal) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_rehearsal_1__mh_g01_month_class rehearsal__mod_calderwick) (STV 1.0 0.99))
(: s1_t1_time (Time sk_rehearsal_1__mh_g01_month_class sk_time_1__mh_g01_month_class) (STV 1.0 0.99))
(: s1_t1_month (Month sk_time_1__mh_g01_month_class march) (STV 1.0 0.99))
(: s1_t1_day (Day sk_time_1__mh_g01_month_class 14) (STV 1.0 0.99))
(: s1_t1_member (Member sk_time_1__mh_g01_month_class day) (STV 1.0 0.99))
~~~

**r3 summary.** Premise predicate(s): Month top x1. Rule `month_class` premise matches (1 step, no engine): 1. Labels with more than one statement: 0.

