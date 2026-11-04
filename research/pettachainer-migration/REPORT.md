# What wmtm would need to change to run on rTreutlein/PeTTaChainer 49ca6f3

## Summary
andy asked what wmtm would need to change to run on rT PeTTaChainer 49ca6f3. Short answer: on the wmtm side, very
little. That is a medium-sized change: rewrite the rule form, repoint one vendor flag and one canary. The real blocker
is that rT 49ca6f3 does not run on GoalChainer v2's pymetta engine. I needed 22+ shims across 66 upstream files just to
get it to load. After all of them, the GoalChainer suite still has the same 117 failures (69 pass with no shims, 31
pass with the last shim set). Basic fact reads still return nothing (open item 1). The shims cleared **none** of the
117 failures. Each one only moved the first error further along the load path.

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
| W1 | wmtm/runtime_config.py:155-156 (`petta_dir`, `pettachainer_dir` = pettachainer-36b3fe6-dedup) | new vendor dir for rT 49ca6f3. The dedup-import patch is no longer needed: rT has no duplicate import (fitness F11) | wmtm | S |
| W2 | wmtm/workers/pc_shadow.py:39-42 (RULES), :44 CANARY | rT dropped `(Implication (Premises ..) (Conclusions ..))`. Rewrite the rules to bare `(Implication p c)` / `And` premises (fitness F2, F18) | wmtm | S |
| W3 | wmtm/semparse_adapter.py:184-207 `normalise()` | it currently converts And -> Premises (Oct 15 canary). It would need to invert that for rT, then re-run the semparse canary | wmtm | M |
| W4 | wmtm/workers/semparse_feed.py:71 (load canary rule), :74-75, :91 | same rule-form rewrite. The canary criterion must allow for rT's population prior (unproved goals get a prior TV, fitness F3) | wmtm | S-M |
| W5 | wmtm/pc_shadow.py:19-22 (`Implication` -> `Implies` head) | recheck: under rT, `Implies rain slippery` failed 2 tests (fitness F10) | wmtm | S-M |
| W6 | wmtm/workers/pc_shadow.py:50-61, semparse_feed.py:67-69 (`PeTTaChainer()`, `add_atom`, `query(steps, timeout_sec)`) | the Python API is unchanged in 49ca6f3. No change expected; re-verify | wmtm | S |
| W7 | wmtm/goals/v2.py:234 (`client()` env) | drops GOALCHAINER_PETTACHAINER_DIR, so the v2 canary never opens PeTTaChainer (fitness F18). Pass it through if v2 should use a non-default PeTTaChainer | wmtm | S |

### 1b. GoalChainer v2 adapter (GoalChainer repo, runs under pymetta-native.2)
| # | where | change | side | effort |
|---|---|---|---|---|
| G1 | src/goal_chainer/evidence_chainer.py:85 | `logic_configs/pln` -> `core/logic_configs/pln` (shim8) | upstream (GC) | S |
| G2 | src/goal_chainer/policy/goalchainer_pettachainer.metta:44-45 | warm-up rules Premises -> bare Implication | upstream (GC) | S |
| G3 | goalchainer_pettachainer.metta:19 `set-backward-premise-prefilter`, :41/:52 `chainer-reset!` | not defined in rT 49ca6f3. `!(chainer-reset!)` returns itself unevaluated (probes/qprobe11.out.txt). Needs an rT equivalent, or GC drops them | upstream (rT or GC) | M |
| G4 | tests/record_pettachainer_petta_beliefs.py:48-49 | same import path and prefilter call | upstream (GC) | S |

### 1c. rT PeTTaChainer under pymetta (the shims; details in README.md)
All of these are **upstream** (rT PeTTaChainer and/or the pymetta engine). None of them is wmtm-side.
| shim | problem | effort to fix properly |
|---|---|---|
| shim1/5/7/17/18 | pymetta refuses annotated arrows whose parameters are themselves annotated arrows (higher-order types) | M (pymetta) or L (rT signatures) |
| shim15/19/23 | pymetta checks return and argument types that PeTTa ignores: `Atom`/`List X`/`SkPattern` -> `%Undefined%`/`Expression`, about 260 sites | L (rT-wide type audit) |
| shim2/3/4/4b/6 | load order, duplicate yall import, double `declare-natives!`, relative Prolog paths | M |
| shim4c/14 | `apply_fn1/3` (PeTTa translator only) used by `finally` | S-M |
| shim9-13, shim20 | Prolog calls into MeTTa functions (`bidirectional-implication-form?`, `canon`, ... see pl_calls.txt). pymetta does not export MeTTa functions as Prolog predicates | L |
| shim21/22 | `prefix-key/3` term_index (same cause) | S once the general fix exists |
| pc_store_access.pl | space-row storage differs under pymetta (`'$metta_atoms:<space>'` modules plus a trailing token). Direct row facts and `retractall` miss | M-L (an rT storage abstraction) |
| heapshim | library(heaps) not visible from the MeTTa module | S |
| probe63/68/75 | `map-flat` drops partial applications; `superpose` does not evaluate its argument | M |
| probe118 (reverted) | curried calls with a Bool accumulator return (). About 20 latent sites | M |
| brand/the/data | builtins from rT PeTTa compact-datatypes 3681b9b, missing from the pymetta wheel | M (pymetta) |

## 2. Open items (not solved here)
1. **Fact reads return () under pymetta.** After `compileadd` or `kb-publish-fact!` of one fact,
   `execute-backward 20 (((C c) (kbx MAIN Nil) $p $tv))` returns `()` (probes/qprobe11.out.txt, 3 of 3 cases).
   Because of this, the shared warm-up `gc-pettachainer-warm-up` answers `(False)` (warmprobe135-137), and that alone
   accounts for 116 of the 117 fa_r2 failures. The suspects are sk-read-fact / sk-fact-matches? / sk-leaf-fact-step
   (runtime/fact_reads/selection.metta:4, :29, :86), which return () for &kb_prefix rows.
   *Best hypothesis:* the rows are written through pymetta's `add_sexp` into `'$metta_atoms:&kb_prefix'` with the
   extra trailing storage token, and the read side then misses them. Either it matches a 5-field row pattern against
   6-field storage terms, or it calls the bare `'&kb_prefix'/5` Prolog facts, which pc_store_access.pl only partly
   redirects. The second suspect is the curried Bool-accumulator bug (probe118), which also yields ().
   *What would settle it:* after one compileadd, dump the stored &kb_prefix row(s) (`metta_storage_term`) and the
   exact pattern that sk-read-fact matches. Then run the same 1-fact query on unmodified rT under PeTTa, where it
   works, and diff the two. That needs at most 2 probes.
2. `chainer-reset!` and `set-backward-premise-prefilter` have no rT equivalent (G3).
3. rT's population prior for unproved goals changes how canaries must be read (W4).
4. The latent Bool-accumulator sites (about 20) were not fixed. probe118's fix was reverted.

## 3. What the shims achieved (from existing logs only; logs/*.summary.txt)
| run | result | first error |
|---|---|---|
| baseline: GC 38b1473 on its own runtime (fitness rev3, F13) | 186 passed | none |
| gc_rt49ca_noshim_r1 | 117 failed / 69 passed | annotated arrow fold-semidet |
| shim1..shim13 (r1/r2, 14 logs) | 117 failed / 69 passed each | moves: foreach-flat -> yall -> declare-natives! -> runtime_helpers path -> context-with-scope -> sk-take! -> particle-map-pairs -> pln path -> bidirectional-implication-form? -> format/3 |
| gc_rt49ca_fa_r1 (5-test subset) | 1 failed / 4 passed | warm-up must answer True |
| gc_rt49ca_fa_r2 (final shim set) | 117 failed / 31 passed (148 tests in this log, vs 186) | 116x `warm-up gc-pettachainer-warm-up must answer True once`, 1x answer diff |

So the evidence failures cleared went from 0 of 117 to 0 of 117. The shims got rT to load and run under pymetta
(load errors 117 -> 0), but every failure became a wrong answer instead: the warm-up's fact read returns (). Note: fa_r2 covers 148 tests and the
other runs cover 186 (the progress bars reach 100% at 148 in fa_r2), so 31 vs 69 passes cannot be compared. The
comparable figure is the 117 failures, which is the same in every run.

## 4. Options
| option | effort | risk | notes |
|---|---|---|---|
| A. Stay (36b3fe6-dedup + GC 38b1473) | 0 | low | works today. 186/186 GC, the wmtm suites are green. Forgoes rT's fixes (no duplicate import, newer rulelookup) |
| B. Adopt for wmtm only (PeTTa path, W1-W7) | M (2-4 days) | medium | wmtm's shadow and semparse run under PeTTa, not pymetta, so section 1c does not apply. The fitness run showed 240+2 fail, so W2-W5 are needed. Not tested beyond the fitness report |
| C. Adopt for GoalChainer v2 | L+ | high | in effect a port of rT to pymetta (section 1c plus open item 1). Risks silent wrong answers from about 260 type relaxations |
| D. Adopt everywhere | L+ | high | B + C |
| E. Wait for named upstream changes | 0 now | low | (1) pymetta: higher-order annotated arrows, MeTTa functions callable from Prolog, compact-datatypes builtins, map-flat/superpose parity; (2) rT: a storage accessor instead of raw row facts, `chainer-reset!`/prefilter equivalents, a documented rule form; (3) GC: G1-G4 |

**Recommendation: A now, plus E.** Raise the E list with Roman (rT) and the pymetta maintainers. If wmtm itself needs
rT fixes before then, B is feasible on its own, because wmtm's shadow and semparse workers use PeTTa, not pymetta.

**Bounded follow-up (optional):** "Settle PeTTaChainer fact-read under pymetta". Scope: open item 1 only, at most
2 h, at most 4 probes. Deliverable: confirm or reject the row-storage hypothesis, quoting the stored row and the
matched pattern. No new shims.
