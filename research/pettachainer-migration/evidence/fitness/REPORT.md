# PeTTaChainer fitness check: current pin vs rTreutlein master (t-2026-11-03-pettachainer-fitness)

Report only. Nothing live was changed. All runs used scratch copies in /tmp/pcfit; the evidence files are in this directory.

## What was compared
- **base** (live pin): MesTTo pettachainer 36b3fe6 with dedup patch, running on PeTTa v1.0.6
- **rt** (candidate): rTreutlein pettachainer master 49ca6f3, running on rT PeTTa pr/compact-datatypes 3681b9b (the version it requires)
- Lineage: the two last share commit 6b88df7 (2026-06-09). From there, rT master is 1,091 commits ahead and 36b3fe6 is 11 commits ahead. I checked all 7 rT branches.

## Findings
1. **API:** wmtm calls only the constructor, add_atom and query, and all three still exist. One change: add_atom now returns a list.
2. **Rule syntax breaks.** rt no longer accepts wmtm's rule format, `(Implication (Premises ...) (Conclusions ...))`.
   - Rules with two premises load without any error but never fire.
   - A rule with one premise is rejected with a Prolog error about `Premises` arity.
   - Inheritance chaining still works on rt, but only because rt handles it natively, not through our rule.
   - Result: on rt, 60 of wmtm's 62 PC tests pass. The 2 failures are test_integration_synthetic and test_integration_worker_writes_admit_file (`(Implies rain slippery)` is not proved).
   - Evidence: pytest_pc_rt*.txt, imp*.py.
3. **The new rule syntax is not backward compatible.** rt expects `(Implication (And A B) C)` with a CTV truth value. base rejects that form with "Invalid evaluated PLN statement" (imp6.py). The two versions accept different rule formats, so wmtm cannot ship one set of RULES that runs on both.
4. **The truth-value form matters on rt.** A rule given a plain STV still fires but with very low confidence: 0.0135 for imp_trans and 0.065 for a one-premise rule. Given a CTV, confidence is normal: 0.90 (imp4.py, imp5.py).
5. **rt answers unprovable queries with a prior.** For `(Member grace robot)`, rt returns `(population-prior ...)` at STV 0.916 / 0.0012. wmtm's check (`head in x`) counts that as proved, so the negative canary fails. A filter that ignores population-prior answers and anything below confidence 0.05 fixes this.
   - With the And/CTV rules plus that filter, rt passes all 62 PC tests (pytest_pc_rt_andform_floor.txt).
   - base fails the same 2 tests under that diff, because it rejects the new rule form.
   - Diffs: pc_shadow_andform.diff, pc_shadow_andform_conffloor.diff.
6. **pc_retest cases** (retest_*):
   - or_in_and: no memory blow-up on either version. base returns []. rt proves the goal at confidence about 1.7e-15.
   - and_elim: base returns []. rt proves both parts at confidence about 1e-16.
   - and_impl: base fails. rt proves it at 0.983.
   - premises_impl and canary: proved on both.
   - multi_concl: fails on both.
   - stv_range: both still accept invalid truth values such as STV 1.0 1.5.
   - The near-zero confidences on rt are probably the same STV-vs-CTV effect as in finding 4. I did not re-run those cases with CTV, so this is not confirmed.
7. **Atoms are rewritten on storage.** rt stores `(Member x c)` as `(c x)` and Inheritance as Implication. Answers come back in the original form, and proof terms have a new shape (by/conjunction/specializes in place of rule-proof).
8. **Duplicate import is fixed upstream.** A module imported twice leaves 2 definitions on PeTTa v1.0.6 but only 1 on the rT PeTTa branch.
9. **Cost on rt:**
   - First canary run: 18.6 s and 595 MB, against 0.3 s and 36 MB on base.
   - Later per-process runs: about 1.8 s and 120 MB, against 0.35 s and 33 MB on base.
   - Startup time and memory are about 4 to 5 times higher on rt.

## Assessment
rt is not a drop-in upgrade. To move to it, wmtm needs:
- the RULES rewritten in the And/CTV form,
- the proof-acceptance check changed to ignore population-prior answers and set a confidence floor,
- semparse_adapter's rule-shape filter (around line 187) reviewed,
- a migration in one step, because neither rule format runs on both versions,
- a check that the higher startup cost fits within worker_mem_mb.

In return, rt gains And-form rules, conjunction elimination and the duplicate-import fix.

Recommendation: stay on 36b3fe6 for now. If an upgrade is wanted, do it as a separate task: switch the RULES and the acceptance filter together with the vendor pin, then re-run the full suite and a shadow pilot before going live.

## Revision 2 additions
10. **Goal suites + PC suites with goal_v2 configured** (run_goals_pc.sh; the earlier "v2_unconfigured" canary failure came from missing WMTM_GOAL_V2_* env and is gone; first run kept in run1_unconfigured/):
    - base 36b3fe6: 242 passed in 31.9 s, peak RSS 139 MB (pytest_goals_pc_base.txt).
    - rt 49ca6f3: 240 passed, 2 failed in 41.2 s, peak RSS 139 MB (pytest_goals_pc_rt.txt).
    - The 2 rt failures are the same two as in finding 2 (`(Implies rain slippery)` not proved). No goal-suite test changes outcome; only the PC rule-form tests differ.
11. **Duplicate import, static scan** (dup_import_static.sh/.txt): on base, `petta_chainer` is imported from 34 places and several context/chainer modules from 2-5 places; lib_import is referenced from 3 files. On rt, no module is imported from more than one file.
12. **Duplicate import, runtime repro** (dup_import_runtime.sh/.txt, imp6.py canary, 600 s cap each):
    - base without the dedup patch: no answer; RSS grew past 1.5 GB and the run was killed at the 600 s cap. This reproduces the Oct12 dup-import blowup, so the dedup patch remains required on base.
    - base with dedup patch: 0.39 s, 37 MB; rejects the And+CTV rule (as in finding 3), proves nothing for the canary.
    - rt: 2.13 s, 134 MB; proves `(Member grace person)` at STV 1.0/0.97 and answers unproved `(Member grace robot)` with population-prior STV 0.92/0.0012 (as in finding 5).

Assessment and recommendation are unchanged by revision 2.


## Revision 3 additions (review 2 follow-up)
All revision-3 runs are under rev3/ and are self-contained: every path is under /tmp (rev3/env.sh), readable by astra (ACL u:astra:rX, recursive and default). No /home access is needed. Copies: /tmp/pcfit/vendor (petta-v1.0.6, pettachainer-36b3fe6-dedup), /tmp/pcfit/toolchains/swi-prolog-9.3.36, /tmp/pcfit/gc-runtime (goalchainer-v2-pymetta-native.2 with relocated venv), /tmp/pcfit/pylib (janus_swi). rT = /tmp/pc_rt (49ca6f3) + /tmp/pcfit/PeTTa; base unpatched = /tmp/pc_me.
To rerun everything: `rev3/run_all.sh` (about 5 min). Single case: `rev3/retest.sh base|rt <case>`.

13. **GoalChainer baseline** (rev3/gc_baseline.sh; tests/test_evidence_chainer.py + tests/test_memory_evidence.py on the pymetta-native.2 runtime):
    - vendored PeTTaChainer 38b1473: **186 passed** in 86 s, peak RSS 331 MB (rev3/pytest_gc_38b1473.txt).
    - same runtime with GOALCHAINER_PETTACHAINER_DIR=rT 49ca6f3: **117 failed, 69 passed** in 58 s, peak RSS 288 MB (rev3/pytest_gc_49ca6f3.txt).
    - All 117 failures have one cause: `metta_add_atom/3: cannot honour the annotated arrow for fold-semidet`. pymetta refuses the `-[semidet]->` annotation in rT petta_chainer. This blocks porting GoalChainer: the pymetta engine cannot load rT until pymetta supports annotated arrows or rT drops the annotation. The 69 passing tests never load the chainer.
14. **pc_retest reruns, self-contained** (rev3/retest_*). Outcomes match finding 6.
    - base: canary proves (Member grace person) STV 1.0/0.99. or_in_and, and_elim and and_impl return [].
    - rt: canary 1.0/0.987 and and_impl 1.0/0.983. and_elim and or_in_and prove, but with confidence about 1e-16 and 1.7e-15.
    - Per-process RSS: base 32-33 MB, rt 120-121 MB. The exception is rt or_in_and at 554 MB in this run (123 MB in the earlier run), so rt peak memory on Or-in-And varies from run to run. There was no blowup, but 554 MB should count against worker_mem_mb.
15. **Duplicate-import canary, self-contained** (rev3/dup_import.txt, 180 s cap):
    - base unpatched: no output before the cap. This agrees with finding 12, where the 600 s cap was hit with RSS above 1.5 GB.
    - base+dedup: 0.37 s, 37 MB. It rejects the And+CTV rule.
    - rt: 2.11 s, 134 MB. It proves (Member grace person) at 1.0/0.97.

Assessment after revision 3: unchanged, and stronger. Do not upgrade now. On top of the wmtm rule and acceptance changes, GoalChainer on pymetta cannot load rT at all (finding 13). An upgrade also needs the annotated-arrow porting issue fixed first.


## Revision 4 additions (self-containment check)
16. **Whole bundle rerun with /home hidden** (bwrap --tmpfs /home): rev3/run_all.sh (rev3/run_all_nohome.log) and rev3/gc_baseline.sh both finished with the same outcomes: goals+PC base 242 passed, rT 2 failed/240 passed; GC 38b1473 186 passed, rT 49ca6f3 117 failed/69 passed (all with the annotated-arrow cause); retests and dup-import as in findings 14-15.
    - Fix: gc_baseline.sh now unsets SWI_HOME_DIR and LD_LIBRARY_PATH, because pymetta bundles its own SWI host and refuses a foreign one. The janus settings in env.sh are only for the pc/goals runs.
    - Fix: removed the last /home mention (a comment) from env.sh.
    - The single "/home" string left in rev3/pytest_gc_49ca6f3.txt is an inherited environment variable (OMEGACLAW_OUTER_LOG) echoed in a pytest traceback dump. It is not a file the run reads; the run passed with /home hidden.

Assessment after revision 4: unchanged. Do not upgrade now.


## Revision 5 additions (review 4 follow-up)
17. **Goal canary with GoalChainer itself on rT (criterion 4).** Review 4 was right: rev3/goals_pc.sh switched only the PC dependency, and GoalChainer stayed on 38b1473. Setting the env var cannot fix this, because wmtm `goals/v2.py` `client()` (around line 234) builds a fixed subprocess environment that drops `GOALCHAINER_PETTACHAINER_DIR`. So rev3/goals_gc_rt.sh uses a second GoalChainer runtime copy, /tmp/pcfit/gc-runtime-rt, whose vendored `external/PeTTaChainer` is rT 49ca6f3. Its .pth file points at the copy, and rev3/goals_gc_rt.log prints the resolved checkout_dir and commit for each arm. The runs used bwrap with /home hidden.
    - 11 goal suites (test_goalchainer_bridge/orchestrator, goal_rank, goals_rc3, track_r/r2/s/t/v, v060, v2): gcbase (38b1473) **180 passed**, 29.1 s, 142,280 KB; gcrt (49ca6f3) **180 passed**, 29.4 s, 143,200 KB.
    - **Harness limitation (this is not evidence of compatibility):** the real-engine goal canary (test_goals_v2 -k test_real, rev3/goal_canary_strace.sh/.log) passes 3/3 on both copies. strace shows that it opens **zero** PeTTaChainer files on either copy (rev3/strace_goal_canary_gc*.txt). The goal/deontic path loads only GoalChainer's own MeTTa policy. Evidence grading (evidence_chainer.py) is the only GoalChainer code that loads PeTTaChainer, and that suite fails 117/186 on rT (finding 13). So the goal-suite result only shows that the goal path does not depend on PeTTaChainer. It is not evidence that rT works.
18. **Complete migration break list (criterion 2)** (rev3/gc_rt_path_audit.sh/.txt). This lists everything GoalChainer's evidence grading needs from PeTTaChainer, on base 38b1473 vs rT 49ca6f3:
    - a. `MettaLibrary(LIBRARY, "logic_configs/pln")` (evidence_chainer.py:85): rT moved the file to `core/logic_configs/pln.metta` (commit 1e6aa353, R100; `predicate_logic.metta` moved the same way). The import path must change.
    - b. `set-backward-premise-prefilter` (called at policy/goalchainer_pettachainer.metta:19): defined in base (chainer/backward_chainer.metta:423), **not defined in rT**.
    - c. `chainer-reset!` (called at goalchainer_pettachainer.metta:41 and :52): defined in base (petta_chainer.metta:121), **not defined in rT**.
    - d. `compileadd` and `query`: still defined in rT, but moved to runtime/ingest.metta and runtime/query.metta. They are reached through petta_chainer.metta, so no GoalChainer change is needed.
    - e. The pymetta annotated-arrow error (`-[semidet]->`, finding 13) stops loading before any of a-c is reached. So a-c come from static audit, not from runtime failures.
    - f. From findings 1-9: rT drops the Premises/Conclusions rule form and requires the And+CTV form. It also answers unproved goals with a population-prior, so acceptance checks must test confidence.

**Migration scope:**
- Make pymetta (or rT) accept annotated arrows.
- Repoint the pln import to `core/logic_configs/pln`.
- Replace or re-add `set-backward-premise-prefilter` and `chainer-reset!` for GoalChainer's grading policy.
- Port the rules to And+CTV.
- Add a confidence floor to the acceptance checks.

After that, the GoalChainer evidence suites (186 tests) on a runtime with rT vendored are the real canary. The goal suites are not, because they never load PeTTaChainer.

Assessment after revision 5: unchanged. Do not upgrade now. Stay on 36b3fe6.
