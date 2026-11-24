#!/bin/bash
# Review 1 finding 3: resume D2 (17 sentences cut by the v1 cap) with spend repriced at published Opus 5.5 rates; same cap 30 incl. D1+pilot.
cd /home/openclaw/research-agent/projects/omegaclaw/clerk-ab/wmtm-wt/tools/clerk_ab
export CLERK_AB_SPH=/home/openclaw/research-agent/projects/omegaclaw/clerk-ab/sph-660127d9 CLERK_AB_WT=/home/openclaw/research-agent/projects/omegaclaw/clerk-ab/wmtm-wt D_CAP_USD=30
D_SPENT_BEFORE=9.024 python3 /srv/hive-evidence/t-2026-11-23-wmtm-gateway-vs-direct/tools/d_drive.py /srv/hive-evidence/t-2026-11-18-wmtm-clerk-ab/result3/a1varfull/sel.jsonl /srv/hive-evidence/t-2026-11-23-wmtm-gateway-vs-direct/d2/run > /srv/hive-evidence/t-2026-11-23-wmtm-gateway-vs-direct/d2/stdout_resume.txt 2>&1
