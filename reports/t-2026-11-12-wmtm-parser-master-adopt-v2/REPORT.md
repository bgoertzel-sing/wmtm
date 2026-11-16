# t-2026-11-12-wmtm-parser-master-adopt-v2

## Summary
The task was to adopt the Man Hin parser master recipe (sph 24e37182) in the WMTM shadow loader, re-parse the 20 f3-ab notes sentence by sentence, and compare the results with the old loader (M17 r1-r3) and with live F3 v3. The loader is done and tested: 280 seeded master rules, per-sentence lowering with a shared name table, predicates loaded before statements, and shared defs loaded once. All 20 notes now parse in sentence mode (124 sentences, at most 30 calls per hour, 0 rate-limit errors). Arm B proves all 105 of its goals, the canary passes and the negative control does not fire. I checked the 23 goals the restatement tagger left untagged by hand: 22 are correct and 1 is wrong (b68, a parser artifact).

My recommendation is not to adopt the loader as it stands. Its goals are almost all restatements: 77 symmetry restatements and 5 coref links, and only 5 of the 105 join two notes. It also produces none of the adjective-class conclusions the old loader found (0 of 12). The cause is known. The parser emits a per-sentence `Implication (Member X c__member_adj) (Member X adj)` rule. Those rules load, but they are not seeded master rules, so they never become goals. A sensitivity run that also builds goals from them (sens_s1r) proves 117/117 and recovers 8 of the 12 old goals. It also brings back both F3 v3 WRONG "effective" rows. Two decisions are needed: (1) should per-sentence adjective implications be seeded rules (recipe change in sph, or loader-side)? (2) the trivial filter needs a symmetry/coref restatement check before any adoption (F1).

## Commits (branch hive/t-2026-11-12-wmtm-parser-master-adopt-v2, unpushed)
- 47bbcd0 pins sph 24e37182 prompt sha (opt-in) and adds master_meta to the shadow record
- 15fabb0 adds the recipe loader wmtm/master_loader.py with 3 synthetic tests (shared class once, name table, preds before load)
- f6439a9 adds pc_shadow load_order=master_ops; the legacy path is unchanged
- 7122df3 integration test (canary/neg gate, 0 add/pred fail); test_pc_shadow 25 passed
- 46ad9f2 tools/recompute.py (counts only); RECOMPUTE_OK on /srv evidence

## Evidence
/srv/hive-evidence/t-2026-11-12-wmtm-parser-master-adopt-v2 (SHA256SUMS at the root). Recompute: `python3 tools/recompute.py <EV>` prints RECOMPUTE_OK.

## Results
| run | notes | goals | proved | canary | neg | multi-note |
|---|---|---|---|---|---|---|
| whole-note A legacy (full) | 19 | 13 | 13 | ok | not proved | - |
| whole-note B master (full) | 19 | 13 | 13 | ok | not proved | - |
| sentence arm B pilot (5 notes) | 5 | 39 | 39 | ok | not proved | 0 |
| sentence arm B full_s1r | 20 | 105 | 105 | ok | not proved | 5 |
| sentence sens_s1r (+per-sentence adj impls) | 20 | 117 | 117 | ok | not proved | 9 |

Whole-note A/B: ep-note-20261104T151833Z failed 3/3 with an upstream internal error and was excluded. Both arms produced 0 diffs. That comparison measures load order only.

Rules that fired in full_s1r: coref_sym 48, so_sym 29, coref_patient 5, coref_member 5, same_coref 3, coref_agent 3, coref_possession 3, coref_theme 2, coref_bearer 2, month_class 2, subset_is_part 1, partof_trans 1, becauseof_cause 1. sens_s1r adds 12 per-sentence `sN_xM_implication` goals.

## Findings
- F1 trivial-filter gap. pc_admit.trivial_reason knows only nwdef_head_noun and narrow_echo, so shipped_trivial=0. It catches none of the 82 restatements (77 symmetry, 5 coref link).
- F2 adjective implications are not seeded. There are 14 per-sentence adjective Implication atoms (STV .9 .7). All load and all premises are stated, but mkspec instantiates only seeded rules, so there are 0 adjective goals. sens_s1r (tools/mkspec_sens.py) confirms this.
- F3 b68 is wrong. The class task__mod_readme_flags is a parser artifact: the modifier was folded into the class name. The other 22 untagged goals are correct (armB/verdicts/verdicts23.tsv).

## Comparison
(a) Old loader M17 r1-r3: 9/11/8 goals, 12 distinct, all Member-adjective. full_s1r has 0/12. sens_s1r has 8/12.
(b) F3 v3: none of the 4 A_v3 rows (2C/2W) appears in either B arm, because the new parse does not produce those entities or classes. Of the 11 B_v3 rows, full_s1r has 0 and sens_s1r has 7: staged C, verbatim C, working C, acl_d C, local C, effective(185132Z) W, effective(185959Z) W, whole U. In other words, adopting F2 brings back both F3 v3 wrong rows.

## Missing conclusions (old or F3 v3, absent from sens_s1r)
Covered M17 goals in sens_s1r (8/12): local, acl_d, staged, effective(185132Z), closed(sk_note_2), verbatim, top, working.

- (Member sk_bundle_1__ep_note_20261028T190214Z acld): spelling variant; the new parse writes acl_d, which is present.
- (Member sk_commit_2__ep_note_20261028T185132Z single): F3 v3 C, M17. The new parse words the sentence differently and emits no adjective implication.
- (Member sk_diff_1__ep_note_20261028T122745Z inline): M17. Same cause, different parse.
- (Member sk_diff_1__ep_note_20261104T051320Z tested): M17. Same cause, different parse.
- (Member sk_check_py_1__ep_note_20261028T185959Z stdlib_only): F3 v3 C. This note was not in the M17 set; the new parse has no such implication.
- (Member sk_note_1__ep_note_20261028T153222Z closed): F3 v3 C. The M17 form (Member sk_note_2__ep_note_20261028T153222Z closed) IS in sens_s1r; only the F3 v3 skolem number (sk_note_1) is missing.
- All 4 A_v3 goals (chat_send valid, goalchainer_v2_status branch, hive_progress_report report, turn_without_send_entry entry): the live-loader entities are not in the sentence parse.

## Open
- Decisions (1) and (2) from the Summary.
- Cleanup after review: /tmp/mav2 and switching the worktree back. Only when a human OKs it.
