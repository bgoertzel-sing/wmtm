# t-2026-11-24-wmtm-s5-ops result (L-02, L-10, L-11, L-05 + add_fail cause)

## Summary
The order asked for four ops checks with no live change: config drift (L-02), integrity of the shared-input copies (L-10), a replay of the s1 switch triggers (L-11), and the gateway cache-patch guard history (L-05), plus a plan for andy. The live flags match the repo. The shared copies match their originals. In the d506783 window only T3 (add_fail>0) fired, and it was already there before the switch. The L-05 cache patch and its guard are both still needed: the gateway is still on the exact build the patch was made for, and there is no upstream fix. The plan for andy is in docs/S5_LIVE_SWITCH_PLAN.md: the repo file becomes the source, and a deploy step with a drift check, backup and atomic rename writes the live file. It also proposes an hourly read-only drift-check cron job. Nothing in it is applied yet.

Revision 2 (review 1) fixes these points. Real-note parser atoms are out of the repo, leaving ids, counts and error kinds only. T6 was a no-op on the live parse_log shape. It now matches the live rate-limit regex and has tests, and the re-replay still gives T6 0. A live_after snapshot shows nothing live changed. **Decision for andy:** the shared copy of the clerk-ab scratch tree included gw.key, and that file holds the live gateway key, the same one as in the protocosmo2 and protomegabot2 env files. It was group-readable under /srv/hive-evidence/shared for about 2 days. I shredded that copy and the 7 engine-token copies and regenerated SHA256SUMS (736 lines, verifies). The originals are untouched. Rotating the gateway key is your call. Separately, the add_fail cause is 7 atoms that PeTTa rejects (5 with an unbound variable, 1 with a numeric class, 1 arity clash). The proposed loader filter is not applied and needs its own task.

---

## L-02 config drift
drift_check.json: status "same". live_sha256 = repo_sha256 = f9e59f7428f0... ; only_live [], only_repo [], value_differs []. No drift.

## L-10 shared-input copy integrity
/srv/hive-evidence/shared/SHA256SUMS: 744 entries, `sha256sum -c` gives 0 failures (run 2026-11-27T00:19Z, nice -n19).
orig.sums has 744 lines; orig_vs_copy.diff is empty. The copies match the originals.

## L-11 trigger replay, d506783 window 2026-11-23T20:20Z to 11-24T20:20Z
fired: T3_canary only (23 rows with add_fail>0; canary_ok false 0; pred_fail 0); first/last 2026-11-24T14:15:49Z / 18:47:07Z.
T1 pin 0, T2 shadow failure 0, T4 timeouts budget 0, T5 admission 0, T6 http429 0.
**T6 caveat (review 1, finding 3):** as first written, T6 counted only an integer http_status/status_code/http_code field, and the live parse_log has none (`parse_log_has_http_field: false` over 255 rows). The live code writes a string `status` and a truncated `error` text and detects rate limits by regex on that text (wmtm/semparse_sentence.py:46, :427). So the "T6 0" above was a no-op, not a clean result. Fixed in this revision: T6 also counts rows whose status is not "ok" and whose error text matches the same LIMIT regex as the live code (2 new tests: fires on 3 such rows in an hour; ignores ok rows, non-limit errors and rows outside the hour). Re-replay of the same window with the fix: see t6_rereplay.json. T7 needs human verdicts (no xr/ni rules pre-switch).
shadow rows 107 (ok 106, canary_fail 1); neg_canary_timeouts 1; admit rows 143 (full-cap rows 6, not a trigger); worker rows ok 21 / share_full 11 / cap_full 2; designed stops with err null 13.
Reading: add_fail>0 was already there on d506783 (pre-switch baseline). This matches s1 ANSWER-1. The cause is now found by the offline joint-load repro (see "add_fail cause" below); the 17:36Z hold lapsed with the s1 rollback.

## L-05 gateway cache-patch guard history
l05_guard_history.txt: 96 guard rows since 2026-11-11T17:49:22Z: PASS 90, FAIL 6. All 6 FAILs are on 2026-11-11 (the first day). Every row from 2026-11-12 to 2026-11-24 is PASS (61 of them on 11-17).
l05_guard_last.json (2026-11-24T16:31:42Z): PASS, fails [], alert null. 4 patched dist files OK against SHA256SUMS.expected-patched. openclaw 2026.9.8 (patch built for 2026.9.8). cacheRetention='long'. Parse 11-22..11-24: 295 catalog-sized calls, 263 warm, 5 warm misses (old pattern).
Reading: the patch guard has been stable since 11-12, with no drift. The 5 warm misses are the known old pattern and do not trip the guard.
**Conclusion (review 1, finding 4): the patch and its guard are both still needed.** The installed gateway is still OpenClaw 2026.9.8 (fc23bc8), the exact build the patch was made for, and no upstream release carries the fix (the gateway-patch-pack report, section 3, is the upstream issue; the fix is not in the installed dist). Without the patch, the embedded runner (`buildAttemptSystemPrompt`) strips the second cache boundary, so the semparse catalog lands in the uncached block (gateway-patch-pack measured about 2,128 cached tokens instead of the catalog). The 263 of 295 warm catalog-sized calls on 11-22..11-24 depend on it. The guard is needed because dist file names are build-hashed: any `openclaw update` replaces the files and silently drops the patch, and the guard's `sha256sum -c` against SHA256SUMS.expected-patched is the only thing that would notice. Remove both only when an upstream OpenClaw release includes the cache-segment fix; at that point re-run the guard's cache check unpatched, and drop the patch if warm hits hold.

## add_fail cause (offline repro, 2026-11-26 21:35 PT, private temp copies, nice -n19, no live change)
Joint load of all 655 non-derived notes from shadow_master_parsed (24526 ops) into one private PeTTaChainer on vendor wmtm-d506783: 7 add_fail, 0 pred_fail. Every failing op is a typed atom `(: <id> ...)`, which is why the earlier summary read as "':' atoms". The ':' is the op head, not the cause; PeTTa compileadd/2 rejects the content with a Domain error:
- 5 of 7: `fact_without_free_variables`, the fact still has a free variable (ep-note-20261117T163655Z twice, ep-note-20261108T233704Z twice, ep-note-20261120T141412Z once; predicate heads only, atom content stays on pop-os). The parser left an argument unbound and the planner emitted it as a fact.
- 1 of 7: `inheritance_class`, an Inheritance atom with a numeric argument where a class symbol is required (ep-note-20261119T211438Z).
- 1 of 7: `predicate_arity`, Between used with 2 and 3 arguments (ep-note-20261120T113506Z). It loads alone, so it fails only in the joint load.
6 of 7 fail when loaded alone too, so "only when all notes load together" holds for the Between arity clash only.
Fix proposal (not applied): in master_loader.plan, before emitting an atom, (a) drop or skolemize facts with unbound variables, (b) reject non-symbol Inheritance args, (c) keep one arity per predicate head (rename arity-variants, e.g. Between/2 vs Between/3), and log each drop as a counted skip instead of add_fail. Evidence: addfail_cause_repro.txt (ids, counts, error kinds only) / .py; the full error text with atom content is on pop-os only (/srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/addfail_cause_repro.full.txt).

## Review 1 responses
1. Real-note atoms: evidence/addfail_cause_repro.txt now holds op index, op kind, exception, domain-error kind, note id and alone-result only. The full text is on pop-os only (addfail_cause_repro.full.txt, mode 640). The REPORT prose names predicate kinds only. `git grep` for skolem/atom patterns over reports/ and docs/ finds nothing.
2. Plan for andy: docs/S5_LIVE_SWITCH_PLAN.md (the switch, rollback, and the routine drift check as a cron proposal, plus 3 decisions).
3. T6: fixed. See the T6 caveat under L-11. 6/6 tests pass. t6_rereplay.json is the same window with the fix: T3 23 (same as before), T6 0, parse_log rows with error text 0. So T6 0 is now a real zero.
4. L-05: conclusion added (patch and guard still needed; remove when upstream ships the fix).
5. Acceptance 4: evidence/live_after.txt (2026-11-27T05:33:58Z). The flags sha f9e59f74 and pin sha 7acf09f1 are identical to live_before.txt.
6. Pop-os hygiene: the evidence dir now has SHA256SUMS, and every file there is group-readable (640/660).
7. Secrets: checked by hashing and grep, with no values printed. gw.key equals the live gateway key, and 4 running processes hold it. gw.key and the 7 state/engine-token files are shredded from the shared copy (list: scrubbed_files.txt; the old sums are in shared_SHA256SUMS.before_scrub on pop-os). The 6 credentials/profile.json files hold a source-key path and settings, not key material. The 3 tokens.jsonl files are token-usage counts, not credentials. Both are kept.
8. Minor: the speaker map in config/live-flags.json is listed as decision 3 in the plan. T5 now counts trivial_refused entries of any type through str(). A canary_fail shadow row from a negative-canary timeout counts toward T2 only, by design: T3 is for canary/add/pred fields, and the window's one such row is listed in t6_rereplay.json (neg_canary_timeouts 1).

## Evidence (sha256)
8587c3544668eedb0253054d705b5cf41b167409af1c49639929a31f41577ce8  drift_check.json
174707f25f60114c34e595aa314509b2a5c3d9648e339926adcc3add27db6ba1  l11_replay.json
51ebd2fc2a64a2679c8380a5f1d3e267ad998af35685dd00f3906a3c5efb38b3  l05_guard_history.txt
8362b80c6a21739ff76a49c9f9fcc238eedf0c33e01ac773b17b23d99e4f52b7  l05_guard_last.json
a41fc6c2f833dcaed6ca01bb976e7c4716767a97c20e0f6e98ad3c905387f314  addfail_cause_repro.py
6383213b152e61b8eef7eb1ca100e3ad799d9583f137540ba9382ec54d768d62  addfail_cause_repro.txt
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  orig_vs_copy.diff
