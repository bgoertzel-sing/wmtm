## Summary
andy asked two things. First, whether B (this branch) holds up on the real turn loop with GoalChainer v2 on, compared with A (live). Second (v3), why B built 0 goals on Man Hin's parser 533c2274. Answer: B builds goals only when the parse puts Narrow inside Member. Neither current parse does that: 533c2274, and a fresh parse at the F3 v3 pin f44d7b74, both give 0 goals. So B fails the count rule (0 correct against A's 2). On the Nov 5 parse, which still has Narrow inside Member, B gets 6 correct and 0 wrong (2 not judged) and passes the rule. The cause is drift in the parser's output, not B's code and not the live path. On the turn loop itself, B matches A: evictions are identical (same 7 ids at the same ticks), GoalChainer v2 was ok and its canary passed on every run, and there were 0 escalations on either arm. B adds recent-focus lines and tagged derived lines, as designed.

Propose deploy: no. On today's parser output B produces no goals, so it fails the count rule. Two fixes on our side would let B use the new parse shape, and neither is applied here: name Narrow when it appears outside Member, and bridge PartOf-group rule antecedents to GroupOf facts. The other option is for Man Hin's parser to emit Narrow inside Member again. That choice is andy's to make.

Supersedes: t-2026-11-09-wmtm-live-path-replay-v2

# t-2026-11-09-wmtm-live-path-replay-v3

Pins: PINS.md. Run notes: runs_offline/ and runs_loop/. Tools: tools/. Raw parse caches are kept off the repo because they contain Name string literals; their sha256 sums are in CACHE_SHA256.txt.

## Live-path turn loop (sandbox, 20 notes x (user turn + automated tick), GoalChainer v2 pymetta-native.2 on)
Every arm ran the same harness (tools/turn_loop.py and tools/run_arms.sh) on the same 20 note ids, with PeTTa 3681b9b and PeTTaChainer b6aacc68 (worktree f873824). Each arm had its own state dir. The harness opens no ports and refuses the live state dir.
{{LOOP_TABLE}}

1. Goal escalations: A {{full_A.escalations}}, B533 {{full_B533.escalations}}, Bp3 {{full_Bp3.escalations}}, Bf44 {{fullf44_Bf44.escalations}}. Choices shown: {{full_A.choices}} / {{full_B533.choices}} / {{full_Bp3.choices}} / {{fullf44_Bf44.choices}}. No tie occurred, so there was no case to show as a choice. The series continued on every run: GoalChainer ok on {{full_A.gc_ok}}/{{full_B533.gc_ok}}/{{full_Bp3.gc_ok}}/{{fullf44_Bf44.gc_ok}} runs, canary ok on {{full_A.gc_canary_ok}}/{{full_B533.gc_canary_ok}}/{{full_Bp3.gc_canary_ok}}/{{fullf44_Bf44.gc_canary_ok}}.
2. Evictions and forgets: A {{full_A.evictions_total}}, B533 {{full_B533.evictions_total}}, Bp3 {{full_Bp3.evictions_total}}, Bf44 {{fullf44_Bf44.evictions_total}}. All of them happened on user turns (forget_phase, STI below 0.05) and none on automated ticks. A and B533 evicted the same 7 recalled ids at the same ticks (10,10,11,11,13,18,18). Evictions did not rise. The per-arm id lists are in runs_loop/*/evictions.json.
3. Recent-focus slots: headers / lines are A {{full_A.focus_headers}}/{{full_A.focus_lines}}, B533 {{full_B533.focus_headers}}/{{full_B533.focus_lines}}, Bp3 {{full_Bp3.focus_headers}}/{{full_Bp3.focus_lines}}, Bf44 {{fullf44_Bf44.focus_headers}}/{{fullf44_Bf44.focus_lines}}. A is 0 by design: vendor rc2 has no recent_focus code.
4. Derived context lines, with a truth value and with sources: A {{full_A.derived_lines}} lines, rc2 has no tags. B533 {{full_B533.derived_lines}} lines. Bp3 {{full_Bp3.derived_lines}} lines, {{full_Bp3.derived_with_tv}} with tv= and {{full_Bp3.derived_with_src}} with from= (example tag: `[derived tv=0.90,0.70 from=ep-note-20261104T151833Z]`). Bf44 {{fullf44_Bf44.derived_lines}} lines. Every derived line B rendered carries both its truth value and its sources.
5. Count rule, §11, warm-up and budget. Offline pc_shadow, k=20, judged by tools/judge.py with the F3 v3 W1-W4 rules (including the DEVIATION_1 nwdef join and the F3 v3 W4 table). No new hand verdicts, per the order.
   - A: 141 atoms, 4 goals, 2C/2W. This reproduces F3 v3 A exactly (same 141 premises and 348 gate rejects).
   - B533: 190 facts, 0 goals, 0C/0W. **FAIL**.
   - Bf44: 205 facts, 0 goals, 0C/0W. **FAIL**.
   - Bp3: 252 facts, 9 goals, 9 proved, 6C/0W/1U plus 2 not judged: (Member sk_config_1__i_ep_note_20261028T185132Z effective) and (Member sk_coverage_1__i_ep_note_20261104T151833Z shown). The rule holds even if both are counted as wrong (6C/2W against 2C/2W).
   - B answers that differ from the 13c6c9c5 runs (F3 v3 B, 11 goals): Bp3 shares 8. It lacks sk_bundle_1 acl_d (190214Z), sk_note_1 closed (153222Z) and sk_config_1 effective (185959Z). It adds sk_coverage_1 shown (151833Z). B533 and Bf44 drop all 11.
   - Warm-up (warm_s): A 0.59 s, B533 23.45 s, Bp3 23.60 s, Bf44 2.74 s. All are under the 120 s gate.
   - Parse budget: B533 23 calls (20 ok, 3 transient api internal errors: bfa7db2c once, 43115a46 twice, ok on a 3rd sandbox-only attempt; see DEVIATIONS), Bf44 20 calls (20 ok). 0 rate-limit (429) errors on either; every fill stayed inside the 20/h cap.
6. Can an asserted fact become a goal? Not in any run that kept its spec: 0 of 4 (A), 0 of 0 (B533), 0 of 49 (Bf3 probe), 0 of 9 (Bp3), 0 of 0 (Bf44). The safeguard is goal_pool/rule_goal_pool's `t in have`. Re-entered conclusions join `rel` as wm<j> facts (pc_shadow.py:452-462), so they are excluded too. GoalChainer v2 proposes actions, not KB goals. Caveat: the loop worker deletes its specs, so this check could not be repeated on the loop's knowledge bases.
8. Propose deploy: no, for the reasons given in the Summary.

## Item 9: why rule_goal_pool is 0 on parser 533c2274 (ids and shapes only)
- Flat rules accepted by _parse_rules (pc_shadow.py:286-303): B533 4 of 55 Implications, Bf44 (fresh f44d7b74) 3 of 41, B2 (1f1a7a6f, Nov 5) 2 of 72 raw. The overall rule-shape mix is similar across the three parses.
- The 4 flat B533 rules (i_ep_note_20261028T183317Z__d1_implication, i_ep_note_20261104T051925Z__dd1_implication, i_ep_note_20261104T193740Z__d1_implication, __d2_implication) all have the antecedent (PartOf $x sk_group_N__i_<note>). The parse declares groups with (GroupOf sk_group_N C), and no PartOf fact has a group as its object, so all 4 match 0 facts.
- The real difference is Member+Narrow: B2 98, B533 2, Bf44 0. F3 v3 B's goal-producing rules were x*_implication of the form (Member sk C__nw_h) -> (Member sk adj), plus 75 nwdef rules, and both come from Narrow inside Member (_name_narrow, pc_shadow.py ~84). The newer parses put Narrow inside GroupOf, As, To or Directive, which _name_narrow does not name.
- Cause: the parser's output content changed. This is seen even at the fixed pin f44d7b74, so it is drift, not only the pin change. Gaps on our side (not fixed here): (a) _name_narrow names Narrow only as a Member class; (b) PartOf-group antecedents vs GroupOf declarations are never bridged.
## Item 10: B on f44d7b74 through the same path
- The F3 v3 raw f44d7b74 cache (/tmp/f3) was deleted after v3 closed. A fresh f44d7b74 re-parse (Bf44, 20/20 ok, 0x429) gives 0 Member+Narrow, 205 facts, goals_n 0 and 0 proved, so B does not get its 11 goals back.
- Stand-in: the Nov 5 B2 parse (1f1a7a6f) gives 9 goals, all 9 proved, 8 of F3 v3 B's 11 goals.


## Item 10: B on f44d7b74
See the Item 9/10 section above. A fresh f44d7b74 parse gives 0 goals and 0 proved, so B does not get its 11 goals back. The raw cache F3 v3 actually used was deleted, so Bp3 (1f1a7a6f, Nov 5, with Narrow inside Member) is the closest replayable stand-in: 9 goals, 9 proved through the same path. This separates the parser output from the live path.

## Deviations
- v2 DEVIATIONS 1-6 carry over (reports/t-2026-11-09-wmtm-live-path-replay-v2/DEVIATIONS.md).
- The offline v2 A/B used different engine pins for A and B. The goal pool is built in Python before the engine runs, so goals_n is unaffected. The turn loop used one pin set.
- The harness writes each note into the sandbox journal under its real note id and mirrors mark_recalled, as the live recall path does. Without this, relevance_stimulus evicted every note on the turn it was admitted (logged in NOTES.txt).
- The F3 v3 parse could not be replayed (its cache was deleted), so Bp3 stands in for it.
