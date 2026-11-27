# t-2026-11-26-wmtm-rebase-r02: R-02 chaining (PR 55) rebased onto main 915bc8c

Supersedes: t-2026-11-24-wmtm-r02-chaining

## Summary

andy asked for the reviewed R-02 work (multi-step chaining in goal generation, flags off by default) to be brought onto current wmtm main so it can merge. Main is 915bc8c (PR 53, P-01 class links). I made a fresh branch from it and cherry-picked (-x) only R-02's own commit, 9dd612f. The pick applied with **no conflicts**. The R-02 branch's copies of the P-01 and S1-bundle files (45fa6a8, 6dddd8e, 7fa69af) were left out, so every P-01/S1 file is main's version. The diff against main is R-02's change only: 12 files, lines added, **0 lines removed**. Its patch-id matches the original 9dd612f exactly (3b9e930ff296).

pytest passes: 1638 passed, 70 skipped, 5 xfailed. That is main's 1631 plus R-02's 7 tests, and all 7 pass. With the flags off, the rebased tree's output is byte-identical to main 915bc8c on all 5 frozen runs × 2 arms (10/10 spec.json). A flag-on canary (k=2) changes the output on 5/5 runs, so the check is not vacuous.

One thing for the merger to know. Main has the `class_links` flag and module, but **not** the S1-bundle loader hook (6dddd8e), because that commit was never merged. On main, `class_links=on` gives the same output as off, and main's outputs differ from the archived S1 "all" specs. That comes from main itself, not from this rebase. It also means R-02's report numbers for its `*cl` arms were measured on the S1 base and would not reproduce on main until the S1 wiring lands. No behaviour change, no live change, nothing pushed.

## Refs

- Base: wmtm main 915bc8caeb32186a093e3227f3c1ec2db38c8210 (= origin/main at start, Merge PR #53)
- Branch: hive/t-2026-11-26-wmtm-rebase-r02 (worktree projects/omegaclaw/rebase-r02/wmtm-wt)
- Code commit: 6583b88037aa0afd014f844457802d6bb6eb0791 = cherry-pick -x of 9dd612ff2ed36e2472f54b306513c0a3eb3888a6
- Original R-02 base: fd48815 + S1 branch 45fa6a8, 6dddd8e, 7fa69af (not brought over)
- Evidence: /srv/hive-evidence/t-2026-11-26-wmtm-rebase-r02/ (SHA256SUMS, 86 files)

## What was brought over and what was dropped

| Commit on R-02 branch | What | Action |
|---|---|---|
| 45fa6a8 | P-01 class_links pass (now in main via PR 53) | dropped, main's version kept |
| 6dddd8e | S1 shadow-bundle: class_links loader wiring, SWITCH_PLAN_S1, bundle report | dropped (S1-bundle, not R-02's) |
| 7fa69af | S1 evidence sums | dropped |
| 9dd612f | R-02: chaining, flags, tests, report | cherry-picked -x |

## Conflicted files and how each was resolved

The cherry-pick of 9dd612f had **no conflicts**. The clash in PR 55 came from the three S1/P-01 commits under it, not from R-02's own diff. Per file:

| File | R-02 change | Resolution |
|---|---|---|
| wmtm/class_links.py, tools/class_links_apply.py, tests/test_class_links.py | none (copies from 45fa6a8) | main's version; identical to main |
| docs/SWITCH_PLAN_S1.md, reports/t-2026-11-24-wmtm-s1-shadow-bundle/* | none (6dddd8e/7fa69af) | not in main, not added |
| reports/t-2026-11-24-wmtm-p01-class-links/* | none | main's version; identical |
| README.md | +4 flag rows | main's file + R-02's 4 rows (applied cleanly) |
| wmtm/runtime_config.py | +4 SPEC entries | main's file + R-02's 4 entries (clean) |
| wmtm/master_loader.py | +158 (chain_goals) | main's code + R-02's addition (clean); main's lack of the S1 class_links hook is kept, not reintroduced |
| wmtm/pc_shadow.py | +17 (chain wiring) | main's code + R-02's addition (clean) |
| tests/test_chain_goals.py | new, 87 lines | added |
| reports/t-2026-11-24-wmtm-r02-chaining/* | R-02's report + evidence sums | added unchanged |

Did anything else change, beyond the copied P-01/S1 files and the shared-file merges? **No.** `git diff --numstat 915bc8c HEAD` lists only these 12 files, with 0 deletions. The patch-id of HEAD equals the patch-id of 9dd612f (3b9e930ff296). The same holds for the code-only diff over wmtm/ tests/ README.md (90baad3544ac on both). The P-01/S1 files checked with `git diff --quiet 915bc8c HEAD` all equal main.

## Tests

- Full suite on the rebased tree: 1638 passed, 70 skipped, 5 xfailed, rc=0 (suite.out)
- Full suite on main 915bc8c: 1631 passed, 70 skipped, 5 xfailed (main_suite.out)
- R-02's tests (tests/test_chain_goals.py): 7 passed (r02_tests.out)

## Flags off = main

This is R-02's original off-spec check (tools/build_spec_r02.py, build_all.sh, note_ids.txt copied from the R-02 evidence), run on the same 5 frozen parse runs (A0, A1, r1, r2, r3). Arms: s1 (class_links off, chain off) and s1cl (class_links on, chain off). Builds are offline with 0 parser calls, run on pop-os at nice 19. Main was built in a detached worktree at 915bc8c.

- rebased vs main: 10/10 spec.json byte-identical (basecheck.out); goals/master_ops counts equal (build_counts.out)
- canary, k2 on the rebased tree: differs from s1 on 5/5 runs, so the chaining path is live and the check is not vacuous (canary.out)
- Caveat, from main and not from the rebase: on main, s1cl == s1 on 5/5 runs, and main's s1cl differs from the archived S1 "all" specs. Cause: 6dddd8e's loader hook (`class_links` in master_loader.plan) is not in main.

## Open / for the merger

- R-02's `*cl` arm measurements (in its report) assumed the S1 class_links loader hook. On main that flag has no loader effect until the S1 wiring is merged. Flags-off behaviour is unaffected.
- No note text in the repo: leak-grep of the added lines found 0 matches.
