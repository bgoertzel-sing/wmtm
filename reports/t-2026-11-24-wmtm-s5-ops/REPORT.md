# t-2026-11-24-wmtm-s5-ops result (L-02, L-10, L-11, L-05 + add_fail cause)

## Summary
The order asked for four ops checks with no live change: config drift (L-02), integrity of the shared-input copies (L-10), a replay of the s1 switch triggers (L-11), and the gateway cache-patch guard history (L-05). All four are clean. The live flags match the repo (no drift). All 744 shared-input copies match their originals. In the d506783 window only T3 (add_fail>0) fired, and it was already there before the switch. The L-05 guard has passed every day since 11-12.

I also found the cause of the add_fail rows by reproducing them offline. When all 655 notes are loaded together, 7 atoms are rejected by PeTTa. Five are facts the parser left with an unbound variable, one uses a number as a class, and one is a Between predicate used with two different arities. Only the arity clash depends on loading the notes together. The proposed fix is to filter these three kinds of atom in master_loader.plan and count them as skips. It is not applied and needs a decision and a separate task. Nothing live was changed.

---

## L-02 config drift
drift_check.json: status "same". live_sha256 = repo_sha256 = f9e59f7428f0... ; only_live [], only_repo [], value_differs []. No drift.

## L-10 shared-input copy integrity
/srv/hive-evidence/shared/SHA256SUMS: 744 entries, `sha256sum -c` gives 0 failures (run 2026-11-27T00:19Z, nice -n19).
orig.sums has 744 lines; orig_vs_copy.diff is empty. The copies match the originals.

## L-11 trigger replay, d506783 window 2026-11-23T20:20Z to 11-24T20:20Z
fired: T3_canary only (23 rows with add_fail>0; canary_ok false 0; pred_fail 0); first/last 2026-11-24T14:15:49Z / 18:47:07Z.
T1 pin 0, T2 shadow failure 0, T4 timeouts budget 0, T5 admission 0, T6 http429 0. T7 needs human verdicts (no xr/ni rules pre-switch).
shadow rows 107 (ok 106, canary_fail 1); neg_canary_timeouts 1; admit rows 143 (full-cap rows 6, not a trigger); worker rows ok 21 / share_full 11 / cap_full 2; designed stops with err null 13.
Reading: add_fail>0 was already there on d506783 (pre-switch baseline). This matches s1 ANSWER-1. The cause is now found by the offline joint-load repro (see "add_fail cause" below); the 17:36Z hold lapsed with the s1 rollback.

## L-05 gateway cache-patch guard history
l05_guard_history.txt: 96 guard rows since 2026-11-11T17:49:22Z: PASS 90, FAIL 6. All 6 FAILs are on 2026-11-11 (the first day). Every row from 2026-11-12 to 2026-11-24 is PASS (61 of them on 11-17).
l05_guard_last.json (2026-11-24T16:31:42Z): PASS, fails [], alert null. 4 patched dist files OK against SHA256SUMS.expected-patched. openclaw 2026.9.8 (patch built for 2026.9.8). cacheRetention='long'. Parse 11-22..11-24: 295 catalog-sized calls, 263 warm, 5 warm misses (old pattern).
Reading: the patch guard has been stable since 11-12, with no drift. The 5 warm misses are the known old pattern and do not trip the guard.

## add_fail cause (offline repro, 2026-11-26 21:35 PT, private temp copies, nice -n19, no live change)
Joint load of all 655 non-derived notes from shadow_master_parsed (24526 ops) into one private PeTTaChainer on vendor wmtm-d506783: 7 add_fail, 0 pred_fail. Every failing op is a typed atom `(: <id> ...)`, which is why the earlier summary read as "':' atoms". The ':' is the op head, not the cause; PeTTa compileadd/2 rejects the content with a Domain error:
- 5 of 7: `fact_without_free_variables`, the fact still has a free variable (ep-note-20261117T163655Z Directive twice; ep-note-20261108T233704Z Stimulus twice; ep-note-20261120T141412Z Theme). The parser left an argument unbound and the planner emitted it as a fact.
- 1 of 7: `inheritance_class`, (Inheritance 429 stop): a number used as a class (ep-note-20261119T211438Z).
- 1 of 7: `predicate_arity`, Between used with 2 and 3 arguments (ep-note-20261120T113506Z). It loads alone, so it fails only in the joint load.
6 of 7 fail when loaded alone too, so "only when all notes load together" holds for the Between arity clash only.
Fix proposal (not applied): in master_loader.plan, before emitting an atom, (a) drop or skolemize facts with unbound variables, (b) reject non-symbol Inheritance args, (c) keep one arity per predicate head (rename arity-variants, e.g. Between/2 vs Between/3), and log each drop as a counted skip instead of add_fail. Evidence: addfail_cause_repro.txt / .py.

## Evidence (sha256)
8587c3544668eedb0253054d705b5cf41b167409af1c49639929a31f41577ce8  drift_check.json
174707f25f60114c34e595aa314509b2a5c3d9648e339926adcc3add27db6ba1  l11_replay.json
51ebd2fc2a64a2679c8380a5f1d3e267ad998af35685dd00f3906a3c5efb38b3  l05_guard_history.txt
8362b80c6a21739ff76a49c9f9fcc238eedf0c33e01ac773b17b23d99e4f52b7  l05_guard_last.json
a41fc6c2f833dcaed6ca01bb976e7c4716767a97c20e0f6e98ad3c905387f314  addfail_cause_repro.py
6383213b152e61b8eef7eb1ca100e3ad799d9583f137540ba9382ec54d768d62  addfail_cause_repro.txt
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  orig_vs_copy.diff
