# t-2026-11-10-wmtm-normaliser-v2 (DRAFT, f44d7b74 column pending)

Supersedes: t-2026-11-10-wmtm-normaliser

## Summary
{{SUMMARY}}

## Pins
- wmtm base 27c1a41; branch hive/t-2026-11-10-wmtm-normaliser-v2 (v1 commits 4b824e5, c67024d carried over).
- PeTTa 3681b9b, PeTTaChainer b6aacc68 (~/scratch/ppv/pc), parser checkouts 533c2274 / f44d7b74 (verified git clones of Man Hin's repo), 1f1a7a6f.
- Notes: the same 20 ids, raw_spec sha256 0a339405... (pop-os only).

## Parse columns: where each cache came from
| column | source | raw sha256 | prompt sha |
|---|---|---|---|
| Nov 5 1f1a7a6f | /tmp/p3_out/ab/B2 (v3 Bp3) | 839129a6f0b23639 | e4c4a76c |
| 533c2274 | parse-variance run r1 (~/scratch/ppv/runs/r1, config f975feb2) | a839f2972a888b3b | 1585e873 |
| f44d7b74 | this task's freeze fill after parse-variance ends | {{F44_SHA}} | 645bff3f |

## B before/after the normaliser (goals / proved), frozen store only, guard on
| parse | cache | before | after |
|---|---|---|---|
| Nov 5 1f1a7a6f | B2 | 9 / 9 | 9 / 9 |
| 533c2274 | ppv r1 | 0 / 0 | 0 / 0 |
| f44d7b74 | freeze fill | {{F44_BEFORE}} | {{F44_AFTER}} |

C/W/U (F3 v3 W1-W4 with the DEVIATION_1 join, then the v2 W1 rule): A 2C/2W; Nov 5 B before = after = 6C/0W/1U with 2 not judged; 533c2274 0 goals. 0 verdicts change under the v2 rule (also 0 across F3 v3's 12 runs).

## Unrecognised shapes per parse (full lists by shape and note id in evidence/unrecognised_*.json)
| parse | Member+Narrow | mapped | known_unused | unrecognised | nwdef |
|---|---|---|---|---|---|
| Nov 5 | 103 | 263 | 413 | 291 | 64 |
| 533c2274 r1 | 0 | 185 | 365 | 260 | 0 |
| f44d7b74 | {{F44_SHAPES}} |

## Acceptance 5: parse call timestamps
- Before v2 (v1, before the 15:59:29 cancel): 15 calls on 533c2274 in /tmp/nrm/parse_533c2274, all ok, 0 x 429: 15:42:38, 15:44:00, 15:44:39, 15:45:50, 15:47:40, 15:51:21, 15:52:19, 15:53:03, 15:54:05, 15:55:17, 15:55:53, 15:56:40, 15:57:46, 15:58:26, 15:59:13. These overlapped parse-variance (started 15:26). That cache is not used for any column.
- After v2: 0 calls until parse-variance finished; f44d7b74 calls: {{F44_CALLS}}.

## Deviations
1. The 533c2274/f44d7b74 caches from v3 were deleted in my /tmp/lpr cleanup; replaced by parse-variance r1 and a fresh freeze fill.
2. ppv r1 was copied at 16:06 while r2/r3 were still running (file copy, no calls); its sha is re-checked after parse-variance ends: {{R1_RECHECK}}.
