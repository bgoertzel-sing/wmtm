# Man Hin's parser at sph 24e37182: replies for the invented examples

Task t-2026-11-17-wmtm-manhin-parser-analysis, Do item 1. These are the examples we sent Man Hin in
../FOR_MAN_HIN.md. They are invented and contain nothing from real notes, so the replies are kept here in full.

## How they were made

- Parser: semparse-hitl pin 24e37182 (prompt catalog `templates/generated/PROMPT_CATALOG.txt`, manifest 31571b39fd6b),
  chat-completions, temperature 0.0.
- Sentence mode, as the live feed sends it: each sentence is its own call, and later sentences get the earlier
  sentences and their instances as CONTEXT.
- 13 examples (12 rule examples g01-g12 plus the label-bug reproduction), 17 sentences, 3 runs (r1, r2, r3).
- Calls: 51, all ok, no 429 or limit error, made 2026-11-17 08:41-14:41 PT under the hive tasks' share
  (10 calls/hour for all hive tasks together, enforced by ParseBudget at wmtm 24b0442).
- Each reply was checked with validate.inspect (the sentence alone) and with block_records (sentence mode, earlier
  sentences as context), both at the pin.
- Check before committing: the `text` of all 51 records appears verbatim in FOR_MAN_HIN.md.

## Files

- `<example>.md`: the sentences, each run's raw `response` (instances, unmapped, issues), the unmapped and issues codes,
  the validate results, our master lowering of the reply, and a per-run summary.
- `<example>.jsonl`: the full reply records, one line per run and sentence (incl. usage and raw_text).
- `summary.json`: the per-run counts the table below is made from.

## Results

"Premise" is where the rule's premise predicate appears in our lowering ("top" = top level). "Matches" is the number of
premise matches for the rule in one step without the engine, for r1,r2,r3. "Inspect" is validate.inspect per sentence.

| Example | Rule | Sentences | Premise | Matches | Unmapped | Inspect |
|---|---|---|---|---|---|---|
| g01_month_class | month_class | 1 | Month top x1 | 1,1,1 | - | ok |
| g02_rank_orders | rank_orders | 1 | none | 0,0,0 | G00 x2-3 | ok |
| g03_becauseof_cause | becauseof_cause | 1 | BecauseOf top x1 | 1,1,1 | - | ok |
| g04_measure_same | measure_same | 1 | Measure top x1 | 1,1,1 | - | ok |
| g05_measure_moreby | measure_moreby | 1 | none | 0,0,0 | G00 x2 | ok |
| g06_unit_measure | unit_measure | 1 | Measure top x1 | 1,1,1 | - | ok |
| g07_unit_atmost | unit_atmost | 1 | none | 0,0,0 | G00 x1 | ok |
| g08_subset_is_part | subset_is_part | 1 | none | 0,0,0 | - | ok |
| g09_located_trans | located_trans | 2 | LocatedIn top x2 | 0,0,0 | - | ok, malformed |
| g10_located_in_part | located_in_part | 1 | LocatedIn + PartOf top (r2 also inside an Implication) | 1,1,1 | - | ok |
| g11_days_before_day | days_before_day | 2 | BeforeBy top x1 (r3 also Day) | 0,0,0 | G00 x1 in r1, r2 | r3: ok, malformed |
| g12_coref_theme | coref_theme | 2 | Coref top x2, Theme top x1 | 1,1,1 | - | ok, malformed |
| bug_label_repeat | (label bug) | 2 | Directive top x2 | n/a | G00 x1 | ok, malformed |

Notes:

- The three runs agree on every example except small differences in g02 (2 or 3 G00 items), g10 (r2 adds an
  Implication) and g11 (r3 parses the day instead of sending it to G00).
- g09: both LocatedIn facts are there, but s2's "the booth" is a new symbol joined to s1's booth only by a Coref, so the
  two facts do not chain in one step. This is the same cross-sentence split seen in the real notes.
- Every "malformed" is validate.inspect on the second sentence alone: its coref antecedent (@s1.x...) is in the earlier
  sentence, which inspect does not see. block_records with the context gives ok for every sentence.
- bug_label_repeat: no label carried more than one statement in any run, so the label bug did not reproduce at this
  pin with sentence mode.
- G00 (no catalog instruction) is the only gap code the invented examples produced.

The classification of the 33 real cases (Do item 2) is counts only and stays on pop-os, in
/srv/hive-evidence/t-2026-11-17-wmtm-manhin-parser-analysis/ (RECOMPUTE_OK).
