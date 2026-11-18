# g11_days_before_day

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `days_before_day`. Premise predicate(s) looked for: `BeforeBy`, `Day`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "The sound check is two days before the concert."
- s2: "The concert is on day 10."

Raw reply records (all fields, incl. usage and raw_text): g11_days_before_day.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g11_days_before_day.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "check",
   "mods": [
    "sound"
   ],
   "definite": true,
   "eventive": true,
   "span": "The sound check"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "concert",
   "definite": true,
   "eventive": true,
   "span": "the concert"
  },
  {
   "t": "time",
   "id": "t1",
   "event": "@x1",
   "offset": 2,
   "unit": "day",
   "direction": "before",
   "anchor": "@x2",
   "tense": "present",
   "span": "two days before the concert"
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
(: s1_x1_member (Member sk_check_1__mh_g11_days_before_day check) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_check_1__mh_g11_days_before_day check__mod_sound) (STV 1.0 0.99))
(: s1_t1_time (Time sk_check_1__mh_g11_days_before_day sk_time_1__mh_g11_days_before_day) (STV 1.0 0.99))
(: s1_t1_beforeby (BeforeBy sk_time_1__mh_g11_days_before_day sk_concert_1__mh_g11_days_before_day 2 day) (STV 1.0 0.99))
(: s1_t1_member (Member sk_time_1__mh_g11_days_before_day day) (STV 1.0 0.99))
(: s1_x2_member (Member sk_concert_1__mh_g11_days_before_day concert) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "g11_days_before_day.s02",
 "instances": [],
 "unmapped": [
  {
   "span": "The concert is on day 10",
   "code": "G00",
   "construction": "An event noun placed by be at a numbered day of a schedule ('day 10'), which no time field carries; without the time the clause states nothing."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "time",
   "text": "The time template has a `week` field for a numbered week of a season or schedule but no field for a numbered day of a schedule ('on day 10'); `day` is the day of the month, and the named-entity template says dates and numbered weeks are times without covering numbered days, so the clause cannot be carried."
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

**r1 summary.** Premise predicate(s): BeforeBy top x1. Rule `days_before_day` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g11_days_before_day.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "check",
   "mods": [
    "sound"
   ],
   "definite": true,
   "eventive": true,
   "span": "The sound check"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "concert",
   "definite": true,
   "eventive": true,
   "span": "the concert"
  },
  {
   "t": "time",
   "id": "t1",
   "event": "@x1",
   "offset": 2,
   "unit": "day",
   "direction": "before",
   "anchor": "@x2",
   "tense": "present",
   "span": "two days before the concert"
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
(: s1_x1_member (Member sk_check_1__mh_g11_days_before_day check) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_check_1__mh_g11_days_before_day check__mod_sound) (STV 1.0 0.99))
(: s1_t1_time (Time sk_check_1__mh_g11_days_before_day sk_time_1__mh_g11_days_before_day) (STV 1.0 0.99))
(: s1_t1_beforeby (BeforeBy sk_time_1__mh_g11_days_before_day sk_concert_1__mh_g11_days_before_day 2 day) (STV 1.0 0.99))
(: s1_t1_member (Member sk_time_1__mh_g11_days_before_day day) (STV 1.0 0.99))
(: s1_x2_member (Member sk_concert_1__mh_g11_days_before_day concert) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "g11_days_before_day.s02",
 "instances": [],
 "unmapped": [
  {
   "span": "The concert is on day 10",
   "code": "G00",
   "construction": "A time predicated of an event noun by be, where the time is a numbered day of a schedule ('day 10') rather than a calendar date, and the time template has no field for such a day."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "time",
   "text": "The time template has a field for a numbered week of a season or schedule ('in week 5' → week) but none for a numbered day ('on day 10'), and its `day` field means the day of the month, so a schedule day cannot be recorded and the clause that places the concert on it cannot be kept."
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

**r2 summary.** Premise predicate(s): BeforeBy top x1. Rule `days_before_day` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g11_days_before_day.s01",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "check",
   "mods": [
    "sound"
   ],
   "definite": true,
   "eventive": true,
   "span": "The sound check"
  },
  {
   "t": "witness",
   "id": "x2",
   "class": "concert",
   "definite": true,
   "eventive": true,
   "span": "the concert"
  },
  {
   "t": "time",
   "id": "t1",
   "event": "@x1",
   "offset": 2,
   "unit": "day",
   "direction": "before",
   "anchor": "@x2",
   "tense": "present",
   "span": "two days before the concert"
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
(: s1_x1_member (Member sk_check_1__mh_g11_days_before_day check) (STV 1.0 0.99))
(: s1_x1_member_2 (Member sk_check_1__mh_g11_days_before_day check__mod_sound) (STV 1.0 0.99))
(: s1_t1_time (Time sk_check_1__mh_g11_days_before_day sk_time_1__mh_g11_days_before_day) (STV 1.0 0.99))
(: s1_t1_beforeby (BeforeBy sk_time_1__mh_g11_days_before_day sk_concert_1__mh_g11_days_before_day 2 day) (STV 1.0 0.99))
(: s1_t1_member (Member sk_time_1__mh_g11_days_before_day day) (STV 1.0 0.99))
(: s1_x2_member (Member sk_concert_1__mh_g11_days_before_day concert) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "g11_days_before_day.s02",
 "instances": [
  {
   "t": "witness",
   "id": "x1",
   "class": "concert",
   "definite": true,
   "eventive": true,
   "span": "The concert"
  },
  {
   "t": "coref",
   "id": "c1",
   "mention": "@x1",
   "antecedent": "@s1.x2",
   "certainty": "certain",
   "span": [
    "the concert",
    "The concert"
   ]
  },
  {
   "t": "time",
   "id": "t1",
   "event": "@x1",
   "day": 10,
   "tense": "present",
   "span": "on day 10"
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "time",
   "text": "A numbered day of a schedule (on day 10) has no slot of its own: the time template covers a numbered week (week) but its day field is the day of the month, so 'day 10' was written as day 10 though no month is meant."
  }
 ]
}
~~~

- unmapped codes: none
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `malformed`, findings: instance x1
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

  - inspect instance: instance 1 (coref): antecedent references unknown instance @s1.x2

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s2_x1_member (Member sk_concert_2__mh_g11_days_before_day concert) (STV 1.0 0.99))
(: s2_t1_time (Time sk_concert_2__mh_g11_days_before_day sk_time_2__mh_g11_days_before_day) (STV 1.0 0.99))
(: s2_t1_day (Day sk_time_2__mh_g11_days_before_day 10) (STV 1.0 0.99))
(: s2_t1_member (Member sk_time_2__mh_g11_days_before_day day) (STV 1.0 0.99))
(: s2_c1_coref (Coref sk_concert_2__mh_g11_days_before_day sk_concert_1__mh_g11_days_before_day) (STV 0.99 0.9))
~~~

**r3 summary.** Premise predicate(s): BeforeBy top x1, Day top x1. Rule `days_before_day` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

