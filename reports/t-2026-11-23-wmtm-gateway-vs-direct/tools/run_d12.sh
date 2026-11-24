#!/bin/bash
# D1 then D2 back to back (warm 5-min cache); D2 cap counts D1 (incl. pilot) spend.
cd /home/openclaw/research-agent/projects/omegaclaw/clerk-ab/wmtm-wt/tools/clerk_ab
export CLERK_AB_SPH=/home/openclaw/research-agent/projects/omegaclaw/clerk-ab/sph-660127d9 CLERK_AB_WT=/home/openclaw/research-agent/projects/omegaclaw/clerk-ab/wmtm-wt D_CAP_USD=30
python3 /srv/hive-evidence/t-2026-11-23-wmtm-gateway-vs-direct/tools/d_drive.py /srv/hive-evidence/t-2026-11-18-wmtm-clerk-ab/result3/a1varfull/sel.jsonl /srv/hive-evidence/t-2026-11-23-wmtm-gateway-vs-direct/d1/run > /srv/hive-evidence/t-2026-11-23-wmtm-gateway-vs-direct/d1/stdout.txt 2>&1 || exit 2
S1=$(python3 -c "import json;print(sum(json.loads(l).get('usd') or 0 for l in open('/srv/hive-evidence/t-2026-11-23-wmtm-gateway-vs-direct/d1/run/calls.jsonl') if l.strip()))")
D_SPENT_BEFORE=$S1 python3 /srv/hive-evidence/t-2026-11-23-wmtm-gateway-vs-direct/tools/d_drive.py /srv/hive-evidence/t-2026-11-18-wmtm-clerk-ab/result3/a1varfull/sel.jsonl /srv/hive-evidence/t-2026-11-23-wmtm-gateway-vs-direct/d2/run > /srv/hive-evidence/t-2026-11-23-wmtm-gateway-vs-direct/d2/stdout.txt 2>&1
