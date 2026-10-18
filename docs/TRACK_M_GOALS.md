# Track M: steering goal generation toward non-trivial conclusions (design only)

Problem (Track K/M replays): every admitted conclusion is a 1-step Member x Inheritance join, and 8 of 12 restate
a bookkeeping label ("core_entry is a entry", "path_x is a path"). `pc_shadow.build_goals` lists all 2-step
joins in sorted order and keeps the first `shadow_max_goals`, so it has no notion of relevance or informativeness.

## Design A: score and rank goals (request anchor + depth + informativeness)
Generate a larger candidate pool (chains up to depth 3: a->b->c->d over Inheritance/Implies, Member + 1-2
Inheritance hops), then keep the top `shadow_max_goals` by
  score = w_req * overlap(goal terms, request terms) + w_depth * (hops - 1) + w_info * info(category) + w_sti * STI(source items)
- request terms: entities from the parse of the current user request item (it is already in the top-K;
  mark it `source_type=user` and take its semparse atoms), plus 1-hop neighbours in the KB.
- info(category) = -log(n_subjects(category) / n_subjects): a category that half the KB belongs to ("entry",
  "path", "flag") scores near 0; a goal whose category merely echoes the subject name (path_x -> path) gets 0.
- Admission keeps the existing per-fact cap; add `min_hops` (default 1) so a flag can require real chains.
Cost: pure Python in the worker, no extra LLM calls; query budget unchanged (same number of goals, better chosen).

## Design B: goals from open questions
The parser already separates queries (`ParseResult.queries`), but they are dropped. Keep them in the cache and turn
them, plus items tagged as open ("ASK", "open item", "?", "TODO"), into variable goals for PeTTaChainer, e.g.
`(: $prf (Member option_choice $c) $tv)` or `(: $prf (Implies patch_fix $x) $tv)`. Answers with a proof go to
admission labelled `answers=<item id>`, so the conclusion is about something the agent was actually asking.
Unanswered ones are logged as "open, no proof" (useful in itself for consolidation). Bound: <= N open-question goals
per cycle, shared with the regular budget.

## Contradiction detection with PeTTaChainer (one line)
For each admitted (Member a b) / (Inheritance a b), also query its negation or (Member a c) for every c with
(Disjoint b c) in the KB; if both sides prove with conf > theta, admit neither and log the pair with both proof
terms to parse_review.jsonl as a contradiction (needs Not/Disjoint atoms from the parser).
