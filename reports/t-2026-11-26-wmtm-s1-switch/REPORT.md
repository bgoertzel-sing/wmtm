## Summary
The s1 switch to fd48815 was not adopted. It was rolled back on the T3 rule (add_fail rate). Step 1 ran live on fd48815 from 17:36:25Z to 02:11:48Z. Step 2, the 4 flags, never ran. The bot is back on d506783 (pin 7acf09f1), and the flags are unchanged (f9e59f74).

In my judgement this is the same add_fail cause on both versions. fd48815 did not raise the rate. Rows with add_fail>0 were less common on fd48815 (5 of 62, 8%) than on d506783 (5 of 17, 29%), and the maximum was 2 on both. The rollback fired because T3 is an absolute count over a 24h window, and fd48815 simply ran for many more rows. The fix belongs in s5-ops: a PrologError on ':' atoms when all notes load together. Proposed shadow_budget_s: 30 (it is 20 now). The R3 deviation lost no state and left nothing half-written. The switch is retried as a new task after s5-ops fixes the cause.

## add_fail before / after
Data is from pc_shadow/shadow.jsonl. Load-stall exception c20473 is excluded.

| window | rows | add_fail>0 | rate | max add_fail | timeouts | pred_fail | build_error | canary fail |
|---|---|---|---|---|---|---|---|---|
| d506783, 24h before 17:36:25Z, excluding c20260* | 17 | 5 | 29% | 2 | 0 | 0 | 0 | 0 |
| fd48815, 17:36:25Z to 02:11:48Z (~8.6 h) | 62 | 5 (20287, 20294, 20305, 20779, 20792) | 8% | 2 | 0 | 0 | 0 | 0 |
| ambiguous: c20802 (start 02:12:28Z, after the pin restore at 02:11:48Z, before admit.json moved at 02:13:28Z) | 1 | 1 | - | 1 | 0 | 0 | 0 | ok |
| d506783 after rollback: c20813 (02:17Z) | 1 | 1 | - | 1 | 0 | 0 | 0 | ok |

*c20260 (17:19Z, add_fail 1) ran on the first short fd48815 switch (17:11:53 to 17:20:33Z). If it is counted, the "before" window is 6 of 18.
The c20473 exception (19:27Z, timeouts 1, prequery 82.96 s, warm 59.2 s) was a load stall. See trigger1_timeouts_1927Z.txt; it was accepted under ANSWER-3.

## Judgement: same cause, not a higher rate
- add_fail shows up the same way on both versions: 1 to 2 per row, with no pred_fail, build_error, timeouts or canary failures alongside it.
- add_fail>0 appears on d506783 both before the switch (c20251 17:05, c20257 17:10, c20263 17:24, c20272 17:30, c20279 17:35, all on d506783) and after the rollback (c20813, 02:17Z). So d506783 produces it on its own. Note: the earlier baseline note said 3 of 15; c20263/c20272/c20279 were added after that note was taken.
- The rate per row is lower on fd48815: 8% versus about 29%. d506783 itself had 5 add_fail>0 rows in the 30 min from 17:05 to 17:35Z, which is already over T3's limit of 3.
- Cause, per cos: a PrologError on ':' atoms when all notes load together. This goes to s5-ops.

## R3 deviation (admit.json moved while shadow procs 807911/2/5 were still running)
- The first rollback script hit the 30 s shell timeout during its process-wait loop, so I moved admit.json at 02:13:28Z in a second step.
- The moved file (backups/wmtm-s1-switch-20261126T1709Z/admit.json.s1redo-20261127T021148Z) is valid JSON.
- The next cycle regenerated admit.json at 02:18:08Z, and it is valid JSON.
- admit_log.jsonl has 167 lines, all of which parse. The last entry is status ok, admitted 0, skipped already_consumed, so nothing was admitted twice.
- shadow.jsonl parses with no bad lines, and c20802 and c20813 were both written in full.
- Result: no state was lost and nothing was half-written. The only effect is that I can't say which version c20802 belongs to (listed separately above).
- Lesson: keep a rollback script under 30 s, or run it with nohup and a log. Don't put a sleep-poll loop inside it.

## shadow_budget_s proposal
prequery_s (excluding c20473):
- d506783, 24h: n 18, median 13.30, p95 21.61, max 22.97
- fd48815: n 62, median 13.09, p95 21.61, max 24.28
- after rollback: 11.93, 12.59

The current shadow_budget_s is 20.0, which is below the p95 of both versions, so about 1 in 10 rows runs past it. Proposal: **30 s**. That is about 25% headroom over the highest value seen (24.28). Load stalls like c20473 (83 s) should stay with the timeouts trigger rather than being covered by the budget. The two versions are the same at the median and p95, so the switch does not need a separate budget.

## Evidence
- redo1/watch.log, redo1/monitor.py, redo1/rollback2.txt
- backups/wmtm-s1-switch-20261126T1709Z/ (_wmtm_pin.py, which is the d506783 pin; _wmtm_pin.py.fd48815-20261127T021148Z; admit.json.s1redo-*)
- R4: _wmtm_pin.load() returns 0.7.0rc2@d5067832, and _wmtm_pkg.json agrees.

Side note: I stopped the Clerk pilot smoke for the three-parser task during the watch. Per ANSWER-4 it restarts after this result is posted.
