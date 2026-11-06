# PeTTaChainer upstream repros (track E, 2026-10-15)

Version: upstream master 36b3fe6 (+ our dedup-import patch except where noted). Run each from `pettachainer/metta/`:
`PATH=<swipl-9.3.36>/bin:$PATH <PeTTa>/run.sh <repro>.metta`. All verified on this machine; actual outputs below.

| ID | Repro | Expected | Actual (36b3fe6) |
|---|---|---|---|
| PC1 | `pc1_and_implication.metta` | proof of `(Inheritance pilot animal)` via `r_and` | `()`; Premises-form control derives `(rule-proof r_pc (rule-proof conjunction f1 f2))` |
| PC2 | `pc2_multi_conclusion.metta` | proofs of `(Member grace person)` and `(Member grace flyer)` | `()` `()`; single-conclusion control derives |
| PC3 | `pc3_and_elimination.metta` | `(Member o offer)`, `(Past o)` from asserted `(And …)` | `()` `()`; the conjunction itself is returned |
| PC3 @202b9379 | `pc3_and_elimination_202b9379.metta`, see `PC3_202b9379.md` | conjuncts with c>0 (true ≈0.54) | derived, but c=3.7e-16 (conjuncts) and 0.0 (And): event_node.pl:82 bound > s(1-s) |
| PC4 | `pc4_stv_range.metta` | add rejected | STV (1.0 1.5), (-0.5 0.9), (2.0 0.5) accepted and returned by query |
| PC6 | `pc6_double_import.metta` (run in an UNPATCHED tree) | fast query | unpatched: timeout at 120 s (`pc6_run_unpatched.txt`); patched: 0.95 s, single `compile_` def (`pc6_run_patched.txt`) |

## Diagnoses (pointers into `pettachainer/metta/chainer/`)
- **PC1** – `compile_` (compile.metta:757) only compiles a rule when the type matches `(Implication (cons Premises …) (cons Conclusions …))`. `(Implication (And A B) C)` fails that match, is not bidirectional, and falls through to the *fact* branch: it is stored as an atom of type Implication and no rule is ever compiled. No error is raised. Candidate fix: at `compile_` entry rewrite `(Implication (And p…) c)` → `(Implication (Premises p…) (Conclusions c))` (and `(Implication p c)` → single-premise form), or reject with an error. Not patched: whether And-antecedents should keep conjunction-TV semantics distinct from Premises is a design call for upstream.
- **PC2** – `build-implication-plan` (compile.metta:487, also :792) collapses all conclusions into one goal head with `seq2expr` (compile.metta:41) → `(And c1 c2)`. The compiled rule therefore only proves the conjunction; a query for `c1` does not unify, and because of PC3 nothing projects the conjunct out. Candidate fix: in `compile-ordinary-implication` (compile.metta:744), when `$conclusions` has >1 element, superpose one compiled rule per conclusion (same premises/TV). Not patched: TV/inversion semantics for multi-conclusion rules (the inverse rule uses `$b` as premise) need upstream judgment.
- **PC3** – `And` is a compound connective (`set-compound-connective And All ProjectAll`, logic_config.metta) and the query side builds conjunctions (`compound-query-temp-stmt`, compile.metta:858 – And-*introduction*), but the fact branch of `compile_` stores `(And …)` as a plain fact; there is no And-*elimination* rule from a stored conjunction to its conjuncts. Candidate fix: in the fact branch, when head is a compound connective with projection, also emit projected facts (TV per the connective's projection formula). Not patched (semantics).
- **PC4** – `PeTTaChainer.add_atom` validates with `pln_validator.check_stmt`, which only checks that the TV *matches the pattern* `(STV $s $c)` (pln_validator.py:5,35); values are never range-checked, and the MeTTa `compileadd` path has no check at all. **Candidate patch `pc4_stv_range_check.patch`** (Python-side, 37 lines): numeric STV must have s,c ∈ [0,1]. Verified: the three bad atoms now raise `ValueError` at add_atom; Grace canary, negative control and Premises-form rule unchanged. Limits: does not cover direct `compileadd` from MeTTa (the .metta repro still shows PC4 there); allows c = 1.0 because the chainer itself uses `(STV 1.0 1.0)` internally (our adapter stays stricter, c < 1).
- **PC6** – `petta_chainer.metta:1` imports `chainer/compile`, and `context/context_generation.metta:16` imports it again (reached via `context/context_from_kb`, petta_chainer.metta:18). PeTTa's `import!` is not idempotent, so every `compile` definition exists twice and nondeterministic calls multiply per nesting level. **Patch: `../../../patches/pettachainer-dedup-import.patch`** (one line, drop the second import) – verified above. A longer-term upstream fix is an import-once guard in PeTTa.
- **PC5/PC7** not in scope (PC5 = missing native mem_inh / doc; PC7 fixed in 36b3fe6).

## Track P1 (rT 202b9379, 2026-11-04)
- **PC8** – `pc8_modus_ponens_202b9379.metta`. Modus ponens from a premise with s<1 halves the conclusion confidence.
  Command: `cd <PeTTaChainer@202b9379>/pettachainer/metta && cp <abs>/pc8_modus_ponens_202b9379.metta ./_pc8.metta && PATH=<swipl-9.3.36>/bin:$PATH <PeTTa@3681b9b>/run.sh ./_pc8.metta`
  Expected: (Q x) with s≈0.81 and c≈0.88 (as on rT 38b1473). Actual: `(STV 0.8325 0.4395)`. Control with premise s=1.0: `(STV 0.85 0.92)`.
  Effect: GoalChainer `tests/test_input_sensitivity.py::test_decision_depends_on_the_request` fails (wrong action ranking).
- **PY1** – `py1_nested_annotated_arrow.metta`. pymetta 0.9.4+goalchainer.native.2 refuses a nested annotated arrow
  (`-[semidet]->` inside `-[semidet]->`), the declaration at PeTTaChainer 202b9379 `lib/collections.metta:2`, so petta_chainer cannot load under pymetta.
  Command: `<venv with pymetta==0.9.4+goalchainer.native.2>/bin/python -c "import metta,sys; print(metta.MeTTa().run(open(sys.argv[1]).read()))" py1_nested_annotated_arrow.metta`
  Expected: declaration accepted; `(fold-semidet add2 0 (Cons 1 (Cons 2 Nil)))` → 3. Actual: `EngineError: metta_add_atom/3: cannot honour the annotated arrow for fold-semidet ... (annotated arrows require a named function and a concrete top-level cardinality and effect ...)` from `metta/_runtime/engine/spaces/arrow_products.pl:58`.

### PY1–PY5: pymetta 0.9.4+goalchainer.native.2 cannot load PeTTaChainer rT 202b9379
Command for every row: `<venv with pymetta==0.9.4+goalchainer.native.2>/bin/python -c "import metta,sys; print(metta.MeTTa().run(open(sys.argv[1]).read()))" <repro>` (run in this directory). The shim column is what a scratch copy tried (not shipped; cos ruled out local engine shims).
Option a = pymetta limitation (engine owner could relax it); option b = rT could change to fit pymetta.

| ID | Repro | Refusal (actual) | rT 202b9379 file:line | What pymetta requires | Shim tried | Option |
|---|---|---|---|---|---|---|
| PY1 | `py1_nested_annotated_arrow.metta` | `metta_add_atom/3: cannot honour the annotated arrow for fold-semidet … nested products are not enforced` | `lib/collections.metta:2` (8 such declarations) | annotated arrow with concrete top-level effect, no nested annotated arrow | inner arrow → plain `->` | a (enforce/ignore nested products) or b (flatten) |
| PY2 | `py2_variable_effect_arrow.metta` | `cannot honour the annotated arrow for foreach-flat … product variables … are not enforced` | `lib/collections.metta:14` | concrete effect, not `-[$e]->` | arrow → plain `->` | a (effect polymorphism) or b |
| PY3 | `py3_quoted_import_list.metta` (+`py3_helper.pl`) | ``Type error: `atom' expected, found `['py3-a','py3-b']' (a list)`` | `bootstrap.metta:37` (`(quote (declare-natives! declare-forward!))`) | bare name list, no `quote` | drop the `quote` | b (one-token change) |
| PY4 | `py4_reimport_yall.metta` (+`py4_helper_yall.pl`) | `loading_loudly/1 … No permission to import yall:(/)/3 into user (already imported from metta_engine)` | `prolog/runtime_helpers.pl:6` (`:- use_module(library(yall))`) | helper must not re-import a library the engine already imported into user | comment the directive out | a (tolerate idempotent import) or b (module-qualify) |
| PY5 | `py5_two_sources_one_name.metta` (+`py3_helper.pl`, `py5_helper_second.pl`) | `refuse_other_sources_name/2: py3-a is already registered from …py3_helper.pl … (two Prolog sources claim one name)` | `declare-natives!` defined in `lib/natives.pl:4` and imported again via the runtime helper (`bootstrap.metta:33-37`) | one Prolog source per name | not shimmed (stopped here) | b (single owner) |

Verified 2026-11-04 on this machine: each repro gives exactly the refusal above (PY3–PY5 load `(library lib_import)` first, as rT bootstrap.metta:6 does).

### PC3 and PC8: proposed shared cause (HYPOTHESIS, not verified)
This is a hypothesis for Roman to confirm or reject. Neither repro has been traced inside the engine to prove it.
- Both regressions are new in rT 202b9379. They do not appear on 38b1473, and both reduce **confidence only**: strength is about right in both.
- PC3 is traced: `polynomial_answer` (`prolog/event_node.pl:82`) returns the conservative variance bound
  `Bound = (Q + max(C,1-C)·sqrt(ZVar·Q)) / EZ²`, capped at s(1-s). With uninformed roots this bound is far above the true
  posterior variance, so `node_stv` maps it to c≈0 (see `PC3_202b9379.md`).
- PC8 hypothesis: modus ponens is evaluated through the same event-node path. With premise s=1.0 the premise term is
  deterministic, so Q=0, `Kind=exact`, and c stays at 0.92 (the control row). With s<1 the node becomes `conservative`, and the
  same loose bound inflates V, which roughly halves c (0.44 against about 0.88 on 38b1473).
- Prediction that would confirm it: run `pc8_modus_ponens_202b9379.metta` with the exact posterior variance put in at
  `event_node.pl:82`, or log `Kind`, `Q` and `ZVar` there. Expect `conservative` and Bound ≫ true variance for the s=0.95 case only.
  If PC8 shows `exact`, the hypothesis is wrong and PC8 has a separate cause.
- If it holds, fix (b) in `PC3_202b9379.md` (exact moments for small nodes) would fix both. Fix (a) would fix neither PC8 nor the PC3 conjuncts.

## P4 follow-up (bdae8d7e, 2026-11-06)
- **R9 (candidate, for LIST-roman next to R2)** – `r9_specializes_bdae8d7e.metta`. When `mem_inh`
  (`(Implication (And (Member $x $a) (Inheritance $a $b)) (Member $x $b))`) is loaded, a direct modus-ponens answer
  `(by r1 f1)` at c=0.70 comes back wrapped as `(specializes (by mem_inh (conjunction f1 r1)) (by r1 f1) ...)` at c=0.018:
  the engine uses the Implication r1 as the Inheritance premise of mem_inh, and the `specializes` combination returns a
  lower confidence than the direct proof it contains. Without mem_inh loaded the same KB gives c=0.70.
  Command (LIST-roman repro.py, in a dir with it): `PETTA_PATH=<PeTTa@3681b9b> PYTHONPATH=<PeTTa@3681b9b>/python:<PeTTaChainer@bdae8d7e> python3 repro.py r9_specializes_bdae8d7e.metta`.
  Effect in wmtm: P4 B flag-off (`WMTM_PC_SHADOW_NWDEF=false`) answers `acl_d` at c=0.042 although a c=0.7 direct proof exists.
