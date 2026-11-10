# t-2026-11-10-wmtm-narrow-preload

## Summary
The order asked for parse_normalise's M2 Narrow rewrite to run in SemParseAdapter just before the PeTTa load, so that narrowed-class statements stop being dropped at load, and for B to be measured on four frozen parses. The change is done as a marked stopgap (`narrow_preload` plus `_admit` in wmtm/semparse_adapter.py). A Member+Narrow statement now loads as its deterministic symbol plus one head-noun nwdef rule. GroupOf is left as written (F1), and the modifier is never made a property (F2). Tests cover all of this with negative controls, and the full suite passes (852 passed, 39 skipped). 0 parse calls.

On the three parse-variance runs (r1/r2/r3), 76/88/75 of the 99/109/101 refused statements are recovered. B goes from 0 goals to 12/14/10 goals, all proved. Under the A/B count rule B gets 6C/0W, 6C/2W and 5C/0W against A's 2C/2W, so the rule holds on all three. **However, every correct conclusion is trivial (0 non-trivial).** Each B goal just repeats the restriction inside the parser's own `(Narrow base (Member R))` together with the parser's matching implication: "a staged commit is staged". The f44d7b74 parse has no Member+Narrow statements, and its rejects log is gone (/tmp/nrm was deleted). It stays at 0 goals, so the count rule fails there (0C < 2C). Open for a human: the stopgap gives B goals but no new knowledge. The real gain still depends on Man Hin's lowering target and on parses that produce non-echo rules.

## Pins and base
- wmtm base 27c1a41 (main), started from the normaliser-v2 branch bae8385 (contains 27c1a41). Branch hive/t-2026-11-10-wmtm-narrow-preload (not pushed).
- PeTTaChainer b6aacc68 (~/scratch/ppv/pc), PeTTa 3681b9b (p1-engine/petta-3681b9b), Man Hin parser 533c2274 (r1/r2/r3, prompt 1585e873), f44d7b74 (prompt 645bff3f).
- Notes: the same 20 ids, raw_spec sha256 0a339405.

## Code
- `narrow_preload(node)`: a STOPGAP comment points to Man Hin's tmpl/lower.py target. It applies `name_narrow_anywhere` only when the named form is a shape `classify()` maps; otherwise the statement is returned unchanged. It returns the nwdef rule(s) for the symbols it used, and for a nested Narrow it includes the chain.
- `SemParseAdapter._admit`: the single load step (narrow_preload, then the context check, then the PeTTa load, then the nwdef rules, each loaded once per adapter). `_accept_forms` calls it.
- `SemParseAdapter.recover_rejected`: sends logged petta-stage atoms (already named and scoped) through `_admit`. This is the same step the live path uses, not a bypass.
- Tests (tests/test_semparse_adapter.py, 9 new): Member+Narrow loads (with a loader that refuses Narrow the way PeTTaChainer does); negative control: the same input without the rewrite is refused at petta; plain Member untouched; nwdef once per symbol; nested chain; F1 GroupOf left as written, with a control; F2 the modifier token appears in no loaded atom, with a control; recover uses `_admit`; Inheritance+Narrow is mapped; GroupOf+Narrow recovery negative control.

## Per parse
Statement counts (r1/r2/r3 from rejects.jsonl stage=petta in each ppv cache; real PeTTaChainer loader, canary ok):

| parse | petta rejects in | statements recovered | nwdef loaded | still refused |
|---|---|---|---|---|
| r1 (533c2274) | 99 (98 member_class, 1 inheritance_class) | 76 | 64 | 23 |
| r2 (533c2274) | 109 (108 member_class, 1 inheritance_class) | 88 | 72 | 21 |
| r3 (533c2274) | 101 (100 member_class, 1 inheritance_class) | 75 | 65 | 26 |
| f44d7b74 (freeze fill b96748ca) | rejects log missing; cache has 0 Member+Narrow (13 Narrow: 12 GroupOf, 1 Not) | 0 | 0 | n/a |

Still refused, and why: in every case a Narrow sits inside a head that is not a mapped Member/Inheritance shape (Implication with a non-flat body, GroupOf, Directive, Theme, Holds, Not, For). M2 maps none of these, so they stay as the parser wrote them (no F1 bridge, no F2 property). PeTTaChainer still refuses the Member class under them (member_class). Counts by outer head and restriction type are in evidence/SUMMARY.json under recovery.*.still_refused_by_shape.

B on a sandbox frozen store (WMTM_EVAL_FROZEN_STORE, guard on, PC canary ok, 0 timeouts, 0 add_fail). Judged with F3 v3 W1-W4, DEVIATION_1 nwdef join and the v2 W1 rule (W4 table W4_f3v3.json; goals not in the table = unjudged):

| parse | goals/proved before | goals/proved after | C/W/U/unjudged after | A (2C/2W) count rule | correct: trivial / non-trivial |
|---|---|---|---|---|---|
| r1 | 0/0 | 12/12 | 6/0/1/5 | HOLDS | 6 / 0 |
| r2 | 0/0 | 14/14 | 6/2 (both W1: sk_config effective in 185132Z and 185959Z)/1/5 | HOLDS (2 ≤ 2) | 6 / 0 |
| r3 | 0/0 | 10/10 | 5/0/1/4 | HOLDS | 5 / 0 |
| f44d7b74 | 0/0 | 0/0 (nothing to recover) | 0/0/0/0 | FAILS (0 < 2) | 0 / 0 |

Trivial split: for all 36 B goals (12+14+10), the top rule is a recovered parser implication `(Member x base__nw_h) -> (Member x R)`, where R is the restriction in that statement's original `(Narrow base (Member R))`. The goal is R itself, an "an X_Y is a Y" echo, so it is trivial (evidence goals.*.trivial_echo). No correct conclusion is non-trivial.

Proof shape note (for review): every proof is a factored revision of the asserted narrowed fact with an `inverted nwdef` branch whose prior is (STV 0.5 0.0), i.e. confidence 0. The conclusion rests on the asserted fact, not on reading nwdef both ways (F7 answer still NO).

## Mesto §11 (per-conclusion diff, every A conclusion B drops, with reason)
| A conclusion | A verdict | in B (r1/r2/r3) | reason |
|---|---|---|---|
| (Inheritance chat_send valid) | WRONG | no | subject and class are not in the B KB (533c2274 parse does not produce these symbols) |
| (Inheritance hive_progress_report report) | CORRECT | no | subject not in the B KB (class `report` is) |
| (Member hive_t_2026_10_28_goalchainer_v2_status branch) | WRONG | no | asserted fact in B; asserted triples are never goals |
| (Member turn_without_send_entry entry) | CORRECT | no | subject and class are not in the B KB |
B adds 12/14/10 new goals, listed per goal in evidence/SUMMARY.json goals.*. This holds for every parse; f44 drops all 4 for the same reasons.

## Parse calls: 0
- recover.py's LLM is a stub that raises; it was never called (the "parse call refused" count in /tmp/npl/rec_r*.err is 0). mkstore.py and run_b.sh read only existing caches; the frozen-store env turns the no-reparse guard on.
- No parse_log or calls file was written by this task. Other parse activity in the window since 12:27, which is not mine: the live wmtm spk1 feed logged 9 ok, and wmtm-parse-caching-ev logged 3 at about 12:36. That is 12 in total, under the cap of 20 per hour, and there were 0 rate-limit errors.

## Deviations
1. f44d7b74: its rejects log (/tmp/nrm/parse_f44d7b74) was deleted with /tmp/nrm; I searched scratch, /var/tmp, the frozen store and the supervisor log and found no copy. I did not re-parse it. Its cache has 0 Member+Narrow, so the pre-load rewrite would change nothing in what was kept; the dropped atoms cannot be recovered.
2. The order counted r1/r2/r3 rejects as 99/109/101, with 98/108/100 member_class. The one other reject in each run, an Inheritance over a Narrow, is a mapped M2 shape, so it is recovered as well.

## Evidence (note-free: ids, parser symbols, counts, hashes)
- evidence/SUMMARY.json (recovery, runs, goals, inputs, judge), extract_ids_only.json, W4_f3v3.json, runs/*/shadow.jsonl (the A records are copied from the f3-ab-v3 report).
- Input sha256: ppv r1 cache a839f2972a888b3b / rejects d6b8bec8dd73b080; r2 8e14bb9dfff121a9 / 9e0cdfa8f47b8fef; r3 3a148d3c3e1df3d7 / 6d9ba77b598133ec; f44 cache b96748ca2aad51bb.
- Recompute off pop-os: `python3 reports/t-2026-11-10-wmtm-narrow-preload/tools/recompute.py` prints RECOMPUTE_OK (it checks shadow shas and re-judges every run).
- Tools: recover.py, mkstore.py, run_b.sh, make_evidence.py, recompute.py.

## Tests
852 passed, 39 skipped (tests/ plus normaliser-v2 tools).
