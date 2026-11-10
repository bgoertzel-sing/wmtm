# t-2026-11-10-wmtm-normaliser-v2

Supersedes: t-2026-11-10-wmtm-normaliser

## Summary
The task asked whether the v2 normaliser (rewriting the Member+Narrow parser shape) changes what B proves, on three parser outputs of the same 20 notes, and whether the v2 W1 rule (the same class-level fact asserted in two notes counts as corroboration, not conflation) changes any verdict. The answer is no change anywhere. Only the Nov 5 parse (1f1a7a6f) has Member+Narrow shapes: 103 of them, and the normaliser rewrites 73. B proves 9 of 9 goals before and after, judged 6 correct, 0 wrong, 1 unclear (2 not judged). The v2 W1 rule changes 0 verdicts here, and 0 across F3 v3's 12 runs.

Both current parser checkouts (533c2274 from parse-variance r1, and f44d7b74 from a fresh freeze fill of 20 calls, all ok, 0 rate-limit errors) emit 0 Member+Narrow. Narrow now appears only under GroupOf. B gets 0 goals from either of them, before and after, so the normaliser has nothing to act on. Open for a human: the bigger problem is the 0 goals on current parser output, not the normaliser. Deciding whether to chase that, on the parser side or the wmtm goal side, is outside this order.

## Pins
- wmtm base 27c1a41; branch hive/t-2026-11-10-wmtm-normaliser-v2 (v1 commits 4b824e5, c67024d carried over).
- PeTTa 3681b9b, PeTTaChainer b6aacc68 (~/scratch/ppv/pc), parser checkouts 533c2274 / f44d7b74 (verified git clones of Man Hin's repo), 1f1a7a6f.
- Notes: the same 20 ids, raw_spec sha256 0a339405... (pop-os only).

## Parse columns: where each cache came from
| column | source | raw sha256 | prompt sha |
|---|---|---|---|
| Nov 5 1f1a7a6f | /tmp/p3_out/ab/B2 (v3 Bp3) | 839129a6f0b23639 | e4c4a76c |
| 533c2274 | parse-variance run r1 (~/scratch/ppv/runs/r1, config f975feb2) | a839f2972a888b3b | 1585e873 |
| f44d7b74 | this task's freeze fill after parse-variance ends | b96748ca2aad51bb | 645bff3f |

## B before/after the normaliser (goals / proved), frozen store only, guard on
| parse | cache | before | after |
|---|---|---|---|
| Nov 5 1f1a7a6f | B2 | 9 / 9 | 9 / 9 |
| 533c2274 | ppv r1 | 0 / 0 | 0 / 0 |
| f44d7b74 | freeze fill (b96748ca) | 0 / 0 | 0 / 0 |

C/W/U (F3 v3 W1-W4 with the DEVIATION_1 join, then the v2 W1 rule): A 2C/2W; Nov 5 B before = after = 6C/0W/1U with 2 not judged; 533c2274 and f44d7b74 0 goals, so no verdicts. 0 verdicts change under the v2 rule (also 0 across F3 v3's 12 runs).

## Unrecognised shapes per parse (full lists by shape and note id in evidence/unrecognised_*.json)
| parse | Member+Narrow | mapped | known_unused | unrecognised | nwdef |
|---|---|---|---|---|---|
| Nov 5 | 103 | 263 | 413 | 291 | 64 |
| 533c2274 r1 | 0 | 185 | 365 | 260 | 0 |
| f44d7b74 | 0 | 207 | 405 | 306 | 0 | |

## Acceptance 5: parse call timestamps
- Before v2 (v1, before the 15:59:29 cancel): 15 calls on 533c2274 in /tmp/nrm/parse_533c2274, all ok, 0 x 429: 15:42:38, 15:44:00, 15:44:39, 15:45:50, 15:47:40, 15:51:21, 15:52:19, 15:53:03, 15:54:05, 15:55:17, 15:55:53, 15:56:40, 15:57:46, 15:58:26, 15:59:13. These overlapped parse-variance (started 15:26). That cache is not used for any column.
- After v2: 0 calls until parse-variance finished; f44d7b74 calls: 20 calls, all ok, 0 x 429, prompt 645bff3f, starting after parse-variance ended at 18:33:47: 18:35:02, 18:35:41, 18:36:39, 18:37:32, 18:39:37, 18:42:07, 18:43:36, 18:44:38, 18:46:01, 18:47:29, 18:48:04, 18:49:27, 18:50:29, 18:58:31, 18:59:27, 19:01:26, 19:03:24, 19:04:56, 19:06:30, 19:07:57. At 18:50:30 my stop check fired wrongly: the pattern '429' matched digits inside the timestamp of an ok record. I fixed the check to look only at status and error, logged it in NOTES.txt, and resumed at 18:58.

## Deviations
1. The 533c2274/f44d7b74 caches from v3 were deleted in my /tmp/lpr cleanup; replaced by parse-variance r1 and a fresh freeze fill.
2. ppv r1 was copied at 16:06 while r2/r3 were still running (file copy, no calls); its sha is re-checked after parse-variance ends: after parse-variance ended (18:33:47) r1 sha = a839f2972a888b3b, the same as the frozen copy.

3. The 18:50:30 F44_HARD_STOP was a false positive in my stop check (see Acceptance 5); no real 429 happened.

## Tests
842 passed, 39 skipped (tests/ plus tools/).
