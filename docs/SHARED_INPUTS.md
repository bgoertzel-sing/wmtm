# Shared note-derived inputs (L-10, t-2026-11-24-wmtm-s5-ops)

Shared inputs that earlier wmtm tasks read from **outside** `/srv/hive-evidence` (/tmp, ~/scratch, ~/work, the frozen
store) were copied on 2026-11-24 to `/srv/hive-evidence/shared/<name>/`. The originals stay in place (tasks may still
read them), but /tmp can be wiped at any reboot.

**Future orders: read these inputs from `/srv/hive-evidence/shared/<name>/`, never from the original path.** Verify
first: `cd /srv/hive-evidence/shared && sha256sum -c --quiet SHA256SUMS` (744 files, 2026-11-24). Treat the folder as
read-only; write task outputs under `/srv/hive-evidence/<task>/`. The content is note-derived: ids, counts and hashes
only in git, reports and chat.

| name | original path | files | set sha (sha256 of its sorted SHA256SUMS lines, 12 hex) | read by (path grep over /srv/hive-evidence) |
|---|---|---|---|---|
| `npl-store` | `/tmp/npl/store` | 7 | dd8fe856b318 | t-2026-11-12-wmtm-sentence-reasoning |
| `frozen_parses-store` | `/home/openclaw/research-agent/projects/omegaclaw/frozen_parses/store` | 1 | c7ea7ac55c51 | t-2026-11-10-wmtm-normaliser, t-2026-11-10-wmtm-gateway-patch-pack |
| `frozen_parses-raw` | `/home/openclaw/research-agent/projects/omegaclaw/frozen_parses/raw` | 3 | 423a60c18b68 | t-2026-11-10-wmtm-normaliser, t-2026-11-10-wmtm-gateway-patch-pack |
| `frozen_parses-inputs` | `/home/openclaw/research-agent/projects/omegaclaw/frozen_parses/inputs` | 1 | 9f9f75d0b795 | t-2026-11-10-wmtm-normaliser, t-2026-11-10-wmtm-gateway-patch-pack |
| `frozen_parses-notes` | `/home/openclaw/research-agent/projects/omegaclaw/frozen_parses/notes` | 1 | 892864501b78 | t-2026-11-10-wmtm-normaliser (run log) |
| `sp2` | `/home/openclaw/scratch/sp2` | 49 | 4626dd77071c | t-2026-11-12-wmtm-parser-master-adopt-v2, t-2026-11-12-wmtm-sentence-reasoning, t-2026-11-17-wmtm-manhin-parser-analysis |
| `p3_out-ab` | `/tmp/p3_out/ab` | 110 | 050811343fb7 | t-2026-11-12-wmtm-parser-master-adopt-v2, t-2026-11-15-wmtm-sentence-feed, t-2026-11-18-wmtm-clerk-ab |
| `p3_out-bparse` | `/tmp/p3_out/bparse` | 41 | 8132881e7d7c | none found by path grep in /srv/hive-evidence (B-arm parses next to p3_out/ab; kept for completeness) |
| `mav2-sent-s1` | `/tmp/mav2/sent/s1` | 1 | fb3f3d800810 | t-2026-11-17-wmtm-manhin-parser-analysis |
| `clerk-ab-scratch` | `/home/openclaw/work/t-2026-11-18-wmtm-clerk-ab/scratch` | 530 | f0251ca60c8b | t-2026-11-18-wmtm-clerk-ab, t-2026-11-23-wmtm-gateway-vs-direct |

Key single files (sha256, 12 hex): frozen_parses/store/frozen.jsonl 904eb18d3691; raw/nov5_1f1a7a6f_cache.jsonl
839129a6f0b2; raw/nov9_f44d7b74_cache.jsonl b96748ca2aad; raw/ppv_r1_533c2274_cache.jsonl a839f2972a88;
inputs/raw_spec_20notes.json 0a339405e8f2; mav2-sent-s1/parsed.jsonl 33b9cb5e604f; npl-store/*/frozen.jsonl:
f44_before 5dadf2b1f03f, r1_before 5db54b90edbc, r1_after aed0afc18d69, r2_before 86626a6fe237, r2_after e82200c659f0,
r3_before 1d7c23119e3d, r3_after 54ad46cb8b1d.

## Not copied (code, not note-derived)
- `frozen_parses/hitl/semparse-hitl-{533c2274,f44d7b74}` (370 MB, git checkouts of the parser), `/tmp/p3_out/hitl`,
  `~/scratch/pma/sph-24e37182` (templates), `~/scratch/ppv/pc` (PeTTaChainer vendor). Pin these by commit instead.
- Live bot files (`<repos>/memory/_wmtm_shadow/...`): live state, read in place, read-only, never moved (order rule).
- Inputs already under `/srv/hive-evidence/<task>/` (e.g. sentence_parse/parsed.jsonl of
  t-2026-11-12-wmtm-parser-master-adopt-v2, clerk-ab a1frozen/result3) need no copy.

## Re-check
`(cd <original> && find . -type f | sort | xargs -d '\n' sha256sum)` with paths prefixed `./<name>/` equals the
matching lines of shared/SHA256SUMS (done 2026-11-24: identical, 744/744).
