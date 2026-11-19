# g02_rank_orders

Invented example from FOR_MAN_HIN.md (nothing from real notes). Rule: `rank_orders`. Premise predicate(s) looked for: `Ordinal`.

Sentences (sentence mode: s2 is sent with s1 and its instances as CONTEXT, as the live feed does):

- s1: "In the setlist, Lantern Song is first and Low Tide is third."

Raw reply records (all fields, incl. usage and raw_text): g02_rank_orders.jsonl, one line per run and sentence.

## r1

### s1

Reply `response` (raw):

~~~json
{
 "id": "g02_rank_orders.s01",
 "instances": [
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Lantern Song",
   "span": "Lantern Song"
  },
  {
   "t": "named-entity",
   "id": "n2",
   "name": "Low Tide",
   "span": "Low Tide"
  }
 ],
 "unmapped": [
  {
   "span": "In the setlist",
   "code": "G00",
   "construction": "A fronted prepositional phrase framing the domain within which the following ranks hold, with no event or class noun for it to attach to."
  },
  {
   "span": "Lantern Song is first",
   "code": "G00",
   "construction": "A bare ordinal predicated by be with no class noun stated, giving a rank within a sequence named only by the fronted frame phrase."
  },
  {
   "span": "Low Tide is third",
   "code": "G00",
   "construction": "A bare ordinal predicated by be with no class noun stated, giving a rank within a sequence named only by the fronted frame phrase."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "superlative",
   "text": "An ordinal predicated with no class noun but with a frame phrase naming the sequence (In the setlist, X is first) is not covered: the template requires a class except for the first to V, and gives no way to use a containing whole such as the setlist as the domain of the rank."
  }
 ]
}
~~~

- unmapped codes: G00, G00, G00
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s1_n1_name (Name lantern_song "Lantern Song") (STV 1.0 0.99))
(: s1_n2_name (Name low_tide "Low Tide") (STV 1.0 0.99))
~~~

**r1 summary.** Premise predicate(s): none. Rule `rank_orders` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r2

### s1

Reply `response` (raw):

~~~json
{
 "id": "g02_rank_orders.s01",
 "instances": [
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Lantern Song",
   "span": "Lantern Song"
  },
  {
   "t": "named-entity",
   "id": "n2",
   "name": "Low Tide",
   "span": "Low Tide"
  }
 ],
 "unmapped": [
  {
   "span": "In the setlist, Lantern Song is first",
   "code": "G00",
   "construction": "A predicative ordinal with no class noun (is first), its domain given only by a fronted place phrase naming a list."
  },
  {
   "span": "Low Tide is third",
   "code": "G00",
   "construction": "A predicative ordinal with no class noun (is third), ranked within the setlist named by the fronted phrase."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "superlative",
   "text": "A bare predicative ordinal (is first, is third) whose ranking domain is a fronted in-phrase naming a list or sequence (In the setlist) has no class noun, and the template says neither whether such a phrase can supply the class or the within restriction nor whether the clause must be reported whole."
  }
 ]
}
~~~

- unmapped codes: G00, G00
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s1_n1_name (Name lantern_song "Lantern Song") (STV 1.0 0.99))
(: s1_n2_name (Name low_tide "Low Tide") (STV 1.0 0.99))
~~~

**r2 summary.** Premise predicate(s): none. Rule `rank_orders` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

## r3

### s1

Reply `response` (raw):

~~~json
{
 "id": "g02_rank_orders.s01",
 "instances": [
  {
   "t": "named-entity",
   "id": "n1",
   "name": "Lantern Song",
   "span": "Lantern Song"
  },
  {
   "t": "named-entity",
   "id": "n2",
   "name": "Low Tide",
   "span": "Low Tide"
  }
 ],
 "unmapped": [
  {
   "span": "In the setlist",
   "code": "G00",
   "construction": "A fronted prepositional phrase naming the sequence within which the ordinal ranks hold; with the ranks unmapped it has nothing to attach to."
  },
  {
   "span": "Lantern Song is first",
   "code": "G00",
   "construction": "A bare ordinal predicated by be with no class noun stated, a rank in a sequence that the superlative template cannot carry without a class."
  },
  {
   "span": "Low Tide is third",
   "code": "G00",
   "construction": "A bare ordinal predicated by be with no class noun stated, a rank in a sequence that the superlative template cannot carry without a class."
  }
 ],
 "issues": [
  {
   "code": "P00",
   "where": "superlative",
   "text": "A bare predicative ordinal ranked within a stated whole ('in the setlist, X is first') has no class noun, and the template allows a missing class only for 'the first to V', so it is unclear whether the whole can serve as the domain or the clause must be left unmapped."
  }
 ]
}
~~~

- unmapped codes: G00, G00, G00
- issues codes: P00
- validate.inspect (pin 24e37182; this sentence alone, text=sentence): status `ok`, findings: none
- block_records (sentence mode, earlier sentences as context): status `ok`, findings: none

Master lowering of this sentence (what our loader loads, before note labels):

~~~
(: s1_n1_name (Name lantern_song "Lantern Song") (STV 1.0 0.99))
(: s1_n2_name (Name low_tide "Low Tide") (STV 1.0 0.99))
~~~

**r3 summary.** Premise predicate(s): none. Rule `rank_orders` premise matches (1 step, no engine): 0. Labels with more than one statement: 0.

