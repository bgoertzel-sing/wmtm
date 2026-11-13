# t-2026-11-12-wmtm-sentence-reasoning: REPORT

## Summary

The question was whether B's reasoning on the sentence-mode parse stores (s1, s2, s3 from sentence-parse v3) gives real rules: any conclusion that is both non-trivial and correct, compared with the whole-note stores r1/r2/r3 on the same notes. **The answer is no.** Over the three sentence stores, B proves 14 conclusions (s1: 10, s3: 3, s2: 1). All 14 are trivial narrow echoes, which the trivial filter refuses (`narrow_echo`). Each one also appears in at least one whole-note parse of the same notes, so sentence mode adds no new conclusion. 0 are non-trivial, 0 are non-trivial and correct, and W1 is 0 everywhere. The whole-note stores behave the same way: 8 to 11 conclusions on the 17 notes, all trivial, 0 non-trivial.

On correctness, sentence mode is no worse than whole-note mode (0 W on every parse). Before the filter, the count rule holds against r1 and r3 but fails against r2 (s1 9C against r2 10C; s2 0C against r2 1C). Each failure comes from one conclusion that r2 has and the sentence parse lacks (Mesto §11 below). After the filter, nothing is admitted on either side (0C/0W), so the rule holds trivially. There was 0 parse calls (the v3 call log is unchanged at 178 lines, same sha256), the trivial filter is on, and the full suite passes. Open for a human: two of the eight hand verdicts are marked uncertain, and a third (UNCLEAR) concerns a conclusion taken from a superseded lesson. None of them changes the key line. Real rules still have to come from the parser side (class rules or instances that share structure), not from splitting notes into sentences.

## Key line
Does any B (sentence-mode) conclusion come out non-trivial and correct? **No. None, on s1, s2 or s3.** Every B conclusion is a trivial narrow echo. The whole-note stores give none either, so there is no difference between A and B on this question.

## Base, pins, rules
- Branch `hive/t-2026-11-12-wmtm-sentence-reasoning`, started from `hive/t-2026-11-11-wmtm-induction` at ab3a328 (passed review; it contains the trivial filter and the goal/induction code; base wmtm 27c1a41 is its ancestor). Local commit only, not pushed, as the order says.
- Pins: PeTTaChainer b6aacc68 (`~/scratch/ppv/pc`), PeTTa 3681b9b (`p1-engine/petta-3681b9b`), Man Hin parser 533c2274 (prompt 1585e873fc3151b8). No upstream code was edited.
- B flags are the same as in the trivial-filter and induction runs (`tools/run_b.sh`, copied from the induction `run_b_ind.sh` with one change, a matched-note spec): `semparse_feed` off, `goalchainer` off, `shadow_normalise` off, sandbox frozen store (`WMTM_EVAL_FROZEN_STORE`, guard on). `admit_trivial_filter` is True and `reasoner_max_admit` is 5, the 5-candidate budget per cycle (defaults, printed by `runtime_config.resolve`). The goal pool is the shipped one, with `shadow_induction` off. Every run was repeated with `shadow_induction` on (min_shared 3), and the conclusion sets are identical in all 12 pairs.
- Judging uses the same rules as the trivial-filter task: judge_v2 (F3 v3 W1 with the DEVIATION_1 nwdef join kept, plus the v2 rule that an identical class-level fact in two notes is NOT W1), W2, W3, then the F3 v3 W4 table. Goals not in that table were judged by hand against the source note on pop-os (`hand_verdicts.json`, in the evidence folder only).

## Stores (sha256 of frozen.jsonl; note ids)
| store | role | sha256 | notes |
|---|---|---|---|
| s1 | B, sentence v3 run 1 | cbb5d31c8541ee43d580fe852b8b14e9ed50de2b7a2c1b33b430ac798fa40e8a | 17 (M17) |
| s2 | B, sentence v3 pilot run 2 | 0bc654b58843c0a82b46dc853dd1d1f767520269d667bc11f456d8b4cdc61034 | 4 (P4: the complete pilot notes) |
| s3 | B, sentence v3 pilot run 3 | 9cc7bcde6a68745f69038a80538c2b2f90c0bda3dc8c85cb63c1f3357e09b2d8 | 5 (P5) |
| r1_after | A, whole-note | aed0afc18d6925ddfb8b00cb15e24f69426db24230a29a7d89eea5cf29564ec7 | 20; run on M17, P5, P4 |
| r2_after | A | e82200c659f0637e889f567a63ff9ef68ab8b431cb2c34e60f8d4590c412691a | 20; run on M17, P5, P4 |
| r3_after | A | 54ad46cb8b1d737b1e8bd5e367de2b15907f24a8cd05f65fd8196fa24bb57178 | 20; run on M17, P5, P4 |

- M17: ep-note-20261028T121808Z, ep-note-20261028T122745Z, ep-note-20261028T153222Z, ep-note-20261028T183317Z, ep-note-20261028T185132Z, ep-note-20261028T190214Z, ep-note-20261103T004843Z, ep-note-20261104T043925Z, ep-note-20261104T045724Z, ep-note-20261104T051320Z, ep-note-20261104T051925Z, ep-note-20261104T154242Z, ep-note-20261104T165705Z, ep-note-20261104T181709Z, ep-note-20261104T193449Z, ep-note-20261104T193740Z, ep-note-20261104T194242Z.
- P5: ep-note-20261028T122745Z, ep-note-20261104T043925Z, ep-note-20261104T051320Z, ep-note-20261104T151833Z, ep-note-20261104T154242Z. P4 is P5 without ep-note-20261104T151833Z, which is not complete in s2.
- A is "restricted to the same notes" through the spec: each run's spec holds only that set's note ids, and the frozen lookup is strict on the spec's notes. A and B in a set share the same spec (raw_spec sha256 0a339405, filtered) and differ only in the store.
- How the B stores were built, with no parse calls. (1) `tools/rebuild.py` replays the v3 analysis path (`~/scratch/sp2/tools/analyze.py`: SemParseAdapter catalog mode, fed the stored sentence replies through a stub, fresh PeTTaChainer loader with canary per note). It writes a cache in the parse-variance row shape, keyed by the raw note's content hash. Canary: the per-note atomset hash equals the v3 analysis.json for 17/17, 4/4 and 5/5 notes (757, 139 and 198 atoms). Input parsed.jsonl sha256: s1 d519fbfb…, s2 d2005860…, s3 a71232f6… (full values in `inputs/rebuild.json`). (2) `tools/recover.py` + `tools/mkstore.py` are the narrow-preload recovery and store build, made path-relative. They recover s1/s2/s3 petta refusals 90/20/36 into 67/17/34 statements (nwdef 56/16/30; still refused 23/3/2). Pipeline canary: the same two tools run on the parse-variance r1/r2/r3 caches rebuild r1/r2/r3_after **byte for byte** (sha256 aed0afc1/e82200c6/54ad46cb). So A and B stores come from the identical construction.

## Per parse (shipped goal pool; the induction-on runs are identical)
| set | parse | notes | goals / proved | C | W | U | trivial | non-trivial | non-trivial C | W1 | uncertain | admitted (filter on, cap 5) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M17 | **s1 (B)** | 17 | 10/10 | 9 | 0 | 1 | 10 | 0 | 0 | 0 | 1 | 0 |
| M17 | r1 (A) | 17 | 9/9 | 9 | 0 | 0 | 9 | 0 | 0 | 0 | 1 | 0 |
| M17 | r2 (A) | 17 | 11/11 | 10 | 0 | 1 | 11 | 0 | 0 | 0 | 1 | 0 |
| M17 | r3 (A) | 17 | 8/8 | 8 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 |
| P5 | **s3 (B)** | 5 | 3/3 | 2 | 0 | 1 | 3 | 0 | 0 | 0 | 1 | 0 |
| P5 | r1 (A) | 5 | 1/1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| P5 | r2 (A) | 5 | 3/3 | 2 | 0 | 1 | 3 | 0 | 0 | 0 | 2 | 0 |
| P5 | r3 (A) | 5 | 1/1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| P4 | **s2 (B)** | 4 | 1/1 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| P4 | r1 (A) | 4 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P4 | r2 (A) | 4 | 2/2 | 1 | 0 | 1 | 2 | 0 | 0 | 0 | 1 | 0 |
| P4 | r3 (A) | 4 | 0/0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

In all 24 runs the canary (Member grace person) is proved and the negative is not, with 0 timeouts and 0 unjudged. Each conclusion has 1 source note. "trivial" is the reader's own `pc_admit.trivial_reason`, `narrow_echo` in every case. The reader replay (`pc_admit.load_candidates`, default config) refuses all of them, so 0 are admitted on every parse.

## Count rule (B C >= A C and B W <= A W, same notes)
| B vs A | before filter | after filter (admitted) |
|---|---|---|
| s1 vs r1 / r2 / r3 | 9C/0W vs 9/0 HOLDS; vs 10/0 **FAILS**; vs 8/0 HOLDS | 0/0 vs 0/0 HOLDS (all three) |
| s3 vs r1 / r2 / r3 | 2/0 vs 1/0 HOLDS; vs 2/0 HOLDS; vs 1/0 HOLDS | 0/0 vs 0/0 HOLDS |
| s2 vs r1 / r2 / r3 | 0/0 vs 0/0 HOLDS; vs 1/0 **FAILS**; vs 0/0 HOLDS | 0/0 vs 0/0 HOLDS |
Against the older F3 v3 A reference (2C/2W, which the induction report used), every parse here admits 0C after the filter, so that legacy rule fails, as in the parent reports.

## Mesto §11 (A conclusions the B parse on the same notes does not prove, with reason)
| set | dropped A conclusion | in A | A verdict | reason |
|---|---|---|---|---|
| M17 | g_d04b848db7 | r1, r2, r3 | CORRECT, trivial | not in B's goal pool; s1 has no symbol for that entity |
| M17 | g_d4abda542f | r1 | CORRECT (uncertain), trivial | not in B's goal pool; the entity is present, but its restriction statement is absent or not recovered |
| P5 | g_c304a30cab | r1, r2 | CORRECT (uncertain), trivial | as above: the entity is present, the restriction is absent |
| P4 | g_e93132d411 | r2 | CORRECT, trivial | not in s2's goal pool; s2 has no symbol for that entity (s1 and s3 do prove it) |
B-only conclusions compared with a single A parse: s1 gains g_e93132d411, g_c8659570bb and g_654f171ce1 over r1 and r3; s3 gains g_8a4f8ba632 over r1/r2 and g_e93132d411 and g_654f171ce1 over r1/r3; s2 gains g_654f171ce1 over r1/r3. Every one of these is trivial, and every one is proved by some other whole-note parse. B conclusions not proved by any whole-note parse on the same notes: 0.

## Conclusions by id (verdict; premise ids per run in `evidence/conclusions.tsv`)
| id | verdict | basis | trivial | W1 | source note | proved in |
|---|---|---|---|---|---|---|
| g_ea846cdf91 | CORRECT | W4 | yes | no | ep-note-20261028T185132Z | M17 r1 r2 r3 s1 |
| g_d04b848db7 | CORRECT | W4 | yes | no | ep-note-20261028T185132Z | M17 r1 r2 r3 |
| g_ff8983670b | CORRECT | hand | yes | no | ep-note-20261028T185132Z | M17 r1 r2 r3 s1 |
| g_4eafaeec16 | CORRECT | W4 | yes | no | ep-note-20261028T185132Z | M17 r1 r2 r3 s1 |
| g_f60f5cd0c8 | CORRECT | hand | yes | no | ep-note-20261028T153222Z | M17 r1 r2 r3 s1 |
| g_1f58f7e743 | CORRECT | W4 | yes | no | ep-note-20261103T004843Z | M17 r1 r2 r3 s1 |
| g_d4abda542f | CORRECT, **uncertain** | hand | yes | no | ep-note-20261028T190214Z | M17 r1 |
| g_54c30ab2ab | CORRECT | hand | yes | no | ep-note-20261028T153222Z | M17 r1 r2 r3 s1 |
| g_a454b7be4f | CORRECT | W4 | yes | no | ep-note-20261028T190214Z | M17 r1 r2 r3 s1 |
| g_e93132d411 | CORRECT | hand | yes | no | ep-note-20261104T051320Z | M17 r2 s1; P4 r2; P5 r2 s3 |
| g_c8659570bb | CORRECT | W4 | yes | no | ep-note-20261028T190214Z | M17 r2 s1 |
| g_654f171ce1 | UNCLEAR, **uncertain** | hand | yes | no | ep-note-20261028T122745Z | M17 r2 s1; P4 r2 s2; P5 r2 s3 |
| g_c304a30cab | CORRECT, **uncertain** | hand | yes | no | ep-note-20261104T151833Z | P5 r1 r2 |
| g_8a4f8ba632 | CORRECT | hand | yes | no | ep-note-20261104T151833Z | P5 r3 s3 |
Notes on the uncertain verdicts (no note text). g_d4abda542f uses the same restriction as the W4-CORRECT g_c8659570bb, but under a different symbol spelling. g_654f171ce1's restriction comes from a lesson that the note itself quotes as superseded, and the note asserts no such membership, so it is UNCLEAR. g_c304a30cab's restriction belongs to the narrowed base, not plainly to the member. Making the uncertain ones WRONG would not change the key line, because all of them are trivial.

## 0 parse calls, evidence, tests
- Parse calls: the sentence-parse call log (`~/scratch/sp2/runs/calls.jsonl`) has 178 lines before and after, with the same sha256 (47b5fe07…). The runs contain 0 live parse-cache files, and no refusal stub was hit (`parse_calls.json`). Every B run reads only the frozen store, with the guard on.
- Evidence folder on pop-os: `/var/tmp/hive-evidence-t-2026-11-12-wmtm-sentence-reasoning/` (stores, caches, recovery, the 24 runs, specs, hand verdicts, inputs, `SHA256SUMS` with 175 files). Default umask: the directory is 755 and the files are 644.
- Recompute command (from the repo root, prints ids and counts only, ends with `RECOMPUTE_OK`):
  `python3 reports/t-2026-11-12-wmtm-sentence-reasoning/tools/recompute.py /var/tmp/hive-evidence-t-2026-11-12-wmtm-sentence-reasoning`
  Its output at commit time is `evidence/recompute_output.txt`. The committed `evidence/SHA256SUMS` is a copy of the folder's SHA256SUMS.
- Full suite on this branch: 913 passed, 41 skipped, 7 xfailed. `admit_trivial_filter` is True.

## Code and tools (this branch; no change to wmtm/)
- `tools/rebuild.py`: sentence caches from the stored v3 replies, with the atomset canary.
- `tools/recover.py`, `tools/mkstore.py`: the narrow-preload tools made path-relative (logic unchanged; the A-store byte-for-byte canary is above).
- `tools/run_b.sh`, `tools/all.sh`: offline B with a matched-note spec, same flags as the induction runs.
- `tools/make_evidence.sh`: builds the evidence folder and SHA256SUMS.
- `tools/recompute.py`: judge plus recompute (SHA256SUMS check, parse-call check, per-run C/W/U, trivial split, W1, reader replay, count rule, Mesto §11, key line).

## Deviations and limits
- **Evidence path.** The order names `/srv/hive-evidence/<task id>/`, but `/srv` is root-owned and `mkdir /srv/hive-evidence` is refused (no sudo). The evidence is in `/var/tmp/hive-evidence-<task id>/`, as in earlier tasks (parse-caching, gateway-patch-pack). It is world-readable, but I could not set the reviewer's read-only ACL. If `/srv/hive-evidence` is created with the ACL, the folder can be copied there unchanged (relative paths; the recompute takes the directory as an argument).
- s2 has 4 complete pilot notes, not 5, so its comparison set P4 is P5 without ep-note-20261104T151833Z.
- Hand verdicts (8 goals not in the W4 table) are mine and were judged against the note text on pop-os. Three are marked uncertain.
- Sentence-mode atoms were rebuilt with the v3 analysis's own adapter checkout (`~/scratch/ppv/wmtm` 2c222b6, the same as the whole-note parse-variance caches). The narrow-preload recovery uses this branch's adapter, the same step that built r*_after.
