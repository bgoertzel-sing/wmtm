# Releases and history rewrite

The history of `main` was rewritten so that it contains no real bot
memories (WMTM state, journal notes, conversation-derived reports or ids).
The `wmtm/` package code was not changed: every rewritten commit has the
same `wmtm/` tree as its original.

## Tags

| Tag | Commit | Content |
|-----|--------|---------|
| `v0.1.0` | `64297af` | = old `v0.1.0` (`225947c`) minus memory-derived docs; `wmtm/` tree `c7c1d30` |
| `v0.2.0-rc2` | tagged commit | = old `v0.2.0-rc1` (`a5cb1e5`) minus memory fixtures/docs, plus synthetic replay fixtures, `WMTM_REPLAY_DATA` opt-in, `.gitignore` guards, invented ids in comment examples; `wmtm/` tree `fab6bf5` |

`v0.2.0-rc1` is retired: its package code is identical to `v0.2.0-rc2` except for
comment/docstring examples (rc1 `wmtm/` tree `1e3dd64`, rc2 `fab6bf5`); tests/docs differ. Deployments pinned to
commit `a5cb1e5` (old rc1) keep working unchanged and can move to
`v0.2.0-rc2` at the next redeploy without a code change.

## Old -> new commits

Commits `b9fcc24` .. `5d4ca52` (the subtree-split package history and the
move into `wmtm/`) were already clean and are unchanged. Rewritten:

| Old | New | Subject |
|-----|-----|---------|
| `225947c` | `64297af` | Add packaging, WMTM tests and docs from snapshot 83ea611 |
| `bd32621` | `502a5b8` | Move generic turn logic and default journal into the package |
| `ea29059` | `8dd28e4` | Add wmtm.api (WMTM, WMTMConfig) and a minimal CLI stub |
| `64728f4` | `14b01d0` | Add reference Iter adapters (not installed anywhere) |
| `a5cb1e5` | `66cc921` | Add replay-equivalence test, known-answer canary and fixtures; 0.2.0rc1 |

What changed in the rewritten commits: memory-derived documents and the
real state/journal fixtures were removed, `PETTA_PIN.md` was reduced to its
technical content, three comments in the Iter glue copies were made
generic, and the replay test switched to synthetic fixtures (real data only
via `WMTM_REPLAY_DATA`, see README).

The pre-rewrite refs exist only in the original local clone
(`old-main-with-fixtures`, `old-v0.1.0`, `old-v0.2.0-rc1`) and must never be
pushed.
