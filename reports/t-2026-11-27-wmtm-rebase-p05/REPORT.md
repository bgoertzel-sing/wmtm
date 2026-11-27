# t-2026-11-27-wmtm-rebase-p05: P-05 question goals (PR 56) rebased onto main 5db1ffd (with R-02)

Supersedes: t-2026-11-24-wmtm-p05-questions-goals

## Summary

andy asked for the reviewed P-05 work (questions in notes as reasoner goals, plus the R-10 admission confidence floor, both flags off by default) to be brought onto current wmtm main so it can merge. Main is 5db1ffd (Merge PR 58), which already contains P-01 (PR 53) and the R-02 rebase (7c1e971). I made a fresh branch from it and cherry-picked (-x) only P-05's own commit, 1c42c1b. The P-05 branch's copies of the P-01 and S1-bundle files (45fa6a8, 6dddd8e, 7fa69af) were left out, so every P-01, S1 and R-02 file is main's version. The pick conflicted in three shared files (README.md, wmtm/master_loader.py, wmtm/pc_shadow.py). Each was resolved by keeping main's code and adding P-05's lines. The only thing not carried over is the S1 `class_links` loader hook, which was never on main and is not P-05's.

pytest passes: 1669 passed, 45 skipped, 5 xfailed. That is main's 1663 plus P-05's 6 tests, and all 6 pass; R-02's and P-01's tests (19) pass too. With P-05's flags off, the rebased tree's spec output is byte-identical to main 5db1ffd on all 5 frozen runs (A0, A1, r1, r2, r3), and also byte-identical to the archived P-05 s1 specs. With R-02's chaining on (k=2) and P-05 off, the output equals main except for one wall-clock timing field. A flag-on canary shows the P-05 path is live. No behaviour change, no live change, nothing pushed.

## Refs

- Base: wmtm main 5db1ffd663ba167823ceae5599297d1ff8f902a9 (origin/main at start, Merge PR #58 = R-02 rebase 7c1e971 on P-01 915bc8c). R-02 is on main: 6583b88 and 7c1e971 are ancestors of 5db1ffd.
- Branch: hive/t-2026-11-27-wmtm-rebase-p05 (worktree projects/omegaclaw/rebase-p05/wmtm-wt)
- Code commit: 1ab2661a65e481b78ff82a906cda3656529b115f = cherry-pick -x of 1c42c1b14daf69f52ee26627acbe3c56cd38f847
- Original P-05 base: fd48815 + 45fa6a8, 6dddd8e, 7fa69af (not brought over)
- Evidence: /srv/hive-evidence/t-2026-11-27-wmtm-rebase-p05/ (SHA256SUMS; copy in EVIDENCE_SHA256SUMS here)

## What was brought over and what was dropped

| Commit on P-05 branch | What | Action |
|---|---|---|
| 45fa6a8 | P-01 class_links pass (on main via PR 53) | dropped, main's version kept |
| 6dddd8e | S1 shadow bundle: class_links loader hook, SWITCH_PLAN_S1, bundle report | dropped (S1, not P-05's) |
| 7fa69af | S1 evidence sums | dropped |
| 1c42c1b | P-05: question goals, R-10 floor, flags, tests, report | cherry-picked -x -> 1ab2661 |

## Conflicted files and how each was resolved

| File | P-05 change | Conflict | Resolution |
|---|---|---|---|
| README.md | +2 flag rows (shadow_question_goals, reasoner_conf_floor) | yes: same spot as R-02's 4 chain rows | main's R-02 rows kept, P-05's 2 rows added after them |
| wmtm/master_loader.py | plan(questions=False) + question block | yes: signature line; the P-05 branch had S1's `class_links=False` param | main's signature (no class_links) + `questions=False`; question block applied cleanly; S1 hook not reintroduced |
| wmtm/pc_shadow.py | pass questions to plan, question goals, spec key | yes: plan call; the P-05 branch passed S1's `class_links=` | main's call + `questions=...` only; goal/spec hunks applied cleanly after main's R-02 chain block (question goals are added after chain and premise goals) |
| wmtm/runtime_config.py | +2 SPEC entries | no | main's file + P-05's 2 entries |
| wmtm/pc_admit.py | R-10 floor | no | applied unchanged |
| tests/test_question_goals.py | new | no | added unchanged |
| reports/t-2026-11-24-wmtm-p05-questions-goals/* | P-05 report + counts-only evidence | no | added unchanged |
| wmtm/class_links.py, tools/class_links_apply.py, tests/test_class_links.py, reports/t-2026-11-24-wmtm-p01-class-links/* | none (P-01 copies) | n/a | main's version; identical to main |
| docs/SWITCH_PLAN_S1.md, reports/t-2026-11-24-wmtm-s1-shadow-bundle/* | none (S1) | n/a | not on main, not added |
| tests/test_chain_goals.py, reports/t-2026-11-24-wmtm-r02-chaining/*, reports/t-2026-11-26-wmtm-rebase-r02/* | none (R-02) | n/a | main's version; identical |

Did anything change beyond the copied P-01/S1 files and the shared-file merges? **No.** `git diff --numstat 5db1ffd 1ab2661` lists 12 files, all from P-05's own commit. The only removed lines are 3 lines of main that P-05 extends in place: the plan() signature line, the plan() call's last argument line, and the master_meta filter line (now also excluding `questions`). For reports/, tests/, wmtm/pc_admit.py and wmtm/runtime_config.py the rebased hunks have the same patch-id as 1c42c1b. The whole-commit patch-id differs (cb5835f9 vs 6188341a) only by the two dropped S1 `class_links` lines in master_loader.py and pc_shadow.py (static.out has the diff of diffs). P-01 and R-02 files: `git diff --quiet 5db1ffd HEAD` is clean for each. This report commit adds only this directory.

## Tests

- Full suite on the rebased tree (sph templates set, as P-05 ran it): 1669 passed, 45 skipped, 5 xfailed, rc=0 (suite.out)
- Full suite on main 5db1ffd, same setting: 1663 passed, 45 skipped, 5 xfailed, rc=0 (main_suite.out)
- Rebased tree without templates: 1642 passed, 72 skipped, 5 xfailed (suite_notemplates.out; the 2 question tests skip, as their marker intends)
- P-05's tests (tests/test_question_goals.py): 6 passed (p05_tests.out)
- R-02's and P-01's tests (tests/test_chain_goals.py, tests/test_class_links.py): 19 passed (r02_p01_tests.out)

## Flags off = main

This is P-05's original off-spec check (tools/build_spec_p05.py and note_ids.txt from the P-05 evidence, extended only by two extra arms in tools/build_spec_rp05.py). It runs on the same 5 frozen parse runs (A0, A1, r1, r2, r3) and builds offline with 0 parser calls (spy count 0; parse files' md5 unchanged, parsed.check). It ran on pop-os at nice 19. Main was built in a detached worktree at 5db1ffd. Arms: s1 (the P-05 baseline: P-05 flags off, chain off), s1cl (class_links on), s1k2 (R-02 shadow_chain_k=2, P-05 off), q (shadow_question_goals on; rebased only).

- s1, rebased vs main: **5/5 byte-identical** spec.json (basecheck.out)
- s1, rebased vs archived P-05 s1 specs (built at 7fa69af): 5/5 byte-identical (basecheck.out)
- s1cl, rebased vs main: 5/5 byte-identical
- s1k2, rebased vs main: identical on 5/5 except `chain.elapsed_s`, the wall-clock time of the chaining step. The same field differs between two builds of main itself (0.215 vs 0.191 on A0). Removing only that field, 5/5 are identical (cmp_k2.out).
- Canary (q on the rebased tree): the spec differs from s1 on 5/5 runs, only by the added `questions` counts key. Goals and master_ops are equal, as in P-05's report (the frozen parses contain 0 parsed questions, 1 unmapped "?" span per run), so the P-05 path runs and the check is not vacuous (canary.out).
- The R-10 floor is admission-side. With it at 0, `pc_admit.load_candidates` is unchanged (test_conf_floor_off_by_default passes; the hunk is patch-identical to 1c42c1b).

## Open / for the merger

- As the R-02 rebase noted, main has no S1 `class_links` loader hook. P-05's report numbers were measured on the S1 base (7fa69af). Its flags-off s1 specs are still byte-identical on main, so the baseline holds.
- No note text in the repo: this report holds ids, hashes and counts only. The synthetic test strings in tests/test_question_goals.py come unchanged from the reviewed P-05 commit.

