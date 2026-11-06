# t-2026-11-06-p4-proof-makeup

## Summary
You asked for the makeup of each P4 answer's proof. The question was whether each answer rests wholly, partly or not at all on antecedent completion or a population prior, counted over every step of the proof term rather than only the top-level step. I used the saved A and B runs, so nothing was rerun. All 4 A answers (rev6) and all 12 flag-off answers (rev5) come from derivation alone. All 12 B answers (PeTTaChainer bdae8d7e) are **partly** derivation and partly antecedent completion. None is wholly completion, and none uses a population prior. A top-level-only reading labels 11 of the B answers as plain derivation and 1 as `conditioned`, so it hides the completion step in every B answer. A population prior appears only in the canary's negative check `(Member grace robot)`.

Admission (pc_admit.load_candidates replayed on the B admit.json): all 12 pass every gate. The default cap (`reasoner_max_admit` 5) admits the first 5. With no cap, all 12 are admitted, so wmtm today would admit answers that rest partly on completion. Open for the humans: should admission tag or discount answers that rest partly on completion? This report changes no code. I could not find the Track P README text with Roman's correction, so I worked from the order's restatement.

## Constructors (PeTTaChainer bdae8d7e)
- Derivation: `by` (metta/runtime/application_discovery/plans.metta:19, metta/compiler/rules.metta:265)
- Antecedent completion: `antecedent-completion` (compiler/rules.metta:572, LANGUAGE_SPEC.md:913) and `inverted` (rules.metta:418, LANGUAGE_SPEC.md:624)
- Population prior: `population-prior` (runtime/backward/skeleton.metta:1155, evaluator/evaluation.metta:222, evaluator/folds.metta:330)
- A `(prior ...)` under `inverted`/`factored-revision` is that step's own cpu/revision prior. It is not a population-prior proof and is not counted.

## Method
`proof_makeup.py` parses each proof term and visits every node. Makeup: derivation only / partly (derivation plus completion or prior) / wholly (completion or prior with no derivation step). `top` gives the kind of the outermost step only, which is the old rule. Known-answer canaries pass: a bare population-prior gives wholly, `by` over facts gives derivation only, `by` over an inverted premise gives partly, and a bare inverted step gives wholly. Output: makeup.jsonl (30 rows); table: TABLE.md.

## Results
See TABLE.md. One B goal, `(Member sk_config_1__i_ep_note_20261028T185959Z effective)`, timed out and has no proof. `sk_config_1__..185132Z effective` has 4 completion nodes (s=0.91, c=0.10). Every other B answer has 1 completion node: an inverted `nwdef_*` rule with cpu prior (STV 0.5 0.0).

## Reproduce
    R=reports/t-2026-11-05-p4-latest
    python3 reports/t-2026-11-06-p4-proof-makeup/proof_makeup.py $R/rev6/A_shadow.jsonl $R/rev3/bdae8d7e/shadow_B.jsonl $R/rev5/nonwdef_flag/shadow.jsonl
