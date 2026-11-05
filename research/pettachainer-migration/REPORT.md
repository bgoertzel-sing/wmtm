# What wmtm would need to change to run on rTreutlein/PeTTaChainer 49ca6f3

## Summary
andy asked what wmtm would need to change to run on rT PeTTaChainer 49ca6f3. Short answer: on the wmtm side, a small to
medium change: rewrite the rule form, give rules CTV instead of STV truth values (W2b), upgrade the PeTTa engine to rT's `pr/compact-datatypes` 3681b9b and repoint the chainer vendor dir (W1), fix pc_shadow's proof-acceptance check so population-prior answers do not count as proofs (W8), and add an evidence-grading canary (W7). The real blocker
is that rT 49ca6f3 does not run on GoalChainer v2's pymetta engine. I needed 22+ shims across 66 upstream files just to
get it to load. After all of them, the GoalChainer suite still has the same 117 failures (69 pass with no shims, 31
pass with the last shim set). Basic fact reads still return nothing (open item 1). The same 117 test IDs fail before and after the shims
(logs/failed_ids), so the shims cleared **none** of them. Each one only moved the first error further along the load path.

**Recommendation: stay** on the current pins (wmtm vendor pettachainer-36b3fe6-dedup, GoalChainer runtime 38b1473),
and **wait for named upstream changes** (section 5). Adopting now would be a large (L+) job: in effect, we would be
porting PeTTaChainer to pymetta in a fork, with a high risk of silent wrong answers. If andy wants one more data point,
I propose one bounded follow-up (at most 2 h): settle open item 1 and nothing else. Still open: andy's choice between
stay and the bounded follow-up.

## 1. Change list
"wmtm-side" = we can change it in this repo. "upstream" = it needs rT PeTTaChainer, pymetta or GoalChainer.
Effort: S < 1 h, M = half a day to 2 days, L = more than a week or unknown.

### 1a. wmtm's own code (runs under PeTTa petta-v1.0.6, not pymetta)
| # | where (f75da21) | change | side | effort |
|---|---|---|---|---|
| W1 | wmtm/runtime_config.py:155 (`petta_dir` = petta-v1.0.6, env WMTM_PC_PETTA; exported as PETTA_PATH at :458-459, read by wmtm/workers/pc_shadow.py:31 and semparse_feed.py:30) and :156 (`pettachainer_dir` = pettachainer-36b3fe6-dedup, env WMTM_PC_VENDOR) | **two vendor changes, not one.** (a) **PeTTa engine upgrade:** rT 49ca6f3 requires rT PeTTa `pr/compact-datatypes` @ 3681b9b (`evidence/fitness/REPORT.md:7`, `evidence/fitness/lineage.txt`); it was only ever tested on that engine, never on petta-v1.0.6. So `petta_dir` must point at a new vendored build of 3681b9b. This swaps the engine under every wmtm PeTTa worker (pc_shadow and semparse_feed), not just the chainer. Risks: startup/memory about 4-5x higher (first run 18.6 s / 595 MB, later ~1.8 s / 120 MB vs 0.35 s / 33 MB, fitness F9) must fit `worker_mem_mb`; the branch is an unmerged PR, not a release; any other wmtm MeTTa code run through PETTA_PATH must be re-tested on it. (b) **Chainer:** `pettachainer_dir` -> new vendor dir for rT 49ca6f3; the dedup-import patch is no longer needed, since the rT engine has no duplicate import (fitness F8/F11) | wmtm | (a) M: vendor build + MANIFEST, re-run all wmtm PeTTa suites, mem-cap check; (b) S |
| W2 | wmtm/workers/pc_shadow.py:39-42 (RULES), :44 CANARY | rT dropped `(Implication (Premises ..) (Conclusions ..))`. Rewrite the rules to bare `(Implication p c)` / `And` premises (fitness F2, F18) | wmtm | S |
| W3 | wmtm/semparse_adapter.py:184-207 `normalise()` | it currently converts And -> Premises (Oct 15 canary). It would need to invert that for rT, then re-run the semparse canary | wmtm | M |
| W4 | wmtm/workers/semparse_feed.py:71 (load canary rule), :74-75, :91 | same rule-form rewrite. The canary criterion must allow for rT's population prior (unproved goals get a prior TV, fitness F3) | wmtm | S-M |
| W2b | truth values: wmtm/workers/pc_shadow.py:40-42 (RULES `(STV 1.0 0.99)`), wmtm/workers/semparse_feed.py:71 (canary rule), wmtm/semparse_adapter.py:146-156 `check_statement()` (accepts only `(STV s c)` for every statement, so rules cannot carry CTV) | **STV -> CTV for rules.** On rT a rule with a plain STV still fires but with very low confidence (0.0135 for imp_trans, 0.065 for a one-premise rule); with a CTV, confidence is normal (0.90) (`evidence/fitness/REPORT.md:18-19`, findings 3-4; the And+CTV rules plus a prior filter pass 62/62 PC tests, :21). Facts (pc_shadow.py:34, :277, CANARY :44) can stay STV. `check_statement()` must allow CTV on Implication statements, and the confidence readers (pc_shadow.py:102 regex `STV\s+...`) must accept the result TV form | wmtm | S-M (rules S; adapter + readers + canary re-run M) |
| W5 | wmtm/pc_shadow.py:19-22 (`Implication` -> `Implies` head) | recheck: under rT, `Implies rain slippery` failed 2 tests (fitness F10) | wmtm | S-M |
| W6 | wmtm/workers/pc_shadow.py:50-61, semparse_feed.py:67-69 (`PeTTaChainer()`, `add_atom`, `query(steps, timeout_sec)`) | the Python API is unchanged in 49ca6f3. No change expected; re-verify | wmtm | S |
| W7 | wmtm/goals/v2.py:234 (`client()` env) | drops GOALCHAINER_PETTACHAINER_DIR. Passing it through is needed for a non-default PeTTaChainer to reach GoalChainer's evidence grading, but it is **not sufficient to test rT**: the v2 goal canary does not use PeTTaChainer at all (the goal/deontic path loads only GoalChainer's own MeTTa policy; strace shows 0 PeTTaChainer files opened, `evidence/fitness/REPORT.md:97`). Evidence grading (`evidence_chainer.py`) is the only GoalChainer code that loads it. So W7 = pass the variable through **and** add a canary that runs evidence grading (e.g. tests/test_evidence_chainer.py), which is where rT fails 117/186 (section 3) | wmtm | S (passthrough) + S-M (new canary) |
| W8 | wmtm/workers/pc_shadow.py:116-117 `ask()` (`ok = any(head in x for x in r)`) and :121 (proof = first answer containing head) | **proof-acceptance check.** On rT an unprovable goal is answered with `(population-prior ...)` at e.g. STV 0.916 / 0.0012 for `(Member grace robot)`; the current check accepts any answer containing the goal head, so this counts as proved and the negative canary falsely passes as a proof (fitness finding 5, `evidence/fitness/REPORT.md:20`). Fix: accept only answers that contain the head, do not contain `population-prior`, and have confidence >= 0.05; apply the same filter when picking the proof at :121. Tested diff: `evidence/fitness/pc_shadow_andform_conffloor.diff` (with W2/W2b rules: 62 passed on rT, `evidence/fitness/pytest_pc_rt_andform_floor.txt`). Distinct from W4 (semparse canary) and W2b (TV form/reader) | wmtm | S |

### 1b. GoalChainer v2 adapter (GoalChainer repo, runs under pymetta-native.2)
| # | where | change | side | effort |
|---|---|---|---|---|
| G1 | src/goal_chainer/evidence_chainer.py:85 | `logic_configs/pln` -> `core/logic_configs/pln` (shim8) | upstream (GC) | S |
| G2 | src/goal_chainer/policy/goalchainer_pettachainer.metta:44-45 | warm-up rules Premises -> bare Implication | upstream (GC) | S |
| G3 | goalchainer_pettachainer.metta:19 `set-backward-premise-prefilter`, :41/:52 `chainer-reset!` | not defined in rT 49ca6f3. `!(chainer-reset!)` returns itself unevaluated (probes/qprobe11.out.txt). Needs an rT equivalent, or GC drops them | upstream (rT or GC) | M |
| G4 | tests/record_pettachainer_petta_beliefs.py:48-49 | same import path and prefilter call | upstream (GC) | S |

### 1c. rT PeTTaChainer under pymetta (the shims)
All of these are **upstream** (rT PeTTaChainer and/or the pymetta engine). None of them is wmtm-side.
Effort to fix properly: arrows M (pymetta)/L (rT); type relaxations (shim15/18/19/23, about 260 declaration sites) L; load order (shim2-6) M; apply_fn1 S-M; Prolog->MeTTa calls (shim9-13/20/21/22) L; storage M-L; heaps S; map-flat/superpose M; Bool accumulator M; compact-datatypes M.

Paths are relative to external/PeTTaChainer/ unless marked GoalChainer. Line numbers are on the shimmed side of `shims/rt49ca-vs-shimmed.diff`. `shims/LOCATIONS.md` lists every hunk per tag (583 hunks, 67 files, generated mechanically from the tags on the edited lines; 14 untagged hunks are listed at its end). The diff also contains two scratch backup files (`kb_publication.metta.orig62`, `.orig68`). They are noise, not shims.

| shim | blocker | location (shimmed tree, file:line) |
|---|---|---|
| shim1 (`shim1_nested_arrows.py`), shim5, shim7 | nested annotated arrows refused (`fold-semidet`, `context-with-scope`, `particle-map-pairs`) | script over every `(: name TYPE)`; surviving untagged hunks: `pettachainer/metta/compiler/source_lowering.metta:623`, `:732`; `pettachainer/metta/runtime/evaluator/folds.metta:77`, `:122`; `pettachainer/metta/core/natives.metta:310` (context-with-scope, shim5); the other rewrites were later overwritten by shim15/17/18 at the same lines (see LOCATIONS.md). shim7 (particle-map-pairs, particle-map2-inner and 2 more): `third_party/pln_formulas/metta/distributions.metta:333`, `:341`, `:350-365`, `:455` (recovered: `shims/recovered/shim7_distributions.metta.diff`, a vendored file outside pettachainer/ and so outside the main diff) |
| shim2, shim4, shim4b | duplicate yall import; relative Prolog path | `pettachainer/metta/bootstrap.metta:33-34` (removed `import_prolog_functions_from_file`; `bootstrap.shim4b.diff` hunk :30-39); `pettachainer/metta/prolog/runtime_helpers.pl:6-11` (yall, tagged shim3) |
| shim3 | double `declare-natives!` registration | `pettachainer/metta/lib/natives.pl:19-37` (removed clause) |
| shim4c, shim14 | `apply_fn1/3` missing under pymetta (`finally/3`) | `pettachainer/metta/lib/natives.pl:28-36` (`pc_apply_unit`), `:81-85` (shim14) |
| shim6 | `sk-take!` not loaded (registration order) | `pettachainer/metta/lib/natives.pl:16-19`: `declare-forward!` routed to `declare-natives!` so forward decls such as `sk-take!` (`pettachainer/metta/core/natives.metta:315`) register (recovered: `shims/recovered/shim6_vs_liborig.diff`; file mtime 14:41:14 falls between the shim6 run 14:39:45 and shim7 run 14:42:50, see `shims/recovered/shim5-8_first_errors.txt`) |
| shim8 | PLN config path moved | GoalChainer `src/goal_chainer/evidence_chainer.py:85` (hunk :82-88) |
| shim9-12 | `bidirectional-implication-form?/2` called from Prolog | `runtime_helpers.shim9.diff` hunk :3-9; forwarding stub in `pettachainer/metta/prolog/ingestion.pl:326-354` |
| shim13, shim20 | Prolog -> MeTTa forwarding (`format/3`, pl_calls.txt) | `pettachainer/metta/prolog/ingestion.pl:326-354`; `pettachainer/metta/lib/natives.metta:13-32` |
| heapshim | library(heaps) not visible | `pettachainer/metta/lib/natives.metta:13-14` (heap arity decls; `empty_heap`/`add_to_heap` type decls removed); standalone `shims/heapshim*.pl` |
| shim15 / shim15b | return types -> `%Undefined%` | 146 hunks / 36 files and 18 hunks / 8 files; e.g. `pettachainer/metta/compiler/rules.metta:611`, `pettachainer/metta/runtime/backward/execution.metta:3`; full list LOCATIONS.md |
| shim17 | higher-order fold/map signatures | `pettachainer/metta/compiler/source_lowering.metta:108`, `:293`; `pettachainer/metta/lib/collections.metta:2-36` |
| shim18 | `List X` -> `Expression` | 290 hunks / 50 files; e.g. `pettachainer/metta/compiler/query_lowering.metta:142`, `:157`, `:412`; full list LOCATIONS.md |
| shim19 | `SkPattern` etc. -> `%Undefined%` | 388 hunks / 23 files; e.g. `pettachainer/metta/compiler/fold_sources.metta:3`, `:20`; full list LOCATIONS.md |
| shim21, shim22 | `prefix-key/3` not a Prolog predicate | `pettachainer/metta/runtime/store/fact_index.metta:28`; `pettachainer/metta/prolog/term_index.pl:108-110` |
| shim23 | 52 `sk-*`/store signature relaxations | `pettachainer/metta/core/natives.metta`: 14 hunks, lines 7-25 ... 324-341 (LOCATIONS.md) |
| pc_store_access | space-row storage under pymetta | new `pettachainer/metta/prolog/pc_store_access.pl:1-21`; `pettachainer/metta/prolog/context_overlay.pl:27`, `:48`, `:56-66`; `pettachainer/metta/prolog/space_store.pl:7`, `:17`, `:36` |
| probe63/68/75 | `map-flat` partial apps; `superpose` arg | `pettachainer/metta/runtime/kb_publication.metta:44-61` |
| probe118 (reverted) | curried Bool accumulator returns () | `pettachainer/metta/runtime/evaluator/versions.metta`; `:163` and `:460` (the two `fold-flat ... false` Bool-accumulator sites). Recovered snapshots: `shims/recovered/probe118_pre118_vs_prefa.diff` (the inlined `foldl-atom` form at both sites), `probe118_prefa_vs_facurrent.diff`, `probe118_facurrent_vs_final.diff` (the revert). The first variant (helper `sk-any-gives-way`) was replaced at the same two sites before a snapshot was taken. The preserved `foldl-atom` form is the same fix, written inline |
| brand/the/data | compact-datatypes builtins missing | no file edit (scratch `add-atom` at runtime, warmprobe136/137) |
| G2 (GoalChainer) | warm-up rules Premises -> bare Implication | GoalChainer `src/goal_chainer/policy/goalchainer_pettachainer.metta:44-45` (hunk :41-48) |

## 2. Open items (not solved here)
1. **Fact reads return () under pymetta.** After `compileadd` or `kb-publish-fact!` of one fact,
   `execute-backward 20 (((C c) (kbx MAIN Nil) $p $tv))` returns `()` (probes/qprobe11.out.txt, 3 of 3 cases).
   Because of this, the shared warm-up `gc-pettachainer-warm-up` answers `(False)` (warmprobe135-137), and that alone
   accounts for 116 of the 117 fa_r2 failures. The suspects are sk-read-fact / sk-fact-matches? / sk-leaf-fact-step
   (runtime/fact_reads/selection.metta:4, :29, :86), which return () for &kb_prefix rows.
   *Contrary evidence: a successful fact read.* Earlier, `probes/warmprobe118.txt:48` and `:52` (run 20:13:15) show both
   backward-query variants, `execute-backward-run` and `execute-backward`, returning the published fact
   `(B b) ... (fact-source (ev-set 1) f2) (STV 1.0 0.9)` with its proof and TV, after the same `kb-publish-fact!` call (:44)
   that later returns () in qprobe11 (21:24:27, `probes/qprobe11.out.txt:45-46`). That run had a version of probe118's
   Bool-accumulator fix in place (the `.prefa` snapshot taken 3 minutes later, 20:16:12, holds the inlined `foldl-atom` form:
   `shims/recovered/probe118_pre118_vs_prefa.diff`; the run may have used the earlier `sk-any-gives-way` helper variant at the
   same two sites). The fix was reverted afterwards
   (`probe118_facurrent_vs_final.diff`, 21:14-21:20). It does not show compatibility: the same probe still ends in
   `PREP TypeError` (:53), and the full suite was never run in that state. But it means reads *can* work under pymetta with the
   same publish path, so the regression is in something changed between 20:13 and 21:24. `evidence/timeline_118_to_q11.txt`
   lists those files: the versions.metta revert, plus store/fact_settings.metta, fact_reads/policy.metta,
   backward/skeleton.metta, the evaluator files and the natives.pl/natives.metta finally/pcapply shims. **This moves the
   Bool-accumulator revert to the leading suspect**, ahead of the storage-row hypothesis below. The success weakens that
   hypothesis (rows written by `kb-publish-fact!` were readable under pymetta at 20:13) but does not rule it out, because
   one store file, `runtime/store/fact_settings.metta`, also changed in the window (21:19:37).
   *Second hypothesis (storage rows):* the rows are written through pymetta's `add_sexp` into `'$metta_atoms:&kb_prefix'` with the
   extra trailing storage token, and the read side then misses them. Either it matches a 5-field row pattern against
   6-field storage terms, or it calls the bare `'&kb_prefix'/5` Prolog facts, which pc_store_access.pl only partly
   redirects. The curried Bool-accumulator bug (probe118) also yields (), and is the leading suspect (see above).
   *What would settle it:* re-apply only the probe118 fix (`shims/recovered/probe118_pre118_vs_prefa.diff`) to the final
   tree and re-run qprobe11. If reads return the fact, the revert is the cause; if not, bisect the other files in
   `evidence/timeline_118_to_q11.txt`. Only then fall back to the row dump (`metta_storage_term` vs sk-read-fact's pattern)
   for the storage hypothesis. At most 4 probes.
2. `chainer-reset!` and `set-backward-premise-prefilter` have no rT equivalent (G3).
3. rT's population prior for unproved goals changes how canaries must be read (W4).
4. The latent Bool-accumulator sites (about 20) were not fixed. probe118's fix was reverted.

## 3. What the shims achieved (from existing logs only; logs/*.summary.txt)
| run | result | first error |
|---|---|---|
| baseline: GC 38b1473 on its own runtime (`evidence/fitness/pytest_gc_38b1473.txt`: `186 passed`; same run as the fitness report's finding 13, `evidence/fitness/REPORT.md`) | 186 passed | none |
| gc_rt49ca_noshim_r1 | 117 failed / 69 passed | annotated arrow fold-semidet |
| shim1..shim13 (r1/r2, 14 logs) | 117 failed / 69 passed each | moves: foreach-flat -> yall -> declare-natives! -> runtime_helpers path -> context-with-scope -> sk-take! -> particle-map-pairs -> pln path -> bidirectional-implication-form? -> format/3 |
| gc_rt49ca_fa_r1 (5-test subset) | 1 failed / 4 passed | warm-up must answer True |
| gc_rt49ca_fa_r2 (final shim set) | 117 failed / 31 passed (148 tests in this log, vs 186) | 116x `warm-up gc-pettachainer-warm-up must answer True once`, 1x answer diff |

**Overlap of failures (by test ID).** `logs/failed_ids/<run>.ids` holds the sorted failing test IDs from each log (`grep -aE '^FAILED ' log | sed -E 's/^FAILED //; s/ - .*//' | sort -u`). Comparing each run with noshim_r1 (`comm`):

| run | failing IDs | shared with noshim_r1 | new | cleared |
|---|---|---|---|---|
| noshim_r1, shim1..shim13 (all 20 r1/r2/warmplain logs) | 117 | 117 | 0 | 0 |
| fa_r2 (final shim set) | 117 | 117 | 0 | 0 |
| fa_r1 (5-test subset) | 1 | 1 | 0 | (not run) |

So the same 117 test IDs fail in every full run, and **none of the original 117 failures cleared** with the shims tested. The shims did change *why* they fail. Load errors became a wrong warm-up answer (116 of 117 in fa_r2). Pass counts are not comparable: fa_r2's log covers 148 tests, the other runs cover 186 (69 vs 31 passes). Limit: this is about the logged runs only. I don't know which of the 69/31 passing tests overlap, because the logs record only failures by ID.

## 4. Options
| option | effort | risk | notes |
|---|---|---|---|
| A. Stay (36b3fe6-dedup + GC 38b1473) | 0 | low | works today. 186/186 GC, the wmtm suites are green. Forgoes rT's fixes (no duplicate import, newer rulelookup) |
| B. Adopt for wmtm only (PeTTa path, W1-W8 incl. W2b) | M (3-5 days: +1 for the engine upgrade W1a) | medium-high: the engine swap to unmerged rT PeTTa 3681b9b affects every wmtm PeTTa worker, with 4-5x startup/memory (F9) against worker_mem_mb; W8 removes a known false-positive proof | wmtm's shadow and semparse run under PeTTa, not pymetta, so section 1c does not apply. The fitness run showed 240 passed / 2 failed (`evidence/fitness/pytest_goals_pc_rt.txt`; base: 242 passed, `pytest_goals_pc_base.txt`), so W2-W5 are needed. Not tested beyond the fitness report |
| C. Adopt for GoalChainer v2 | L+ | high | in effect a port of rT to pymetta (section 1c plus open item 1). Risks silent wrong answers from about 260 type relaxations |
| D. Adopt everywhere | L+ | high | B + C |
| E. Wait for named upstream changes | 0 now | low | (1) pymetta: higher-order annotated arrows, MeTTa functions callable from Prolog, compact-datatypes builtins, map-flat/superpose parity; (2) rT: a storage accessor instead of raw row facts, `chainer-reset!`/prefilter equivalents, a documented rule form; (3) GC: G1-G4 |

**Recommendation: A now, plus E.** Raise the E list with Roman (rT) and the pymetta maintainers. If wmtm itself needs
rT fixes before then, B is feasible on its own, because wmtm's shadow and semparse workers use PeTTa, not pymetta.

**Bounded follow-up (optional):** "Settle PeTTaChainer fact-read under pymetta". Scope: open item 1 only, at most
2 h, at most 4 probes. Deliverable: confirm or reject that reverting probe118's Bool-accumulator fix broke fact reads
(warmprobe118 read OK at 20:13; qprobe11 () at 21:24), then, if needed, the row-storage hypothesis. No new shims.
