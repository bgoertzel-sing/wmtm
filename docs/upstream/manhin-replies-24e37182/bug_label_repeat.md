# bug_label_repeat

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `none: label bug reproduction`. Premise predicate(s) looked for: `Directive`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "Please set up the speakers in the hall for Mira."
- s2: "Please set up the speakers in the hall for Mira, the big ones and the black ones."

Raw reply records (all fields, incl. usage and raw_text): bug_label_repeat.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "bug_label_repeat.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "speaker",
   "definite": true,
   "span": "the speakers"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "hall",
   "definite": true,
   "span": "the hall"
  },
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Mira",
   "span": "Mira"
  },
  {
   "t": "activity",
   "id": "v1",
   "verb": "set_up",
   "patient": "@g1",
   "tense": "present",
   "span": "set up the speakers"
  },
  {
   "t": "location",
   "id": "l1",
   "event": "@v1",
   "place": "@x1",
   "head": "Location",
   "preposition": "in",
   "span": "in the hall"
  },
  {
   "t": "adjunct",
   "id": "a1",
   "event": "@v1",
   "participant": "@n1",
   "head": "Beneficiary",
   "preposition": "for",
   "span": "for Mira"
  },
  {
   "t": "imperative",
   "id": "s1",
   "over": [
    "@v1"
   ],
   "span": "Please set up the speakers in the hall for Mira"
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
(: s1_g1_groupof (GroupOf sk_group_1__mh_bug_label_repeat speaker) (STV 1.0 0.99))
(: s1_x1_member (Member sk_hall_1__mh_bug_label_repeat hall) (STV 1.0 0.99))
(: s1_n1_name (Name sk_mira_1__mh_bug_label_repeat "Mira") (STV 1.0 0.99))
(: s1_s1_directive (Directive (And (Member sk_set_up_1__mh_bug_label_repeat set_up) (Patient sk_set_up_1__mh_bug_label_repeat sk_group_1__mh_bug_label_repeat) (Location sk_set_up_1__mh_bug_label_repeat sk_hall_1__mh_bug_label_repeat) (Beneficiary sk_set_up_1__mh_bug_label_repeat sk_mira_1__mh_bug_label_repeat))) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "bug_label_repeat.s02",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "speaker",
   "definite": true,
   "span": "the speakers"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "hall",
   "definite": true,
   "span": "the hall"
  },
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Mira",
   "span": "Mira"
  },
  {
   "t": "activity",
   "id": "v1",
   "verb": "set_up",
   "patient": "@g1",
   "tense": "present",
   "span": "set up the speakers"
  },
  {
   "t": "location",
   "id": "l1",
   "event": "@v1",
   "place": "@x1",
   "head": "Location",
   "preposition": "in",
   "span": "in the hall"
  },
  {
   "t": "adjunct",
   "id": "a1",
   "event": "@v1",
   "participant": "@n1",
   "head": "Beneficiary",
   "preposition": "for",
   "span": "for Mira"
  },
  {
   "t": "imperative",
   "id": "s1",
   "over": [
    "@v1"
   ],
   "span": "Please set up the speakers in the hall for Mira"
  },
  {
   "t": "coref",
   "id": "c1",
   "mention": "@g1",
   "antecedent": "@s1.g1",
   "certainty": "certain",
   "span": [
    "the speakers",
    "the speakers"
   ]
  },
  {
   "t": "coref",
   "id": "c2",
   "mention": "@x1",
   "antecedent": "@s1.x1",
   "certainty": "certain",
   "span": [
    "the hall",
    "the hall"
   ]
  },
  {
   "t": "coref",
   "id": "c3",
   "mention": "@n1",
   "antecedent": "@s1.n1",
   "certainty": "certain",
   "span": [
    "Mira",
    "Mira"
   ]
  }
 ],
 "unmapped": [
  {
   "span": "the big ones and the black ones",
   "code": "G00",
   "construction": "A detached appositive of coordinated noun phrases headed by the pro-form 'ones', specifying which speakers are meant."
  }
 ],
 "issues": []
}
~~~

- unmapped codes: G00
- issues codes: none
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `malformed`, findings: instance x3
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

  - inspect instance: instance 7 (coref): antecedent references unknown instance @s1.g1
  - inspect instance: instance 8 (coref): antecedent references unknown instance @s1.x1
  - inspect instance: instance 9 (coref): antecedent references unknown instance @s1.n1

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s2_g1_groupof (GroupOf sk_group_2__mh_bug_label_repeat speaker) (STV 1.0 0.99))
(: s2_x1_member (Member sk_hall_2__mh_bug_label_repeat hall) (STV 1.0 0.99))
(: s2_n1_name (Name sk_mira_2__mh_bug_label_repeat "Mira") (STV 1.0 0.99))
(: s2_s1_directive (Directive (And (Member sk_set_up_2__mh_bug_label_repeat set_up) (Patient sk_set_up_2__mh_bug_label_repeat sk_group_2__mh_bug_label_repeat) (Location sk_set_up_2__mh_bug_label_repeat sk_hall_2__mh_bug_label_repeat) (Beneficiary sk_set_up_2__mh_bug_label_repeat sk_mira_2__mh_bug_label_repeat))) (STV 1.0 0.99))
(: s2_c1_coref (Coref sk_group_2__mh_bug_label_repeat sk_group_1__mh_bug_label_repeat) (STV 0.99 0.9))
(: s2_c2_coref (Coref sk_hall_2__mh_bug_label_repeat sk_hall_1__mh_bug_label_repeat) (STV 0.99 0.9))
(: s2_c3_coref (Coref sk_mira_2__mh_bug_label_repeat sk_mira_1__mh_bug_label_repeat) (STV 0.99 0.9))
~~~

**r1 summary.** Premise predicate(s): Directive top x2. Rule `None` premise matches (1 step, no engine): None. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "bug_label_repeat.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "speaker",
   "definite": true,
   "span": "the speakers"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "hall",
   "definite": true,
   "span": "the hall"
  },
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Mira",
   "span": "Mira"
  },
  {
   "t": "activity",
   "id": "v1",
   "verb": "set_up",
   "patient": "@g1",
   "tense": "present",
   "span": "set up the speakers"
  },
  {
   "t": "location",
   "id": "l1",
   "event": "@v1",
   "place": "@x1",
   "head": "Location",
   "preposition": "in",
   "span": "in the hall"
  },
  {
   "t": "adjunct",
   "id": "a1",
   "event": "@v1",
   "participant": "@n1",
   "head": "Beneficiary",
   "preposition": "for",
   "span": "for Mira"
  },
  {
   "t": "imperative",
   "id": "s1",
   "over": [
    "@v1"
   ],
   "span": "Please set up the speakers in the hall for Mira"
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
(: s1_g1_groupof (GroupOf sk_group_1__mh_bug_label_repeat speaker) (STV 1.0 0.99))
(: s1_x1_member (Member sk_hall_1__mh_bug_label_repeat hall) (STV 1.0 0.99))
(: s1_n1_name (Name sk_mira_1__mh_bug_label_repeat "Mira") (STV 1.0 0.99))
(: s1_s1_directive (Directive (And (Member sk_set_up_1__mh_bug_label_repeat set_up) (Patient sk_set_up_1__mh_bug_label_repeat sk_group_1__mh_bug_label_repeat) (Location sk_set_up_1__mh_bug_label_repeat sk_hall_1__mh_bug_label_repeat) (Beneficiary sk_set_up_1__mh_bug_label_repeat sk_mira_1__mh_bug_label_repeat))) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "bug_label_repeat.s02",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "speaker",
   "definite": true,
   "span": "the speakers"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "hall",
   "definite": true,
   "span": "the hall"
  },
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Mira",
   "span": "Mira"
  },
  {
   "t": "activity",
   "id": "v1",
   "verb": "set_up",
   "patient": "@g1",
   "tense": "present",
   "span": "set up the speakers"
  },
  {
   "t": "location",
   "id": "l1",
   "event": "@v1",
   "place": "@x1",
   "head": "Location",
   "preposition": "in",
   "span": "in the hall"
  },
  {
   "t": "adjunct",
   "id": "a1",
   "event": "@v1",
   "participant": "@n1",
   "head": "Beneficiary",
   "preposition": "for",
   "span": "for Mira"
  },
  {
   "t": "imperative",
   "id": "s1",
   "over": [
    "@v1"
   ],
   "span": "Please set up the speakers in the hall for Mira"
  },
  {
   "t": "coref",
   "id": "c1",
   "mention": "@g1",
   "antecedent": "@s1.g1",
   "certainty": "certain",
   "span": [
    "the speakers",
    "the speakers"
   ]
  },
  {
   "t": "coref",
   "id": "c2",
   "mention": "@x1",
   "antecedent": "@s1.x1",
   "certainty": "certain",
   "span": [
    "the hall",
    "the hall"
   ]
  },
  {
   "t": "coref",
   "id": "c3",
   "mention": "@n1",
   "antecedent": "@s1.n1",
   "certainty": "certain",
   "span": [
    "Mira",
    "Mira"
   ]
  }
 ],
 "unmapped": [
  {
   "span": "the big ones and the black ones",
   "code": "G00",
   "construction": "An appositive of coordinated noun phrases headed by the pro-form ones, specifying which of the definite speakers are meant."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "Unmapped spans",
   "text": "It is unclear whether an appositive that specifies subsets of a definite group (the speakers, the big ones and the black ones) is a restriction whose loss widens the claim, requiring the whole command to be left out, or an elaboration of the referent that may be reported alone; no template covers one-anaphora appositives."
  }
 ]
}
~~~

- unmapped codes: G00
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `malformed`, findings: instance x3
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

  - inspect instance: instance 7 (coref): antecedent references unknown instance @s1.g1
  - inspect instance: instance 8 (coref): antecedent references unknown instance @s1.x1
  - inspect instance: instance 9 (coref): antecedent references unknown instance @s1.n1

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s2_g1_groupof (GroupOf sk_group_2__mh_bug_label_repeat speaker) (STV 1.0 0.99))
(: s2_x1_member (Member sk_hall_2__mh_bug_label_repeat hall) (STV 1.0 0.99))
(: s2_n1_name (Name sk_mira_2__mh_bug_label_repeat "Mira") (STV 1.0 0.99))
(: s2_s1_directive (Directive (And (Member sk_set_up_2__mh_bug_label_repeat set_up) (Patient sk_set_up_2__mh_bug_label_repeat sk_group_2__mh_bug_label_repeat) (Location sk_set_up_2__mh_bug_label_repeat sk_hall_2__mh_bug_label_repeat) (Beneficiary sk_set_up_2__mh_bug_label_repeat sk_mira_2__mh_bug_label_repeat))) (STV 1.0 0.99))
(: s2_c1_coref (Coref sk_group_2__mh_bug_label_repeat sk_group_1__mh_bug_label_repeat) (STV 0.99 0.9))
(: s2_c2_coref (Coref sk_hall_2__mh_bug_label_repeat sk_hall_1__mh_bug_label_repeat) (STV 0.99 0.9))
(: s2_c3_coref (Coref sk_mira_2__mh_bug_label_repeat sk_mira_1__mh_bug_label_repeat) (STV 0.99 0.9))
~~~

**r2 summary.** Premise predicate(s): Directive top x2. Rule `None` premise matches (1 step, no engine): None. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "bug_label_repeat.s01",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "speaker",
   "definite": true,
   "span": "the speakers"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "hall",
   "definite": true,
   "span": "the hall"
  },
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Mira",
   "span": "Mira"
  },
  {
   "t": "activity",
   "id": "v1",
   "verb": "set_up",
   "patient": "@g1",
   "tense": "present",
   "span": "set up the speakers"
  },
  {
   "t": "imperative",
   "id": "s1",
   "over": [
    "@v1"
   ],
   "span": "Please set up the speakers in the hall for Mira"
  },
  {
   "t": "location",
   "id": "l1",
   "event": "@v1",
   "place": "@x1",
   "head": "Location",
   "preposition": "in",
   "span": "in the hall"
  },
  {
   "t": "adjunct",
   "id": "a1",
   "event": "@v1",
   "participant": "@n1",
   "head": "Beneficiary",
   "preposition": "for",
   "span": "for Mira"
  }
 ],
 "unmapped": [],
 "issues": [
  {
   "code": "P00",
   "where": "location",
   "text": "A place phrase after a definite object ('set up the speakers in the hall') can be read either as where the event happens (location) or as where the speakers are (a locative inside the noun phrase); the instructions give the test 'decide by what the phrase modifies' but no guidance when both readings are available."
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
(: s1_g1_groupof (GroupOf sk_group_1__mh_bug_label_repeat speaker) (STV 1.0 0.99))
(: s1_x1_member (Member sk_hall_1__mh_bug_label_repeat hall) (STV 1.0 0.99))
(: s1_n1_name (Name sk_mira_1__mh_bug_label_repeat "Mira") (STV 1.0 0.99))
(: s1_s1_directive (Directive (And (Member sk_set_up_1__mh_bug_label_repeat set_up) (Patient sk_set_up_1__mh_bug_label_repeat sk_group_1__mh_bug_label_repeat) (Location sk_set_up_1__mh_bug_label_repeat sk_hall_1__mh_bug_label_repeat) (Beneficiary sk_set_up_1__mh_bug_label_repeat sk_mira_1__mh_bug_label_repeat))) (STV 1.0 0.99))
~~~

### s2

Reply `response` (raw):

~~~json
{
 "id": "bug_label_repeat.s02",
 "instances": [
  {
   "t": "group",
   "id": "g1",
   "class": "speaker",
   "definite": true,
   "span": "the speakers"
  },
  {
   "t": "witness",
   "id": "x1",
   "class": "hall",
   "definite": true,
   "span": "the hall"
  },
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Mira",
   "span": "Mira"
  },
  {
   "t": "activity",
   "id": "v1",
   "verb": "set_up",
   "patient": "@g1",
   "tense": "present",
   "span": "set up the speakers"
  },
  {
   "t": "imperative",
   "id": "s1",
   "over": [
    "@v1"
   ],
   "span": "Please set up the speakers in the hall for Mira"
  },
  {
   "t": "location",
   "id": "l1",
   "event": "@v1",
   "place": "@x1",
   "head": "Location",
   "preposition": "in",
   "span": "in the hall"
  },
  {
   "t": "adjunct",
   "id": "a1",
   "event": "@v1",
   "participant": "@n1",
   "head": "Beneficiary",
   "preposition": "for",
   "span": "for Mira"
  },
  {
   "t": "coref",
   "id": "c1",
   "mention": "@g1",
   "antecedent": "@s1.g1",
   "certainty": "certain",
   "span": [
    "the speakers"
   ]
  },
  {
   "t": "coref",
   "id": "c2",
   "mention": "@x1",
   "antecedent": "@s1.x1",
   "certainty": "certain",
   "span": [
    "the hall"
   ]
  },
  {
   "t": "coref",
   "id": "c3",
   "mention": "@n1",
   "antecedent": "@s1.n1",
   "certainty": "certain",
   "span": [
    "Mira"
   ]
  }
 ],
 "unmapped": [
  {
   "span": "the big ones and the black ones",
   "code": "G00",
   "construction": "An appositive list of definite sub-descriptions (one-anaphora with adjectives) specifying which members of the group are meant."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "part-whole",
   "text": "The list-of-members rule covers named members and rejects lists of kinds, but says nothing of an appositive list of definite one-anaphoric descriptions (the big ones and the black ones) that may identify or restrict a definite group."
  }
 ]
}
~~~

- unmapped codes: G00
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `malformed`, findings: instance x3
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

  - inspect instance: instance 7 (coref): antecedent references unknown instance @s1.g1
  - inspect instance: instance 8 (coref): antecedent references unknown instance @s1.x1
  - inspect instance: instance 9 (coref): antecedent references unknown instance @s1.n1

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s2_g1_groupof (GroupOf sk_group_2__mh_bug_label_repeat speaker) (STV 1.0 0.99))
(: s2_x1_member (Member sk_hall_2__mh_bug_label_repeat hall) (STV 1.0 0.99))
(: s2_n1_name (Name sk_mira_2__mh_bug_label_repeat "Mira") (STV 1.0 0.99))
(: s2_s1_directive (Directive (And (Member sk_set_up_2__mh_bug_label_repeat set_up) (Patient sk_set_up_2__mh_bug_label_repeat sk_group_2__mh_bug_label_repeat) (Location sk_set_up_2__mh_bug_label_repeat sk_hall_2__mh_bug_label_repeat) (Beneficiary sk_set_up_2__mh_bug_label_repeat sk_mira_2__mh_bug_label_repeat))) (STV 1.0 0.99))
(: s2_c1_coref (Coref sk_group_2__mh_bug_label_repeat sk_group_1__mh_bug_label_repeat) (STV 0.99 0.9))
(: s2_c2_coref (Coref sk_hall_2__mh_bug_label_repeat sk_hall_1__mh_bug_label_repeat) (STV 0.99 0.9))
(: s2_c3_coref (Coref sk_mira_2__mh_bug_label_repeat sk_mira_1__mh_bug_label_repeat) (STV 0.99 0.9))
~~~

**r3 summary.** Premise predicate(s): Directive top x2. Rule `None` premise matches (1 step, no engine): None. Labels with more than one statement: 0.

