# Switch plan S1: WMTM shadow bundle (t-2026-11-24-wmtm-s1-shadow-bundle)

Status: PLAN ONLY. Nothing here has been run on the live bot. andy decides whether and when to switch.

## 0. What would go live
| feature | flag (runtime_config) | in main since | measured gain (5 frozen runs) | in this plan |
|---|---|---|---|---|
| R-01 extra rules (supersedes / contradicts) + R-11 Not Current/Valid wording | `shadow_extra_rules` | a70dc86 (+ pc_admit wording) | +9..+11 conclusions, 8..10 C / 1 U / 0 W | ON |
| R-12 note-implication goals (premise proving stays off) | `shadow_note_impl_goals` (`shadow_note_impl_premise` stays false) | aa87f6d | +13..+19 conclusions, all C, 0 W | ON |
| P-03 later label replaces earlier | `shadow_label_replace` | bb5d2be | 1..3 labels replaced per run, 0 conclusion change | ON (correctness: a re-issued statement wins) |
| P-01 class links | `class_links` | not in main (hive branch of t-2026-11-24-wmtm-p01-class-links + S1 wiring) | 29..36 links per run, 0 new goals | OFF (no consumer, zero gain) |

## 1. Precondition: a package move, not only a flags edit
The live package is `vendor/wmtm-d506783` (pin `_wmtm_pin.py` sha256 7acf09f1..., EXPECTED_COMMIT d5067832). None of
the flags above exist in d506783 (grep: 0 files). An unknown key in the flags file is ignored by d506783, so writing
the flags alone does NOTHING. The switch is therefore:
1. a new vendored package `wmtm-<C7>` built from the merged wmtm main commit `<C7>` that contains a70dc86, aa87f6d, bb5d2be
   (fd48815 or later; plus the S1 branch only if class_links is wanted), and
2. a pin edit (WMTM_VENDOR, EXPECTED_VERSION, EXPECTED_COMMIT), and
3. the flags delta below.
Do steps 1-2 first with the flags unchanged (= the measured all-off arm, byte-identical to fd48815 on all 5 runs),
let it run through the first-notes check, and only then apply step 3. Two separate changes, two separate rollbacks.

## 2. Flags file delta
File: `<repos>/memory/_wmtm_flags.json`, current sha256 `f9e59f7428f059f0565794ee1fb256d576d0a1e0c9bceac4f2f8f5f012216785`.
Add exactly these keys (no other key changes):
```diff
+  "shadow_extra_rules": true,
+  "shadow_note_impl_goals": true,
+  "shadow_note_impl_premise": false,
+  "shadow_label_replace": true,
```
Optional, not recommended: `"class_links": true` (needs the S1 branch merged; adds atoms with no consumer).
Write it atomically (copy to `.tmp`, `json.load` check, `mv -f`), record the new sha256 in the switch evidence.

## 3. Pre-checks (all must pass; stop otherwise)
1. Backup: `cp -a` the flags file and `_wmtm_pin.py` to `backups/wmtm-s1-switch-<UTC>/`; `sha256sum -c` shows
   flags f9e59f74... and pin 7acf09f1....
2. Package: `vendor/wmtm-<C7>/wmtm/runtime_config.py` lists the 4 keys; VERSION commit = `<C7>`; full test suite of `<C7>`
   passes in that directory.
3. Canary off: build the master_ops spec for the 20 notes from A0 parses with `<C7>` and the CURRENT flags: byte-identical
   to `/srv/hive-evidence/t-2026-11-24-wmtm-s1-shadow-bundle/runs/A0/off/spec.json` (tools/build_spec_base.py).
4. Canary on: same with the new flags: goals = 130 and the goal set equals `runs/A0/all/spec.json` minus class_links
   (i.e. the xr+ni goals, 105 + 11 + 14).
5. Budget headroom: the all-on shadow run took 17.7-24.1 s wall with prequery 9.2-14.7 s against `shadow_budget_s` 20 and
   0 skipped goals. Live k may differ: check the last 24 h of live shadow rows have `skipped_budget` 0 and prequery_s
   < 12 s; if not, do not switch (or raise `shadow_budget_s` as a separate, reviewed change).
6. No running worker is mid-cycle (same c7_procs wait as `rollback-master.sh`).
7. `parse_role`, `parse_cap_per_hour`, share and prompt keys are unchanged (diff of the two JSON objects shows only the 4 keys).

## 4. Rollback
- Flags only (step 3 of section 1): restore `backups/wmtm-s1-switch-<UTC>/memory/_wmtm_flags.json` atomically;
  `sha256sum -c` must give f9e59f7428f059f0565794ee1fb256d576d0a1e0c9bceac4f2f8f5f012216785. Re-read every cycle, no restart.
  Then move the current `memory/_wmtm_shadow/pc_shadow/admit.json` aside (it may hold xr/ni conclusions) after the
  worker wait, exactly as R3 in `backups/wmtm-master-switch-20261116T2258Z/rollback-master.sh`.
- Package: restore `_wmtm_pin.py` (sha256 7acf09f1a2c64805...) from the same backup; d506783 stays in `vendor/`. Use
  `rollback-master.sh`'s R2/R3 steps with that backup dir (script sha256 c5c1dc29...; it targets ddd2096 + e6496a47 for
  the older switch, so pass the S1 backup dir, never run it unmodified for this switch).
- Derived items already written back by the reasoner carry provenance goal ids; xr goals start `(Not (Current`/`(Not (Valid`
  or rule `xr_*`, ni goals rule `nimpl:*`; list them by rule from `admit.json` before moving it aside.

## 5. Triggers (roll back the flags on any of these)
Built to avoid the L-11 false alarms of t-2026-11-17-wmtm-master-live-check (snap.py fired on idle/budget states).
Each trigger names the exact field; normal idle states are listed as NOT triggers.

Real triggers:
- T1 pin/package: `ImportError` "wmtm pin mismatch" in the bot log lines emitted by the package path (traceback frames
  under `vendor/wmtm-<C7>/`), 1 occurrence. Tracebacks from ad-hoc shell commands or other paths are not counted.
- T2 shadow failure: 2 consecutive shadow rows with `status` not in {`ok`} AND not a designed stop. Designed stops that
  never count: `busy`, `nothing_pending`, `budget_zero`, `share_full`, `cap_full`, `rate_limited` with `err` null.
- T3 canary: any shadow row with `canary.ok` false, or `add_fail` > 0, or `pred_fail` > 0.
- T4 timeouts/budget: `timeouts` > 0 or `skipped_budget` > 0 in 2 consecutive shadow rows (pre-switch baseline is 0).
- T5 admission quality: any admitted conclusion whose rule is `xr_*` or `nimpl:*` and that is a restatement
  (pc_admit trivial filter should drop it; count from admit.json `results[].rule` and the trivial-refused list), or
  any run admitting more than `reasoner_max_admit` (live file does not set it, so the default 5 applies; the cap
  should make this impossible, so one occurrence means the admit gate is broken). On the 5 frozen runs the all-on
  arm had 45-55 admissible candidates against 27-32 all-off (scored with the cap lifted to 1000), so the cap of 5
  will be full on most live cycles: a full cap is normal and is NOT a trigger.
- T6 HTTP 429: only the integer HTTP status field of parse-log rows equals 429 (never a substring match in hashes,
  timestamps or token counts), 3 or more in one hour.
- T7 wrong conclusion: any human-confirmed W among admitted xr/ni conclusions in the first 24 h.

NOT triggers (idle and normal states): no traffic (0 new store items), 0 worker runs in an hour, `budget_zero`/
`share_full`/`cap_full` worker rows with err null and used <= share, empty admit file, unchanged goal count across
cycles, shadow skipped because `shadow_min_interval_s` (300 s) has not passed.

## 6. Checks after the flags switch
Read-only, counts only, no note text. Compare against the pre-switch 24 h baseline (same fields).
- First notes (first 3 shadow rows after the flags sha changes): status ok, canary ok, `master_meta.extra_rules` = 4,
  `master_meta.label_replaced` present, `note_impl` stats present, goals >= pre-switch goals for the same k, 0 timeouts,
  0 skipped_budget, total_s < 30. Admitted xr/ni conclusions listed by id and rule for a human verdict.
- +6 h: T1-T6 all clear; shadow rows all ok; proved/asked = 100 %; admitted xr+ni count and their verdicts so far;
  prequery_s p95 vs baseline (+50 % or more = investigate, not a trigger).
- +24 h: T1-T7 clear; verdicts on every admitted xr/ni conclusion (count rule: 0 W, else roll back); reader-visible
  effect: xr Not Current/Valid items appear with their wording; write the result with flags sha, pin sha, counts.

## 7. Evidence for this plan
`/srv/hive-evidence/t-2026-11-24-wmtm-s1-shadow-bundle/` (score.json, reader.json, reader_ub.json, basecheck.out,
SHA256SUMS, recompute.sh). Report: `reports/t-2026-11-24-wmtm-s1-shadow-bundle/REPORT.md`.
