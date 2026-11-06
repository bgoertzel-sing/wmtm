# The deploy flag WMTM_PC_SHADOW_NWDEF, reconsidered against Roman's answer (P4 follow-up, criterion 4)

## What the flag does
`shadow_nwdef` (default `true`, `wmtm/runtime_config.py:134`) decides whether the `nwdef_*` defining rules
`(Implication (Member $x <base>__nw_<hash>) (Member $x <base>))` go into the shadow KB (`wmtm/pc_shadow.py:162,444`).
These rules are the F7 design: they are the only thing that links a narrowed-class symbol to its base class.
False leaves them out. Facts and parser rules stay as they are.

## On these 20 notes (B spec, rev3/spec_B.json: 410 atoms, 74 nwdef rules, 22 parser implications, 13 goals)
- **Conclusions:** at the engine, off removes none here (12 of 13 proved either way). At admission it removes one: see the admission bullet below. All 68 facts typed by a narrowed symbol also have the base-class fact asserted,
  because the parser emits it itself (87 of 98 narrowed Member facts in the parse cache come with it). The 13 goals are
  reached through parser implications whose antecedent is the symbol fact itself (15 of 22), so they need no
  symbol->base step.
- **Proof kind and TV** (rev6/PROOF_KINDS.md, read from the proof terms):
  - On: 12 of 12 proved answers contain antecedent completion. The engine inverts the nwdef rule from a (STV 0.5 0.0)
    prior, revises the asserted premise with it and drops c from 0.7 to about 0.20 (R2, CTV rule form).
  - Off: 12 of 12 proved answers are derivation only. 11 have c=0.7; `acl_d` has c=0.042 through a `specializes` proof
    (R9 candidate, upstream/pettachainer/r9_specializes_bdae8d7e.metta).
  - **Admission (correction, review 2):** wmtm does gate on confidence. `wmtm/pc_admit.py:26` sets `MIN_CONFIDENCE = 0.05`
    and `wmtm/pc_admit.py:157` drops any conclusion below it as `below_threshold`. In the flag-off run this dropped `acl_d`
    (c=0.042): rev5/admit/ADMIT_AB.json, `nonwdef_flag`, `below_threshold: 1`. Strengths stay at 0.90 or above either way,
    so the strength gate (>= 0.5) drops nothing. The admitted list is the same 5 answers either way only because
    `reasoner_max_admit` caps it at 5 (`wmtm/pc_admit.py:183`); without the cap, off would admit one answer fewer than on.
- **Which goal times out at 10 s varies between runs** (on: `185959Z effective`; off: `stdlib_only`). It is the same R4 shape, not a flag effect.

## In general
Off breaks the design link. On these notes the parser asserted the base fact next to every narrowed fact (68 of 68
asserted facts; the other `(Member x (Narrow ...))` occurrences in the parse cache sit inside Implication/Equivalence atoms
and rule bodies, not asserted facts), so nothing is lost here. In general the parser need not do that: wherever it emits a
narrowed fact without the base fact, the entity is no longer a member of the base class, and no rule or goal that uses
the base class can reach it. Facts about
narrowed classes then turn into isolated symbols. On keeps that link, and the price on bdae8d7e is the upstream R2
confidence loss on every answer whose premise is a symbol fact.

## Recommendation: changed
P4 proposed deploying with `false`. I now propose keeping the default `true` (the design).
- Roman: never use a confidence cutoff; read how an answer was obtained from its proof term and use its TV. The
  c=0.20 is an engine artefact (R2), already on Roman's list, and the proof term shows it. wmtm does still gate on c:
  `MIN_CONFIDENCE = 0.05` in `wmtm/pc_admit.py:26,157`. That conflicts with Roman's rule. With `true` no answer here
  is near it (all c≈0.20, 0.10 the lowest); with `false` it drops `acl_d` (c=0.042, the R9 artefact). This task does not
  change code; whether to remove that cutoff is an open decision for the humans (see REPORT.md Result 6).
- Off would buy higher c on these notes by removing the rules Roman called the design, and it adds its own engine
  artefact (R9, c=0.04).
- The shadow path only logs. Keeping `true` changes nothing live.

If the humans prefer `false` until R2 is fixed upstream, the cost on these notes is one answer (`acl_d`) lost at the
MIN_CONFIDENCE=0.05 admission cutoff, hidden here by the cap of 5, and in general it is the lost symbol->base link described above. The humans decide.
