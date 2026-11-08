# Deviation 1 (2026-11-07 20:19 PDT): first shadow run (v1, 20:14-20:18) VOID
What: v1 canary/pilot/full runs for A and B were started concurrently on ONE spec file per stage (/tmp/f3/ab/{canary,pilot,full}_spec.json) with --keep-spec. The pc_shadow worker rewrites its --spec file in place (raw_items -> built snapshot: facts, goals, ...). Whichever arm finished first rewrote the shared spec; the other arm read a mix.
Evidence: full_spec.json after v1 has keys [atom_src, atoms, facts, goals, ...] (built snapshot), raw_spec.json has [cycle,k,raw_items,source,ts]; v1 A proved 1/4 (P3 A: 4/4); a sequential A re-run on the rewritten file (repA) gave B's 251 facts/11 goals with A's engine, 0 proved.
Fix (v2, /tmp/f3/ab/v2/run.sh): one private spec copy per arm and stage, built fresh from /tmp/p3_out/ab/raw_spec.json; arms run sequentially; raw_spec sha256 checked before and after (unchanged).
v2 A reproduces P3 A exactly: 141 facts, 4 goals, 4 proved, same stv. No number from v1 is used. v1 outputs kept under void_v1/ for audit.
Criterion (PREREG.md) unchanged; no A/B result was used to change it.
